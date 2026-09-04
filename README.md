# RB19 POS - Kiosk, Kafe, Kiçik restoran və Anbar sistemi

Kiçik biznes üçün hazırlanmış, toxunma-dostu (touch-friendly) satış nöqtəsi (POS) sistemi. Flask (Python) və PostgreSQL/SQLite üzərində qurulub, Railway-də deploy edilə bilər.

## Texnologiyalar

- **Backend:** Python, Flask
- **Verilənlər bazası:** PostgreSQL (production), SQLite (local test)
- **Frontend:** HTML, CSS, JavaScript (Chart.js - hesabatlar üçün)
- **Deploy:** Railway
- **Kod idarəetməsi:** Git + GitHub

## Xüsusiyyətlər

### 1. POS / Kiosk səhifəsi
- Kateqoriya üzrə məhsul seçimi (Drinks, Fastfood, Other, Protein, Salads, Snacks)
- Toxunma-dostu interfeys, miqdar seçimi ilə səbətə əlavə etmə
- Səbətdə real-vaxt cəm hesablama
- Satışı təsdiqləmə - stok avtomatik azalır
- Azərbaycan, İngilis, Rus və Türk dilləri arasında keçid

### 2. Açıq qalanlar / Nisyə sifarişlər
- Səbətdəki məhsulları müştərinin adı ilə açıq sifariş kimi saxlamaq
- Sonrakı səfərdə həmin müştərinin sifarişinə yeni məhsullar əlavə etmək
- Açıq sifariş bağlananda onu ödənilmiş borc tarixçəsində saxlamaq
- Açıq nisyə sifariş yaradılarkən və yenilənərkən stokun avtomatik azaldılması

### 3. Əməliyyatlar (Transactions)
- Bütün satışlar, daxilolmalar (məhsul girişi) və itkilər (zay/xarab olma) bir tarixçədə
- Daxilolma qeyd ediləndə əlaqəli məhsulun stoku artır
- İtki qeyd ediləndə stok azalır, mövcud stokdan çox miqdara icazə verilmir

### 4. Hesabatlar
- Tarix aralığı seçimi ilə filtrlənən analitika
- Ən çox / ən az satılan məhsullar
- Kateqoriya üzrə satış payı (pie chart)
- Gün üzrə satış məbləği (bar chart)
- Top 5 məhsul (bar chart)

### 5. Rol-əsaslı giriş sistemi
4 rəqəmli PIN kodları ilə iki səlahiyyət səviyyəsi:

| Rol | Giriş imkanları |
|---|---|
| Satıcı | Yalnız POS/Kiosk |
| Müdir | POS + Məhsul əlavə etmə + Əməliyyatlar + Hesabatlar |

Hazırkı PIN-lər `app.py` daxilində `PIN_USERS` xəritəsində təyin olunur. Production mühitində onları dəyişmək tövsiyə edilir.
PIN-lər artıq `.env` dəyişənlərindən oxunur:

- `SELLER_PIN`
- `MANAGER_PIN`
- `SECRET_KEY`

### 6. Audit və təhlükəsizlik

- Satışın kim tərəfindən yaradıldığı audit jurnalında saxlanılır.
- Məhsul yaratma, dəyişmə və silmə əməliyyatları qeydə alınır.
- Audit jurnalına yalnız müdirin `/api/audit-log` endpoint-i ilə çıxışı var.
- Satışın ləğvi üçün müdir PIN-i tələb olunur; ləğv edilən məhsulların stoku bərpa edilir.
- Ləğv edilmiş satışlar hesabatlara daxil edilmir.

## Layihəni lokal işə salmaq

```bash
# Kitabxanaları quraşdır
pip install -r requirements.txt

# .env faylını yarat (.env.example-a bax)
# Production üçün DATABASE_URL təyin et.
# DATABASE_URL yoxdursa, SQLITE_DB_PATH ilə lokal SQLite istifadə olunur.

# Tətbiqi işə sal
python app.py
```

Brauzerdə aç: `http://127.0.0.1:5000`

## Deploy (Railway)

1. Railway-də yeni layihə yarat, GitHub repository-ni qoş
2. `+ New → Database → PostgreSQL` ilə baza əlavə et
3. `DATABASE_URL` və `PORT` dəyişənlərini **Variables** bölməsində təyin et
4. Deploy et

`Procfile` Railway üçün Gunicorn başlanğıc əmrini təqdim edir:

```text
web: gunicorn -w 4 -b 0.0.0.0:$PORT app:app
```

## Verilənlər bazası

İlk sorğuda cədvəllər avtomatik yaradılır. Əsas cədvəllər:

- `products`, `categories`
- `sales`, `sale_items`
- `stock_movements`
- `credit_orders`, `credit_order_items`

`DATABASE_URL` təyin edildikdə əsas və qalıcı storage PostgreSQL olur. `DATABASE_URL` olmadıqda lokal development üçün `SQLITE_DB_PATH` (default: `app.db`) istifadə edilir. Railway-də məlumatların itirilməməsi üçün PostgreSQL servisini qoşduqdan sonra onun verdiyi `DATABASE_URL` dəyişənini tətbiqə əlavə edin.

## Qeyd

Bu sistem daxili satış/anbar idarəetməsi üçündür. Azərbaycanda rəsmi
nəzarət-kassa aparatı tələbləri ayrıca yoxlanılmalıdır - bu proqram
rəsmi fiskal kassa əvəzi deyil.

## Gələcək planlar

- Barkod skaneri inteqrasiyası
