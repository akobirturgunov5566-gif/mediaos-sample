# Navoiyda Bugun — ekotizim boti

Bitta bot, to'rt xizmat. Bot ham, kelajakdagi **Navoiyda Bugun ilovasi** ham bitta backend'ga
(`app/services`) ulanadi — API-first.

```
          @navoiydabugun_bot (markaz)
       /        |          |         \
   🔍 Ish   📦 Topildi   🏠 Ijara   ❗ Muammo
  (pul)     (obro')      (pul)     (kontent)
```

| Xizmat | Kim to'laydi | Chiqish qoidasi |
|---|---|---|
| **Ish** (Vohada Ish) | ish beruvchi | maosh majburiy; bepul e'lon 120 daqiqadan keyin, 3 referal bilan darhol |
| **Topildi / Yo'qoldi** | hech kim | bepul, shartsiz, darhol; telefon kanalda ko'rinmaydi, bog'lanish bot orqali |
| **Ijara** | ijaraga beruvchi | Ish bilan bir xil mexanika |
| **Muammo** (svet, gaz, suv, yo'l) | hech kim | darhol; ERP uchun tayyor "Tezkor/Rasmiy" mavzu |

Hamma e'lon avval **moderator guruhiga** tushadi: ✅ Tasdiqla / ❌ Rad (sabab so'raladi) / 🚫 Spam.

## Odam botni o'chirmasligi uchun

- Bot **o'zi yozmaydi**. Faqat: e'lon chiqdi, rad etildi, 3-kun so'rovi, obuna bo'lgan kategoriya digesti (18:00, kuniga 1 ta).
- Telefon faqat e'lon berganda so'raladi, ko'rishda emas.
- Har xabarda 🔕 tugmasi. `/sozlamalar` → bildirishnoma, obunalar.
- `/stats` → foydalanuvchi, 7 kunlik tiriklik, **blok %** (5% dan oshsa ogohlantiradi).
- Blok qilganlar `my_chat_member` orqali avtomatik belgilanadi, ularga boshqa yozilmaydi.

## Ishga tushirish

```bash
cd navoiyda-bugun-bot
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # BOT_TOKEN, CHANNEL_ID, MOD_CHAT_ID, ADMIN_IDS ni to'ldiring
python -m app.bot.main   # bot (polling)
uvicorn app.api.main:app --port 8080   # ilova uchun API (ixtiyoriy)
```

Bot kanalda **admin** bo'lishi, moderator guruhiga qo'shilgan bo'lishi kerak.
Baza: `DATABASE_URL` bo'sh bo'lsa `bot.db` (SQLite). Production: `postgresql+asyncpg://...`.
Server: `deploy/navoiydabugun-bot.service` (systemd).

## Test

```bash
pytest -q      # 13 test: servislar + to'liq bot oqimi (mock Telegram) + API
```

## Tuzilish

```
app/
  config.py        .env sozlamalari
  models.py        users, listings, referrals, events
  services/        listings (hayot sikli), users, referrals, metrics  ← bot va API shuni ishlatadi
  bot/
    handlers/      start+sozlamalar, create (FSM), browse, my, moderation
    jobs.py        har 60 s: chiqarish, eskirish, 3-kun so'rovi, 18:00 digest
    publisher.py   faqat shu fayl kanalga yozadi
    texts.py       hamma matn (o'zbek lotin)
  api/main.py      GET /api/listings, /api/listings/{id}, /api/stats
```

## Buyruqlar

| Kim | Buyruq |
|---|---|
| hamma | `/start`, `/sozlamalar` |
| moderator guruhi | `/pending` (navbat), `/stats` |
| admin | `/broadcast <matn>` — haftada 1 martadan ko'p emas |
