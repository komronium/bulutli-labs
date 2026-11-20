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

## Topshiriqlar (har biri 10 ball, jami 100)

Ekranda har doim bitta joriy vazifa turadi (A3/A4 dagidek): **Qayerda**, **Qadamlar**, **Natija** va **Maslahat olish**. Bosilishi kerak bo'lgan tugma yonib-o'chib turadi. Vazifalar ketma-ket ochiladi, server o'zi tekshiradi.

| # | Topshiriq | Nima o'rganiladi |
|---|---|---|
| E1 | `web-server`, Ubuntu 24.04, t2.micro namuna ishga tushirish | AMI, namuna turi, `pending → running` |
| E2 | Namunani to'xtatish | `stopped`: disk qoladi, public IP bo'shatiladi |
| E3 | Turini t2.small ga o'zgartirish | Faqat to'xtatilgan namunada mumkin |
| E4 | Qayta ishga tushirish | Yangi public IP beriladi |
| E5 | Reboot | IP o'zgarmaydi |
| D1 | `Talabalar` jadvali, partition key `talaba_id` (String) | Jadval, kalit, `CREATING → ACTIVE` |
| D2 | 3 ta element qo'shish | PutItem, atributlar, String/Number |
| D3 | GetItem bilan element o'qish | Kalit bo'yicha o'qish |
| D4 | `Baholar`: partition key `talaba_id` + sort key `fan`, bitta talabaga 2 ta fan | Murakkab (composite) kalit |
| F1 | `web-server` ni terminate qilish | Keraksiz resurslarni tozalash |

## Jamoalar va reyting

Talaba kirganda 4 jamoadan eng kichigiga tushadi: **Bulut**, **Chaqmoq**, **Raketa** va **Yulduz**.
Har bir jamoaning o'z rangi va ikonkasi bor.

- Har bir vazifa — 10 ball, jami 100.
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
├── app.py          # server: API, EC2/DynamoDB simulyatsiyasi, tekshiruv
└── web/            # sahifalar: index.html (talaba), teacher.html, style.css, common.js, student.js
```
