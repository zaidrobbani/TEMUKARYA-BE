# Kontrak API Notifikasi

Base URL `http://localhost:8000/api/v1`, wajib login. Figma: Notifikasi UMKM (tab Semua / Project / Pembayaran / Pesan).

## `GET /notifications`

Query: `category` (`PROJECT` | `PAYMENT` | `MESSAGE`, opsional), `unread_only` (bool), `limit` 1-100, `offset`.

```json
{
  "items": [{
    "id": "…", "type": "SUBMISSION_RECEIVED", "category": "PROJECT",
    "title": "Andi Ramadhan mengirim hasil kerja", "body": "Rebranding Pouch Kopi kini Menunggu Review (v1.0)",
    "reference_type": "PROJECT", "reference_id": "uuid-project",
    "is_read": false, "created_at": "2026-11-10T03:45:00.000Z", "read_at": null
  }],
  "limit": 20, "offset": 0, "has_more": false,
  "unread_count": 3,
  "counts": { "ALL": 6, "PROJECT": 4, "PAYMENT": 1, "MESSAGE": 1 }
}
```

Urut terbaru dulu. Grup "Hari ini / Kemarin" dan waktu relatif ("5 mnt") dihitung Android dari `created_at`.
Navigasi saat diketuk: `reference_type = PROJECT` → detail alur project (`GET /projects/{reference_id}/workflow`),
`CONVERSATION` → ruang chat (`reference_id` = conversation id).

## Lainnya

- `GET /notifications/unread-count` → `{ "unread_count": 3 }` (badge lonceng).
- `PATCH /notifications/{id}/read` → notifikasi yang sudah ditandai dibaca (idempoten). Milik user lain → `404 Notifikasi tidak ditemukan`.
- `PATCH /notifications/read-all` → `{ "updated": 3 }`.

## Jenis notifikasi

| `type` | Kategori | Penerima | Kapan |
|---|---|---|---|
| `APPLICATION_RECEIVED` | PROJECT | UMKM | freelancer melamar project |
| `APPLICATION_ACCEPTED` | PROJECT | freelancer | dipilih UMKM ("Pengajuanmu disetujui!") |
| `APPLICATION_NOT_SELECTED` | PROJECT | pelamar lain | UMKM memilih freelancer lain |
| `AGREEMENT_UPDATED` | PROJECT | pihak lain | detail kesepakatan / rencana pengerjaan diubah |
| `AGREEMENT_APPROVED` | PROJECT | pihak lain | satu pihak menekan Lanjut Project |
| `AGREEMENT_CHANGES_REQUESTED` | PROJECT | freelancer | UMKM "Minta Ubah" |
| `AGREEMENT_FINALIZED` | PROJECT | keduanya | kesepakatan final, menunggu pembayaran |
| `PROJECT_CANCELLED` | PROJECT | pihak lain / pelamar | project dibatalkan |
| `WORK_STARTED` | PROJECT | UMKM | freelancer mulai mengerjakan |
| `MILESTONE_COMPLETED` | PROJECT | UMKM | milestone ditandai selesai |
| `SUBMISSION_RECEIVED` | PROJECT | UMKM | hasil / hasil revisi dikirim |
| `REVISION_REQUESTED` | PROJECT | freelancer | UMKM meminta revisi |
| `SUBMISSION_APPROVED` | PROJECT | freelancer | hasil disetujui, project selesai |
| `REVIEW_RECEIVED` | PROJECT | freelancer | UMKM memberi ulasan |
| `PAYMENT_SUCCEEDED` | PAYMENT | UMKM | pembayaran berhasil (dana ditahan) |
| `PAYMENT_FAILED` | PAYMENT | UMKM | simulasi pembayaran gagal |
| `PAYMENT_RECEIVED` | PAYMENT | freelancer | UMKM sudah membayar, dana ditahan |
| `FUNDS_RELEASED` | PAYMENT | freelancer | dana masuk saldo tersedia |
| `NEW_MESSAGE` | MESSAGE | lawan bicara | pesan chat baru |

Notifikasi dibuat dalam transaksi yang sama dengan aksinya: bila aksi gagal, notifikasi tidak terkirim.
Kontrak untuk modul lain: `Notifier.notify(user_id, type, title, body, reference_type, reference_id)`
(`app/modules/notifications/application/use_cases.py`), tidak commit sendiri.

## Keputusan yang perlu dicek

| # | Hal | Keputusan | Alasan |
|---|---|---|---|
| N1 | Notifikasi lamaran & pesan chat | Ditambahkan ke modul applications (Faruqi) lewat hook opsional dan ke router chat | Figma Notifikasi menampilkan "freelancer mengajukan diri" dan "Pesan baru" |
| N2 | "3 freelancer mengajukan diri" (digabung) | Satu notifikasi per lamaran, tidak digabung | Penggabungan bisa dilakukan Android per project; menghindari update notifikasi lama |
| N3 | Push notification (FCM) | Belum ada; Android menarik data (`unread-count`) | Tidak ada di PRD |
