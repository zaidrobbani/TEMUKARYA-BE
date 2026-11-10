# CONTEXT PROYEK BACKEND TEMUKARYA

REST API untuk aplikasi Android TEMUKARYA: marketplace jasa yang mempertemukan UMKM dengan freelancer digital.
Proyek tim (4 orang), kelas Pengembangan Aplikasi Perangkat Bergerak. Admin dashboard berupa web terpisah.

## Cara kerja dengan user (PENTING)

- Sejak 2026-11-02 Claude **langsung mengerjakan kode** di repo, **satu fitur sampai tuntas** per sesi/PR
  (tidak lagi memandu user mengetik manual). Deadline padat: jangan banyak tanya, ambil keputusan wajar lalu laporkan.
- Setiap fitur wajib: semua skenario error ditangani + dites (use case dengan fake repo, dan HTTP via `TestClient`),
  plus dokumen kontrak di `docs/api/<fitur>.md` berisi request/response, tabel status code + pesan per skenario error,
  dan tabel **"Keputusan yang perlu dicek"** untuk hal yang beda/tidak diatur di PRD atau Figma, supaya user bisa review.
- Kode rapi, komentar minim: Indonesia, singkat, hanya untuk "kenapa" yang tidak jelas dari kode.
- Bahasa percakapan: Indonesia.

## Sumber kebenaran

- **PRD / Project Blueprint** (Google Docs): https://docs.google.com/document/d/1I6QYim1_ckMlTXCV6_pVzhk6SUS_ZGC6mlhAnklUonI
  Tab "2. Analisis Sistem" lebih baru dan lebih detail daripada tab "1. Blueprint"; kalau bertentangan, ikuti Analisis Sistem.
- **Figma UI**: https://www.figma.com/design/5iVDEAnceSXwLeTePb5Nv1/PAPB-UI-UX
- **ERD** (ERDPlus, 26 entitas) + **dokumen Audit ERD / Data Dictionary**: acuan nama tabel, kolom, tipe, constraint.
  Model SQLAlchemy mengikuti audit; DDL final di-generate dari migrasi (`alembic upgrade head --sql`), tidak ditulis manual.

## Pembagian tanggung jawab (4 fungsi inti)

| Fungsi | PIC |
|---|---|
| F1. Matching proyek–freelancer (rekomendasi skill, threshold 60%) | Faruqi |
| F2. Validasi alur proyek & revisi (state machine status) | Taqiya |
| F3. Simulasi pembayaran & pengelolaan dana (komisi, HELD/RELEASED, idempotensi) | **Zaid (user)** |
| F4. Progres milestone & risiko keterlambatan | Putri |

Zaid juga memegang setup arsitektur backend & Docker.

## Stack & arsitektur

FastAPI, MySQL 8.4, SQLAlchemy 2.0, Alembic, Pydantic v2, pytest, Docker Compose. Detail perintah ada di `README.md`.

Clean Architecture per modul di `app/modules/<modul>/`:

```
domain/          entity (dataclass), repository interface (ABC), exception domain
application/     use case (terima interface lewat constructor) + DTO input
infrastructure/  model SQLAlchemy + implementasi repository
presentation/    router, schema Pydantic, dependencies.py (composition root)
```

Aturan:
- `domain` & `application` tidak boleh import FastAPI, SQLAlchemy, atau Pydantic.
- Use case yang mengubah data wajib `uow.commit()`; tanpa itu perubahan di-rollback.
- Error bisnis = subclass `AppError` (`app/core/exceptions.py`), dipetakan ke HTTP di `error_handlers.py`. Jangan raise `HTTPException` dari use case.
- Model baru wajib di-import di `alembic/env.py` agar terdeteksi autogenerate; router baru didaftarkan di `app/main.py`.
- Swagger `/docs` dikelompokkan per role (Umum / UMKM / Freelancer / Admin) di `app/openapi.py`: endpoint baru wajib ditambahkan ke `GROUPS` (dicek `tests/api/test_openapi_groups.py`).
- Test use case di `tests/modules/<modul>/` memakai fake repository in-memory (tanpa DB). Contoh: `tests/modules/users/test_use_cases.py`.
- Modul `users` + `auth` adalah contoh pola yang harus ditiru. Fake repository bersama ada di `tests/fakes.py`;
  contoh test HTTP: `tests/api/test_auth_api.py`.

Kontrak API (untuk Android & admin web):
- Semua router di-mount di prefix `/api/v1` (`API_PREFIX` di `app/core/config.py`, dirakit di `app/main.py`). Router modul tetap memakai path relatif (`/projects`), jangan tulis prefix di modul. Konvensi umum + daftar endpoint: `docs/api/README.md`.
- `DELETE` menjawab `200` + `data: null`. Error bisnis `400`, `422` hanya untuk validasi field (`errors[]`).
- Pembanding role selalu pakai `UserRole` (nilai huruf besar), jangan literal `"umkm"`/`"freelancer"`.
- Semua response memakai envelope `{"success": bool, "message": str, "data": ...}`. Sukses: router `return success_response("...", data)`
  dengan `response_model=ApiResponse[Schema]` dan `responses=error_responses(...)` (`app/core/responses.py`).
- Error: `{"success": false, "message": ..., "data": null}`; khusus 422 ditambah `errors: [{field, message}]` dengan pesan Indonesia. Error yang perlu dibedakan client boleh menambah `code` (atribut `code` di subclass `AppError`).
  Handler ada di `app/core/error_handlers.py` (AppError, validasi, 404/405, 500).
- Datetime di response pakai tipe `UtcDateTime` (ISO UTC berakhiran `Z`).
- Setiap enum yang dipakai client didaftarkan di `app/modules/enums/registry.py` (`{value, label}`), otomatis tersedia di `GET /enums` dan `GET /enums/{nama}`.
- Endpoint yang butuh login: `Depends(get_current_user)` atau `Depends(require_roles(UserRole.X))` dari `app/modules/auth/presentation/dependencies.py`.

## Konvensi data

- Nama tabel huruf kecil, jamak, snake_case, bahasa Inggris (`projects`, `project_applications`).
- Uang: integer rupiah bulat (`BIGINT`), **jangan float**. Komisi = `floor(nilai * 5 / 100)`, hak freelancer = nilai − komisi.
- Status/enum: `VARCHAR` + `StrEnum` di Python (bukan ENUM MySQL), nilai huruf besar (`TERBUKA`, `HELD`).
- Skill: master 26 skill dengan kode tetap dari PRD (`logo_design`, `web_programming`, ...), dipakai bersama oleh freelancer & project lewat tabel junction `freelancer_skills` / `project_skills`.
- FK data keuangan/riwayat: `ON DELETE RESTRICT`, jangan CASCADE.
- Integritas penting dijaga dengan constraint DB, bukan hanya cek di Python (contoh: `UNIQUE(project_id, freelancer_id)` lamaran, `UNIQUE(project_id)` agreement, `UNIQUE(agreement_id)` payment).

## Aturan bisnis inti (ringkas)

Status project (dikendalikan backend, tidak bisa diset bebas oleh client):
`TERBUKA → MENUNGGU_KESEPAKATAN → MENUNGGU_PEMBAYARAN → SIAP_DIKERJAKAN → SEDANG_DIKERJAKAN → MENUNGGU_REVIEW ⇄ REVISI → SELESAI`, plus `DIBATALKAN` (hanya sebelum pembayaran berhasil).
Status lamaran, kesepakatan, pembayaran, dana, dan milestone adalah state machine terpisah dari status project.

F3 (pembayaran, simulasi, tanpa uang sungguhan):
- Satu project = satu tagihan. Status pembayaran: `MENUNGGU | BERHASIL | GAGAL | DIBATALKAN`. Status dana: `NULL → HELD → RELEASED`.
- Bayar berhasil → dana HELD + project SIAP_DIKERJAKAN dalam **satu transaksi DB**.
- UMKM setujui hasil → project SELESAI + dana RELEASED dalam satu transaksi. Request berulang tidak boleh melepas dana dua kali.
- Nominal diambil dari data kesepakatan di backend; Android tidak mengirim nilai komisi/hak freelancer.
- Pencairan dana ke rekening **di luar scope MVP**.

F4: total bobot milestone harus 100; progres dihitung dari milestone SELESAI (tidak diinput manual); progres 100% tidak otomatis membuat project SELESAI.

## Status pengerjaan

- [x] Fondasi: Docker, MySQL, Alembic, core (config, database, UoW, exceptions, PasswordHasher scrypt), modul `users` (register + get).
- [x] Migrasi skema lengkap 28 tabel + seed skills & kategori (diuji upgrade/downgrade di DB terpisah).
- [x] Modul `users` memakai UUID.
- [x] Fitur auth (branch `3-feat/auth-jwt`): register, login app, login admin, `/auth/me`, logout (revoke token di tabel `revoked_tokens`),
  `get_current_user`, `require_roles`, role `ADMIN` (dibuat via `python -m app.scripts.create_admin`), envelope response, error handler,
  endpoint enum. Kontrak + skenario error: `docs/api/auth.md`. Menunggu review user atas tabel "Keputusan yang perlu dicek".
- [x] Auth disamakan dengan Figma (2026-11-04): verifikasi email wajib sebelum login, lupa password via tautan, login Google (akun terdaftar saja),
  `terms_accepted`, tabel `auth_action_tokens`, port `EmailSender` (SMTP + Mailpit di Compose) dan `GoogleTokenVerifier`. Android belum menyesuaikan field & alur baru.
- [x] Integrasi 10 PR ke `dev` (2026-11-09, branch `20-chore/integrate-prs`): skills, profiles, projects, applications, discovery,
  matching, milestones (baca), chat, admin statistik. Auth stub diganti JWT asli, semua response envelope, prefix `/api/v1`.
  Keputusan integrasi: tabel di `docs/api/README.md`.
- [x] Fitur Zaid (2026-11-10, branch `21-feat/workflow-payments`, migrasi `workflow_payment_details`): workflow F2 (pilih freelancer,
  kesepakatan, Lanjut/Minta Ubah, batal, mulai, riwayat status, `GET /workflow/projects`), payments F3 (tagihan, simulasi QRIS + idempotensi,
  dana HELD/RELEASED, wallet, riwayat transaksi), submissions + revisi + approve (pelepasan dana), reviews, notifications (kontrak `Notifier.notify`),
  admin keuangan, endpoint tulis milestone + kontrak `reset_approvals`. Kontrak: `docs/api/{workflow,payments,submissions,notifications,admin-finance}.md`.
  Menunggu review user atas tabel "Keputusan yang perlu dicek" di dokumen tersebut.
- [ ] Di luar scope (keputusan PRD): pencairan dana & rekening bank (Figma Dompet: Cairkan Dana), push notification.

## Skema database (sudah final di migrasi)

28 tabel ERD dibuat lewat 5 migrasi di `alembic/versions/` (identity_and_profiles → projects_and_applications →
collaboration_and_delivery → communication → finance), ditambah migrasi `revoked_tokens_and_uppercase_roles`
(tabel `revoked_tokens` untuk logout + nilai `users.role` jadi huruf besar) dan `email_verification_and_password_reset`
(tabel `auth_action_tokens` + kolom `users.email_verified_at/password_changed_at/terms_accepted_at`). DDL lengkap: `docs/schema.sql` (generate, jangan edit manual).
Model SQLAlchemy yang ditulis per modul **harus cocok** dengan migrasi ini; perubahan skema selanjutnya lewat migrasi baru.

Keputusan yang sudah diambil:
- ID: **string UUID `CHAR(36)`** di semua tabel, digenerate di Python (`str(uuid4())`) dan juga punya default DB `(UUID())`.
  Karena UUID acak, urutan data selalu pakai kolom waktu, bukan `id`.
- Master data memakai kode string sebagai PK: `skills.id` (`logo_design`, ...), `project_categories.id` (`website`, ...).
- PK profil = `user_id` (PK+FK ke `users.id`), jadi `umkm_id`/`freelancer_id` di tabel lain = id user.
- Timezone: **UTC** di MySQL (`--default-time-zone=+00:00`); Python pakai `datetime.now(UTC)`; Android konversi ke WIB.
- Timestamp `DATETIME(3)` (presisi milidetik) → di model pakai `mysql.DATETIME(fsp=3)`.
- `users.name` dipertahankan (tidak di-rename ke `full_name`) supaya kode modul users tetap jalan.
- Usulan tambahan audit yang ikut diterapkan: `payments.fund_status` + `released_at`, `UNIQUE(payment_id, transaction_type, balance_type)`,
  `payment_attempts.idempotency_key`, `project_agreements.application_id` + `selection_source`, `notifications.reference_type/reference_id`,
  `conversations.project_key` (kolom generated agar chat tanpa project tidak dobel).

Belum diputuskan:
- Penyimpanan file (`storage_key`): saat ini folder lokal di volume Docker `uploads` (`/app/storage/{portfolios,projects,submissions}`); object storage belum.

## Git

Branch: `main`, `dev`, dan branch tugas `[nomor]-<type>/<deskripsi>` (contoh `14-feat/auth-jwt`). Jangan push langsung ke `dev`/`main`; PR ke `dev`.
