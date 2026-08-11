# MediaOS — sample (President AI Award)

> **EN summary.** MediaOS is the internal operating system of a regional media
> company (961K-follower Instagram brand, 70M+ monthly views): a deterministic
> content-factory state machine (script → shoot → edit → approve → publish)
> with an AI layer on top that *reads* live operational state and explains it.
> Result: on-time publishing grew **43% → 65%** (June → August) across
> **3,850+ tracked tasks**. This is a sanitized public sample; the full
> repository is private. Live demo available on request.

## MediaOS nima?

MediaOS — media-kompaniyaning ichki operatsion tizimi (ERP). U kontent-zavodning
butun zanjirini **saqlaydi** (slot/vazifa/deadline holat-mashinasi),
**kuzatadi** (kechikish, bosqich-o'tishlar, eskalatsiya) va **tushuntiradi**
(AI qatlam jonli DB holatini o'qib rahbariyatga oddiy tilda izohlaydi).

**Tamoyil: deterministik yadro + ustida AI.** Qarorni holat-mashinasi qabul
qiladi; AI hech qachon to'g'ridan-to'g'ri DB'ga yozmaydi — faqat qo'riqlangan
read-only darvoza orqali o'qiydi va tavsiya beradi.

## Natija

- On-time publish: **43% → 65%** (iyun → avgust)
- **3,850+** vazifa tizim orqali kuzatilgan
- 30+ avtomatik fon-job (deadline, eskalatsiya, hisobot) — har biri heartbeat bilan

## Papkalar

| Papka | Nima | Fayllar |
|---|---|---|
| `core/` | Vazifa-oqimi yadrosi: qoida-asosli avto-tayinlash (load-balance bilan) va post vaqtidan orqaga hisoblanadigan deadline-zanjiri | `auto_assignment.py`, `deadline_calculator.py` |
| `ai/` | AI qatlam: jonli prod-DB ustidagi qo'riqlangan read-only oyna (SQL-guard) — AI shu darvoza orqali holatni o'qiydi va tushuntiradi | `db_query_guard.py` |
| `notifications/` | Xabar-darvoza: shablon-render → topic-routing → vaqt-darvoza ("odam dam oladi — tizim ishlaydi": ish-vaqtidan tashqari xabar navbatga tushadi, 🔴 favqulodda doim o'tadi) | `gateway.py`, `schedule.py`, `topics.py` |

## Jamoa

- **Akobir** — Founder / Product
- **Muhammadali** — Lead Developer
- **Bobur** — CEO

## Eslatma

Bu — tozalangan namuna (sanitized sample): maxfiy biznes-logika (KPI/moliya),
autentifikatsiya qatlamlari va konfiguratsiya olib tashlangan; fayllar
illyustrativ, mustaqil ishga tushirish uchun emas. To'liq repo private.
Demo — so'rov bo'yicha.
