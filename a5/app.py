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
from http.cookies import SimpleCookie
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
    "ekran.html": "text/html; charset=utf-8",
}
TEACHER_USER = os.environ.get("A5_TEACHER_USER", "ustoz")
TEACHER_PASS = os.environ.get("A5_TEACHER_PASSWORD", "admin123")
STATE_FILE = os.environ.get("A5_STATE", os.path.join(HERE, "state.json"))
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
DELAY = float(os.environ.get("A5_DELAY", "3"))  # holatlar orasidagi kutish, soniya

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lesson import AMIS, MISSIONS, TASKS, TYPES, BY_ID, EVENT_TASK  # noqa: E402
import lesson as L  # noqa: E402

MAX_INSTANCES, MAX_TABLES, MAX_ITEMS, MAX_STUDENTS = 5, 10, 100, 500
POINTS = 10

# Jamoalar: talaba kirganda eng kichik jamoaga tushadi. Jamoa balli = a'zolar ballining o'rtachasi.
TEAMS = [
    {"id": "bulut", "name": "Bulut", "color": "#696cff", "icon": "cloud"},
    {"id": "chaqmoq", "name": "Chaqmoq", "color": "#f59e0b", "icon": "bolt"},
    {"id": "raketa", "name": "Raketa", "color": "#ef4444", "icon": "rocket"},
    {"id": "yulduz", "name": "Yulduz", "color": "#10b981", "icon": "star"},
]
TEAM = {t["id"]: t for t in TEAMS}

TOTAL = POINTS * len(TASKS)
IDX = {t["id"]: n for n, t in enumerate(TASKS)}

# Dars oqimi (A3/A4 dagidek, o'qituvchi boshqaradi): Kutish → [Namuna → Mustaqil → Yakun] × 5 missiya
STEP_LABEL = {"kutish": "Kutish", "namuna": "Namuna", "mustaqil": "O'zingiz bajaring", "yakun": "Yakun"}
SEQ = [(1, "kutish")] + [(m["no"], st) for m in MISSIONS for st in ("namuna", "mustaqil", "yakun")]
BLOCKED = {"kutish": "Dars hali boshlanmagan. O'qituvchi boshlashini kuting.",
           "namuna": "Namuna vaqti: o'qituvchini kuzating. Vazifalar birozdan keyin ochiladi.",
           "yakun": "Missiya yakunlandi. Natijalarni birga muhokama qilamiz."}

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
    DB.setdefault("tsess", [])
    if tuple(DB.get("flow", {}).values())[:2] not in [(m, st) for m, st in SEQ]:
        DB["flow"] = {"mission": 1, "step": "kutish"}
    for st in DB["students"].values():  # eski versiyadagi topshiriqlar hisobga olinmaydi
        st["done"] = {k: v for k, v in st["done"].items() if k in BY_ID}
    DB.pop("key", None)
    for st in DB["students"].values():  # eski talabalarga ham jamoa
        if st.get("team") not in TEAM and not st.get("demo"):
            st["team"] = pick_team()
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


def flow():
    return DB["flow"]


def can_act(s):
    return s.get("demo") or flow()["step"] == "mustaqil"


def task_open(s, t):
    """Topshiriq ochiqmi: o'qituvchi shu missiyaning Mustaqil qadamini ochgan bo'lsa (namuna konsolida — doim)."""
    f = flow()
    return s.get("demo") or t["mission"] < f["mission"] or (t["mission"] == f["mission"] and f["step"] in ("mustaqil", "yakun"))


def ready(s, tid):
    """Qat'iy ketma-ket: oldingi hamma topshiriqlar bajarilgan va bu topshiriq ochiq."""
    n = IDX[tid]
    return all(p["id"] in s["done"] for p in TASKS[:n]) and task_open(s, TASKS[n])


def event(s, name):
    """Voqea (reboot, terminate, GetItem…) faqat unga mos topshiriq navbatda turganda hisobga olinadi."""
    tid = EVENT_TASK.get(name)
    if tid and tid not in s["done"] and ready(s, tid) and name not in s["flags"]:
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
    for t in TASKS:
        if t["kind"] == "do" and t["id"] not in s["done"] and ready(s, t["id"]) and L.check(s, t["id"]):
            s["done"][t["id"]] = now
            DIRTY.set()


def _standing(s):
    order, teams = ranking()
    if s.get("demo"):
        return {"team": None, "place": 0, "class_n": len(order),
                "teams": [{k: t[k] for k in ("id", "name", "color", "icon", "avg", "members", "place")} for t in teams]}
    return {"team": s["team"], "place": next(n for n, x in enumerate(order) if x is s) + 1, "class_n": len(order),
            "teams": [{k: t[k] for k in ("id", "name", "color", "icon", "avg", "members", "place")} for t in teams]}


def view(s):
    tick(s)
    tasks = []
    for t in TASKS:
        st = "done" if t["id"] in s["done"] else "current" if ready(s, t["id"]) else "locked"
        x = dict(L.public(t), state=st)
        if st == "current" and t["kind"] == "do":
            x["check"] = L.checklist(s, t["id"])
        tasks.append(x)
    f = flow()
    return {
        "name": s["name"], "group": s["group"], "demo": bool(s.get("demo")),
        "score": POINTS * len(s["done"]), "total": TOTAL, "tasks": tasks, "missions": MISSIONS,
        "flow": {**f, "label": STEP_LABEL[f["step"]], "blocked": None if can_act(s) else BLOCKED[f["step"]]},
        **_standing(s),
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
        if act in ("reboot", "terminate"):
            event(s, ("reboot:" if act == "reboot" else "term:") + i["name"])
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
    if found:
        event(s, "get:" + t["name"])
    cli = f"aws dynamodb get-item --table-name {t['name']} \\\n  --key {quote(ddb_json(key))}"
    return ("Element topildi" if found else "Bunday kalitli element yo'q"), cli, {"item": found}


def ddb_delete_item(s, a):
    t = get_table(s, a.get("table"))
    key = key_of(t, a.get("key"))
    if not any(same_key(x, key) for x in t["items"]):
        raise Fail("Element topilmadi")
    t["items"] = [x for x in t["items"] if not same_key(x, key)]
    event(s, f"del:{t['name']}:{key[t['pk']][1]}")
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


def task_answer(s, a):
    t = BY_ID.get(str(a.get("id")))
    if not t or t["kind"] == "do":
        raise Fail("Noma'lum topshiriq")
    if t["id"] in s["done"]:
        raise Fail("Bu topshiriq allaqachon bajarilgan")
    if not ready(s, t["id"]):
        raise Fail("Avval oldingi topshiriqlarni bajaring")
    ok, why = L.answer(s, t["id"], a.get("value"))
    if not ok:
        raise Fail(why)
    s["done"][t["id"]] = time.time()
    return "To'g'ri! +10 ball", f"# {t['title']} — javob qabul qilindi"


def do_op(s, a):
    fn = OPS.get(a.get("op")) or (task_answer if a.get("op") == "task.answer" else None)
    if not fn:
        raise Fail("Noma'lum amal")
    if not can_act(s):
        raise Fail(BLOCKED[flow()["step"]])
    tick(s)
    res = fn(s, a)
    msg, cli, extra = res if len(res) == 3 else (*res, {})
    s["log"] = (s["log"] + [{"t": time.time(), "msg": msg, "cli": cli}])[-25:]
    s["last"] = time.time()
    DIRTY.set()
    return msg, extra


# ---------------------------------------------------------------- jamoalar va reyting
def pick_team():
    n = Counter(st.get("team") for st in DB["students"].values() if not st.get("demo"))
    return min(TEAMS, key=lambda t: (n[t["id"]], TEAMS.index(t)))["id"]


def finish_time(s):
    return max(s["done"].values()) if s["done"] else float("inf")


def ranking():
    """Sinf reytingi: ball ko'p bo'lgan oldinda; ball teng bo'lsa — oxirgi vazifani ertaroq bajargan oldinda.
    Jamoa reytingi: a'zolar ballining o'rtachasi (jamoalar soni teng bo'lmasa ham adolatli)."""
    for st in DB["students"].values():
        tick(st)
    order = sorted((st for st in DB["students"].values() if not st.get("demo")), key=lambda st: (-len(st["done"]), finish_time(st), st["name"].lower()))
    teams = []
    for t in TEAMS:
        mem = [st for st in order if st["team"] == t["id"]]
        avg = round(sum(POINTS * len(st["done"]) for st in mem) / len(mem), 1) if mem else 0
        teams.append(dict(t, members=len(mem), avg=avg, full=sum(len(st["done"]) == len(TASKS) for st in mem)))
    teams.sort(key=lambda t: (not t["members"], -t["avg"], -t["full"], TEAMS.index(TEAM[t["id"]])))
    for n, t in enumerate(teams):
        t["place"] = n + 1
    return order, teams


# ---------------------------------------------------------------- o'qituvchi
def teacher_rows(order=None):
    order = order or ranking()[0]
    now = time.time()
    return [{"place": n + 1, "name": s["name"], "group": s["group"], "team": s["team"],
             "score": POINTS * len(s["done"]), "done": list(s["done"]), "ago": int(now - s["last"]),
             "missions": [sum(t["id"] in s["done"] for t in TASKS if t["mission"] == m["no"]) for m in MISSIONS],
             "running": sum(i["state"] == "running" for i in s["instances"]), "tables": len(s["tables"])}
            for n, s in enumerate(order)]


def teacher_csv():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["O'rin", "Ism familiya", "Guruh", "Jamoa", "Ball"] + [t["id"] + " " + t["title"] for t in TASKS])
    for r in teacher_rows():
        w.writerow([r["place"], r["name"], r["group"], TEAM[r["team"]]["name"], r["score"]]
                   + [1 if t["id"] in r["done"] else 0 for t in TASKS])
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

    def teacher_ok(self, q=None):
        c = SimpleCookie(self.headers.get("Cookie", ""))
        return "a5t" in c and c["a5t"].value in DB["tsess"]

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
        if u.path == "/teacher":
            return self.page("teacher.html")  # kirmagan bo'lsa, sahifaning o'zi login oynasini ko'rsatadi
        if u.path == "/ekran":
            return self.page("ekran.html")
        if u.path in ("/api/teacher", "/teacher.csv"):
            if not self.teacher_ok():
                return self.send(401, {"ok": False, "msg": "Avval o'qituvchi sifatida kiring"})
            with LOCK:
                if u.path == "/teacher.csv":
                    return self.send(200, teacher_csv(), "text/csv; charset=utf-8",
                                     {"Content-Disposition": 'attachment; filename="a5-natijalar.csv"'})
                order, teams = ranking()
                f = flow()
                cur = [t["id"] for t in TASKS if t["mission"] == f["mission"]]
                behind = [st["name"] for st in order if not all(x in st["done"] for x in cur)]
                return self.send(200, {
                    "ok": True, "students": teacher_rows(order), "teams": teams, "total": TOTAL,
                    "flow": {**f, "label": STEP_LABEL[f["step"]], "index": SEQ.index((f["mission"], f["step"])),
                             "last": len(SEQ) - 1, "done": len(order) - len(behind), "behind": behind[:12],
                             "n": len(order)},
                    "missions": [dict(m, tasks=sum(t["mission"] == m["no"] for t in TASKS)) for m in MISSIONS],
                    "tasks": [{"id": t["id"], "title": t["title"], "mission": t["mission"]} for t in TASKS]})
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
                DB["students"][token] = {"name": name, "group": group, "team": pick_team(), "joined": time.time(),
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
            if u.path == "/api/teacher/login":
                ok = secrets.compare_digest(str(a.get("username", "")).strip(), TEACHER_USER) & \
                    secrets.compare_digest(str(a.get("password", "")), TEACHER_PASS)
                if not ok:
                    time.sleep(0.7)  # parolni tez-tez taxmin qilishni sekinlatadi
                    return self.send(200, {"ok": False, "msg": "Login yoki parol noto'g'ri"})
                tok = secrets.token_urlsafe(24)
                DB["tsess"] = (DB["tsess"] + [tok])[-20:]
                DIRTY.set()
                return self.send(200, {"ok": True}, headers={
                    "Set-Cookie": f"a5t={tok}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000"})
            if u.path == "/api/teacher/logout":
                c = SimpleCookie(self.headers.get("Cookie", ""))
                if "a5t" in c and c["a5t"].value in DB["tsess"]:
                    DB["tsess"].remove(c["a5t"].value)
                    DIRTY.set()
                return self.send(200, {"ok": True}, headers={"Set-Cookie": "a5t=; Path=/; Max-Age=0"})
            if u.path in ("/api/teacher/flow", "/api/teacher/demo") and not self.teacher_ok():
                return self.send(401, {"ok": False, "msg": "Avval o'qituvchi sifatida kiring"})
            if u.path == "/api/teacher/flow":
                i = SEQ.index((flow()["mission"], flow()["step"]))
                act = a.get("action")
                if act == "next":
                    i = min(i + 1, len(SEQ) - 1)
                elif act == "prev":
                    i = max(i - 1, 0)
                elif act == "goto":
                    key = (int(a.get("mission", 0) or 0), str(a.get("step", "")))
                    if key not in SEQ:
                        return self.send(200, {"ok": False, "msg": "Bunday qadam yo'q"})
                    i = SEQ.index(key)
                DB["flow"] = {"mission": SEQ[i][0], "step": SEQ[i][1]}
                DIRTY.set()
                return self.send(200, {"ok": True, "flow": DB["flow"]})
            if u.path == "/api/teacher/demo":  # o'qituvchining namuna konsoli: reytingga kirmaydi, doim ochiq
                tok = next((k for k, v in DB["students"].items() if v.get("demo")), None)
                if not tok:
                    tok = secrets.token_urlsafe(16)
                    DB["students"][tok] = {"name": "O'qituvchi (namuna)", "group": "", "team": None, "demo": True,
                                           "joined": time.time(), "last": time.time(), "instances": [],
                                           "tables": {}, "done": {}, "flags": [], "log": []}
                    DIRTY.set()
                return self.send(200, {"ok": True, "token": tok})
            if u.path == "/api/teacher/reset":
                if not self.teacher_ok():
                    return self.send(401, {"ok": False})
                DB["flow"] = {"mission": 1, "step": "kutish"}
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
        print("Hamma talaba natijalari tozalandi.")
    threading.Thread(target=saver, daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    ip = lan_ip()
    print("A5 laboratoriya serveri ishga tushdi\n"
          f"  Talabalar:   http://{ip}:{PORT}\n"
          f"  O'qituvchi:  http://{ip}:{PORT}/teacher   (login: {TEACHER_USER}, parol: A5_TEACHER_PASSWORD, standart admin123)\n"
          f"  Proyektor:   http://{ip}:{PORT}/ekran\n"
          "  (VPS da IP o'rniga serverning tashqi IP manzilini yozing.)  To'xtatish: Ctrl+C", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTo'xtatildi.")


if __name__ == "__main__":
    main()
