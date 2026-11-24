# Kontrak API Hasil Kerja, Review Hasil, dan Ulasan

Base URL `http://localhost:8000/api/v1`, semua endpoint wajib login.
Figma: Modal Unggah Draf (Freelancer), Modal Ajukan Revisi (UMKM), Notifikasi Permintaan Revisi, Bandingkan Draf,
Review Hasil Project, Konfirmasi Pelepasan Escrow & Selesai Proyek, Sukses Penyelesaian Proyek, Beri Ulasan Freelancer.

## Alur

1. Freelancer `POST /projects/{id}/submissions` saat `SEDANG_DIKERJAKAN` atau `REVISI` → project `MENUNGGU_REVIEW`.
2. UMKM meninjau **kiriman terbaru**:
   - `POST …/submissions/{submission_id}/request-revision` → `REVISI` (dana tetap ditahan);
   - `POST …/submissions/{submission_id}/approve` → `SELESAI` + dana `RELEASED` ke saldo tersedia freelancer (satu transaksi).
3. Kiriman revisi selalu entri baru (`version_number` +1) sehingga versi lama tetap bisa dibuka (Bandingkan Draf).
4. Setelah `SELESAI`, UMKM bisa memberi ulasan (sekaligus saat approve, atau `POST /projects/{id}/review`).

## `POST /projects/{id}/submissions` → `201` (multipart/form-data)

| Field | Tipe | Keterangan |
|---|---|---|
| `files` | file, boleh berulang | 0-10 file, masing-masing ≤ 50 MB. Format: AI, PSD, PDF, ZIP, PNG, JPG/JPEG, MP4, DOCX (isi file dicek, bukan hanya ekstensi) |
| `note` | teks, opsional | "Catatan & Panduan Review", maks. 5000 |
| `result_url` | teks, opsional | tautan hasil http/https (mis. Google Drive), maks. 1000 |

Minimal satu file **atau** `result_url`. Contoh response:

```json
{
  "id": "…", "project_id": "…", "version_number": 1, "version_label": "v1.0",
  "submission_note": "Halo Bu Rina, berikut 2 opsi draf…", "result_url": null,
  "submitted_at": "2026-11-10T03:45:00.000Z",
  "files": [{
    "id": "…", "original_file_name": "KopiSenja_Mockup_Pouch_v1.pdf", "mime_type": "application/pdf",
    "file_size_bytes": 13002342, "uploaded_at": "…",
    "download_path": "/api/v1/projects/{id}/submissions/{submission_id}/files/{file_id}"
  }],
  "review": null
}
```

`version_label`: kiriman pertama `v1.0`, revisi berikutnya `v1.1`, `v1.2`, …

## `GET /projects/{id}/submissions`

Semua versi (terbaru dulu) + review masing-masing. UMKM pemilik dan freelancer terpilih.

```json
{
  "project_id": "…", "project_title": "…", "project_status": "MENUNGGU_REVIEW", "project_status_label": "Menunggu Review",
  "freelancer": { "id": "…", "name": "Andi Ramadhan", "subtitle": "Desainer Grafis", "average_rating": 4.9, "...": "…" },
  "revision_count": 1,
  "items": [ { "...": "objek kiriman seperti di atas" } ]
}
```

`GET /projects/{id}/submissions/{submission_id}` = satu kiriman.
`GET …/files/{file_id}` = isi file (biner, `Content-Disposition: attachment`); nama asli ada di `original_file_name`.

## `POST /projects/{id}/submissions/{submission_id}/request-revision`

```json
{
  "note": "opsional, catatan umum",
  "focus_areas": ["Tipografi & Teks", "Motif Batik Kawung"],
  "items": [
    { "title": "Ketebalan Nama Varian Kopi",
      "detail": "Font \"Arabica Single Origin\" mohon ditebalkan (semi-bold)…",
      "area": "Label Bagian Depan" }
  ]
}
```

`note` atau minimal satu `items` wajib ada. `focus_areas` maks. 10 (≤ 60 karakter), `items` maks. 20
(`title` ≤ 120, `detail` ≤ 1000, `area` opsional ≤ 120). Response = kiriman dengan `review`:

```json
"review": {
  "decision": "REVISION_REQUESTED", "decision_label": "Revisi diminta",
  "review_note": "1. Ketebalan Nama Varian Kopi: Font …",
  "focus_areas": ["Tipografi & Teks", "Motif Batik Kawung"],
  "items": [{ "title": "…", "detail": "…", "area": "Label Bagian Depan" }],
  "reviewed_at": "…"
}
```

Bila `note` kosong, `review_note` disusun dari poin-poin (kolom ini wajib terisi untuk revisi).

## `POST /projects/{id}/submissions/{submission_id}/approve` (Setujui & Selesai)

Body opsional (ulasan langsung dari layar konfirmasi):

```json
{ "review": { "rating": 5, "review_text": "Hasil revisi sangat memuaskan", "highlights": ["RESPONSIF_KOMUNIKATIF", "TEPAT_WAKTU"] } }
```

```json
{
  "project_id": "…", "project_title": "…", "project_status": "SELESAI", "project_status_label": "Selesai",
  "completed_at": "…",
  "freelancer": { "name": "Andi Ramadhan", "...": "…" },
  "submission": { "...": "kiriman yang disetujui, review.decision = APPROVED" },
  "payment": { "id": "…", "transaction_number": "TMK-20261024-88492", "gross_amount": 1500000,
               "platform_fee_amount": 75000, "freelancer_amount": 1425000,
               "fund_status": "RELEASED", "fund_status_label": "Dana diteruskan", "released_at": "…" },
  "review": { "id": "…", "rating": 5, "review_text": "…",
              "highlights": [{ "value": "TEPAT_WAKTU", "label": "Tepat Waktu" }], "created_at": "…" }
}
```

Permintaan ulang untuk kiriman yang sama setelah selesai → `200`, message `Proyek sudah selesai sebelumnya`,
**dana tidak dilepas dua kali** (dikunci per baris + constraint unik `wallet_transactions`; diuji dua request bersamaan di MySQL).

## Ulasan freelancer

- `POST /projects/{id}/review` → `201`, body `{ "rating": 1-5, "review_text": "opsional ≤ 2000", "highlights": [...] }`.
  Hanya UMKM pemilik, project `SELESAI`, satu ulasan per project.
- `GET /projects/{id}/review` — UMKM pemilik / freelancer terpilih.
- `GET /freelancers/{freelancer_id}/reviews?limit&offset` — semua user login (bagian "Review Klien UMKM" di profil):

```json
{
  "average_rating": 4.9, "review_count": 48,
  "items": [{
    "id": "…", "project_id": "…", "rating": 5, "review_text": "…", "highlights": [], "created_at": "…",
    "project_title": "Desain Kemasan Keripik Tempe",
    "reviewer": { "user_id": "…", "name": "Rina Wijaya", "business_name": "Keripik Tempe Renyah", "profile_image_url": null }
  }],
  "limit": 20, "offset": 0, "has_more": false
}
```

`highlights` ("Keunggulan Utama"): `RESPONSIF_KOMUNIKATIF`, `HASIL_BERKUALITAS`, `TEPAT_WAKTU`, `PAHAM_KEBUTUHAN`
(`GET /enums/review_highlights`). Rating di discovery/profil (milik Faruqi) otomatis ikut terhitung.

## Skenario error

| Endpoint | Kondisi | Status | Pesan |
|---|---|---|---|
| semua | tanpa token | 401 | `Silakan login terlebih dahulu` |
| semua | bukan UMKM pemilik / freelancer terpilih | 404 | `Proyek tidak ditemukan` |
| kirim hasil | UMKM yang mengirim | 403 | `Hanya freelancer terpilih yang dapat mengirim hasil` |
| | tanpa file dan tanpa tautan | 400 | `Lampirkan minimal satu file atau tautan hasil` |
| | tautan bukan http/https | 400 | `Tautan hasil harus URL http/https yang valid` |
| | > 10 file / file kosong / isi tidak cocok dengan format | 400 | `Maksimal 10 file per kiriman` / `File … kosong` / `Isi file … tidak sesuai dengan formatnya` |
| | format tidak didukung | 415 | `Format file tidak didukung. Gunakan AI, PSD, PDF, ZIP, PNG, JPG, MP4, atau DOCX` |
| | file > 50 MB | 413 | `File … melebihi 50 MB` |
| | belum mulai / sedang direview / selesai / dibatalkan | 409 | `Tekan Mulai Pengerjaan terlebih dahulu` / `Hasil terakhir sedang ditinjau UMKM` / `Proyek sudah selesai` / `Proyek sudah dibatalkan` |
| | penyimpanan file gagal | 503 | `Penyimpanan file tidak tersedia, silakan coba lagi` |
| lihat / unduh | kiriman atau file tidak ada | 404 | `Kiriman hasil tidak ditemukan` / `File tidak ditemukan` |
| minta revisi / setujui | freelancer yang memanggil | 403 | `Hanya UMKM pemilik proyek yang dapat meninjau hasil` |
| | project tidak `MENUNGGU_REVIEW` | 409 | `Hasil hanya dapat ditinjau saat proyek Menunggu Review` |
| | bukan kiriman terbaru / sudah ditinjau | 409 | `Hanya kiriman terbaru yang belum ditinjau yang dapat diproses` |
| minta revisi | catatan & poin kosong | 400 | `Catatan revisi wajib diisi` |
| | panjang/jumlah melebihi batas | 400 / 422 | pesan batas |
| setujui | `review` tidak valid (rating di luar 1-5, highlight tidak dikenal) | 422 | `errors[]` (tidak ada perubahan data) |
| ulasan | project belum selesai | 409 | `Ulasan hanya dapat diberikan setelah proyek selesai` |
| | sudah ada ulasan | 409 | `Proyek ini sudah diberi ulasan` |
| | freelancer memberi ulasan | 403 | `Hanya UMKM pemilik proyek yang dapat memberi ulasan` |
| | ulasan belum ada (`GET`) | 404 | `Proyek ini belum diberi ulasan` |
| | `freelancer_id` bukan freelancer | 404 | `Freelancer tidak ditemukan` |

## Keputusan yang perlu dicek

| # | Hal | Keputusan | Alasan |
|---|---|---|---|
| S1 | Format file | Figma: AI, PSD, PDF, ZIP, PNG. Ditambah JPG/JPEG, MP4, DOCX | Jasa fotografi, video, dan penulisan juga ada di 26 skill PRD |
| S2 | Kuota revisi ("Revisi 1 dari 3, sisa 2x gratis") | Tidak dibatasi, hanya `revision_count` | PRD Analisis Sistem: versi awal belum menetapkan batas revisi |
| S3 | Tenggat draf / tenggat revisi ("Tenggat Draf 1: 4 hari lagi") | Tidak disimpan; tidak ada di PRD/ERD | Bisa ditambah kolom bila tim memutuskan |
| S4 | Poin revisi terstruktur & aspek perbaikan | Disimpan sebagai JSON di `submission_reviews.revision_items` / `focus_areas` (migrasi baru) | Figma "Modal Ajukan Revisi" |
| S5 | Label versi | `v1.0`, `v1.1`, … (Figma juga sempat memakai "v2.0") | Konsisten dengan Bandingkan Draf v1.0 → v1.1 |
| S6 | Highlights ulasan | 4 pilihan tetap; "Hasil Siap Cetak Sempurna" di Figma digeneralisasi jadi `HASIL_BERKUALITAS` | Supaya berlaku untuk semua jenis jasa |
| S7 | Lampiran foto di ulasan ("Hasil Desain Kemasan Disertakan") | Tidak dibuat | Tidak ada di PRD/ERD |
| S8 | Unduh semua berkas ZIP ("Unduh Semua Berkas ZIP") | Tidak dibuat; unduh per file | Bisa ditambah kemudian |
| S9 | Ukuran upload | 10 × 50 MB per request diterima server sebelum divalidasi | Batas ketat per-request perlu reverse proxy (nginx `client_max_body_size`) saat deploy |
