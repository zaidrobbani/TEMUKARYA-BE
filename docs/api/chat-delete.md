# Kontrak API: Hapus Pesan Chat

Ala WhatsApp: pilih satu atau banyak pesan, lalu **Hapus untuk saya** atau **Hapus untuk semua orang**.

```
POST /api/v1/conversations/{conversation_id}/messages/delete
Authorization: Bearer <token>   (UMKM / FREELANCER peserta percakapan)
```

```json
{ "message_ids": ["…", "…"], "scope": "ME" }
```

| `scope` | Siapa / pesan mana | Efek |
|---|---|---|
| `ME` | Pesan siapa pun di percakapan ini | Pesan hilang dari riwayat **user ini saja**; lawan bicara tetap melihatnya |
| `EVERYONE` | Hanya pesan **milik sendiri**, dikirim ≤ 48 jam lalu | Teks & lampiran dibuang (file ikut dihapus dari storage); pesan tetap ada di riwayat kedua peserta dengan `deleted_at` terisi dan `message_text: null` |

Label scope tersedia di `GET /enums/message_delete_scopes`.

Sukses `200`:

```json
{ "success": true, "message": "Pesan berhasil dihapus untuk semua orang",
  "data": { "conversation_id": "…", "scope": "EVERYONE", "message_ids": ["…"], "deleted_at": "2026-11-27T02:48:48.068Z" } }
```

Pesan untuk `ME`: `"Pesan berhasil dihapus untuk saya"`.

## Perubahan di endpoint lain

- `MessageResponse` (REST riwayat, kirim pesan, event WebSocket `message`) punya field baru `deleted_at` (`null` = normal).
  Bila terisi, tampilkan placeholder **"Pesan ini telah dihapus"**; `message_text` `null` dan `attachments` kosong.
- `GET /conversations/{id}/messages` tidak lagi mengembalikan pesan yang sudah dihapus untuk saya oleh user yang login.
- WebSocket: setelah `EVERYONE`, server mengirim ke semua peserta yang tersambung:

```json
{ "type": "message_deleted", "conversation_id": "…", "message_ids": ["…"], "deleted_at": "2026-11-27T02:48:48.068Z" }
```

`ME` tidak di-push (hanya berlaku di perangkat penghapus; client langsung membuang pesan dari layar).

## Error

Semua-atau-tidak-sama-sekali: satu id bermasalah menggagalkan seluruh permintaan, tidak ada yang terhapus.

| Kode | Kapan | `message` |
|---|---|---|
| 400 | Ada id kosong, > 36 karakter, atau berisi `/`, `\` | `Message ID tidak valid` |
| 400 `code: MESSAGE_DELETE_EXPIRED` | `EVERYONE` untuk pesan > 48 jam | `Pesan yang lebih dari 48 jam hanya bisa dihapus untuk saya` |
| 401 | Token tidak ada / tidak valid | `Silakan login terlebih dahulu` / `Token tidak valid, silakan login kembali` |
| 403 | `EVERYONE` berisi pesan lawan bicara | `Hanya pesan milik sendiri yang bisa dihapus untuk semua orang` |
| 404 | Percakapan tidak ada / bukan peserta | `Percakapan tidak ditemukan` |
| 404 | Ada id pesan yang tidak ada di percakapan ini | `Pesan tidak ditemukan` |
| 422 | `message_ids` kosong, > 100 item, atau `scope` bukan `ME`/`EVERYONE` | `errors[]` per field |

Hapus ulang bersifat idempotent: `ME` untuk pesan yang sudah disembunyikan, atau `EVERYONE` untuk pesan yang sudah
dihapus, tetap `200` (pesan yang sudah dihapus tidak dicek batas 48 jam dan `deleted_at`-nya tidak berubah).

## Skema

Migrasi `c3e8d41f7a52_message_deletion`: kolom `messages.deleted_at DATETIME(3) NULL`, check `ck_messages_text_required`
dilonggarkan (`… OR deleted_at IS NOT NULL`), tabel `hidden_messages (message_id, user_id, hidden_at)` PK gabungan,
FK `ON DELETE CASCADE`.

## Keputusan yang perlu dicek

| # | Keputusan | Alasan |
|---|---|---|
| 1 | `POST …/messages/delete` dengan body, bukan `DELETE` | Hapus banyak pesan sekaligus; body pada `DELETE` kurang didukung client/proxy. Menjawab data (bukan `null`) supaya client tahu `deleted_at` |
| 2 | Batas hapus untuk semua orang 48 jam | Meniru WhatsApp (± 2 hari); konstanta `DELETE_FOR_EVERYONE_WINDOW` |
| 3 | Pesan terhapus tetap dihitung di `last_message_at` | Urutan daftar percakapan tidak melompat; isi pesan sudah tidak ada |
| 4 | Notifikasi "Pesan baru" yang sudah terkirim tidak ditarik | Notifikasi adalah riwayat terpisah; PRD tidak mengatur |
| 5 | File lampiran dihapus setelah commit, kegagalan hapus file diabaikan | Bila commit gagal, lampiran tetap utuh; file yatim lebih aman daripada pesan rusak |
| 6 | Tidak ada "batalkan hapus untuk saya" | Sama seperti WhatsApp |
