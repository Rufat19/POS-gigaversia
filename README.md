# RB19 POS - Kiosk, Kafe, Kiçik restoran və Anbar sistemi

Kiçik biznes üçün hazırlanmış, toxunma-dostu (touch-friendly) satış nöqtəsi (POS) sistemi. Flask (Python) və PostgreSQL üzərində qurulub, Railway-də deploy edilir.

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

### 2. Əməliyyatlar (Transactions)
- Bütün satışlar, daxilolmalar (məhsul girişi) və itkilər (zay/xarab olma) bir tarixçədə
- Daxilolma qeyd ediləndə əlaqəli məhsulun stoku artır
- İtki qeyd ediləndə stok azalır, mövcud stokdan çox miqdara icazə verilmir

### 3. Hesabatlar
- Tarix aralığı seçimi ilə filtrlənən analitika
- Ən çox / ən az satılan məhsullar
- Kateqoriya üzrə satış payı (pie chart)
- Gün üzrə satış məbləği (bar chart)
- Top 5 məhsul (bar chart)

### 4. Rol-əsaslı giriş sistemi
5 rəqəmli PIN kodları ilə üç səlahiyyət səviyyəsi:

| Rol | Giriş imkanları |
|---|---|
| Satıcı | Yalnız POS/Kiosk |
| Müdir | POS + Məhsul əlavə etmə + Əməliyyatlar + Hesabatlar |
| Admin | Tam giriş (aşağıdakı admin panel daxil) |

### 5. Admin Paneli
- Sayt görünüşünü dəyişmək (banner şəkil, başlıq, alt yazı)
- Məhsulları redaktə/silmək (ad, qiymət, stok, kateqoriya, şəkil)
- Rolların PIN kodlarını idarə etmək
- Əməliyyat/tarixçə sıfırlama və təmizlik

## Layihəni lokal işə salmaq

```bash
# Kitabxanaları quraşdır
pip install -r requirements.txt

# .env faylını yarat (.env.example-a bax)
# DATABASE_URL, SATICI_PIN, MUDIR_PIN, ADMIN_PIN dəyərlərini təyin et

# Tətbiqi işə sal
python app.py
```

Brauzerdə aç: `http://127.0.0.1:5000`

## Deploy (Railway)

1. Railway-də yeni layihə yarat, GitHub repository-ni qoş
2. `+ New → Database → PostgreSQL` ilə baza əlavə et
3. `DATABASE_URL` və PIN dəyişənlərini **Variables** bölməsində təyin et
4. Deploy et

## Qeyd

Bu sistem daxili satış/anbar idarəetməsi üçündür. Azərbaycanda rəsmi
nəzarət-kassa aparatı tələbləri ayrıca yoxlanılmalıdır - bu proqram
rəsmi fiskal kassa əvəzi deyil.

## Gələcək planlar

- Barkod skaneri inteqrasiyası
