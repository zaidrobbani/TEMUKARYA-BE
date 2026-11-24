# Kontrak API: Lampiran Chat (Foto & Dokumen)

Pilihan Galeri, Kamera, dan Dokumen di ruang chat. Satu lampiran per pesan (seperti WhatsApp), caption opsional.
Semua endpoint butuh login dan hanya untuk peserta percakapan.

## `POST /conversations/{conversation_id}/attachments` (multipart)

| Field | Wajib | Keterangan |
|---|---|---|
| `file` | ya | Foto JPG/PNG/WebP atau dokumen, maks **10 MB** |
| `caption` | tidak | Keterangan, maks 4000 karakter (spasi depan/belakang dibuang) |

Jenis ditentukan dari **isi file** (magic bytes), bukan dari nama/Content-Type:

| Jenis | `message_type` | Penyimpanan |
|---|---|---|
| Foto (JPG/PNG/WebP) | `IMAGE` | Dikompres ulang: EXIF/GPS dibuang, sisi terpanjang maks **1600 px**, WebP **≤ 400 KB**, ditambah thumbnail **320 px ≤ 30 KB**. Foto asli tidak disimpan |
| PDF, Word (`.docx`), Excel (`.xlsx`), PowerPoint (`.pptx`), TXT/CSV (UTF-8), ZIP | `FILE` | Disimpan apa adanya setelah isinya dicek (mis. `.docx` harus berisi folder `word/`) |

Sukses `201`: `data` = `{ message, attachments: [ { id, message_id, original_file_name, mime_type, file_size_bytes,
uploaded_at, download_path, thumbnail_path } ] }`. `thumbnail_path` hanya terisi untuk foto.
Pesan langsung di-push ke WebSocket (`{"type":"message","message":…,"attachments":[…]}`) dan dibuat notifikasi
"Pesan baru" berisi caption, atau `📷 Foto` / `📄 <nama file>`.

| Kode | Kapan | `message` |
|---|---|---|
| 413 | File > 10 MB | `Ukuran lampiran maksimal 10 MB` |
| 415 | Program/executable, format tak dikenal, teks bukan UTF-8 | `File program tidak boleh dikirim`, `Format dokumen didukung: …` |
| 400 | File kosong, rusak, isi tidak sesuai ekstensi, foto animasi/terlalu besar | `File lampiran kosong`, `Isi file tidak sesuai dengan formatnya`, … |
| 404 | Percakapan tidak ada / bukan peserta | `Percakapan tidak ditemukan` |
| 503 | Penyimpanan tidak tersedia | `Penyimpanan lampiran sedang tidak tersedia, silakan coba lagi` |

## `GET /conversations/{conversation_id}/attachments/{attachment_id}/file`

Biner file. `?thumbnail=true` untuk pratinjau foto (404 untuk dokumen). Header `Cache-Control: private, max-age=604800,
immutable` karena lampiran tidak pernah berubah. Lampiran percakapan lain / non-peserta → 404.

`GET /conversations/{id}/messages` kini juga mengisi `download_path` & `thumbnail_path` di setiap lampiran.

File disimpan di volume `uploads` (`/app/storage/chat`, env `CHAT_STORAGE_ROOT`). Tidak ada migrasi: memakai tabel
`message_attachments` yang sudah ada; thumbnail berpasangan dengan nama file (`<id>.webp` → `<id>.thumb.webp`).

## Keputusan yang perlu dicek

| # | Hal | Keputusan | Alasan |
|---|---|---|---|
| 1 | Satu lampiran per pesan | Bukan album | Sederhana & mirip WhatsApp; batas lama `MAX_ATTACHMENTS = 5` tetap |
| 2 | Foto dikirim sebagai dokumen | Tetap dikompres sebagai foto | Menjaga server ringan |
| 3 | Batas dokumen | 10 MB (aturan chat yang sudah ada) | WhatsApp jauh lebih besar, tapi permintaan Zaid agar ringan |
| 4 | Jenis dokumen | PDF, DOCX, XLSX, PPTX, TXT, CSV, ZIP; format lama `.doc/.xls`, `.ai/.psd` ditolak | Bisa dicek isinya; file desain besar disarankan dikirim lewat ZIP atau Kirim Hasil |
