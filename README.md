# Robo POS - Kiosk, Kafe, Kiçik restoran və Anbar sistemi

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
- İstifadədən çıxarılan məhsullar arxivlənir; satış, masa və borc tarixçəsindəki məhsul qeydləri saxlanılır
- Əməliyyatlar bölməsindən bütün aktiv məhsulları birdəfəlik arxivləmək mümkündür; tarixçə saxlanılır
- Toxunma-dostu interfeys, miqdar seçimi ilə səbətə əlavə etmə
- Səbətdə real-vaxt cəm hesablama
- Satışı təsdiqləmə - stok avtomatik azalır, qalıq kifayət etmədikdə satış mənfi stokla da davam edir
- Satışdan sonra 80 mm termal qəbz çap pəncərəsi açılır; qəbz Xprinter üçün formatlanır
- Azərbaycan, İngilis, Rus və Türk dilləri arasında keçid

### 2. Açıq qalanlar / Nisyə sifarişlər
- Səbətdəki məhsulları müştərinin adı ilə açıq sifariş kimi saxlamaq
- Masa hesabını borclunun adı ilə Açıq qalanlara köçürmək və masanı boşaltmaq
- Sonrakı səfərdə həmin müştərinin sifarişinə yeni məhsullar əlavə etmək
- Açıq sifariş bağlananda onu ödənilmiş borc tarixçəsində saxlamaq
- Açıq nisyə sifariş yaradılarkən və yenilənərkən stokun avtomatik azaldılması

### 3. Masalar
- Masalar kateqoriyaya görə avtomatik qruplaşdırılır; boş/dolu vəziyyətinə görə filtrləmək, ad və nömrəyə görə sıralamaq mümkündür
- Masa hesabını ödəyib bağlamaq və ya borc kimi Açıq qalanlara köçürmək mümkündür; köçürülən masa dərhal boşalır
- Müdir və admin üçün masa/kateqoriya tənzimləmələri Masalar bölməsindəki Tənzimləmələr düyməsindədir

### 4. Əməliyyatlar (Transactions)
- Məhsul daxilolmaları və itkilər üçün anbar hərəkətləri tarixçəsi
- Daxilolma qeyd ediləndə əlaqəli məhsulun stoku artır
- İtki qeyd ediləndə stok azalır, mövcud stokdan çox itkiyə icazə verilmir
- Satış zamanı stok miqdarı satışa mane olmur və qalıq mənfiyə düşə bilər
- Müdir və admin anbar tarixçəsini silə bilər; cari stok qalıqları dəyişmir

### 5. Satış tarixçəsi
- Satış sətirləri ayrıca bölmədə göstərilir
- Satıcı, müdir və admin üçün daim açıqdır
- Səhifə Bakı vaxtı ilə cari günün satışları ilə açılır; “Bu gün” və digər hazır filtrlər, eləcə də tarix aralığı seçimi mövcuddur
- Müdir və admin bütün satış tarixçəsini ayrıca və geri qaytarılmayacaq şəkildə silə bilər

### 6. Hesabatlar
- Tarix aralığı seçimi ilə filtrlənən analitika
- Ən çox / ən az satılan məhsullar
- Kateqoriya üzrə satış payı (pie chart)
- Gün üzrə satış məbləği (bar chart)
- Top 5 məhsul (bar chart)

Müdir və admin borc tarixçəsini də təmizləyə bilər. Bu əməliyyat ödənilmiş borclarla yanaşı açıq və ödənilməmiş sifarişləri də silir; satış tarixçəsini və məhsul stokunu dəyişmir. Tarixçə təmizləmə düymələri satıcılara göstərilmir.

### 7. Rol-əsaslı giriş sistemi
4 rəqəmli PIN kodları ilə üç rol:

| Rol | Giriş imkanları |
|---|---|
| Satıcı | POS/Kiosk + Satış tarixçəsi |
| Müdir | POS + Məhsul əlavə etmə + Əməliyyatlar + Satış tarixçəsi + Hesabatlar |
| Admin | Bütün bölmələr + İdarəetmə |

PIN-lər production mühitində yalnız Railway Variables bölməsindən verilməlidir.
PIN-lər artıq `.env` dəyişənlərindən oxunur:

- `SELLER_PIN`
- `MANAGER_PIN`
- `ADMIN_PIN`
- `SECRET_KEY`

### Gündəlik e-poçt hesabatı

Admin bölməsində müdirlərin bir və ya bir neçə e-poçt ünvanını qeyd edin və test məktubu göndərərək SMTP bağlantısını yoxlayın. Hər gün Bakı vaxtı ilə saat 00:00-da göndərilən hesabatda əvvəlki Bakı təqvim gününün satış cəmi və məhsul xülasəsi, həmin gün yaradılmış borcların müştəri adı/məbləği, həmçinin bütün aktiv məhsulların cari stok qalığı olur.

SMTP parametrləri Railway Variables-da saxlanmalıdır: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS`, `SMTP_USE_SSL` və istəyə görə `SMTP_TIMEOUT`. Bu e-poçt giriş məlumatlarını admin səhifəsinə və ya repozitoriyə yazmayın.

Railway-də eyni layihə/verilənlər bazasından istifadə edən ayrıca Cron service yaradın:

- **Start Command:** `flask --app app send-daily-report`
- **Cron Schedule:** `0 20 * * *` (Railway cron UTC işləyir; 20:00 UTC Bakı vaxtı ilə 00:00-dır)
- **Variables:** web service-in `DATABASE_URL` və `SMTP_*` dəyişənləri ilə eyni dəyərləri istifadə edin.

Cron service işləyən web service-dən ayrı olmalıdır; beləliklə Gunicorn worker-lərinin hər birində ayrıca planlayıcı açılıb eyni hesabatı təkrar göndərməyəcək. Test məktubunu admin panelindən yoxladıqdan və Railway Cron service-i aktiv etdikdən sonra gündəlik göndəriş başlayır.

`ADMIN_PIN` verilməsə, lokal inkişaf üçün `414541` istifadə olunur. Production-da
öz admin PIN-inizi Railway Variables bölməsində təyin edin.

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

Qəbz çapı zamanı printer parametrlərində 80 mm rulon ölçüsünü seçin, kənar boşluqları
minimuma endirin və brauzerin çap dialoqunda Xprinter-i göstərin. Adi brauzer rejimində
istifadəçi çapı təsdiqləyir; təsdiqsiz çap üçün POS kompüterində ayrıca kiosk və ya lokal
çap köməkçisi konfiqurasiyası tələb olunur.

## Deploy (Railway)

1. Railway-də yeni layihə yarat və GitHub repository-ni qoş.
2. `+ New → Database → PostgreSQL` ilə PostgreSQL servisi əlavə et.
3. Tətbiq servisinin **Variables** bölməsində PostgreSQL bağlantı dəyişənini əlavə et. Railway-də bağlantı URL-i adətən PostgreSQL servisindən `${{Postgres.DATABASE_URL}}` reference kimi seçilir.
4. Bu dəyişənləri də əlavə et:
   - `SECRET_KEY`: uzun, təsadüfi, ən azı 32 simvolluq dəyər
   - `SELLER_PIN`: yalnız satıcının bildiyi yeni PIN
   - `MANAGER_PIN`: satıcı PIN-indən fərqli, yeni rəhbər PIN-i
   - `ADMIN_PIN`: yalnız sistem sahibinin bildiyi admin PIN-i
5. `FLASK_DEBUG` dəyişənini əlavə etmə və production-da `True` etmə.
6. Deploy et və Railway-in verdiyi public domain üzərindən giriş səhifəsini yoxla.

Admin PIN-i ilə daxil olduqda `/admin` səhifəsindən Məhsullar, Masalar, Açıq qalanlar,
Əməliyyatlar və Hesabatlar bölmələrini satıcı və müdir üçün ayrıca bloklamaq/açmaq olar.
Yanlış 6 rəqəmli admin PIN-i cəhdləri 3 səhvdən sonra 30 saniyə, sonra 60, 120 və
artan intervallarla bloklanır.

Admin bölməsindəki **setup.exe endir** düyməsi Windows masaüstü proqramının
quraşdırıcısını serverdən yükləyir. Lokal mühitdə standart fayl yolu
`desktop/release/RoBo POS Setup 1.0.0.exe`-dir. `desktop/release/` deploy-a
daxil edilmədiyi üçün Railway-də quraşdırıcını persistent volume-a yerləşdirin və
web service Variables-da `DESKTOP_INSTALLER_PATH` dəyişənini həmin faylın tam
yolu ilə təyin edin (məsələn, `/data/RoBo POS Setup 1.0.0.exe`). Fayl serverdə
tapılmadıqda endpoint yükləmə uğursuzluğunu açıq şəkildə bildirir.

`DATABASE_URL`, `SECRET_KEY` və PIN-ləri GitHub-a, README-yə və ya source fayllarına yazma. Bu dəyişənlər yalnız Railway Variables bölməsində saxlanmalıdır.

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
