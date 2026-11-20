# A5 — Virtual mashina namunasi va Amazon DynamoDB jadvallari

**Mavzu:** Virtual mashina namunasini ishga tushirish va boshqarish. Amazon DynamoDB da jadvallar yaratish.

Brauzerda ishlaydigan sinf simulyatori: talaba AWS konsoliga o'xshash sahifada EC2 namunasini
(virtual mashinani) ishga tushiradi, to'xtatadi, turini o'zgartiradi, reboot va terminate qiladi,
so'ng DynamoDB da jadval yaratib, element qo'shadi va o'qiydi. Har bir amalning **AWS CLI
ekvivalenti** ham ko'rsatiladi. Haqiqiy AWS akkaunti kerak emas, pul sarflanmaydi.

- Faqat **Python 3.9+** — hech qanday `pip install` kerak emas.
- Tashqi CDN yo'q: internet bo'lmasa ham ishlaydi. Telefon va kompyuterda ishlaydi.

## Ishga tushirish

```bash
cd a5
python3 app.py
```

Konsolda havolalar chiqadi:

```
Talabalar:   http://<IP>:8000
O'qituvchi:  http://<IP>:8000/teacher   (login: ustoz, parol: admin123)
Proyektor:   http://<IP>:8000/ekran
```

| Sozlama | Misol |
|---|---|
| Boshqa port | `PORT=8005 python3 app.py` |
| O'qituvchi paroli | `A5_TEACHER_PASSWORD=yangi-parol python3 app.py` (login: `A5_TEACHER_USER`, standart `ustoz`) |
| Natijalarni tozalash | `python3 app.py --reset` |

## VPS da

```bash
git clone https://github.com/komronium/bulutli-labs.git   # birinchi marta
cd bulutli-labs && git pull                               # keyingi safar
cd a5 && python3 app.py
```

Brauzerda `http://<VPS-IP>:8000` ni oching. Ochilmasa, portni oching: `sudo ufw allow 8000`.

Terminal yopilganda ham ishlab tursin desangiz (repo papkasidan):

```bash
nohup python3 a5/app.py > a5.log 2>&1 &   # to'xtatish: pkill -f a5/app.py
```

Shu serverda boshqa laboratoriya ham 8000-portda ishlayotgan bo'lsa: `PORT=8005 python3 a5/app.py`.

## Dars oqimi (A3/A4 dagidek, o'qituvchi boshqaradi)

Har bir missiya: **Namuna → Mustaqil → Yakun**. Darsdan oldin — **Kutish**.

| Qadam | Talaba ekranida | Konsol |
|---|---|---|
| Kutish | "Dars hali boshlanmagan" | yopiq |
| Namuna | missiya maqsadi va namunalar, "O'qituvchini kuzating" | yopiq |
| Mustaqil | bitta joriy vazifa: Qayerda · Qadamlar · Natija · Tekshiruv · Maslahat | ochiq |
| Yakun | natija va "Siz nimani o'rgandingiz" | yopiq |

O'qituvchi panelida **▶ Keyingi qadam** (yoki istalgan qadamni bosib o'tish). Namunani
**Namuna konsoli**da ko'rsating (`/?demo=1`): u doim ochiq va reytingga kirmaydi. Proyektor
(`/ekran`) Namuna qadamida namunalarni, boshqa paytda jamoalar poygasini ko'rsatadi.

## Missiyalar (5 ta, 27 vazifa, har biri 10 ball — jami 270)

| Missiya | Vazifalar |
|---|---|
| 1. Birinchi virtual mashina | web-server (Ubuntu, t2.micro) · Public IP ni yozish · Instance ID ni yozish · test-server (Amazon Linux, t2.nano) · savol |
| 2. Mashinani boshqarish | Stop · turini t2.small ga · Start · yangi Public IP ni yozish · Reboot · savol |
| 3. To'g'ri tur va tozalash | katta-server (2 vCPU / 4 GB ni o'zi topadi) · RAM necha GB · katta-server ni Stop · test-server ni Terminate · savol |
| 4. DynamoDB: birinchi jadval | Talabalar jadvali · 3 element · GetItem · T002 ni o'zgartirish · T003 ni o'chirish · savol |
| 5. Ikki qismli kalit va yakun | Baholar (PK + SK) · T001 ga 2 fan · T002 ga fan · savol · hamma mashinalarni Terminate |

Vazifalar ketma-ket ochiladi; keyingi missiya vazifalari o'qituvchi ochguncha qulflangan.
Taxminiy vaqt: 70–80 daqiqa. Dars mazmuni (vazifalar, namunalar, tekshiruvlar) — `lesson.py`.

## Jamoalar va reyting

Talaba kirganda 4 jamoadan eng kichigiga tushadi: **Bulut**, **Chaqmoq**, **Raketa** va **Yulduz**.
Har bir jamoaning o'z rangi va ikonkasi bor.

- Har bir vazifa — 10 ball, jami 270.
- Jamoa balli — a'zolar ballining **o'rtachasi** (jamoalar soni teng bo'lmasa ham adolatli).
- Ball teng bo'lsa, oxirgi vazifani ertaroq bajargan talaba yuqorida turadi.

Talaba o'z ekranida ballini, sinfdagi o'rnini va jamoalar reytingini ko'radi.

## Talaba qayerda adashganini ko'radi

Vazifa kartasida jonli **Tekshiruv** ro'yxati bor: har bir shart ✓ yoki ✗ bo'ladi.
Xato bo'lsa, yonma-yon yoziladi: `sizda: Web Server → kerak: web-server`.
Bajarilmagan amal xabari kartada qizil qutida qoladi.

## O'qituvchi paneli va proyektor

- `/teacher` — login `ustoz`, parol `admin123`. Jamoa kartalari, "Ball qanday hisoblanadi" izohi,
  talabalar reytingi (har 3 soniyada yangilanadi), **CSV**, **Tozalash** (yangi guruh uchun; avval CSV ni saqlang).
- `/ekran` — katta ekran uchun: jamoalar poygasi, eng yaxshi 5 talaba va qoidalar.
  Avval shu brauzerda `/teacher` ga kiring.

## Fayllar

```
a5/
├── app.py          # server: API, EC2/DynamoDB simulyatsiyasi, dars oqimi, reyting
├── lesson.py       # dars mazmuni: 5 missiya, 27 vazifa, namunalar, tekshiruvlar
└── web/            # sahifalar: index.html (talaba), teacher.html, ekran.html, style.css, common.js, student.js
```
