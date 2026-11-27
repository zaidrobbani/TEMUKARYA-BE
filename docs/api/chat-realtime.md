# Kontrak API: Chat Real-time (WebSocket)

Melengkapi endpoint REST chat (`/conversations/...`). REST tetap berfungsi dan menjadi cadangan; pesan yang dikirim lewat
REST (`POST /conversations/{id}/messages`) dan penandaan dibaca (`PATCH /conversations/{id}/read`) juga di-push ke socket.

## Koneksi

```
WS ws://localhost:8000/api/v1/conversations/{conversation_id}/ws
```

Token login dikirim lewat header `Authorization: Bearer <token>` (Android/OkHttp) **atau** query `?token=<token>`
(browser, websocat). Hanya peserta percakapan (UMKM & freelancer-nya) yang boleh tersambung.

| Kondisi | Hasil |
|---|---|
| Berhasil | Server mengirim `{"type":"ready","conversation_id":"..."}` |
| Token tidak ada / tidak valid / logout / kedaluwarsa | Ditutup dengan kode **4401** |
| Percakapan tidak ada atau user bukan peserta | Ditutup dengan kode **4404** |

Koneksi diterima (handshake 101) lalu langsung ditutup dengan kode di atas, karena penolakan sebelum handshake membuat
uvicorn menjawab HTTP 403 tanpa kode.

## Event client → server

| Event | Efek |
|---|---|
| `{"type":"message","text":"Halo"}` | Pesan disimpan (sama seperti REST, termasuk notifikasi "Pesan baru"), lalu dikirim ke semua peserta yang tersambung, termasuk pengirim |
| `{"type":"read"}` | Pesan masuk ditandai dibaca, lalu event `read` dikirim ke semua peserta |
| `{"type":"ping"}` | Dijawab `{"type":"pong"}` |

## Event server → client

```json
{ "type": "message", "message": { "id": "…", "conversation_id": "…", "sender_user_id": "…", "message_text": "Halo",
  "message_type": "TEXT", "sent_at": "2026-11-23T05:10:00.000Z", "created_at": "…", "read_at": null } }
{ "type": "read", "conversation_id": "…", "reader_user_id": "…", "marked_count": 2, "read_at": "2026-11-23T05:10:03.120Z" }
{ "type": "message_deleted", "conversation_id": "…", "message_ids": ["…"], "deleted_at": "2026-11-27T02:48:48.068Z" }
{ "type": "error", "message": "Pesan teks tidak boleh kosong" }
```

`message_deleted` dikirim setelah `POST /conversations/{id}/messages/delete` dengan scope `EVERYONE` (lihat [chat-delete.md](chat-delete.md)).

`message` memakai bentuk yang sama dengan `MessageResponse` REST. Error validasi tidak menutup koneksi.

## Batasan

- Hub koneksi disimpan di memori proses: berlaku untuk **satu proses uvicorn** (setup Docker sekarang). Untuk multi-worker
  atau beberapa server, broadcast perlu dipindah ke pub/sub bersama (mis. Redis).
- Setiap aksi socket membuka session DB sendiri, jadi koneksi pool tidak tertahan selama socket terbuka.

## Cara uji manual

```bash
# Terminal 1 & 2 (dua akun peserta), butuh websocat
websocat "ws://localhost:8000/api/v1/conversations/<id>/ws?token=<TOKEN_UMKM>"
websocat "ws://localhost:8000/api/v1/conversations/<id>/ws?token=<TOKEN_FREELANCER>"
# lalu ketik: {"type":"message","text":"Halo"}
```

## Keputusan yang perlu dicek

| # | Hal | Keputusan | Alasan |
|---|---|---|---|
| 1 | Satu socket per percakapan | Bukan satu socket per user untuk semua percakapan | Sederhana & cukup untuk layar ruang chat; daftar chat tetap via REST |
| 2 | Pengirim juga menerima event `message` | Client cukup menunggu event (tidak perlu optimistic insert) dan dedupe berdasarkan `id` | Satu sumber kebenaran |
| 3 | Lampiran | Belum lewat socket (BE chat baru mendukung teks) | Sama dengan REST |
| 4 | Hub in-memory | Tanpa Redis | Deploy saat ini satu proses |
