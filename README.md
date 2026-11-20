# VirtLab — virtualizatsiya simulyatori

«Virtualizatsiya turlari va qo'llanilishi» amaliy mashg'uloti uchun sinf simulyatori.
Talabalar brauzerdan (kompyuter yoki telefon) kirib, «BulutStart» startapining yangi tizim
administratori sifatida virtual mashinalar (VM) yaratadi, ishga tushiradi, holat nusxasi oladi
va xost resurslari cheklovi bilan kurashadi. Haqiqiy VirtualBox kerak emas — hamma narsa serverda
simulyatsiya qilinadi.

Hamma interfeys matni o'zbek (lotin) tilida. Bitta fayl: `app.py` (FastAPI + SSE, tashqi CDN yo'q).
Shriftlar (Inter va konsol uchun JetBrains Mono, SIL OFL litsenziyasi) `app.py` ichiga joylangan —
internet bo'lmasa ham to'g'ri ko'rinadi.

### Sahifalar tuzilmasi

- **Talaba:** yuqori panel (ism, jamoa, ball, taymer) → 4 bosqich qadami → chapda topshiriqlar
  (hozirgisi ochiq, bajarilganlari bir qatorda, keyingilari xira) → o'ngda xost server, VM lar va «Yangi VM» shakli.
- **O'qituvchi:** 4 ta bosqich plitkasi (progress va «Ochish» / «Avariya!» tugmasi shu yerda) → sinf (pauza, taymer)
  va e'lon → jamoalar → talabalar jadvali.
- **Proyektor:** bosqich va taymer → jamoalar va eng ko'p ball → avariya paytida birinchi tiklaganlar.

## O'rnatish

Python 3.10+ kerak.

```bash
pip install fastapi uvicorn
```

(Ixtiyoriy, alohida muhit: `python -m venv .venv && .venv/bin/pip install fastapi uvicorn`)

## Ishga tushirish

```bash
python app.py
```

Server `0.0.0.0:8000` da ishga tushadi va konsolga quyidagilarni chiqaradi:

- **Talabalar uchun** havola(lar): `http://<LAN-IP>:8000`
- **O'qituvchi** havolasi: `http://<LAN-IP>:8000/teacher?key=KALIT`
- **Proyektor** havolasi: `http://<LAN-IP>:8000/screen?key=KALIT`

Kalit (`KALIT`) `VIRTLAB_KEY` muhit o'zgaruvchisidan olinadi, bo'lmasa tasodifiy 6 xonali raqam
yaratiladi va `state.json` ga saqlanadi (server qayta ishga tushsa, kalit o'zgarmaydi).

```bash
VIRTLAB_KEY=424242 python app.py        # o'zingiz kalit tanlash
PORT=9000 python app.py                 # boshqa port
```

Boshqa sozlamalar: `VIRTLAB_STATE=/yo'l/state.json` (holat fayli), `VIRTLAB_STUCK_SECONDS=180`
(o'qituvchi jadvalida «qotib qolgan» deb belgilash chegarasi, soniyada).

Holat har o'zgarishdan keyin (≈0,25 soniya ichida) `state.json` ga yoziladi; server qayta
ishga tushsa, hamma narsa tiklanadi — talabalar sahifani yangilamasdan davom etadi.
Server o'chirilib qayta yoqilganda ochiq sahifalar o'zi qayta ulanadi.

## LAN yoki tunnel

### 1) Bir xil Wi-Fi / LAN (tavsiya etiladi)

Hamma qurilma o'qituvchi noutbuki bilan bir tarmoqda bo'lsa, talabalarga
`http://<noutbuk-IP>:8000` manzilini bering. IP manzil server ishga tushganda konsolda
ko'rsatiladi. Agar ulanmasa, noutbukning xavfsizlik devorida (firewall) 8000-portni oching.

> **Boshqa qurilmalar `http://<IP>:8000` ni ochmasa:** ko'p universitet va jamoat Wi-Fi tarmoqlarida
> «client isolation» yoqilgan — bir tarmoqdagi qurilmalar bir-birini ko'rmaydi. Bunga noutbukdan
> hech narsa qilib bo'lmaydi. Yechimlar: (a) quyidagi **internet tunneli**, yoki (b) telefoningizdan
> **hotspot** yoqib, noutbuk va talabalarni shu hotspotga ulash, yoki (c) o'z Wi-Fi routeringiz.
> Tekshirish: telefonda `http://<IP>:8000/health` ni oching — `{"ok":true...}` chiqsa, LAN ishlaydi.

### 2) Internet orqali: Cloudflare tunnel (tavsiya, akkaunt kerak emas)

Bir marta o'rnatish (Linux):

```bash
mkdir -p ~/.local/bin
curl -L -o ~/.local/bin/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x ~/.local/bin/cloudflared
```

(Windows: `cloudflared-windows-amd64.exe` ni yuklab, `cloudflared.exe` nomi bilan `app.py` yoniga qo'ying.)

Keyin serverni shunday ishga tushiring:

```bash
python app.py --tunnel
```

5–15 soniyadan keyin konsolda `https://....trycloudflare.com` manzil chiqadi. U o'qituvchi
panelining tepasida («Talabalar kiradigan manzil», nusxa olish tugmasi bilan) va proyektor
ekranining pastida ham ko'rinadi. Talabalar uni istalgan tarmoqdan (mobil internetdan ham) ochadi.
Har ishga tushirishda manzil yangi bo'ladi — darsdan oldin ishga tushiring.

> Bepul Cloudflare tunneli SSE oqimini bufer qiladi. Sahifalar buni o'zi aniqlaydi: 6 soniyada
> ma'lumot kelmasa, **long-poll** ga o'tadi (bitta so'rov o'zgarish bo'lguncha kutadi). Shuning uchun
> tunnelda birinchi ochilishda yangilanishlar ~6 soniyadan keyin boshlanadi — bu normal.

### 3) Boshqa tunnellar

```bash
jprq http 8000
# yoki
ngrok http 8000
```

Tunnel bergan `https://...` manzilni talabalarga yuboring. O'qituvchi va proyektor sahifalarini
ham shu manzil orqali (yoki LAN orqali) `?key=KALIT` bilan oching.

> **ngrok eslatmasi:** bepul ngrok manzilida birinchi kirishda «Visit Site» degan brauzer
> ogohlantirish sahifasi chiqadi. Har bir talaba bir marta **«Visit Site»** tugmasini bosishi
> kerak. Sahifaning o'zi so'rovlarga `ngrok-skip-browser-warning` sarlavhasini qo'shadi,
> lekin dastlabki sahifa ochilishi uchun tugmani bosish shart.
>
> Tunnelda so'rovlar soni cheklangan bo'lishi mumkin — shuning uchun ilova qisqa intervalli
> so'rov (polling) ishlatmaydi: yangilanishlar bitta SSE oqimi orqali keladi.

## Dars davomida

0. **Kutish zali.** Server ishga tushganda (yoki tozalangandan keyin) dars hali boshlanmagan bo'ladi:
   talabalar kiradi, jamoasini ko'radi, lekin hech narsa qila olmaydi. Hamma kirgach, o'qituvchi
   panelidagi **«Darsni boshlash»** tugmasi 1-bosqichni ochadi.

1. Talabalar manzilni ochib, **Ism familiya** ni kiritadi (**Guruh** ixtiyoriy). Server ularni eng kichik
   jamoaga (Cache, Cloud, Router, Firewall) joylaydi. Sahifani yangilash seansni saqlaydi.
2. 1-bosqich dastlab ochiq. Keyingilarini o'qituvchi panelidagi **«N-bosqichni ochish»** bilan ochadi.
   Bosqich xato bilan ochilsa, joriy bosqich plitkasidagi **«Bosqichni yopish»** (ikki marta bosiladi)
   uni yana yopadi; talabalar ballari saqlanadi. Avariya boshlangandan keyin 4-bosqich yopilmaydi.
3. 4-bosqichda o'qituvchi **«Avariya!»** tugmasini bosadi (tasodifan bosilmasligi uchun ikki marta
   bosish kerak): hamma talabaning ishlayotgan VM lari «Buzilgan» bo'ladi. Birinchi uch tiklagan
   talaba +30 / +20 / +10 ball oladi. Keyin 5 savollik viktorina.
4. **O'qituvchi paneli** imkoniyatlari: e'lon yuborish (hamma talabada banner), **Pauza**
   («O'qituvchini tinglang» — talabalarning harakatlari to'xtaydi), jonli jadval (qiynalayotganlar
   yuqorida, 3 daqiqadan oshsa qizg'ish), bosqichlar progressi, talabani o'chirish yoki jamoasini
   almashtirish, **CSV yuklab olish**.
5. **Proyektor** sahifasini (`/screen?key=...`) katta ekranga chiqaring: jamoalar balli, eng yaxshi 5
   talaba, avariya paytida «birinchi bo'lib tiklaganlar» ro'yxati.

### Ball tizimi

| Topshiriq | Ball |
|---|---|
| Oddiy topshiriq | 10 (Yordam ishlatilsa — 5) |
| Bonus topshiriq | 15 (Yordam ishlatilsa — 7) |
| Avariyadan tiklash, 1/2/3-o'rin | +30 / +20 / +10 |
| Viktorina | har to'g'ri javob uchun 10 |

Jamoa balli = a'zolarning **o'rtacha** balli (jamoalar soni teng bo'lmasa ham adolatli).

## Javob yoziladigan topshiriqlar

Ba'zi topshiriqlarda talaba buyruq natijasini **o'qib, javob maydoniga yozadi** — server tekshiradi:

| Topshiriq | Nimani yozadi |
|---|---|
| 1.4 | `free -h` dagi **available** qiymat (masalan `1.6Gi`) |
| 1.5 | `df -h` dagi `/dev/vda1` ning **Used** qiymati (masalan `3.9G`) |
| 2.5 | Tiklangan VM da `ls` natijasi (fayl nomlari) |
| 3.A | 3 ta VM ishlab turganda xost panelidagi bo'sh xotira (GB) |

Qiymatlar har bir VM da biroz boshqacha, shuning uchun qo'shnidan ko'chirib bo'lmaydi.
Buyruq berilmagan bo'lsa server avval buyruqni berishni so'raydi (bu xato hisoblanmaydi).
3 ta noto'g'ri javobdan keyin topshiriq balli yarmiga tushadi.

## Tozalash (yangi guruh uchun)

O'qituvchi panelidagi **«Hammasini tozalash»** tugmasi (tasdiqlash so'raladi) hamma talaba va
natijalarni o'chiradi, bosqichni 1 ga qaytaradi. Yoki serverni to'xtatib, `state.json` ni
o'chirib qo'ying, yoki `python app.py --reset` (kalit saqlanadi). Natijalarni tozalashdan **oldin** «CSV yuklab olish» bilan saqlab oling.

## Sinov

`simulate.py` 32 ta talabani API orqali simulyatsiya qiladi (tasodifiy tezlik, Yordam ishlatish,
qotib qolish, avariya, viktorina) va ballar, jamoa o'rtachalari, top-3 tartibi, SSE yangilanishlari,
o'qituvchi jadvali va CSV ni tekshiradi:

```bash
VIRTLAB_KEY=123456 VIRTLAB_STUCK_SECONDS=3 python app.py     # 1-terminal
pip install httpx && python simulate.py                       # 2-terminal
python simulate.py --reset                                    # tozalash
```

## Xavfsizlik va cheklovlar

- Talaba kiritgan hamma matn sahifada `textContent` orqali chiqariladi (HTML sifatida emas);
  server hamma kirishni tekshiradi.
- O'qituvchi/proyektor sahifalari va API ga `key` kerak. Kalitni talabalarga bermang.
- `/health` — oddiy tekshiruv (`{"ok": true, ...}`).
- Bu dars uchun mo'ljallangan oddiy dastur: HTTPS va autentifikatsiya tunnel zimmasida.
# bulutli-labs
