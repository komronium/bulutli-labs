#!/usr/bin/env python3
"""A5 laboratoriya: virtual mashina namunasini ishga tushirish va boshqarish,
Amazon DynamoDB da jadvallar yaratish (sinf simulyatori).

Faqat Python 3.9+ standart kutubxonasi kerak:   python3 app.py
Sahifalar: web/ papkasi (HTML, CSS, JS — tashqi CDN yo'q).
"""
import csv
import io
import json
import os
import random
import re
import secrets
import socket
import sys
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")
STATIC = {  # web/ papkasidagi ruxsat berilgan fayllar
    "index.html": "text/html; charset=utf-8",
    "teacher.html": "text/html; charset=utf-8",
    "style.css": "text/css; charset=utf-8",
    "common.js": "text/javascript; charset=utf-8",
    "student.js": "text/javascript; charset=utf-8",
}
STATE_FILE = os.environ.get("A5_STATE", os.path.join(HERE, "state.json"))
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
DELAY = float(os.environ.get("A5_DELAY", "3"))  # holatlar orasidagi kutish, soniya

UBUNTU = "ami-0a91c2e5b3d7f4e01"
AMIS = {
    UBUNTU: "Ubuntu Server 24.04 LTS",
    "ami-0b52d8f1c6e3a9702": "Amazon Linux 2023",
    "ami-0c13e7a9d2f5b6803": "Debian 12",
    "ami-0d84f3b6e1c7a2904": "Windows Server 2022",
}
TYPES = {
    "t2.nano": "1 vCPU · 0.5 GB",
    "t2.micro": "1 vCPU · 1 GB",
    "t2.small": "1 vCPU · 2 GB",
    "t2.medium": "2 vCPU · 4 GB",
}
MAX_INSTANCES, MAX_TABLES, MAX_ITEMS, MAX_STUDENTS = 5, 10, 100, 500
POINTS = 10

TASKS = [
    ("e1", "ec2", "Virtual mashina yarating",
     "«Ishga tushirish» shaklida: nomi **web-server**, AMI **Ubuntu Server 24.04 LTS**, "
     "turi **t2.micro**. Holat **running** bo'lishini kuting."),
    ("e2", "ec2", "Namunani to'xtating",
     "**web-server** qatorida «To'xtatish» ni bosing. Holat **stopped** bo'ladi: disk saqlanadi, "
     "CPU uchun pul olinmaydi, public IP bo'shatiladi."),
    ("e3", "ec2", "Namuna turini o'zgartiring",
     "To'xtatilgan **web-server** turini **t2.small** (1 vCPU · 2 GB) ga o'zgartiring. "
     "Ishlab turgan namunada bu mumkin emas."),
    ("e4", "ec2", "Qayta ishga tushiring",
     "**web-server** ni «Ishga tushirish» bilan yoqing. **Public IP** yangi bo'lganiga e'tibor bering."),
    ("e5", "ec2", "Qayta yuklang (reboot)",
     "Ishlab turgan **web-server** ni «Qayta yuklash» bilan reboot qiling. Bunda IP o'zgarmaydi."),
    ("d1", "ddb", "Jadval yarating",
     "DynamoDB bo'limida: jadval nomi **Talabalar**, partition key **talaba_id** (String), "
     "sort key bo'sh. Holat **ACTIVE** bo'lishini kuting."),
    ("d2", "ddb", "Elementlar qo'shing",
     "**Talabalar** ni oching va kamida **3 ta** element qo'shing. Masalan: talaba_id = **T001**, "
     "boshqa atributlar: ism = Ali Valiyev, guruh = 101."),
    ("d3", "ddb", "Elementni kalit bo'yicha o'qing",
     "«Olish (GetItem)» bilan **Talabalar** dan mavjud elementni **talaba_id** bo'yicha toping."),
    ("d4", "ddb", "Murakkab kalitli jadval",
     "**Baholar** jadvali: partition key **talaba_id** (String), sort key **fan** (String). "
     "Bitta talaba uchun **2 ta** fan qo'shing (masalan T001 + Matematika, T001 + Fizika)."),
    ("f1", "fin", "Resurslarni tozalang",
     "Ish tugadi: **web-server** ni «O'chirish» (terminate) qiling. Bulutda keraksiz qolgan "
     "resurs uchun ham pul olinadi!"),
]
TASKS = [dict(id=a, sec=b, title=c, text=d) for a, b, c, d in TASKS]
PREREQ = {
    t["id"]: [p["id"] for p in TASKS[:n] if t["sec"] == "fin" or p["sec"] == t["sec"]]
    for n, t in enumerate(TASKS)
}
TOTAL = POINTS * len(TASKS)

NAME_RE = re.compile(r"^[\w .-]{1,40}$")
TABLE_RE = re.compile(r"^[A-Za-z0-9_.-]{3,40}$")
ATTR_RE = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")
NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")

LOCK = threading.RLock()
DB = {"key": None, "students": {}}
DIRTY = threading.Event()


class Fail(Exception):
    pass


# ---------------------------------------------------------------- holat fayli
def load():
    global DB
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            DB = json.load(f)
    except FileNotFoundError:
        pass
    except Exception as e:  # buzilgan fayl — noldan boshlaymiz
        print("state.json o'qilmadi:", e)
    DB.setdefault("students", {})
    DB["key"] = os.environ.get("A5_KEY") or DB.get("key") or f"{random.randint(0, 999999):06d}"
    DIRTY.set()


def saver():
    while True:
        DIRTY.wait()
        time.sleep(0.5)
        with LOCK:
            DIRTY.clear()
            data = json.dumps(DB, ensure_ascii=False)
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, STATE_FILE)


# ---------------------------------------------------------------- yordamchilar
def clean(v, n):
    v = str(v if v is not None else "").strip()
    if len(v) > n:
        raise Fail(f"Juda uzun matn (ko'pi bilan {n} belgi)")
    return v


def quote(s):
    return "'" + s.replace("'", "'\\''") + "'"


def ddb_json(d):
    return json.dumps({k: {t: v} for k, (t, v) in d.items()}, ensure_ascii=False)


def web(s):
    xs = [i for i in s["instances"] if i["name"] == "web-server" and i["state"] != "terminated"]
    return xs[-1] if xs else None


def ready(s, tid):
    return all(p in s["done"] for p in PREREQ[tid])


def table_ok(s, name, pk, sk=None):
    t = s["tables"].get(name)
    if t and t["status"] == "ACTIVE" and t["pk"] == pk and t["pkt"] == "S" and t["sk"] == sk \
            and (sk is None or t["skt"] == "S"):
        return t
    return None


def d4_ok(s):
    t = table_ok(s, "Baholar", "talaba_id", "fan")
    return bool(t) and any(c >= 2 for c in Counter(i["talaba_id"][1] for i in t["items"]).values())


CHECKS = {
    "e1": lambda s, w: bool(w) and w["ami"] == UBUNTU and w["type"] == "t2.micro" and w["state"] == "running",
    "e2": lambda s, w: bool(w) and w["state"] == "stopped",
    "e3": lambda s, w: bool(w) and w["type"] == "t2.small",
    "e4": lambda s, w: bool(w) and w["type"] == "t2.small" and w["state"] == "running",
    "e5": lambda s, w: "reboot_web" in s["flags"],
    "d1": lambda s, w: bool(table_ok(s, "Talabalar", "talaba_id")),
    "d2": lambda s, w: bool(table_ok(s, "Talabalar", "talaba_id"))
    and len(s["tables"]["Talabalar"]["items"]) >= 3,
    "d3": lambda s, w: "get_talabalar" in s["flags"],
    "d4": lambda s, w: d4_ok(s),
    "f1": lambda s, w: "term_web" in s["flags"],
}


def flag(s, name, tid):
    """Bayroq faqat topshiriq navbati kelganda qo'yiladi (oldindan bajarib qo'yib bo'lmaydi)."""
    if ready(s, tid) and name not in s["flags"]:
        s["flags"].append(name)


def tick(s):
    """Vaqt o'tishi bilan holatlarni yangilash va topshiriqlarni tekshirish."""
    now = time.time()
    for i in s["instances"]:
        if i["until"] and now >= i["until"]:
            i["state"], i["until"], i["next"] = i["next"], None, None
            if i["state"] == "running" and not i["public_ip"]:
                i["public_ip"] = f"3.{random.randint(64, 250)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
            DIRTY.set()
    for name in list(s["tables"]):
        t = s["tables"][name]
        if t["until"] and now >= t["until"]:
            if t["status"] == "DELETING":
                del s["tables"][name]
            else:
                t["status"], t["until"] = "ACTIVE", None
            DIRTY.set()
    w = web(s)
    for t in TASKS:
        if t["id"] not in s["done"] and ready(s, t["id"]) and CHECKS[t["id"]](s, w):
            s["done"][t["id"]] = now
            DIRTY.set()


def view(s):
    tick(s)
    tasks = [dict(t, state="done" if t["id"] in s["done"] else "current" if ready(s, t["id"]) else "locked")
             for t in TASKS]
    return {
        "name": s["name"], "group": s["group"],
        "score": POINTS * len(s["done"]), "total": TOTAL, "tasks": tasks,
        "instances": [{k: i[k] for k in ("id", "name", "ami", "type", "state", "public_ip", "private_ip")}
                      | {"ami_name": AMIS[i["ami"]]} for i in s["instances"]],
        "tables": [{k: t[k] for k in ("name", "status", "pk", "pkt", "sk", "skt", "items")}
                   for t in s["tables"].values()],
        "log": s["log"],
    }


# ---------------------------------------------------------------- EC2
def find_inst(s, iid):
    for i in s["instances"]:
        if i["id"] == iid:
            return i
    raise Fail("Namuna topilmadi")


def ec2_launch(s, a):
    name, ami, typ = clean(a.get("name"), 40), a.get("ami"), a.get("type")
    if not name:
        raise Fail("Namunaga nom bering (masalan, web-server)")
    if not NAME_RE.match(name):
        raise Fail("Nomda faqat harf, raqam, probel, _ . - bo'lsin")
    if ami not in AMIS:
        raise Fail("AMI (tizim obrazi) ni tanlang")
    if typ not in TYPES:
        raise Fail("Namuna turini tanlang")
    if sum(i["state"] != "terminated" for i in s["instances"]) >= MAX_INSTANCES:
        raise Fail(f"Limit: bir vaqtda {MAX_INSTANCES} tadan ortiq namuna bo'lmaydi. Keraksizini o'chiring.")
    i = {"id": "i-0" + secrets.token_hex(8), "name": name, "ami": ami, "type": typ,
         "state": "pending", "until": time.time() + DELAY, "next": "running", "public_ip": None,
         "private_ip": f"172.31.{random.randint(0, 255)}.{random.randint(2, 254)}"}
    s["instances"].append(i)
    while len(s["instances"]) > 12:  # eski o'chirilganlarni ro'yxatdan olib tashlash
        dead = [x for x in s["instances"] if x["state"] == "terminated"]
        if not dead:
            break
        s["instances"].remove(dead[0])
    cli = (f"aws ec2 run-instances --image-id {ami} --instance-type {typ} --count 1 \\\n"
           f"  --tag-specifications {quote(f'ResourceType=instance,Tags=[{{Key=Name,Value={name}}}]')}")
    return f"«{name}» ishga tushirilmoqda (pending → running)", cli


# amal: (qaysi holatdan, oraliq holat, yakuniy holat, CLI buyrug'i, xabar)
ACTIONS = {
    "start": (("stopped",), "pending", "running", "start-instances", "ishga tushirilmoqda"),
    "stop": (("running",), "stopping", "stopped", "stop-instances", "to'xtatilmoqda"),
    "reboot": (("running",), "rebooting", "running", "reboot-instances", "qayta yuklanmoqda"),
    "terminate": (("running", "stopped"), "shutting-down", "terminated", "terminate-instances",
                  "butunlay o'chirilmoqda"),
}


def ec2_action(act):
    allowed, mid, final, cmd, msg = ACTIONS[act]

    def run(s, a):
        i = find_inst(s, a.get("id"))
        if i["state"] not in allowed:
            raise Fail(f"Bu amal faqat «{' / '.join(allowed)}» holatida mumkin (hozir: {i['state']})")
        i["state"], i["until"], i["next"] = mid, time.time() + DELAY, final
        if act in ("stop", "terminate"):
            i["public_ip"] = None
        if i["name"] == "web-server":
            if act == "reboot" and i["type"] == "t2.small":
                flag(s, "reboot_web", "e5")
            if act == "terminate":
                flag(s, "term_web", "f1")
        return f"«{i['name']}» {msg}", f"aws ec2 {cmd} --instance-ids {i['id']}"
    return run


def ec2_modify(s, a):
    i, typ = find_inst(s, a.get("id")), a.get("type")
    if typ not in TYPES:
        raise Fail("Namuna turini tanlang")
    if i["state"] != "stopped":
        raise Fail("Turini o'zgartirish uchun avval namunani to'xtating (stopped)")
    if typ == i["type"]:
        raise Fail(f"Namuna allaqachon {typ}")
    i["type"] = typ
    return (f"«{i['name']}» turi {typ} ga o'zgartirildi",
            f"aws ec2 modify-instance-attribute --instance-id {i['id']} --instance-type Value={typ}")


# ---------------------------------------------------------------- DynamoDB
def get_table(s, name, active=True):
    t = s["tables"].get(str(name or ""))
    if not t:
        raise Fail("Jadval topilmadi")
    if active and t["status"] != "ACTIVE":
        raise Fail(f"Jadval hali tayyor emas ({t['status']}). Bir necha soniya kuting.")
    return t


def key_of(t, src):
    if not isinstance(src, dict):
        src = {}
    key = {}
    for attr, typ in ((t["pk"], t["pkt"]), (t["sk"], t["skt"])):
        if not attr:
            continue
        v = clean(src.get(attr), 200)
        if not v:
            raise Fail(f"«{attr}» kalit qiymatini kiriting")
        if typ == "N" and not NUM_RE.match(v):
            raise Fail(f"«{attr}» Number turida — raqam kiriting")
        key[attr] = [typ, v]
    return key


def same_key(item, key):
    return all(item.get(k) == v for k, v in key.items())


def ddb_create(s, a):
    name, pk, sk = clean(a.get("name"), 40), clean(a.get("pk"), 40), clean(a.get("sk"), 40)
    pkt, skt = a.get("pkt"), a.get("skt")
    if not TABLE_RE.match(name):
        raise Fail("Jadval nomi: 3–40 belgi, faqat lotin harfi, raqam, _ . -")
    if name in s["tables"]:
        raise Fail(f"«{name}» jadvali allaqachon bor")
    if len(s["tables"]) >= MAX_TABLES:
        raise Fail(f"Ko'pi bilan {MAX_TABLES} ta jadval")
    if not ATTR_RE.match(pk):
        raise Fail("Partition key nomini kiriting (lotin harfi, raqam, _ . -)")
    if pkt not in ("S", "N") or (sk and skt not in ("S", "N")):
        raise Fail("Kalit turini tanlang")
    if sk and not ATTR_RE.match(sk):
        raise Fail("Sort key nomi noto'g'ri (lotin harfi, raqam, _ . -)")
    if sk == pk:
        raise Fail("Sort key partition key bilan bir xil bo'lmasin")
    s["tables"][name] = {"name": name, "pk": pk, "pkt": pkt, "sk": sk or None, "skt": skt if sk else None,
                         "status": "CREATING", "until": time.time() + DELAY, "items": []}
    defs = f"AttributeName={pk},AttributeType={pkt}" + (f" AttributeName={sk},AttributeType={skt}" if sk else "")
    schema = f"AttributeName={pk},KeyType=HASH" + (f" AttributeName={sk},KeyType=RANGE" if sk else "")
    cli = (f"aws dynamodb create-table --table-name {name} \\\n  --attribute-definitions {defs} \\\n"
           f"  --key-schema {schema} \\\n  --billing-mode PAY_PER_REQUEST")
    return f"«{name}» jadvali yaratilmoqda (CREATING → ACTIVE)", cli


def ddb_delete_table(s, a):
    t = get_table(s, a.get("table"), active=False)
    if t["status"] == "DELETING":
        raise Fail("Jadval allaqachon o'chirilmoqda")
    t["status"], t["until"] = "DELETING", time.time() + DELAY
    return f"«{t['name']}» jadvali o'chirilmoqda", f"aws dynamodb delete-table --table-name {t['name']}"


def ddb_put(s, a):
    t = get_table(s, a.get("table"))
    item = key_of(t, a.get("item"))
    for n, line in enumerate(clean(a.get("extra"), 3000).splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if "=" not in line:
            raise Fail(f"{n}-qator: «nom = qiymat» ko'rinishida yozing")
        k, v = (x.strip() for x in line.split("=", 1))
        if not ATTR_RE.match(k):
            raise Fail(f"{n}-qator: atribut nomi noto'g'ri (lotin harfi, raqam, _ . -)")
        if k in item:
            raise Fail(f"«{k}» takrorlangan yoki kalit atributi")
        if not v or len(v) > 200:
            raise Fail(f"{n}-qator: «{k}» qiymati bo'sh yoki juda uzun")
        item[k] = ["N" if NUM_RE.match(v) else "S", v]
    if len(item) > 12:
        raise Fail("Bitta elementda ko'pi bilan 12 ta atribut")
    key = {k: item[k] for k in (t["pk"], t["sk"]) if k}
    old = any(same_key(x, key) for x in t["items"])
    if not old and len(t["items"]) >= MAX_ITEMS:
        raise Fail(f"Jadvalda ko'pi bilan {MAX_ITEMS} ta element")
    t["items"] = [x for x in t["items"] if not same_key(x, key)] + [item]
    msg = ("Shu kalitli element bor edi — PutItem uni yangisi bilan almashtirdi" if old
           else f"«{t['name']}» ga element qo'shildi")
    return msg, f"aws dynamodb put-item --table-name {t['name']} \\\n  --item {quote(ddb_json(item))}"


def ddb_get(s, a):
    t = get_table(s, a.get("table"))
    key = key_of(t, a.get("key"))
    found = next((x for x in t["items"] if same_key(x, key)), None)
    if found and t["name"] == "Talabalar":
        flag(s, "get_talabalar", "d3")
    cli = f"aws dynamodb get-item --table-name {t['name']} \\\n  --key {quote(ddb_json(key))}"
    return ("Element topildi" if found else "Bunday kalitli element yo'q"), cli, {"item": found}


def ddb_delete_item(s, a):
    t = get_table(s, a.get("table"))
    key = key_of(t, a.get("key"))
    if not any(same_key(x, key) for x in t["items"]):
        raise Fail("Element topilmadi")
    t["items"] = [x for x in t["items"] if not same_key(x, key)]
    return "Element o'chirildi", f"aws dynamodb delete-item --table-name {t['name']} \\\n  --key {quote(ddb_json(key))}"


def ddb_scan(s, a):
    t = get_table(s, a.get("table"))
    return f"«{t['name']}»: {len(t['items'])} ta element", f"aws dynamodb scan --table-name {t['name']}"


OPS = {
    "ec2.launch": ec2_launch, "ec2.modify": ec2_modify,
    **{f"ec2.{k}": ec2_action(k) for k in ACTIONS},
    "ddb.create": ddb_create, "ddb.delete_table": ddb_delete_table, "ddb.put": ddb_put,
    "ddb.get": ddb_get, "ddb.delete_item": ddb_delete_item, "ddb.scan": ddb_scan,
}


def do_op(s, a):
    fn = OPS.get(a.get("op"))
    if not fn:
        raise Fail("Noma'lum amal")
    tick(s)
    res = fn(s, a)
    msg, cli, extra = res if len(res) == 3 else (*res, {})
    s["log"] = (s["log"] + [{"t": time.time(), "msg": msg, "cli": cli}])[-25:]
    s["last"] = time.time()
    DIRTY.set()
    return msg, extra


# ---------------------------------------------------------------- o'qituvchi
def teacher_rows():
    rows = []
    for s in DB["students"].values():
        tick(s)
        rows.append({"name": s["name"], "group": s["group"], "score": POINTS * len(s["done"]),
                     "done": list(s["done"]), "ago": int(time.time() - s["last"]),
                     "running": sum(i["state"] == "running" for i in s["instances"]),
                     "tables": len(s["tables"])})
    return sorted(rows, key=lambda r: (-r["score"], r["name"].lower()))


def teacher_csv():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Ism familiya", "Guruh", "Ball"] + [t["id"] + " " + t["title"] for t in TASKS])
    for r in teacher_rows():
        w.writerow([r["name"], r["group"], r["score"]] + [1 if t["id"] in r["done"] else 0 for t in TASKS])
    return "﻿" + buf.getvalue()  # BOM — Excel o'zbek harflarini to'g'ri ko'rsatsin


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "A5Lab"

    def log_message(self, *args):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
        if not isinstance(body, (str, bytes)):
            body = json.dumps(body, ensure_ascii=False)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def teacher_ok(self, q):
        return q.get("key", [""])[0] == DB["key"]

    def page(self, name):
        with open(os.path.join(WEB, name), "rb") as f:
            self.send(200, f.read(), STATIC[name])

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/":
            return self.page("index.html")
        if u.path.startswith("/static/") and u.path[8:] in STATIC:
            return self.page(u.path[8:])
        if u.path == "/api/meta":
            return self.send(200, {"amis": AMIS, "types": TYPES})
        if u.path == "/health":
            return self.send(200, {"ok": True, "students": len(DB["students"])})
        if u.path == "/api/state":
            with LOCK:
                s = DB["students"].get(q.get("token", [""])[0])
                if not s:
                    return self.send(401, {"ok": False, "msg": "Qaytadan kiring"})
                return self.send(200, {"ok": True, "state": view(s)})
        if u.path in ("/teacher", "/api/teacher", "/teacher.csv"):
            if not self.teacher_ok(q):
                return self.send(403, "Kalit noto'g'ri: /teacher?key=KALIT", "text/plain; charset=utf-8")
            if u.path == "/teacher":
                return self.page("teacher.html")
            with LOCK:
                if u.path == "/teacher.csv":
                    return self.send(200, teacher_csv(), "text/csv; charset=utf-8",
                                     {"Content-Disposition": 'attachment; filename="a5-natijalar.csv"'})
                return self.send(200, {"ok": True, "students": teacher_rows(),
                                       "tasks": [{"id": t["id"], "title": t["title"]} for t in TASKS]})
        self.send(404, "Topilmadi", "text/plain; charset=utf-8")

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            a = json.loads(self.rfile.read(n) or b"{}") if 0 < n <= 65536 else {}
            if not isinstance(a, dict):
                a = {}
        except (ValueError, UnicodeDecodeError):
            return self.send(400, {"ok": False, "msg": "So'rov noto'g'ri"})
        with LOCK:
            if u.path == "/api/join":
                try:
                    name, group = clean(a.get("name"), 60), clean(a.get("group"), 20)
                except Fail as e:
                    return self.send(200, {"ok": False, "msg": str(e)})
                if len(name) < 3:
                    return self.send(200, {"ok": False, "msg": "Ism familiyangizni kiriting"})
                if len(DB["students"]) >= MAX_STUDENTS:
                    return self.send(200, {"ok": False, "msg": "Talabalar soni chegarasiga yetildi"})
                token = secrets.token_urlsafe(16)
                DB["students"][token] = {"name": name, "group": group, "joined": time.time(),
                                         "last": time.time(), "instances": [], "tables": {},
                                         "done": {}, "flags": [], "log": []}
                DIRTY.set()
                return self.send(200, {"ok": True, "token": token})
            if u.path == "/api/do":
                s = DB["students"].get(str(a.get("token", "")))
                if not s:
                    return self.send(401, {"ok": False, "msg": "Qaytadan kiring"})
                try:
                    msg, extra = do_op(s, a)
                    return self.send(200, {"ok": True, "msg": msg, "state": view(s), **extra})
                except Fail as e:
                    return self.send(200, {"ok": False, "msg": str(e), "state": view(s)})
            if u.path == "/api/teacher/reset":
                if not self.teacher_ok(q):
                    return self.send(403, {"ok": False})
                DB["students"] = {}
                DIRTY.set()
                return self.send(200, {"ok": True})
        self.send(404, {"ok": False})




def lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # paket yuborilmaydi, faqat chiquvchi interfeys aniqlanadi
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def main():
    load()
    if "--reset" in sys.argv:
        DB["students"] = {}
        print("Hamma talaba natijalari tozalandi (kalit saqlandi).")
    threading.Thread(target=saver, daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    ip = lan_ip()
    print("A5 laboratoriya serveri ishga tushdi\n"
          f"  Talabalar:   http://{ip}:{PORT}\n"
          f"  O'qituvchi:  http://{ip}:{PORT}/teacher?key={DB['key']}\n"
          "  (VPS da IP o'rniga serverning tashqi IP manzilini yozing.)  To'xtatish: Ctrl+C", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTo'xtatildi.")


if __name__ == "__main__":
    main()
