# CONTEXT PROYEK BACKEND TEMUKARYA

REST API untuk aplikasi Android TEMUKARYA: marketplace jasa yang mempertemukan UMKM dengan freelancer digital.
Proyek tim (4 orang), kelas Pengembangan Aplikasi Perangkat Bergerak. Admin dashboard berupa web terpisah.

## Cara kerja dengan user (PENTING)

- User **mengetik kode sendiri secara manual**. Jangan langsung mengedit/membuat file kode di repo.
  Pandu langkah demi langkah: jelaskan struktur, berikan potongan kode lengkap per file, lalu tunggu user selesai mengetik.
- Edit langsung hanya kalau user secara eksplisit meminta (misalnya file dokumentasi seperti ini).
- Bahasa percakapan: Indonesia. Komentar di kode: Indonesia, singkat, hanya untuk "kenapa" yang tidak jelas dari kode.
- Kerjakan per langkah kecil yang bisa dijalankan dan dites, jangan sekaligus banyak modul.

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
- Test use case di `tests/modules/<modul>/` memakai fake repository in-memory (tanpa DB). Contoh: `tests/modules/users/test_use_cases.py`.
- Modul `users` adalah contoh pola yang harus ditiru.

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
- [ ] Sesuaikan modul `users` ke UUID (id `str`, model `CHAR(36)` + `default=lambda: str(uuid4())`, `DATETIME(3)`), termasuk test.
- [ ] Langkah 1: modul `auth` (login JWT via PyJWT, `/auth/me`, `get_current_user`, `require_roles`), role `ADMIN`, larang register sebagai admin.
- [ ] Langkah 2: model + modul `profiles` & `skills` (tabel sudah ada).
- [ ] Berikutnya: projects + kategori + `project_skills` → applications → agreements/workflow → milestones → payments/wallet → submissions/review → matching → chat, notifications, admin.

## Skema database (sudah final di migrasi)

Seluruh 28 tabel sudah dibuat lewat 5 migrasi di `alembic/versions/` (identity_and_profiles → projects_and_applications →
collaboration_and_delivery → communication → finance). DDL lengkap: `docs/schema.sql` (generate, jangan edit manual).
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
- Penyimpanan file (`storage_key`): folder lokal/volume Docker atau object storage.
- Role `ADMIN` di `UserRole` (kolom `role` sudah VARCHAR, tidak perlu migrasi).

## Git

Branch: `main`, `dev`, dan branch tugas `[nomor]-<type>/<deskripsi>` (contoh `14-feat/auth-jwt`). Jangan push langsung ke `dev`/`main`; PR ke `dev`.
