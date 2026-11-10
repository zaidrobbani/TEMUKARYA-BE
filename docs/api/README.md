# Kontrak API TEMUKARYA (umum)

Base URL: `http://localhost:8000/api/v1`. Swagger: `http://localhost:8000/docs`.
Path tanpa prefix (mis. `/projects`, `/health`) sudah tidak dipakai dan menjawab `404`.

## Format response

Semua response JSON memakai envelope yang sama.

```json
{ "success": true, "message": "Project berhasil dibuat", "data": { "...": "..." } }
```

```json
{ "success": false, "message": "Hanya pengguna UMKM yang dapat membuat proyek", "data": null }
```

Validasi field (`422`) menambahkan `errors`:

```json
{
  "success": false,
  "message": "Data yang dikirim tidak valid",
  "data": null,
  "errors": [{ "field": "job_title", "message": "Wajib diisi" }]
}
```

Aturan:
- Daftar berhalaman tetap di dalam `data`: `{ "items": [...], "limit": 20, "offset": 0, "has_more": false }`
  (chat: `{ "conversation_id", "items", "has_more", "next_before" }`).
- `DELETE` menjawab `200` dengan `data: null` (tidak lagi `204` tanpa body).
- Datetime selalu UTC ISO-8601 berakhiran `Z` dengan presisi milidetik (`2026-11-02T01:42:19.441Z`). Tanggal saja (`deadline`, `start_date`) tetap `YYYY-MM-DD`.
- Login wajib: header `Authorization: Bearer <access_token>` dari `POST /auth/login`.
- Nilai role huruf besar: `UMKM`, `FREELANCER`, `ADMIN` (lihat `GET /enums`).
- Endpoint unduh file (`.../file`) mengembalikan isi file biner, bukan JSON. Error-nya tetap envelope.

Status code:

| Status | Arti |
|---|---|
| 400 | Aturan bisnis ditolak (mis. kategori tidak aktif, skill duplikat, filter tidak valid) |
| 401 | Tidak/salah token, sesi logout, akun hilang |
| 403 | Role tidak berhak atau email belum diverifikasi |
| 404 | Data tidak ada atau bukan milik user (sengaja disamakan agar tidak bocor) |
| 409 | Konflik state (duplikat, data terkait, batas jumlah) |
| 413 / 415 | File terlalu besar / tipe file tidak didukung |
| 422 | Validasi field request (`errors[]`); upload file rusak memakai 422 tanpa `errors` |
| 503 | Layanan penyimpanan file tidak tersedia |
| 500 | `Terjadi kesalahan pada server, silakan coba lagi` |

## Daftar endpoint

| Modul | Method & path | Role | Sukses |
|---|---|---|---|
| core | `GET /health` | - | 200 |
| auth | `/auth/...` (register, login, google, admin/login, me, logout, email, password) | lihat [auth.md](auth.md) | |
| users | `GET /users/{user_id}` | diri sendiri / ADMIN | 200 |
| enums | `GET /enums`, `GET /enums/{name}` | - | 200 |
| skills | `GET /skills`, `GET /project-categories` | - | 200 |
| profiles | `POST /profiles/umkm` | UMKM | 201 |
| | `GET`, `PUT /profiles/umkm/me` | UMKM | 200 |
| | `POST /profiles/freelancer` | FREELANCER | 201 |
| | `GET`, `PUT /profiles/freelancer/me` | FREELANCER | 200 |
| | `GET`, `PUT /profiles/freelancer/skills` | FREELANCER | 200 |
| | `POST /profiles/freelancer/experiences`; `GET` daftar | FREELANCER | 201 / 200 |
| | `PUT`, `DELETE /profiles/freelancer/experiences/{experience_id}` | FREELANCER | 200 |
| | `POST /profiles/freelancer/portfolios`; `GET` daftar (`limit`, `offset`) | FREELANCER | 201 / 200 |
| | `GET`, `PUT`, `DELETE /profiles/freelancer/portfolios/{portfolio_id}` | FREELANCER | 200 |
| | `.../portfolios/{portfolio_id}/media`: `POST` (multipart `file`), `GET`, `GET /{media_id}/file`, `PATCH /{media_id}/cover`, `PATCH /order`, `DELETE /{media_id}` | FREELANCER | 201 / 200 |
| projects | `POST /projects` | UMKM | 201 |
| | `GET /projects` (cari project terbuka: `search`, `category_id`, `min_budget`, `max_budget`, `limit`, `offset`) | FREELANCER | 200 |
| | `GET /projects/mine` | UMKM | 200 |
| | `GET /projects/{project_id}` | pemilik; user lain hanya project `TERBUKA` yang sudah publish | 200 |
| | `PUT`, `DELETE /projects/{project_id}` | UMKM pemilik | 200 |
| | `/projects/{project_id}/attachments`: `POST` (multipart `file`), `GET`, `GET /{attachment_id}/file`, `DELETE /{attachment_id}` | UMKM pemilik | 201 / 200 |
| applications | `POST /projects/{project_id}/applications` | FREELANCER | 201 |
| | `GET /applications/mine` | FREELANCER | 200 |
| | `GET /projects/{project_id}/applications` | UMKM pemilik | 200 |
| discovery | `GET /freelancers` (filter skill, kota, harga, rating, dll.), `GET /freelancers/{freelancer_id}` | UMKM | 200 |
| matching | `GET /projects/{project_id}/recommendations/freelancers` | UMKM pemilik | 200 |
| | `GET /freelancers/me/recommendations/projects` | FREELANCER | 200 |
| milestones | `GET /projects/{project_id}/milestones`, `/milestones/progress`, `/milestones/delay-risk` | UMKM pemilik / freelancer terpilih | 200 |
| | `PUT /projects/{project_id}/milestones` (rencana pengerjaan) | UMKM pemilik / freelancer terpilih | 200 |
| | `PATCH /projects/{project_id}/milestones/{milestone_id}/complete` | freelancer terpilih | 200 |
| chat | `POST /conversations` (buat atau ambil yang sudah ada) | UMKM / FREELANCER | 200 |
| | `GET /conversations`, `GET /conversations/{conversation_id}` | peserta | 200 |
| | `POST /conversations/{conversation_id}/messages` | peserta | 201 |
| | `GET /conversations/{conversation_id}/messages` (`limit`, `before_at` + `before_id`) | peserta | 200 |
| | `PATCH /conversations/{conversation_id}/read` | peserta | 200 |
| workflow | `GET /workflow/projects` (Project Saya / Project Aktif) | UMKM / FREELANCER | 200 |
| | `GET /projects/{project_id}/workflow` (detail alur + tombol yang tersedia) | UMKM pemilik / freelancer terpilih | 200 |
| | `POST /projects/{project_id}/agreement` (pilih freelancer) | UMKM pemilik | 201 |
| | `GET`, `PATCH /projects/{project_id}/agreement` | UMKM pemilik / freelancer terpilih | 200 |
| | `POST /projects/{project_id}/agreement/approve` (Lanjut Project) | UMKM pemilik / freelancer terpilih | 200 |
| | `POST /projects/{project_id}/agreement/request-changes` (Minta Ubah) | UMKM pemilik | 200 |
| | `POST /projects/{project_id}/cancel` | UMKM pemilik / freelancer terpilih | 200 |
| | `POST /projects/{project_id}/start` (Mulai Pengerjaan) | freelancer terpilih | 200 |
| payments | `GET /projects/{project_id}/payment` (detail & bukti) | UMKM pemilik / freelancer terpilih | 200 |
| | `POST /projects/{project_id}/payment/simulate` (header `Idempotency-Key`), `POST …/payment/qris` | UMKM pemilik | 200 |
| | `GET /payments/history` (`group`, `search`) | UMKM | 200 |
| | `GET /wallet`, `GET /wallet/transactions` (`type`) | FREELANCER | 200 |
| submissions | `POST /projects/{project_id}/submissions` (multipart `files`, `note`, `result_url`) | freelancer terpilih | 201 |
| | `GET /projects/{project_id}/submissions`, `GET …/{submission_id}`, `GET …/{submission_id}/files/{file_id}` | UMKM pemilik / freelancer terpilih | 200 |
| | `POST …/submissions/{submission_id}/request-revision`, `POST …/approve` | UMKM pemilik | 200 |
| reviews | `POST /projects/{project_id}/review` | UMKM pemilik | 201 |
| | `GET /projects/{project_id}/review` | UMKM pemilik / freelancer terpilih | 200 |
| | `GET /freelancers/{freelancer_id}/reviews` | semua user login | 200 |
| notifications | `GET /notifications` (`category`, `unread_only`), `GET /notifications/unread-count` | semua user login | 200 |
| | `PATCH /notifications/{notification_id}/read`, `PATCH /notifications/read-all` | pemilik notifikasi | 200 |
| admin | `GET /admin/users` (`role`, `search`), `GET /admin/users/{user_id}` | ADMIN | 200 |
| | `GET /admin/projects` (`status`, `search`), `GET /admin/projects/{project_id}` | ADMIN | 200 |
| | `GET /admin/statistics` | ADMIN | 200 |
| | `GET /admin/finance/summary`, `/transactions`, `/transactions/{payment_id}`, `/commissions`, `/income-chart` | ADMIN | 200 |

Detail aturan tiap modul: [auth.md](auth.md), [workflow.md](workflow.md), [payments.md](payments.md),
[submissions.md](submissions.md) (hasil kerja & ulasan), [notifications.md](notifications.md), [admin-finance.md](admin-finance.md),
[`../self-profiles.md`](../self-profiles.md), [`../portfolio-media.md`](../portfolio-media.md),
serta deskripsi PR masing-masing modul di GitHub.

Error yang perlu dibedakan Android memakai field `code` (selain `message`): `MILESTONE_PLAN_INCOMPLETE`, `AGREEMENT_CHANGED`,
`QRIS_EXPIRED`, `QRIS_REFRESH_REQUIRED`, `PAYMENT_ALREADY_PAID`.

## Keputusan yang perlu dicek

Diambil saat integrasi 10 PR (2026-11-09).

| # | Hal | Keputusan | Alasan |
|---|---|---|---|
| 1 | Prefix URL | Semua endpoint, termasuk `/health`, dipindah ke `/api/v1`. Tautan email verifikasi & reset ikut `.../api/v1/auth/...` | Permintaan tim; versi API eksplisit |
| 2 | `DELETE` | `204` tanpa body → `200` + envelope `data: null` | Envelope wajib di semua response |
| 3 | `ValueError` di use case projects | Dulu `422` dengan `detail` string, sekarang `400` (`BadRequestError`) | `422` dipakai khusus validasi field dengan `errors[]`; error bisnis lain di project ini `400` |
| 4 | Role di modul chat & milestones | Pembanding `"umkm"/"freelancer"` diganti `UserRole` (`UMKM`/`FREELANCER`) | Data role di DB huruf besar sejak migrasi auth; tanpa ini semua akses chat & milestone ditolak |
| 5 | Filter role admin | `?role=` menerima `UMKM`/`FREELANCER` (huruf apa saja) | Kode admin sudah case-insensitive |
| 6 | Delay risk | Project yang mulai setelah deadline → `OVERDUE`, bukan error 500 | Kasus nyata bila freelancer dipilih terlambat |
| 7 | Datetime response modul baru | Pakai `UtcDateTime` (akhiran `Z`, milidetik) | Konsisten dengan auth; cursor chat `next_before.sent_at` bisa dikirim balik apa adanya |
| 8 | Volume upload Docker | `portfolio_uploads` + `project_uploads` (bentrok di mount `/app/storage`) → satu volume `uploads` | Dua volume tidak bisa di-mount ke path yang sama |
| 9 | Dependency | `Pillow==13.0.0` (profiles minta 13, projects minta `<13`), `pypdf==6.21.4` | Satu versi pasti; seluruh test & upload lolos dengan Pillow 13 |
| 10 | Model master data | Tambah model `skills` & `project_categories`, FK `project_applications` dideklarasikan | Tanpa ini ORM tidak bisa me-resolve FK; `alembic check` kini bersih |
| 11 | Pesan sukses | Setiap endpoint modul baru punya `message` Indonesia singkat (mis. `"Lamaran berhasil dikirim"`) | Dibuat saat integrasi, boleh diganti tim |
| 12 | Lampiran project | Hanya UMKM pemilik yang bisa melihat/mengunduh, freelancer belum bisa | Perilaku asli PR #7, belum diubah; perlu diputuskan untuk alur kerja |
| 13 | Pesan error media | Beberapa pesan masih bahasa Inggris campur (mis. `"Upload gagal; file perlu orphan cleanup"`) | Perilaku asli PR #5, belum diubah |

Fitur Zaid (workflow, pembayaran, hasil kerja, ulasan, notifikasi, admin keuangan; 2026-11-10). Keputusan per modul ada di dokumen masing-masing; yang menyentuh modul lain:

| # | Hal | Keputusan | Alasan |
|---|---|---|---|
| 14 | Modul milestones | Freelancer terpilih kini bisa membaca & menyusun rencana; deadline risiko = deadline kesepakatan; endpoint tulis `PUT /milestones` dan `PATCH …/complete` dibuat (memakai use case Faruqi + kontrak `reset_approvals`) | Sebelumnya fail-closed menunggu kontrak workflow; tanpa ini Lanjut Project tidak pernah bisa (butuh bobot 100%) |
| 15 | Modul applications & chat | Ditambah hook notifikasi (lamaran baru ke UMKM, pesan baru ke lawan bicara), ikut transaksi yang sama | Layar Notifikasi Figma |
| 16 | Pesan validasi 422 | Ditambah terjemahan untuk batas angka, jumlah item, tanggal, desimal | Pesan Pydantic bawaan berbahasa Inggris |
| 17 | Status code baru | `413` (file > 50 MB) dan `415` (format file) untuk upload hasil kerja lewat `PayloadTooLargeError` / `UnsupportedMediaTypeError` di core | Sudah tercantum di tabel status code |
