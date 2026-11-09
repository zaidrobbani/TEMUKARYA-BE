# Kontrak API: Autentikasi

Base URL lokal: `http://localhost:8000/api/v1`. Semua path di dokumen ini relatif terhadap base URL tersebut
(contoh `POST /auth/login` = `POST http://localhost:8000/api/v1/auth/login`). Swagger: `http://localhost:8000/docs`.
Konvensi umum seluruh modul: [`README.md`](README.md).

## Format response

Semua endpoint (termasuk error) memakai envelope yang sama.

Sukses:
```json
{ "success": true, "message": "Login berhasil", "data": { ... } }
```

Error:
```json
{ "success": false, "message": "Email atau kata sandi salah", "data": null }
```

Error validasi (422) menambahkan `errors` per field:
```json
{
  "success": false,
  "message": "Data yang dikirim tidak valid",
  "data": null,
  "errors": [
    { "field": "email", "message": "Format email tidak valid (harus mengandung domain lengkap)" },
    { "field": "password_confirmation", "message": "Konfirmasi kata sandi tidak sama dengan kata sandi" }
  ]
}
```

Error yang perlu dibedakan client tanpa mencocokkan pesan menambahkan `code`. Saat ini hanya `EMAIL_NOT_VERIFIED` (lihat `POST /auth/login`).

Aturan umum:
- Waktu selalu UTC ISO-8601 dengan akhiran `Z` (`2026-11-02T01:42:19.441Z`); Android konversi ke WIB.
- Endpoint yang butuh login memakai header `Authorization: Bearer <access_token>`.
- Nilai enum huruf besar (`UMKM`, `FREELANCER`, `ADMIN`). Daftar lengkap ada di `GET /enums`.

## Objek `User`

```json
{
  "id": "8ef5536f-8bfb-4811-aa94-ab2b5506aa72",
  "name": "Rina Pratiwi",
  "email": "rina.pratiwi@kulinerbandung.id",
  "phone_number": "+6281234567890",
  "role": "UMKM",
  "profile_image_url": null,
  "email_verified_at": "2026-11-02T01:50:00.000Z",
  "created_at": "2026-11-02T01:42:19.441Z"
}
```

`email_verified_at` bernilai `null` selama email belum diverifikasi.

## Pemetaan layar Figma (section "1 · Auth")

| Layar | Endpoint |
|---|---|
| Pilih Peran | `GET /enums/registration_roles` |
| Registrasi (UMKM & Freelancer) | `POST /auth/register` |
| Login, tombol Masuk | `POST /auth/login` |
| Login, tombol Akun Google | `POST /auth/google` |
| Lupa Password, Kirim Tautan Reset | `POST /auth/password/forgot` |
| Tautan Reset Terkirim, kirim ulang setelah 00:59 | `POST /auth/password/forgot` lagi |
| Profil, Keluar ("Akhiri sesi di perangkat ini") | `POST /auth/logout` |

---

## POST `/auth/register`

Request:
```json
{
  "name": "Rina Pratiwi",
  "email": "rina.pratiwi@kulinerbandung.id",
  "phone_number": "0812-3456-7890",
  "password": "KaryaHebat2024",
  "password_confirmation": "KaryaHebat2024",
  "role": "UMKM",
  "terms_accepted": true
}
```

| Field | Aturan |
|---|---|
| `name` | wajib, 1–100 karakter setelah spasi depan/belakang dibuang |
| `email` | wajib, maks 255, harus `x@domain.tld`; disimpan huruf kecil tanpa spasi |
| `phone_number` | wajib, nomor HP Indonesia. Boleh `08…`, `8…`, `62…`, `+62…`, `+6208…` (prefix `+62` di Figma + `0812…`), dengan spasi/strip/titik. Disimpan sebagai `+628…` |
| `password` | wajib, 8–128 karakter |
| `password_confirmation` | wajib, harus sama dengan `password` |
| `role` | wajib, `UMKM` atau `FREELANCER` (ambil dari `GET /enums/registration_roles`) |
| `terms_accepted` | wajib `true` (checkbox Syarat & Ketentuan). Waktu persetujuan disimpan di `users.terms_accepted_at` |

Sukses `201`: `message` = `"Registrasi berhasil, silakan cek email untuk verifikasi"`, `data` = objek `User` dengan `email_verified_at: null`. Response ini tidak menyertakan token. Tautan verifikasi dikirim ke email setelah response; kalau pengiriman gagal, registrasi tetap sukses dan user bisa memakai `POST /auth/email/resend`.

| Kode | Kapan | `message` |
|---|---|---|
| 422 | Field kosong / tidak dikirim | `errors[].message` = `Wajib diisi` |
| 422 | Nama > 100 karakter | `Maksimal 100 karakter` |
| 422 | Email salah format | `Format email tidak valid (harus mengandung domain lengkap)` |
| 422 | Nomor bukan HP Indonesia (mis. `021…`, `12345`, ada huruf) | `Nomor WhatsApp tidak valid, contoh: 081234567890` |
| 422 | Password < 8 / > 128 | `Minimal 8 karakter` / `Maksimal 128 karakter` |
| 422 | Konfirmasi beda | `Konfirmasi kata sandi tidak sama dengan kata sandi` |
| 422 | Role bukan nilai enum (termasuk huruf kecil `umkm`) | `Pilihan tidak valid, gunakan salah satu dari ...` |
| 422 | `terms_accepted` = `false` | `Syarat & Ketentuan Layanan wajib disetujui` |
| 422 | `terms_accepted` bukan boolean | `Harus berupa true atau false` |
| 422 | Tipe salah (mis. `name: 123`) | `Harus berupa teks` |
| 422 | Body bukan JSON valid | field `body`: `Format JSON tidak valid` |
| 403 | `role` = `ADMIN` | `Akun admin tidak dapat dibuat melalui registrasi` |
| 409 | Email sudah terdaftar (tidak peka huruf besar/kecil) | `Email <email> sudah terdaftar` |

Registrasi bersamaan dengan email yang sama tetap aman: satu request `201`, sisanya `409` (dijaga oleh `UNIQUE(email)` di DB).

## POST `/auth/login`

Untuk aplikasi Android (UMKM & Freelancer).

Request:
```json
{ "email": "rina.pratiwi@kulinerbandung.id", "password": "KaryaHebat2024" }
```

Sukses `200`:
```json
{
  "success": true,
  "message": "Login berhasil",
  "data": {
    "access_token": "eyJhbGciOi...",
    "token_type": "Bearer",
    "expires_at": "2026-11-03T01:42:19.000Z",
    "user": { "...": "objek User" }
  }
}
```
Android menentukan halaman utama dari `data.user.role`.

| Kode | Kapan | `message` |
|---|---|---|
| 422 | Email/password kosong, email salah format | per field (lihat register) |
| 401 | Email tidak terdaftar **atau** password salah (pesan sengaja sama) | `Email atau kata sandi salah` |
| 403 | Akun ADMIN mencoba login lewat aplikasi | `Akun admin hanya dapat login melalui dashboard admin` |
| 403 + `code: EMAIL_NOT_VERIFIED` | Email & sandi benar, tetapi email belum diverifikasi | `Email belum diverifikasi, silakan cek email kamu` |

Pada `EMAIL_NOT_VERIFIED`, Android menawarkan kirim ulang lewat `POST /auth/email/resend`.
Status verifikasi hanya terlihat kalau sandi benar, jadi tidak membocorkan apa pun ke orang yang tidak tahu sandinya.

## POST `/auth/google`

Android mengambil ID token dari Google Sign-In (memakai Web client ID yang sama dengan `GOOGLE_CLIENT_ID` di backend), lalu mengirimnya ke sini. Hanya untuk akun yang **sudah terdaftar**.

Request:
```json
{ "id_token": "eyJhbGciOiJSUzI1NiIs..." }
```

Sukses `200`: sama dengan `/auth/login`. Akun yang belum terverifikasi otomatis jadi terverifikasi, dan sandi lamanya diganti (lihat Keputusan #20).

| Kode | Kapan | `message` |
|---|---|---|
| 422 | `id_token` kosong | `Wajib diisi` |
| 401 | Token palsu, kedaluwarsa, atau untuk aplikasi lain | `Token Google tidak valid, silakan coba masuk kembali` |
| 403 | Email di akun Google belum terverifikasi oleh Google | `Email akun Google ini belum terverifikasi` |
| 403 | Akun ADMIN | `Akun admin hanya dapat login melalui dashboard admin` |
| 404 | Email Google belum terdaftar. Android arahkan ke Pilih Peran | `Akun Google ini belum terdaftar, silakan daftar terlebih dahulu` |
| 503 | `GOOGLE_CLIENT_ID` kosong, atau public key Google tidak bisa diambil | `Login Google sedang tidak tersedia, silakan masuk dengan email` |

## Verifikasi email

Alur: register → email berisi tautan `{PUBLIC_BASE_URL}/api/v1/auth/email/verify?token=...` → user membuka tautan di browser dan menekan tombol **Verifikasi Email** → login. Tautan berlaku 24 jam.

### POST `/auth/email/verify`

Dipanggil oleh halaman tautan, atau oleh Android kalau nanti memakai deep link.

Request: `{ "token": "..." }`. Sukses `200`: `message` = `"Email berhasil diverifikasi, silakan login"`, `data` = `null`.

| Kode | Kapan | `message` |
|---|---|---|
| 200 | Akun sudah terverifikasi (tautan dibuka dua kali) | `Email berhasil diverifikasi, silakan login` |
| 400 | Token tidak dikenal, atau tautan lama yang sudah diganti tautan baru | `Tautan verifikasi tidak valid atau sudah digunakan` |
| 400 | Lewat 24 jam | `Tautan verifikasi sudah kedaluwarsa, silakan minta tautan baru` |
| 422 | Token kosong / > 512 karakter | per field |

### POST `/auth/email/resend`

Request: `{ "email": "..." }`. Selalu `200` dengan `message` = `"Jika email perlu diverifikasi, tautan baru sudah dikirim"`, supaya status akun tidak bisa ditebak. Email hanya benar-benar dikirim kalau akun ada, belum terverifikasi, dan sudah lewat 60 detik dari kiriman terakhir. Tautan lama langsung tidak berlaku.

| Kode | Kapan | `message` |
|---|---|---|
| 422 | Email kosong / salah format | per field |

## Lupa password

Alur: layar Lupa Password → layar Tautan Reset Terkirim → email berisi tautan `{PUBLIC_BASE_URL}/api/v1/auth/password/reset?token=...` → user mengisi sandi baru di halaman web → login. Tautan berlaku 30 menit dan hanya bisa dipakai sekali (sesuai Figma).

### POST `/auth/password/forgot`

Request: `{ "email": "..." }`. Selalu `200` dengan `message` = `"Jika email terdaftar, tautan reset sudah dikirim"`, juga untuk email yang tidak terdaftar. Timer "Kirim ulang dalam 00:59" dijalankan di Android; di server, permintaan dalam 60 detik diabaikan tanpa error dan tautan sebelumnya tetap berlaku.

| Kode | Kapan | `message` |
|---|---|---|
| 422 | Email kosong / salah format | per field |

### POST `/auth/password/reset`

Dipanggil oleh halaman tautan, atau oleh Android kalau nanti memakai deep link.

Request:
```json
{ "token": "...", "password": "SandiBaru2024", "password_confirmation": "SandiBaru2024" }
```

Sukses `200`: `message` = `"Kata sandi berhasil diubah, silakan login"`, `data` = `null`. Semua sesi lama di semua perangkat langsung berakhir. Kalau email belum terverifikasi, otomatis jadi terverifikasi.

| Kode | Kapan | `message` |
|---|---|---|
| 400 | Token tidak dikenal, sudah dipakai, atau sudah diganti tautan baru | `Tautan reset tidak valid atau sudah digunakan` |
| 400 | Lewat 30 menit | `Tautan reset sudah kedaluwarsa, silakan minta tautan baru` |
| 422 | Sandi < 8 / > 128, konfirmasi beda, field kosong. Tautan **tidak** hangus | per field |

## POST `/auth/admin/login`

Untuk dashboard admin (web). Request dan response sama dengan `/auth/login`, `message` = `"Login admin berhasil"`.

| Kode | Kapan | `message` |
|---|---|---|
| 422 | Validasi | per field |
| 401 | Email/password salah | `Email atau kata sandi salah` |
| 403 | Akun UMKM/Freelancer | `Akun ini tidak memiliki akses ke dashboard admin` |

Akun admin dibuat lewat CLI:
```bash
docker compose exec api python -m app.scripts.create_admin --name "Admin" --email admin@temukarya.id
```

## GET `/auth/me`

Butuh token. Sukses `200`: `message` = `"Data akun berhasil diambil"`, `data` = objek `User`.

## POST `/auth/logout`

Butuh token. Sukses `200`: `{"success": true, "message": "Logout berhasil", "data": null}`.
Token yang dipakai langsung tidak berlaku lagi di server. Sesi di perangkat lain (token lain) tetap aktif.

## GET `/users/{user_id}`

Butuh token. User biasa hanya boleh membaca datanya sendiri; ADMIN boleh membaca user mana pun.

| Kode | Kapan | `message` |
|---|---|---|
| 403 | UMKM/Freelancer membaca user lain (id ada atau tidak) | `Anda tidak memiliki akses ke data user ini` |
| 404 | ADMIN meminta id yang tidak ada | `User <id> tidak ditemukan` |

## Error token (berlaku untuk semua endpoint yang butuh login)

| Kode | Kapan | `message` |
|---|---|---|
| 401 | Header `Authorization` tidak ada, kosong, atau bukan skema `Bearer` | `Silakan login terlebih dahulu` |
| 401 | Token rusak, signature salah, klaim kurang, `alg: none` | `Token tidak valid, silakan login kembali` |
| 401 | Token kedaluwarsa (default 24 jam) | `Sesi sudah kedaluwarsa, silakan login kembali` |
| 401 | Token sudah di-logout | `Sesi sudah berakhir karena logout, silakan login kembali` |
| 401 | Token dibuat sebelum kata sandi direset | `Kata sandi telah diubah, silakan login kembali` |
| 401 | Akun pemilik token sudah dihapus | `Akun tidak ditemukan, silakan login kembali` |
| 403 | Role tidak diizinkan untuk endpoint (`require_roles`) | `Anda tidak memiliki akses ke fitur ini` |

Semua 401 berarti Android harus menghapus token dan kembali ke halaman login.

## Enum

| Endpoint | Isi |
|---|---|
| `GET /enums` | Semua enum: `{ "user_roles": [...], "registration_roles": [...] }` |
| `GET /enums/user_roles` | `UMKM` (Pemilik UMKM), `FREELANCER` (Freelancer Digital), `ADMIN` (Admin) |
| `GET /enums/registration_roles` | `UMKM`, `FREELANCER` (pilihan di layar Pilih Peran) |

Item enum: `{ "value": "UMKM", "label": "Pemilik UMKM" }`. Nama enum yang tidak ada → `404` `Enum <nama> tidak ditemukan`.

## Error umum

| Kode | Kapan | `message` |
|---|---|---|
| 404 | Endpoint tidak ada | `Endpoint tidak ditemukan` |
| 405 | Method salah (mis. `GET /auth/login`) | `Metode HTTP tidak diizinkan untuk endpoint ini` |
| 500 | Error tak terduga | `Terjadi kesalahan pada server, silakan coba lagi` |

## Konfigurasi email & Google

| Env | Default | Keterangan |
|---|---|---|
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Awal tautan di email. Untuk tes dari HP, isi dengan IP laptop |
| `SMTP_HOST`, `SMTP_PORT` | `mailpit`, `1025` (Docker Compose) | Saat development, email ditangkap Mailpit dan dibaca di http://localhost:8025 |
| `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS` | kosong, `false` | Isi kalau memakai SMTP sungguhan |
| `EMAIL_FROM` | `TEMUKARYA <no-reply@temukarya.id>` | Pengirim |
| `GOOGLE_CLIENT_ID` | kosong | Web client ID Google. Kosong berarti `/auth/google` menjawab 503 |

---

## Keputusan yang perlu dicek (beda / tidak diatur di PRD & Figma)

| # | Hal | Implementasi sekarang | Sumber |
|---|---|---|---|
| 1 | Nilai role | Diganti huruf besar `UMKM`/`FREELANCER`/`ADMIN` (sebelumnya huruf kecil), mengikuti konvensi enum proyek. Data lama di-upgrade lewat migrasi | Konvensi CLAUDE.md |
| 2 | Endpoint register | Pindah dari `POST /users` ke `POST /auth/register` | — |
| 3 | Register tidak memberi token | User harus verifikasi email lalu login. Figma tidak menunjukkan layar sesudah "Daftar Sekarang" | PRD TK-F-G-01/02 |
| 4 | Login Google hanya untuk akun terdaftar | Email baru mendapat 404 dan diarahkan ke Pilih Peran, karena akun baru butuh role dan nomor WhatsApp, dan tombol Google hanya ada di layar Login | Figma Login, tidak ada di PRD |
| 5 | Lupa password | Mengikuti Figma: tautan 30 menit, kirim ulang 60 detik. Figma tidak punya layar buat sandi baru, jadi dibuat halaman web sederhana dari backend | Figma Lupa Password, tidak ada di PRD |
| 6 | Checkbox Syarat & Ketentuan | Wajib `terms_accepted: true`, waktu persetujuan disimpan di kolom baru `users.terms_accepted_at`. **Field baru: Android wajib mengirimnya** | Figma Registrasi |
| 7 | Nomor WhatsApp | Wajib, hanya nomor HP Indonesia | Figma Registrasi (PRD hanya "data akun yang diperlukan") |
| 8 | Aturan password | Minimal 8 karakter, tanpa syarat huruf besar/angka/simbol | Tidak diatur PRD |
| 9 | Admin | Tidak bisa login di aplikasi (403), punya endpoint sendiri, dibuat lewat CLI | PRD TK-F-A-01 |
| 10 | Logout | Token dicabut di server lewat tabel baru `revoked_tokens` (tabel ke-29, belum ada di ERD) | PRD TK-F-U-27, TK-F-F-26, TK-F-A-12 |
| 11 | Masa berlaku token | 24 jam, tanpa refresh token, jadi user login ulang tiap hari. Bisa dinaikkan lewat `JWT_EXPIRE_MINUTES` | Tidak diatur PRD |
| 12 | `GET /users/{id}` | Sekarang wajib login dan hanya untuk diri sendiri/admin, karena memuat email & nomor HP. Profil publik freelancer/UMKM ada di modul profiles | TK-NF-06 |
| 13 | Brute force login | Belum ada rate limit | TK-NF-06 |
| 14 | Akun nonaktif/diblokir | Belum ada (tidak ada kolom status di `users`) | — |
| 15 | Pesan email duplikat | Memberi tahu bahwa email sudah terdaftar (perlu untuk UX register) | — |
| 16 | Pembersihan `revoked_tokens` & `auth_action_tokens` | Baris kedaluwarsa belum dihapus otomatis | — |
| 17 | Verifikasi email wajib sebelum login | Permintaan langsung dari Zaid. **Figma dan PRD tidak punya layar atau aturannya**: chip "UMKM Terverifikasi" di Figma adalah label profil, bukan status email. Layar sesudah register perlu dibuat di Android, bisa memakai ulang layout "Cek email kamu" | Keputusan backend |
| 18 | Masa berlaku tautan verifikasi | 24 jam, kirim ulang 60 detik (disamakan dengan reset) | Tidak diatur |
| 19 | Tautan berbentuk halaman web, bukan deep link Android | Jalan di browser HP tanpa pekerjaan tambahan di Android. Aksi baru jalan setelah tombol ditekan, agar pemindai tautan email tidak memakai token. Android bisa mengambil alih URL yang sama lewat App Links | Keputusan backend |
| 20 | Google pada akun belum terverifikasi | Sandi lama diganti acak. Sandi itu bisa saja dibuat orang lain yang mendaftar memakai email tersebut. Pemilik yang lupa bisa memakai Lupa Password | Keamanan |
| 21 | Akun lama saat migrasi | Dianggap terverifikasi (`email_verified_at = created_at`) agar tidak terkunci. Admin dari CLI juga langsung terverifikasi | Migrasi `a1d4e7c29b63` |
| 22 | Reset mengakhiri semua sesi | Lewat kolom baru `users.password_changed_at`, dibandingkan dengan `iat` token. Berbeda dari logout yang hanya mengakhiri satu perangkat | Keamanan |
| 23 | Field `code` di response error | Tambahan dari kontrak envelope, hanya muncul kalau ada. Dipakai Android untuk membedakan dua jenis 403 di login | Keputusan backend |
| 24 | Istilah pesan | Pesan error memakai "kata sandi" mengikuti label Figma, dan pesan format email mengikuti teks layar Login. **Pesan berubah dari versi sebelumnya** | Figma |
| 25 | `sub` Google tidak disimpan | Akun dicocokkan lewat email saja, tidak perlu kolom baru | Keputusan backend |
| 26 | Ubah kata sandi saat login | **Belum dibuat.** Ada menu "Keamanan & Kata Sandi" di layar Profil, di luar section Auth | Figma Profil |
| 27 | Email sungguhan | Belum ada SMTP produksi. Domain pengirim `temukarya.id` hanya contoh | — |
| 28 | Email hanya teks polos, tanpa HTML dan tombol | Saat diuji lewat Gmail SMTP ke akun `student.ub.ac.id`, email teks + HTML dijawab `250 OK` tetapi tidak terlihat di mailbox, sedangkan teks polos sampai. Penyebab pastinya belum diketahui, email teks + HTML bisa jadi masuk Spam. Tautan `localhost` bisa saja tidak otomatis bisa diklik, jadi salin ke browser kalau perlu | Hasil uji 2026-11-04 |
