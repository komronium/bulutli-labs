"""A5 dars mazmuni: 5 missiya, 27 topshiriq, namunalar va tekshiruvlar.

Topshiriq turlari:
  do      — konsolda bajariladi, server holatga qarab o'zi tekshiradi (check)
  answer  — talaba qiymatni kartadagi maydonga yozadi (answer)
  quiz    — "Nega?" savoli: variantlardan birini tanlaydi
Har bir "do" topshiriqda jonli tekshiruv ro'yxati bor (checklist): ✓/✗, "sizda" va "kerak".
"""

from __future__ import annotations

import re
from collections import Counter

UBUNTU, AMAZON, DEBIAN, WINDOWS = ("ami-0a91c2e5b3d7f4e01", "ami-0b52d8f1c6e3a9702",
                                  "ami-0c13e7a9d2f5b6803", "ami-0d84f3b6e1c7a2904")
AMIS = {UBUNTU: "Ubuntu Server 24.04 LTS", AMAZON: "Amazon Linux 2023", DEBIAN: "Debian 12",
        WINDOWS: "Windows Server 2022"}
TYPES = {"t2.nano": "1 vCPU · 0.5 GB", "t2.micro": "1 vCPU · 1 GB", "t2.small": "1 vCPU · 2 GB",
         "t2.medium": "2 vCPU · 4 GB"}
RAM = {"t2.nano": 0.5, "t2.micro": 1, "t2.small": 2, "t2.medium": 4}

MISSIONS = [
    {"no": 1, "icon": "rocket", "title": "Birinchi virtual mashina",
     "goal": "Bulutda virtual kompyuter (EC2 instance) yaratamiz va uning manzilini topamiz.",
     "namuna": [
         {"do": "EC2 → Nomi: demo-server · Ubuntu Server 24.04 LTS · t2.micro → «Ishga tushirish»",
          "mean": "Bir necha soniyada holat pending → running bo'ladi."},
         {"do": "Mashina kartasi: Public IP va Instance ID",
          "mean": "Public IP — internetdagi manzil. Instance ID — mashinaning noyob raqami (i- bilan boshlanadi)."}],
     "learned": ["Virtual mashina bir necha soniyada tayyor bo'ladi.",
                 "Har bir mashinaning o'z Public IP manzili va Instance ID si bor."]},
    {"no": 2, "icon": "server", "title": "Mashinani boshqarish",
     "goal": "Mashinani to'xtatamiz, turini kattalashtiramiz, qayta yoqamiz va qayta yuklaymiz.",
     "namuna": [
         {"do": "«To'xtatish» → holat stopped",
          "mean": "Protsessor to'xtaydi, disk saqlanadi, Public IP bo'shatiladi."},
         {"do": "To'xtatilgan mashina: ro'yxatdan yangi tur → «Turini o'zgartirish» → «Ishga tushirish»",
          "mean": "Tur faqat to'xtatilgan mashinada o'zgaradi. Yoqilganda yangi IP beriladi."},
         {"do": "«Qayta yuklash» (reboot)", "mean": "Qayta yuklanganda IP o'zgarmaydi."}],
     "learned": ["Stop — mashina to'xtaydi, IP bo'shatiladi; Start — yangi IP beriladi.",
                 "Turni faqat to'xtatilgan mashinada o'zgartirish mumkin. Reboot IP ni o'zgartirmaydi."]},
    {"no": 3, "icon": "cpu", "title": "To'g'ri tur va tozalash",
     "goal": "Ishga mos turni tanlaymiz va keraksiz mashinalarni o'chiramiz.",
     "namuna": [
         {"do": "2 vCPU va 4 GB kerak → «Namuna turi» ro'yxatida mosini topamiz",
          "mean": "Ro'yxatda har bir tur yonida vCPU va GB yozilgan."},
         {"do": "«O'chirish» (terminate) → shutting-down → terminated",
          "mean": "O'chirilgan mashina qaytmaydi. Keraksiz mashina uchun pul to'lanmaydi."}],
     "learned": ["Turni ishga qarab tanlaymiz: ortiqcha quvvat — ortiqcha pul.",
                 "Stop — vaqtincha; Terminate — butunlay o'chirish."]},
    {"no": 4, "icon": "db", "title": "DynamoDB: birinchi jadval",
     "goal": "Jadval yaratamiz, element qo'shamiz, topamiz, o'zgartiramiz va o'chiramiz.",
     "namuna": [
         {"do": "DynamoDB → Jadval nomi: Kitoblar · Partition key: kitob_id (String) → «Jadval yaratish»",
          "mean": "Jadval CREATING → ACTIVE bo'ladi."},
         {"do": "«Ochish» → kitob_id: K001 · Boshqa atributlar: nomi = Alpomish → «Element qo'shish»",
          "mean": "Har bir element — jadvaldagi bitta qator."},
         {"do": "GetItem: kitob_id = K001 · Shu kalit bilan qayta qo'shish · Qatordagi «O'chirish»",
          "mean": "Kalit bilan topamiz. Bir xil kalit bilan qo'shsak, eski qator yangisiga almashadi."}],
     "learned": ["Partition key — har bir qatorning noyob kaliti.",
                 "Bir xil kalit bilan qo'shilgan element eskisini almashtiradi."]},
    {"no": 5, "icon": "trophy", "title": "Ikki qismli kalit va yakun",
     "goal": "Sort key bilan jadval yaratamiz va dars oxirida resurslarni tozalaymiz.",
     "namuna": [
         {"do": "Jadval: Buyurtmalar · Partition key: mijoz_id · Sort key: sana",
          "mean": "Ikki qismli kalit: bitta mijozning bir nechta buyurtmasi saqlanadi."},
         {"do": "Har bir mashinada «O'chirish» (terminate)",
          "mean": "Dars oxirida keraksiz resurslar o'chiriladi — pul ketmaydi."}],
     "learned": ["Partition key + Sort key: bitta kalitga bir nechta qator.",
                 "Ishlatilmayotgan resurslarni doim o'chiramiz."]},
]


def T(id, mission, kind, title, **kw):
    return dict(id=id, mission=mission, kind=kind, title=title, where=kw.pop("where", None), **kw)


TASKS = [
    # ---- 1-missiya
    T("m1a", 1, "do", "Birinchi virtual mashinani ishga tushiring.", where="ec2",
      steps=["Nomi: **web-server**", "Tizim (AMI): **Ubuntu Server 24.04 LTS**", "Turi: **t2.micro**",
             "«Ishga tushirish» tugmasini bosing"],
      expect="Ro'yxatda web-server paydo bo'ladi. 3 soniyadan keyin holati «running» bo'ladi.",
      hint="Nomni aynan shunday yozing: kichik harflar, o'rtada chiziqcha — web-server.",
      success="Zo'r! Bulut sizga bir necha soniyada alohida kompyuter ajratdi."),
    T("m1b", 1, "answer", "web-server ning Public IP manzilini yozing.", where="ec2",
      steps=["EC2 da web-server kartasini toping", "**Public IP** qatoridagi raqamni ko'chiring",
             "Pastdagi maydonga yozib, «Tekshirish» ni bosing"],
      expect="Manzil 3. bilan boshlanadi, masalan 3.120.45.7", placeholder="3.___.___.___",
      hint="Public IP — internetdagi manzil. U kartada globus belgisi yonida turadi.",
      success="To'g'ri! Shu manzil orqali mashinaga internetdan murojaat qilinadi."),
    T("m1c", 1, "answer", "web-server ning Instance ID sini yozing.", where="ec2",
      steps=["web-server kartasida nom ostidagi **i-** bilan boshlanadigan yozuvni toping",
             "Uni to'liq ko'chirib, pastga yozing"],
      expect="i-0 bilan boshlanadigan uzun yozuv.", placeholder="i-0…",
      hint="Ko'chirishda boshidagi «i-» ni ham oling.",
      success="To'g'ri! Instance ID — mashinaning noyob raqami, AWS CLI buyruqlarida ishlatiladi."),
    T("m1d", 1, "do", "Ikkinchi mashina: test-server.", where="ec2",
      steps=["Nomi: **test-server**", "Tizim (AMI): **Amazon Linux 2023**", "Turi: **t2.nano**",
             "«Ishga tushirish»"],
      expect="Ro'yxatda ikkita mashina: web-server va test-server, ikkalasi running.",
      hint="Bu safar AMI va tur boshqacha — ro'yxatdan diqqat bilan tanlang.",
      success="Ikkinchi mashina tayyor. Har birining IP si boshqa-boshqa."),
    T("m1q", 1, "quiz", "Virtual mashina (EC2 instance) nima?",
      options=["Bulutdan ijaraga olingan virtual kompyuter", "Kompyuterdagi oddiy papka",
               "Internet brauzeri", "Telefon ilovasi"], correct=0,
      hint="EC2 bo'limida nimani yaratdingiz? U ishga tushadi, IP manzil oladi…",
      success="To'g'ri! EC2 instance — provayder serveridan sizga ajratilgan virtual kompyuter."),
    # ---- 2-missiya
    T("m2a", 2, "do", "web-server ni to'xtating.", where="ec2",
      steps=["web-server kartasida **«To'xtatish»** ni bosing"],
      expect="Holat «stopped» bo'ladi, Public IP yo'qoladi.",
      hint="Tugma faqat mashina «running» bo'lganda chiqadi.",
      success="To'xtatildi. Endi protsessor uchun pul olinmaydi, disk esa saqlanadi."),
    T("m2b", 2, "do", "web-server turini t2.small ga o'zgartiring.", where="ec2",
      steps=["web-server kartasidagi ro'yxatdan **t2.small** ni tanlang", "**«Turini o'zgartirish»** ni bosing"],
      expect="Kartada «t2.small · 1 vCPU · 2 GB» yoziladi.",
      hint="Turini faqat to'xtatilgan mashinada o'zgartirib bo'ladi.",
      success="Bajarildi! Yangi kompyuter sotib olmasdan mashina kattalashdi."),
    T("m2c", 2, "do", "web-server ni qayta yoqing.", where="ec2",
      steps=["web-server kartasida **«Ishga tushirish»** ni bosing"],
      expect="Holat «running» bo'ladi.",
      hint="Kartadagi yashil «Ishga tushirish» tugmasi.",
      success="Mashina ishlayapti — endi yangi turda."),
    T("m2d", 2, "answer", "web-server ning yangi Public IP sini yozing.", where="ec2",
      steps=["web-server kartasidagi **Public IP** ga qarang — u o'zgargan", "Yangi manzilni pastga yozing"],
      expect="1-missiyadagidan boshqa manzil.", placeholder="3.___.___.___",
      hint="To'xtatilganda IP bo'shatilgan edi, shuning uchun yangisi berildi.",
      success="To'g'ri! Stop → Start da Public IP o'zgaradi."),
    T("m2e", 2, "do", "web-server ni qayta yuklang (reboot).", where="ec2",
      steps=["web-server kartasida **«Qayta yuklash»** ni bosing"],
      expect="Holat bir zum «rebooting», keyin yana «running». IP o'zgarmaydi.",
      hint="Reboot — kompyuterni o'chirib-yoqish kabi, lekin manzili saqlanadi.",
      success="Qayta yuklandi va IP o'sha-o'sha qoldi."),
    T("m2q", 2, "quiz", "Stop va Reboot ning farqi nimada?",
      options=["Farqi yo'q, ikkalasi bir xil", "Reboot mashinani butunlay o'chirib yuboradi",
               "Reboot qayta yuklaydi va IP saqlanadi; Stop to'xtatadi va IP bo'shatiladi",
               "Stop dan keyin mashinani qayta yoqib bo'lmaydi"], correct=2,
      hint="Ikkala holatda Public IP ga nima bo'lganini eslang.",
      success="To'g'ri! Reboot da IP saqlanadi, Stop da esa bo'shatiladi."),
    # ---- 3-missiya
    T("m3a", 3, "do", "Ishga mos mashina: katta-server.", where="ec2",
      steps=["Nomi: **katta-server**", "Tizim (AMI): **Debian 12**",
             "Turi: **2 vCPU va 4 GB** bo'lgan turni o'zingiz toping", "«Ishga tushirish»"],
      expect="katta-server running, turi 2 vCPU · 4 GB.",
      hint="«Namuna turi» ro'yxatida har bir turning yonida vCPU va GB yozilgan.",
      success="To'g'ri tanlov! Ishga mos tur — ortiqcha pul yo'q."),
    T("m3b", 3, "answer", "web-server da necha GB xotira (RAM) bor?", where="ec2",
      steps=["web-server kartasidagi tur qatoriga qarang: «1 vCPU · ? GB»", "Faqat sonni yozing"],
      expect="Bitta son, masalan 4", placeholder="GB",
      hint="web-server ni 2-missiyada t2.small ga o'zgartirgan edingiz.",
      success="To'g'ri! t2.small da 2 GB xotira bor."),
    T("m3c", 3, "do", "katta-server ni to'xtating.", where="ec2",
      steps=["katta-server kartasida **«To'xtatish»** ni bosing"],
      expect="katta-server holati «stopped».",
      hint="Hozir kerak bo'lmasa, to'xtatib qo'yamiz — protsessor puli ketmaydi.",
      success="To'xtatildi. Kerak bo'lganda qayta yoqiladi."),
    T("m3d", 3, "do", "test-server ni butunlay o'chiring.", where="ec2",
      steps=["test-server kartasida **«O'chirish»** ni bosing", "Oynada tasdiqlang"],
      expect="test-server holati «shutting-down», keyin «terminated».",
      hint="test-server ni 1-missiyada yaratgan edingiz. Boshqa mashinani o'chirmang!",
      success="test-server o'chirildi — endi uning uchun pul to'lanmaydi."),
    T("m3q", 3, "quiz", "Stop va Terminate ning farqi nimada?",
      options=["Ikkalasi bir xil", "Terminate — butunlay o'chiradi; Stop — vaqtincha to'xtatadi",
               "Terminate faqat IP ni o'chiradi", "Stop mashinani diski bilan birga yo'q qiladi"], correct=1,
      hint="test-server va katta-server ga nima bo'ldi? Qaysi birini qayta yoqsa bo'ladi?",
      success="To'g'ri! Terminate qilingan mashinani qaytarib bo'lmaydi."),
    # ---- 4-missiya
    T("m4a", 4, "do", "«Talabalar» jadvalini yarating.", where="ddb",
      steps=["Jadval nomi: **Talabalar**", "Partition key: **talaba_id** (String)", "Sort key — bo'sh qolsin",
             "«Jadval yaratish»"],
      expect="Jadval kartasi paydo bo'ladi: avval «CREATING», keyin «ACTIVE».",
      hint="Katta-kichik harf muhim: Talabalar — bosh harf bilan, talaba_id — kichik harflar bilan.",
      success="Jadval tayyor. Partition key — har bir qatorning noyob raqami."),
    T("m4b", 4, "do", "Jadvalga 3 ta talaba qo'shing.", where="ddb",
      steps=["«Talabalar» kartasida **«Ochish»**", "talaba_id: **T001**", "Boshqa atributlar: **ism = Ali Valiyev**",
             "«Element qo'shish» — keyin **T002** va **T003** ham"],
      expect="Pastdagi jadvalda 3 ta qator.",
      hint="Har bir talabaning talaba_id si har xil bo'lsin.",
      success="3 ta element qo'shildi."),
    T("m4c", 4, "do", "T001 ni kalit bo'yicha toping (GetItem).", where="ddb",
      steps=["«Kalit bo'yicha olish» bo'limida talaba_id: **T001**", "**«Olish»** ni bosing"],
      expect="Pastda T001 ning ma'lumotlari chiqadi.",
      hint="Kalitni aynan yozing: bosh harf T, keyin 001.",
      success="Topildi! Kalit bo'yicha qidirish eng tez usul."),
    T("m4d", 4, "do", "T002 ning guruhini 102 ga o'zgartiring.", where="ddb",
      steps=["Element qo'shish: talaba_id: **T002**", "Boshqa atributlar: **guruh = 102**", "«Element qo'shish»"],
      expect="Jadvalda T002 qatorida guruh = 102. Qatorlar soni o'zgarmaydi.",
      hint="Bir xil kalit bilan qayta qo'shsangiz, eski qator yangisiga almashadi (PutItem).",
      success="O'zgartirildi! Bir xil kalit — eski qator almashtirildi."),
    T("m4e", 4, "do", "T003 ni jadvaldan o'chiring.", where="ddb",
      steps=["Pastdagi «Elementlar» jadvalida **T003** qatorini toping", "Qator oxiridagi **o'chirish** belgisini bosing"],
      expect="Jadvalda T003 qolmaydi.",
      hint="Qizil savatcha belgisi — o'chirish (DeleteItem).",
      success="T003 o'chirildi."),
    T("m4q", 4, "quiz", "Partition key nima uchun kerak?",
      options=["Jadvalning rangini belgilash uchun", "Har bir qatorni ajratib turadigan noyob kalit",
               "Jadvalni o'chirish paroli", "Faqat raqamlar saqlanadigan ustun"], correct=1,
      hint="T002 ni qayta qo'shganingizda nima bo'ldi?",
      success="To'g'ri! Partition key bo'yicha har bir qator topiladi."),
    # ---- 5-missiya
    T("m5a", 5, "do", "«Baholar» jadvali: ikki qismli kalit.", where="ddb",
      steps=["Jadval nomi: **Baholar**", "Partition key: **talaba_id**", "Sort key: **fan**", "«Jadval yaratish»"],
      expect="Baholar kartasida PK va SK ikkalasi ko'rinadi.",
      hint="Sort key maydonini bu safar to'ldiring: fan.",
      success="Ikki qismli kalitli jadval tayyor."),
    T("m5b", 5, "do", "T001 ga 2 ta fan qo'shing.", where="ddb",
      steps=["«Baholar» ni oching", "talaba_id: **T001**, fan: **Matematika**, baho = 5",
             "talaba_id: **T001**, fan: **Fizika**, baho = 4"],
      expect="Jadvalda T001 ning 2 ta qatori.",
      hint="talaba_id bir xil, fan har xil — shuning uchun ikkalasi saqlanadi.",
      success="Bitta talabaga ikki qator — sort key tufayli."),
    T("m5c", 5, "do", "T002 ga ham fan qo'shing.", where="ddb",
      steps=["talaba_id: **T002**, fan: **Matematika**, baho = 5"],
      expect="Jadvalda T002 qatori ham bor.",
      hint="Xuddi oldingi qadamdagidek, faqat talaba_id boshqa.",
      success="Endi jadvalda ikki talabaning baholari bor."),
    T("m5q", 5, "quiz", "Sort key (fan) nima beradi?",
      options=["Jadvalni tezroq o'chiradi", "Talabaning parolini saqlaydi",
               "Bitta talaba uchun bir nechta qator saqlash imkonini beradi", "Jadvalni ikkiga bo'ladi"],
      correct=2, hint="T001 ning nechta qatori bor?",
      success="To'g'ri! Partition key + Sort key — bitta talabaga ko'p qator."),
    T("m5d", 5, "do", "Dars yakuni: hamma mashinalarni o'chiring.", where="ec2",
      steps=["EC2 da qolgan har bir mashinada **«O'chirish»** ni bosing", "Hammasi «terminated» bo'lsin"],
      expect="Hamma kartalar «terminated» (yoki «shutting-down»).",
      hint="To'xtatilgan (stopped) mashina ham o'chirilishi kerak — uning diski uchun pul ketadi.",
      success="Tabriklaymiz! A5 laboratoriya ishi to'liq bajarildi."),
]
BY_ID = {t["id"]: t for t in TASKS}
# Voqea → u bajaradigan topshiriq (voqea faqat topshiriq ochiq bo'lganda hisobga olinadi)
EVENT_TASK = {"reboot:web-server": "m2e", "term:test-server": "m3d", "get:Talabalar": "m4c",
              "del:Talabalar:T003": "m4e"}


# ---------------------------------------------------------------- yordamchilar
def inst(s, name):
    xs = [i for i in s["instances"] if i["name"] == name and i["state"] != "terminated"]
    return xs[-1] if xs else None


def guess_inst(s, name, skip=()):
    alive = [i for i in s["instances"] if i["state"] != "terminated" and i["name"] not in skip]
    return inst(s, name) or (alive[-1] if alive else None)


def table_ok(s, name, pk, sk=None):
    t = s["tables"].get(name)
    if t and t["status"] == "ACTIVE" and t["pk"] == pk and t["pkt"] == "S" and t["sk"] == sk \
            and (sk is None or t["skt"] == "S"):
        return t
    return None


def item(t, pk_val):
    return next((x for x in t["items"] if x.get(t["pk"], [None, None])[1] == pk_val), None) if t else None


def count(t, pk_val):
    return sum(1 for x in t["items"] if x.get(t["pk"], [None, None])[1] == pk_val) if t else 0


def spec_ok(i, ami, typ):
    return bool(i) and i["ami"] == ami and i["type"] == typ and i["state"] == "running"


def check(s, tid):
    """«do» topshiriq bajarilganmi?"""
    w, f = inst(s, "web-server"), s["flags"]
    tal, bah = table_ok(s, "Talabalar", "talaba_id"), table_ok(s, "Baholar", "talaba_id", "fan")
    return {
        "m1a": lambda: spec_ok(w, UBUNTU, "t2.micro"),
        "m1d": lambda: spec_ok(inst(s, "test-server"), AMAZON, "t2.nano"),
        "m2a": lambda: bool(w) and w["state"] == "stopped",
        "m2b": lambda: bool(w) and w["type"] == "t2.small",
        "m2c": lambda: bool(w) and w["type"] == "t2.small" and w["state"] == "running",
        "m2e": lambda: "reboot:web-server" in f,
        "m3a": lambda: spec_ok(inst(s, "katta-server"), DEBIAN, "t2.medium"),
        "m3c": lambda: bool(inst(s, "katta-server")) and inst(s, "katta-server")["state"] == "stopped",
        "m3d": lambda: "term:test-server" in f,
        "m4a": lambda: bool(tal),
        "m4b": lambda: bool(tal) and len(tal["items"]) >= 3,
        "m4c": lambda: "get:Talabalar" in f,
        "m4d": lambda: bool(item(tal, "T002")) and item(tal, "T002").get("guruh", [0, ""])[1] == "102",
        "m4e": lambda: "del:Talabalar:T003" in f and not item(tal, "T003"),
        "m5a": lambda: bool(bah),
        "m5b": lambda: count(bah, "T001") >= 2,
        "m5c": lambda: count(bah, "T002") >= 1,
        "m5d": lambda: bool(s["instances"]) and all(i["state"] in ("terminated", "shutting-down") for i in s["instances"]),
    }[tid]()


def _norm(v):
    return re.sub(r"\s+", "", str(v or ""))


def answer(s, tid, value):
    """«answer» va «quiz» topshiriqlar: (to'g'rimi, noto'g'ri bo'lsa — tushuntirish)."""
    t = BY_ID[tid]
    if t["kind"] == "quiz":
        try:
            pick = int(value)
        except (TypeError, ValueError):
            return False, "Variantlardan birini tanlang."
        return pick == t["correct"], "Bu javob noto'g'ri. Maslahat: " + t["hint"]
    w, v = inst(s, "web-server"), _norm(value)
    if not v:
        return False, "Avval maydonga javobni yozing."
    if not w:
        return False, "web-server topilmadi. EC2 bo'limida web-server bo'lishi kerak."
    if tid in ("m1b", "m2d"):
        if not w["public_ip"]:
            return False, "web-server hozir ishlamayapti (running emas) — Public IP faqat ishlab turganda bo'ladi."
        if v == w["public_ip"]:
            return True, ""
        return False, f"«{v}» — web-server ning Public IP si emas. Kartadagi «Public IP» ni aynan ko'chiring."
    if tid == "m1c":
        if v == w["id"]:
            return True, ""
        if not v.startswith("i-"):
            return False, "Instance ID «i-» bilan boshlanadi. Kartada nom ostidagi yozuvni to'liq ko'chiring."
        return False, "Instance ID mos kelmadi. Bitta harf ham xato bo'lmasin — kartadan aynan ko'chiring."
    if tid == "m3b":
        m = re.match(r"^(\d+(?:[.,]\d+)?)(gb)?$", v.lower())
        if m and float(m.group(1).replace(",", ".")) == RAM[w["type"]]:
            return True, ""
        return False, "Noto'g'ri. web-server kartasidagi tur qatoriga qarang («… vCPU · ? GB») va GB oldidagi sonni yozing."
    return False, "Noma'lum topshiriq."


# ---------------------------------------------------------------- "nega o'tmayapti?" ro'yxati
TYPE_S = {"S": "String", "N": "Number"}


def _i(ok, label, want=None, got=None):
    return {"ok": bool(ok), "label": label, "want": want, "got": got}


def _inst_items(i, name, ami, typ):
    if not i:
        return [_i(False, "Mashina yaratilgan", name, "hali yo'q")]
    return [_i(i["name"] == name, "Nomi", name, i["name"]),
            _i(i["ami"] == ami, "Tizim (AMI)", AMIS[ami], AMIS[i["ami"]]),
            _i(i["type"] == typ, "Turi", f"{typ} ({TYPES[typ]})", f"{i['type']} ({TYPES[i['type']]})"),
            _i(i["state"] == "running", "Holati running", "running", i["state"])]


def _guess_table(s, name, skip=()):
    if name in s["tables"]:
        return s["tables"][name]
    for t in s["tables"].values():
        if t["name"].lower() == name.lower():
            return t
    rest = [t for t in s["tables"].values() if t["name"] not in skip]
    return rest[-1] if rest else None


def _table_items(t, name, pk, sk):
    if not t:
        return [_i(False, f"«{name}» jadvali yaratilgan", name, "jadval yo'q")]
    out = [_i(t["name"] == name, "Jadval nomi", name, t["name"]),
           _i(t["pk"] == pk, "Partition key", pk, t["pk"]),
           _i(t["pkt"] == "S", "Partition key turi", "String", TYPE_S[t["pkt"]])]
    if sk:
        out.append(_i(t["sk"] == sk and t["skt"] == "S", "Sort key", f"{sk} (String)",
                      f"{t['sk']} ({TYPE_S[t['skt']]})" if t["sk"] else "bo'sh"))
    else:
        out.append(_i(not t["sk"], "Sort key bo'sh", "bo'sh", t["sk"]))
    return out + [_i(t["status"] == "ACTIVE", "Holati ACTIVE", "ACTIVE", t["status"])]


def checklist(s, tid):
    w, f = inst(s, "web-server"), s["flags"]
    need_w = [_i(w, "web-server mashinasi bor", "web-server", None if w else "topilmadi")]
    tal, bah = table_ok(s, "Talabalar", "talaba_id"), table_ok(s, "Baholar", "talaba_id", "fan")
    k = inst(s, "katta-server")
    c = {
        "m1a": lambda: _inst_items(guess_inst(s, "web-server"), "web-server", UBUNTU, "t2.micro"),
        "m1b": lambda: need_w + [_i(w and w["public_ip"], "web-server ishlayapti (Public IP bor)", "running", w and w["state"])],
        "m1c": lambda: need_w,
        "m1d": lambda: _inst_items(guess_inst(s, "test-server", ("web-server",)), "test-server", AMAZON, "t2.nano"),
        "m2a": lambda: need_w + [_i(w and w["state"] == "stopped", "Holati stopped", "stopped", w and w["state"])],
        "m2b": lambda: need_w + [_i(w and (w["state"] == "stopped" or w["type"] == "t2.small"), "Avval to'xtatilgan", "stopped", w and w["state"]),
                                 _i(w and w["type"] == "t2.small", "Turi", "t2.small", w and w["type"])],
        "m2c": lambda: need_w + [_i(w and w["state"] == "running", "Holati running", "running", w and w["state"])],
        "m2d": lambda: need_w + [_i(w and w["public_ip"], "web-server ishlayapti (Public IP bor)", "running", w and w["state"])],
        "m2e": lambda: need_w + [_i("reboot:web-server" in f, "«Qayta yuklash» bosildi", "ha", "hali bosilmagan")],
        "m3a": lambda: _inst_items(guess_inst(s, "katta-server", ("web-server", "test-server")), "katta-server", DEBIAN, "t2.medium"),
        "m3b": lambda: need_w,
        "m3c": lambda: [_i(k, "katta-server bor", "katta-server", None if k else "topilmadi"),
                        _i(k and k["state"] == "stopped", "Holati stopped", "stopped", k and k["state"])],
        "m3d": lambda: [_i("term:test-server" in f, "test-server o'chirildi (terminate)", "terminated",
                           (inst(s, "test-server") or {}).get("state", "topilmadi — qayta yarating va o'chiring"))],
        "m4a": lambda: _table_items(_guess_table(s, "Talabalar", ("Baholar",)), "Talabalar", "talaba_id", None),
        "m4b": lambda: [_i(tal, "«Talabalar» jadvali tayyor", "ACTIVE", None if tal else "yo'q"),
                        _i(tal and len(tal["items"]) >= 3, "Elementlar soni", "3 ta", f"{len(tal['items']) if tal else 0} ta")],
        "m4c": lambda: [_i(item(tal, "T001"), "Jadvalda T001 bor", "T001", None if item(tal, "T001") else "yo'q — avval qo'shing"),
                        _i("get:Talabalar" in f, "GetItem bilan topildi", "Olish bosildi", "hali topilmagan")],
        "m4d": lambda: [_i(item(tal, "T002"), "Jadvalda T002 bor", "T002", None if item(tal, "T002") else "yo'q"),
                        _i(check(s, "m4d"), "T002 ning guruhi", "102", (item(tal, "T002") or {}).get("guruh", [0, "yo'q"])[1])],
        "m4e": lambda: [_i(not item(tal, "T003"), "T003 jadvalda qolmagan", "yo'q", "hali bor" if item(tal, "T003") else None),
                        _i("del:Talabalar:T003" in f, "O'chirish bosildi", "ha", "hali bosilmagan")],
        "m5a": lambda: _table_items(_guess_table(s, "Baholar", ("Talabalar",)), "Baholar", "talaba_id", "fan"),
        "m5b": lambda: [_i(bah, "«Baholar» jadvali tayyor", "ACTIVE", None if bah else "yo'q"),
                        _i(count(bah, "T001") >= 2, "T001 qatorlari", "2 ta", f"{count(bah, 'T001')} ta")],
        "m5c": lambda: [_i(count(bah, "T002") >= 1, "T002 qatorlari", "1 ta", f"{count(bah, 'T002')} ta")],
        "m5d": lambda: [_i(i["state"] in ("terminated", "shutting-down"), i["name"], "terminated", i["state"])
                        for i in s["instances"]][-6:] or [_i(False, "Mashinalar", "terminated", "hali yo'q")],
    }.get(tid)
    return c() if c else []


def public(t):
    """Brauzerga yuboriladigan qism (to'g'ri javob yuborilmaydi)."""
    return {k: v for k, v in t.items() if k != "correct"}
