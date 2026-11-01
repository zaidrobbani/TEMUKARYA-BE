# Audit dan kontrak profil sendiri

Branch: `3-feat/profiles`. Implementasi mempertahankan autentikasi Profiles
fail-closed dan tidak mengubah JWT, core, users, migration, atau tabel database.

## Audit sebelum perubahan

| Resource | Endpoint yang sudah tersedia |
| --- | --- |
| Profil UMKM | `POST /profiles/umkm` |
| Profil Freelancer | `POST /profiles/freelancer` |
| Skills Freelancer | GET dan PUT `/profiles/freelancer/skills` |
| Experiences | POST/GET koleksi, PUT/DELETE berdasarkan ID |
| Portfolio metadata | POST/GET koleksi, GET/PUT/DELETE berdasarkan ID |
| Portfolio media | Upload, daftar, file privat, cover, urutan, delete |

GET/PUT profil sendiri belum ada. Domain sudah menyediakan entity profil;
DTO, use case, dan request schema profil dasar hanya mendukung create.
Repository profil hanya menyediakan `get_by_user_id` dan `add`.
Router memakai identitas dependency, memeriksa role, dan terdaftar satu kali
di [app/main.py](../app/main.py). Tidak ada perubahan pada registrasi router.

Semua endpoint Profiles tetap memakai
[get_authenticated_profile_user](../app/modules/profiles/presentation/auth.py).
Regression test aplikasi asli memeriksa setiap method/path, registrasi tunggal,
dependency tersebut, serta 401 untuk anonymous dan forged headers. Override
identitas hanya berada dalam instance FastAPI khusus pengujian.

Inspeksi `SHOW CREATE TABLE` MySQL aktual (InnoDB, utf8mb4_unicode_ci):

| Tabel | Kolom |
| --- | --- |
| `umkm_profiles` | `user_id CHAR(36)` PK; `business_name VARCHAR(160)`, `business_category VARCHAR(100)`, `business_address VARCHAR(300)`, `city VARCHAR(100)` semuanya NOT NULL |
| `freelancer_profiles` | `user_id CHAR(36)` PK; `professional_title VARCHAR(150)`, `city VARCHAR(100)`, `availability_status VARCHAR(25)` NOT NULL; `bio TEXT`, `service_price_min BIGINT UNSIGNED`, `service_price_max BIGINT UNSIGNED` nullable |

Kedua `user_id` adalah FK ke `users.id` dengan ON DELETE CASCADE. Kedua tabel
mempunyai `created_at DATETIME(3)` default CURRENT_TIMESTAMP(3), serta
`updated_at DATETIME(3)` default CURRENT_TIMESTAMP(3) ON UPDATE
CURRENT_TIMESTAMP(3). Freelancer memiliki CHECK harga minimum <= maksimum
bila keduanya non-null. Default availability adalah `AVAILABLE`; database dan
kode belum mendefinisikan enum status. Tidak ada kolom atau constraint baru.

Temuan validasi: Create Freelancer sebelumnya membatasi harga negatif/range
di application, tetapi belum membatasi maksimum BIGINT UNSIGNED di lapisan
tersebut (HTTP schema sudah membatasi). Validator bersama sekarang menolak
overflow dan tipe harga non-integer sebelum repository, dengan regression test.
Validasi UTF-8 juga berlaku untuk field teks pendek. Ini perubahan terbatas
pada validasi profil agar create dan update konsisten dengan MySQL.

## Endpoint baru dan kontrak PUT

| Method/path | Role | Sukses |
| --- | --- | --- |
| `GET /profiles/umkm/me` | UMKM | 200, profil sendiri |
| `PUT /profiles/umkm/me` | UMKM | 200, profil setelah penggantian |
| `GET /profiles/freelancer/me` | FREELANCER | 200, profil sendiri |
| `PUT /profiles/freelancer/me` | FREELANCER | 200, profil setelah penggantian |

PUT mengganti seluruh field yang dapat diedit, bukan upsert. Seluruh field
non-null wajib dikirim. Freelancer wajib mengirim `availability_status`;
`bio`, `service_price_min`, `service_price_max` yang dihilangkan atau dikirim
null menjadi null. Bio whitespace saja dinormalisasi menjadi null. Field teks
di-trim; string wajib tidak boleh kosong. Status mengikuti batas VARCHAR(25),
tanpa mengarang enum baru. Harga JSON harus integer 0..18446744073709551615.
Bio dibatasi 65535 byte UTF-8 setelah trim, bukan 65535 karakter.

Contoh body UMKM:

```json
{
  "business_name": "Kopi Malang",
  "business_category": "Food & Beverage",
  "business_address": "Jl. Soekarno Hatta",
  "city": "Malang"
}
```

Contoh body Freelancer:

```json
{
  "professional_title": "UI/UX Designer",
  "city": "Malang",
  "bio": "Desainer aplikasi mobile",
  "service_price_min": 150000,
  "service_price_max": 1000000,
  "availability_status": "AVAILABLE"
}
```

Response GET/PUT memakai schema profil yang sudah ada: field tersebut ditambah
`user_id` dari autentikasi, tanpa tanggal audit. Tidak ada endpoint ID pengguna
yang dapat dipilih klien. Query/header identitas tidak menentukan pemilik.
Body PUT melarang field ekstra, termasuk `id`, `user_id`, `role`, ownership,
`created_at` dan `updated_at`.

- 401: belum terautentikasi. Saat ini seluruh request aplikasi asli tetap 401
  karena JWT belum terintegrasi, termasuk Bearer token palsu.
- 403: role tidak cocok, setelah dependency autentikasi kelak terintegrasi.
- 404: profil pengguna login tidak ditemukan; tidak membuat profil otomatis.
- 422: body tidak sesuai schema, field wajib hilang/null, field ekstra,
  tipe/panjang/nilai numerik di luar batas.
- 400: validasi application seperti teks whitespace, bio melebihi kapasitas
  byte, UTF-8 tidak valid, atau rentang harga terbalik. Mengikuti error handler
  proyek yang sudah ada.

## Arsitektur dan transaksi

Presentation memeriksa role dan membangun DTO tanpa identitas. Application
menerima user_id dari dependency, memvalidasi, dan memanggil repository.
Repository menjalankan UPDATE dengan WHERE user_id dan daftar field eksplisit,
tanpa menyentuh key/timestamp. Update yang tidak menemukan baris menghasilkan
404, termasuk bila profil hilang setelah pemeriksaan awal. GET tidak commit;
PUT commit melalui UnitOfWork. Exception database diteruskan; lifecycle session
yang sudah ada melakukan rollback saat session ditutup tanpa commit.

Validasi create dan PUT memakai fungsi bersama. GET/PUT memakai entity dan
response schema lama. Tidak menambah dependency eksternal atau konfigurasi.
PUT bersifat idempotent untuk data; update identik tetap 200 (matched-row
semantics SQLAlchemy/MySQL). Perubahan timestamp diserahkan kepada MySQL.

## Pengujian

- Unit: get/update, normalisasi, semua batas kolom, rentang harga, kapasitas byte,
  profil hilang/terhapus bersamaan, kegagalan update/commit, overflow pada create.
- Repository SQLite terisolasi: pembatasan pemilik, tidak upsert, no-op update,
  identity map, nullable fields, rollback, serta pengguna lain tidak berubah.
- HTTP: get/put sukses, 403/404/400/422, field terlarang, required fields,
  manipulasi query/header, nullable replacement. Test aplikasi asli yang sudah
  ada otomatis mencakup empat endpoint baru untuk 401 dan registrasi tunggal.
- MySQL opt-in: akun UUID acak untuk UMKM/Freelancer, create/read/update melalui
  use case dan repository asli, batas UTF-8/uint64, timestamp server, no-op
  update, missing owner dan isolasi pengguna. UoW test hanya flush. Event guard
  menolak commit session/connection. Outer transaction di-rollback; koneksi baru
  memverifikasi nol users/umkm_profiles/freelancer_profiles uji tersisa.
- Integration dibatasi konfigurasi Docker lokal development/test, host `db`,
  port 3306, database `temukarya`/`temukarya_test`, dan tabel InnoDB. Tidak ada DDL.

Jalankan:

```sh
docker compose exec -T api python -m pytest -q
docker compose exec -T -e TEMUKARYA_MYSQL_INTEGRATION=1 api python -m pytest -q
```

Hasil verifikasi implementasi:

| Konfigurasi | Hasil |
| --- | --- |
| Suite default | **468 passed, 4 skipped**, 1 warning, 27.47 detik |
| Suite dengan MySQL integration aktif | **472 passed**, 1 warning, 29.10 detik |

Empat skip pada mode default adalah integration tests opt-in. Dua pengujian
MySQL profil sendiri juga dijalankan terarah: **2 passed**, dengan keluaran
verifikasi rollback `users=0`, `umkm_profiles=0`, `freelancer_profiles=0`
untuk masing-masing transaksi. Seluruh pengujian lama dipertahankan.

## File dalam perubahan ini

Diubah:

- [domain/repositories.py](../app/modules/profiles/domain/repositories.py)
- [application/dto.py](../app/modules/profiles/application/dto.py)
- [application/use_cases.py](../app/modules/profiles/application/use_cases.py)
- [infrastructure/repositories.py](../app/modules/profiles/infrastructure/repositories.py)
- [presentation/schemas.py](../app/modules/profiles/presentation/schemas.py)
- [presentation/dependencies.py](../app/modules/profiles/presentation/dependencies.py)
- [presentation/router.py](../app/modules/profiles/presentation/router.py)
- [tests/conftest.py](../tests/modules/profiles/conftest.py)

Ditambahkan:

- [application/profile_validation.py](../app/modules/profiles/application/profile_validation.py)
- [application/self_profile_use_cases.py](../app/modules/profiles/application/self_profile_use_cases.py)
- [test_self_profile_use_cases.py](../tests/modules/profiles/test_self_profile_use_cases.py)
- [test_self_profile_repository.py](../tests/modules/profiles/test_self_profile_repository.py)
- [test_self_profile_router.py](../tests/modules/profiles/test_self_profile_router.py)
- [test_self_profile_mysql_integration.py](../tests/modules/profiles/test_self_profile_mysql_integration.py)
- Dokumen ini.

Perubahan Docker, requirements, registrasi router, dan Portfolio Media yang
sudah ada di working tree berasal dari pekerjaan sebelumnya.

## Dependensi dan risiko tersisa

- Integrasi JWT Zaid tetap diperlukan. Setelah tersedia, uji end-to-end token
  sah/kedaluwarsa/palsu, role, UUID user, dan akses lintas pengguna dengan token
  nyata. Jangan membuka auth stub sebelum integrasi siap.
- Nilai bisnis availability belum memiliki enum resmi. Sepakati kontraknya
  dengan frontend sebelum memberlakukan daftar status terbatas.
- Update bersamaan mengikuti last-write-wins; belum ada version/ETag. Bila
  dibutuhkan deteksi lost update, desain terpisah diperlukan.
- Users ORM masih memakai ID integer sementara MySQL aktual memakai CHAR(36).
  Tidak diubah karena milik tim lain. Seed integration memakai SQL parameterized
  dengan UUID. Koordinasikan konsistensi ID saat integrasi Auth/users.
- Satu warning deprecation Starlette/AnyIO berasal dari stack test lama;
  pembaruan dependency di luar cakupan.
