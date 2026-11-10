# Kontrak API Alur Kerja Sama (F2)

Base URL `http://localhost:8000/api/v1`. Semua endpoint wajib login (`Authorization: Bearer <token>`).
Format envelope, status code umum, dan datetime: lihat [README.md](README.md).

Figma yang diacu: Pengajuan Freelancer, Profil Freelancer (Pilih & Buat Kesepakatan), Negosiasi (UMKM/Freelancer),
Modal Batalkan Project, Project Dibatalkan, Rencana Pengerjaan, Tinjau Rencana Pengerjaan, Status Pengajuan,
Project Saya, Beranda (Project Aktif Saya), Pemantauan Progres.

## Status project

`TERBUKA → MENUNGGU_KESEPAKATAN → MENUNGGU_PEMBAYARAN → SIAP_DIKERJAKAN → SEDANG_DIKERJAKAN → MENUNGGU_REVIEW ⇄ REVISI → SELESAI`,
plus `DIBATALKAN` (hanya dari tiga status pertama). Label Indonesia tersedia di `GET /enums/project_statuses`.
Status hanya berubah lewat endpoint aksi di bawah; setiap perubahan dicatat di riwayat (`history`).

| Aksi (tombol) | Endpoint | Siapa | Syarat | Status sesudah |
|---|---|---|---|---|
| Setujui & Buat / Pilih & Buat Kesepakatan | `POST /projects/{id}/agreement` | UMKM pemilik | project `TERBUKA` | `MENUNGGU_KESEPAKATAN` |
| Ubah kesepakatan | `PATCH /projects/{id}/agreement` | UMKM / freelancer terpilih | `MENUNGGU_KESEPAKATAN` | tetap (persetujuan direset) |
| Simpan Draf / susun rencana | `PUT /projects/{id}/milestones` | UMKM / freelancer terpilih | `MENUNGGU_KESEPAKATAN` | tetap (persetujuan direset) |
| Lanjut Project / Ajukan ke UMKM / Setujui Rencana | `POST /projects/{id}/agreement/approve` | UMKM / freelancer terpilih | total bobot milestone 100% | `MENUNGGU_PEMBAYARAN` bila keduanya sudah setuju |
| Minta Ubah | `POST /projects/{id}/agreement/request-changes` | UMKM pemilik | `MENUNGGU_KESEPAKATAN` | tetap (persetujuan direset) |
| Bayar | lihat [payments.md](payments.md) | UMKM pemilik | `MENUNGGU_PEMBAYARAN` | `SIAP_DIKERJAKAN` |
| Mulai Pengerjaan | `POST /projects/{id}/start` | freelancer terpilih | `SIAP_DIKERJAKAN` + pembayaran `BERHASIL` | `SEDANG_DIKERJAKAN` |
| Tandai Selesai (milestone) | `PATCH /projects/{id}/milestones/{milestone_id}/complete` | freelancer terpilih | `SEDANG_DIKERJAKAN` / `REVISI` | tetap |
| Kirim Hasil / Minta Revisi / Setujui Hasil | lihat [submissions.md](submissions.md) | | | |
| Batalkan | `POST /projects/{id}/cancel` | UMKM (semua tahap) / freelancer (setelah dipilih) | sebelum pembayaran berhasil | `DIBATALKAN` |

## Objek detail alur (`WorkflowDetail`)

Semua endpoint di dokumen ini (kecuali daftar dan milestone) menjawab objek yang sama, supaya layar cukup memakai satu model.

```json
{
  "project": {
    "id": "6f1c…", "title": "Desain Rebranding Logo & Kemasan Pouch Kopi 250gr",
    "description": "…", "category_id": "graphic_design", "budget": 1500000, "deadline": "2026-11-30",
    "status": "MENUNGGU_KESEPAKATAN", "status_label": "Menunggu Kesepakatan",
    "published_at": "2026-11-01T02:00:00.000Z", "started_at": null, "completed_at": null
  },
  "my_role": "UMKM",
  "umkm": { "id": "…", "name": "Rina Pratiwi", "subtitle": "Kedai Kopi Senja", "profile_image_url": null,
            "city": "Bandung", "average_rating": null, "review_count": 0 },
  "freelancer": { "id": "…", "name": "Andi Ramadhan", "subtitle": "Desainer Grafis", "profile_image_url": null,
                  "city": "Yogyakarta", "average_rating": 4.9, "review_count": 48 },
  "agreement": {
    "id": "…", "project_id": "…", "freelancer_id": "…", "application_id": "…", "selection_source": "APPLICATION",
    "scope_of_work": "2 alternatif logo + mockup pouch",
    "agreed_price": 1500000, "agreed_deadline": "2026-11-24", "duration_days": 14,
    "commission_percent": 5, "platform_fee_amount": 75000, "freelancer_amount": 1425000,
    "payment_method": "QRIS_SIMULATION", "payment_method_label": "QRIS (simulasi)",
    "status": "PENDING_APPROVAL", "status_label": "Menunggu persetujuan", "agreement_version": 1,
    "umkm_approved_at": null, "freelancer_approved_at": "2026-11-10T03:00:00.000Z",
    "approved_by_me": false, "waiting_for": ["UMKM"],
    "change_request_note": null, "change_requested_at": null,
    "created_at": "2026-11-10T02:00:00.000Z", "updated_at": "2026-11-10T03:00:00.000Z"
  },
  "payment": null,
  "latest_submission": null,
  "revision_count": 0,
  "has_review": false,
  "available_actions": [
    { "action": "UPDATE_AGREEMENT", "label": "Ubah kesepakatan" },
    { "action": "EDIT_MILESTONE_PLAN", "label": "Susun rencana pengerjaan" },
    { "action": "APPROVE_AGREEMENT", "label": "Lanjut project" },
    { "action": "REQUEST_AGREEMENT_CHANGES", "label": "Minta ubah rencana" },
    { "action": "CANCEL_PROJECT", "label": "Batalkan project" }
  ],
  "history": [
    { "id": "…", "previous_status": "TERBUKA", "previous_status_label": "Terbuka",
      "new_status": "MENUNGGU_KESEPAKATAN", "new_status_label": "Menunggu Kesepakatan",
      "action": "SELECT_FREELANCER", "action_label": "Pilih freelancer", "change_source": "USER",
      "changed_by_user_id": "…", "reason_code": null, "change_reason": null,
      "changed_at": "2026-11-10T02:00:00.000Z" }
  ],
  "cancellation": null
}
```

- `available_actions` = tombol yang boleh ditampilkan untuk user yang login (nilai: `GET /enums/workflow_actions`).
  Android tidak perlu menghitung sendiri kapan tombol muncul.
- `payment` terisi setelah kesepakatan final: `{id, status, status_label, fund_status, fund_status_label, gross_amount,
  platform_fee_amount, freelancer_amount, transaction_number, paid_at, released_at, expires_at}`.
- `latest_submission`: `{id, version_number, version_label, submitted_at, decision, decision_label}`.
- `cancellation` terisi bila `DIBATALKAN`: `{reason, reason_label, note, cancelled_by: "UMKM"|"FREELANCER", cancelled_at, has_payment: false}`
  (layar "Project dibatalkan").
- `duration_days` = `agreed_deadline` − tanggal (WIB) kesepakatan dibuat.

## Endpoint

### `GET /workflow/projects` (Project Saya / Project Aktif Saya)

UMKM: semua project miliknya (termasuk `TERBUKA`). Freelancer: project yang dia terpilih.
Query: `status` (opsional, salah satu status project), `limit` 1-100 (default 20), `offset` ≥ 0.

```json
{
  "items": [{
    "project": { "...": "sama seperti di atas" },
    "counterpart": { "id": "…", "name": "Andi Ramadhan", "subtitle": "Desainer Grafis", "...": "…" },
    "agreement": { "agreed_price": 1500000, "agreed_deadline": "2026-11-24", "duration_days": 14, "status": "APPROVED" },
    "payment": { "status": "BERHASIL", "fund_status": "HELD", "...": "…" },
    "application_count": 0,
    "progress_percent": 20.0
  }],
  "limit": 20, "offset": 0, "has_more": false,
  "status_counts": { "TERBUKA": 1, "MENUNGGU_KESEPAKATAN": 1, "...": 0, "ALL": 4 }
}
```

`counterpart` = freelancer (untuk UMKM) atau UMKM (untuk freelancer); `null` bila belum ada freelancer.
`application_count` = pengajuan yang masih menunggu ("3 Penawaran Masuk"). `progress_percent` `null` bila belum ada rencana milestone.

### `GET /projects/{id}/workflow` dan `GET /projects/{id}/agreement`

Detail alur. Hanya UMKM pemilik atau freelancer terpilih (orang lain `404`). `/agreement` menjawab `404` bila belum ada kesepakatan.

### `POST /projects/{id}/agreement` → `201`

```json
{ "application_id": "uuid-lamaran" }
```
atau pilih langsung dari profil freelancer:
```json
{ "freelancer_id": "uuid-freelancer", "scope_of_work": "2 alternatif logo + mockup pouch" }
```

Isi otomatis kesepakatan:
- dari lamaran: `agreed_price` = harga penawaran, `agreed_deadline` = hari ini (WIB) + estimasi hari;
- langsung (`freelancer_id`): `agreed_price` = budget project, `agreed_deadline` = deadline project. Bila freelancer itu
  sudah pernah melamar, lamarannya yang dipakai.
- `scope_of_work` default = deskripsi project.

Efek: lamaran terpilih `ACCEPTED`, lamaran lain `NOT_SELECTED`, notifikasi ke freelancer terpilih ("Pengajuanmu disetujui!")
dan ke pelamar lain.

### `PATCH /projects/{id}/agreement`

Semua field opsional, minimal satu: `scope_of_work` (1-5000), `agreed_price` (1 s/d 1.000.000.000.000),
`agreed_deadline` (`YYYY-MM-DD`, > hari ini) **atau** `duration_days` (1-365, dihitung dari tanggal kesepakatan dibuat).
Bila ada perubahan: `agreement_version` +1, persetujuan kedua pihak dihapus, pihak lain diberi notifikasi.
Nilai sama persis = tidak dianggap perubahan.

### `PUT /projects/{id}/milestones` (rencana pengerjaan)

```json
{ "items": [
  { "name": "Riset & Moodboard Brand", "weight_percent": 20 },
  { "name": "Konsep Logo (2 Alternatif)", "weight_percent": 30, "description": "opsional" },
  { "name": "Desain Kemasan Pouch 250gr", "weight_percent": 35 },
  { "name": "Mockup & File Siap Cetak", "weight_percent": "15.00" }
] }
```

Mengganti seluruh rencana (urutan list = urutan milestone). Draf boleh total < 100% ("Simpan Draf"); total > 100% ditolak.
Bobot > 0, ≤ 100, maks. 2 desimal, maks. 20 milestone. Setiap penyimpanan mereset persetujuan kesepakatan.
Response = `MilestonePlanResponse` (sama dengan `GET /projects/{id}/milestones`).

### `POST /projects/{id}/agreement/approve` (Lanjut Project)

Body opsional: `{ "agreement_version": 3 }` (disarankan: versi yang sedang dilihat user).
- Satu pihak setuju → tetap `MENUNGGU_KESEPAKATAN`, pihak lain diberi notifikasi. Message: `Persetujuan tercatat, menunggu pihak lain`.
- Kedua pihak setuju → kesepakatan `APPROVED`, project `MENUNGGU_PEMBAYARAN`, tagihan dibuat (`MENUNGGU`, QRIS berlaku 15 menit).
  Message: `Kesepakatan final, proyek menunggu pembayaran`.
- Klik ulang oleh pihak yang sudah setuju / setelah final: `200` tanpa perubahan.

Alur Figma: freelancer "Ajukan ke UMKM" = `PUT /milestones` lalu `approve`; UMKM "Setujui Rencana" = `approve`.

### `POST /projects/{id}/agreement/request-changes` (Minta Ubah)

`{ "note": "Pisahkan revisi logo jadi milestone sendiri" }` (1-2000). Hanya UMKM. Persetujuan direset,
catatan disimpan di `agreement.change_request_note`, freelancer diberi notifikasi.

### `POST /projects/{id}/cancel`

```json
{ "reason": "HARGA_TIDAK_SESUAI", "note": null }
```
`reason`: `HARGA_TIDAK_SESUAI` (Harga belum sesuai), `JADWAL_TIDAK_COCOK`, `KEBUTUHAN_BERUBAH`, `LAINNYA` (wajib `note`, maks. 500).
Efek: project & kesepakatan dibatalkan, tagihan yang belum dibayar `DIBATALKAN`, lamaran terkait `CANCELLED`,
pihak lain (dan pelamar bila project masih terbuka) diberi notifikasi.

### `POST /projects/{id}/start` (Mulai Pengerjaan)

Tanpa body. `started_at` diisi (dipakai perhitungan risiko keterlambatan). Klik ulang saat sudah `SEDANG_DIKERJAKAN` → `200` tanpa perubahan.

### `PATCH /projects/{id}/milestones/{milestone_id}/complete` (Tandai Selesai)

Tanpa body. Response = progres (`MilestoneProgressResponse`). Idempoten: klik ulang tidak menambah progres.
UMKM diberi notifikasi saat milestone benar-benar berubah menjadi selesai. Progres 100% tidak membuat project Selesai.

## Skenario error

| Endpoint | Kondisi | Status | Pesan / code |
|---|---|---|---|
| semua | tanpa token / token tidak valid | 401 | `Silakan login terlebih dahulu` |
| semua `/projects/{id}/…` | project tidak ada, atau user bukan UMKM pemilik / freelancer terpilih | 404 | `Proyek tidak ditemukan` |
| `GET /workflow/projects` | role ADMIN | 403 | `Hanya UMKM atau freelancer yang memiliki daftar proyek` |
| | `status` tidak dikenal, `limit`/`offset` di luar batas | 422 | `errors[]` |
| `POST /agreement` | role bukan UMKM | 403 | `Hanya UMKM yang dapat memilih freelancer` |
| | `application_id` dan `freelancer_id` sama-sama kosong / sama-sama diisi | 422 | `Isi salah satu: application_id atau freelancer_id` |
| | lamaran tidak ada / milik project lain | 404 | `Pengajuan tidak ditemukan` |
| | `freelancer_id` bukan freelancer | 404 | `Freelancer tidak ditemukan` |
| | lamaran sudah tidak aktif | 409 | `Pengajuan ini sudah tidak aktif` |
| | project sudah punya freelancer terpilih (termasuk dua klik bersamaan) | 409 | `Proyek sudah memiliki freelancer terpilih` |
| | project bukan `TERBUKA` (mis. dibatalkan) | 409 | `Freelancer hanya dapat dipilih saat proyek berstatus Terbuka` |
| | project belum publish | 409 | `Proyek belum dipublikasikan` |
| | pilih langsung tapi deadline project sudah lewat | 400 | `Deadline proyek sudah lewat, perbarui deadline proyek sebelum memilih freelancer` |
| `PATCH /agreement` | body kosong | 400 | `Tidak ada perubahan kesepakatan yang dikirim` |
| | `agreed_deadline` dan `duration_days` sama-sama diisi | 400 | `Isi salah satu: agreed_deadline atau duration_days` |
| | deadline ≤ hari ini / durasi > 365 hari | 400 | `Deadline harus setelah hari ini` / `Durasi pengerjaan maksimal 365 hari` |
| | tipe/format field salah | 422 | `errors[]` |
| | kesepakatan sudah final | 409 | `Kesepakatan sudah final dan tidak dapat diubah` |
| | project dibatalkan | 409 | `Proyek sudah dibatalkan` |
| `PUT /milestones` | total bobot > 100%, nama kosong, dll. | 400 | pesan validasi milestone |
| | bobot ≤ 0, > 100, > 2 desimal | 422 | `errors[]` |
| | setelah kesepakatan final | 409 | `Rencana pengerjaan hanya dapat diubah sebelum kesepakatan final` |
| `POST /approve` | total bobot rencana ≠ 100% | 409 | `code: MILESTONE_PLAN_INCOMPLETE`, `Total bobot rencana pengerjaan harus 100% … (saat ini 40%)` |
| | `agreement_version` tidak sama dengan versi terbaru | 409 | `code: AGREEMENT_CHANGED`, `Detail kesepakatan sudah berubah, muat ulang sebelum menyetujui` |
| | belum ada kesepakatan | 404 | `Kesepakatan belum dibuat` |
| | project dibatalkan | 409 | `Proyek sudah dibatalkan` |
| `POST /request-changes` | bukan UMKM | 403 | `Hanya UMKM pemilik yang dapat meminta perubahan rencana` |
| | catatan kosong / > 2000 | 422 | `errors[]` |
| | kesepakatan sudah final | 409 | `Kesepakatan sudah final dan tidak dapat diubah` |
| `POST /cancel` | `reason` tidak dikenal | 422 | `errors[]` |
| | `LAINNYA` tanpa `note` | 400 | `Tuliskan alasan pembatalan` |
| | freelancer membatalkan project `TERBUKA` (belum terpilih) | 404 | `Proyek tidak ditemukan` |
| | pembayaran sudah berhasil | 409 | `Proyek tidak dapat dibatalkan setelah pembayaran berhasil` |
| | sudah dibatalkan | 409 | `Proyek sudah dibatalkan` |
| `POST /start` | bukan freelancer terpilih | 403 / 404 | `Hanya freelancer terpilih yang dapat memulai pengerjaan` |
| | belum bayar | 409 | `Proyek belum dibayar, tunggu pembayaran UMKM berhasil` |
| | masih negosiasi | 409 | `Kesepakatan belum disetujui kedua pihak` |
| | sudah lewat tahap mulai | 409 | `Pengerjaan sudah dimulai (status …)` |
| `PATCH …/complete` | bukan freelancer terpilih | 403 | `Hanya freelancer terpilih yang dapat menandai milestone selesai` |
| | belum mulai / sedang direview / selesai | 409 | `Tekan Mulai Pengerjaan …` / `… saat hasil sedang direview UMKM` / `Proyek sudah selesai …` |
| | milestone tidak ada | 404 | `Milestone tidak ditemukan` |

Pemilihan freelancer, persetujuan, pembatalan, dan mulai pengerjaan mengunci baris project (`SELECT … FOR UPDATE`),
jadi dua permintaan bersamaan tidak bisa menghasilkan dua freelancer terpilih atau dua perubahan status (diuji di MySQL).

## Keputusan yang perlu dicek

| # | Hal | Keputusan | Alasan |
|---|---|---|---|
| W1 | Siapa menyusun rencana milestone | Freelancer terpilih **dan** UMKM pemilik boleh `PUT /milestones` selama negosiasi. Kode Faruqi sebelumnya hanya mengizinkan UMKM; diubah + test-nya disesuaikan | PRD Fungsi 4 & Figma "Rencana Pengerjaan (Freelancer)": freelancer mengusulkan; layar UMKM juga punya tombol tambah/hapus |
| W2 | "Ajukan ke UMKM" & "Setujui Rencana" | Tidak ada status rencana terpisah; keduanya = `approve` kesepakatan. Kesepakatan final = rencana + nilai + deadline disetujui kedua pihak | PRD: "kedua pihak menyetujui kesepakatan final" sebelum bayar; menghindari state machine kedua |
| W3 | Syarat Lanjut | Total bobot milestone harus tepat 100% sebelum pihak mana pun menekan Lanjut | Kontrak jobdesk ("syarat Lanjut adalah total bobot 100") |
| W4 | Isi otomatis kesepakatan | Dari lamaran: harga penawaran + (hari ini + estimasi hari). Pilih langsung: budget + deadline project | PRD tidak mengatur nilai awal; Figma negosiasi memakai nilai penawaran |
| W5 | Ubah kesepakatan | Kedua pihak boleh ubah harga, lingkup, deadline/durasi selama negosiasi. Notulen 9 Nov menyebut "harga penawaran tidak bisa diganti, estimasi hari bisa" — itu untuk **lamaran**; kesepakatan tetap bisa dinegosiasi | PRD: "perubahan kesepakatan sebelum pembayaran membatalkan kedua persetujuan" |
| W6 | Lamaran pelamar lain | Saat freelancer dipilih → `NOT_SELECTED` ("Tidak dipilih"); saat project dibatalkan → `CANCELLED` | Figma tab Pengajuan: Menunggu / Disetujui / Dibatalkan. Android bisa menaruh `NOT_SELECTED` di tab Dibatalkan |
| W7 | Pengajuan Freelancer di Figma berlabel "Menunggu Kesepakatan" | Backend tetap `TERBUKA` sampai UMKM memilih | PRD Analisis Sistem: lamaran tidak mengubah status project |
| W8 | Alasan batal | 4 pilihan sesuai modal Figma; `LAINNYA` wajib catatan. Disimpan di riwayat status (`reason_code`, `change_reason`) | Figma "Modal Batalkan Project" |
| W9 | Freelancer membatalkan | Boleh di `MENUNGGU_KESEPAKATAN` dan `MENUNGGU_PEMBAYARAN` | PRD: "salah satu pihak terkait dapat membatalkan selama pembayaran belum berhasil" |
| W10 | Endpoint daftar project | `GET /workflow/projects` (baru), tidak mengubah `GET /projects/mine` milik Faruqi | Butuh data freelancer, kesepakatan, pembayaran, progres untuk "Project Saya" dan "Project Aktif Saya" |
| W11 | Detail project untuk freelancer terpilih | Pakai `GET /projects/{id}/workflow`; `GET /projects/{id}` (Faruqi) tetap hanya untuk project `TERBUKA` | Tidak mengubah modul projects |
| W12 | Deadline untuk risiko keterlambatan | Modul milestones kini memakai `agreed_deadline` kesepakatan (bukan deadline awal project) | Deadline final hasil negosiasi |
| W13 | Batas revisi ("Revisi 1 dari 3" di Figma) | Tidak dibatasi; backend hanya mengirim `revision_count` | PRD Analisis Sistem: "versi awal belum menetapkan batas jumlah revisi" |
