# Kontrak API Pembayaran & Dompet (F3)

Simulasi pembayaran QRIS: **tidak ada uang sungguhan**, tidak terhubung payment gateway.
Base URL `http://localhost:8000/api/v1`, semua endpoint wajib login.

Figma: Detail Pembayaran QRIS, Bukti Pembayaran Berhasil, Riwayat Transaksi UMKM, Dompet Freelancer,
Konfirmasi Pelepasan Escrow, Sukses Penyelesaian Proyek.

## Aturan nominal

- Komisi = `floor(nilai_project × 5 / 100)`, hak freelancer = nilai − komisi, total dibayar UMKM = nilai project.
  Contoh Rp1.500.000 → komisi Rp75.000, freelancer Rp1.425.000.
- Semua nominal integer rupiah. Nominal diambil dari kesepakatan di backend; Android tidak mengirim nominal.
- Satu project = satu tagihan (dibuat otomatis saat kesepakatan final).

| Kejadian | `status` | `fund_status` | Project |
|---|---|---|---|
| Kesepakatan final (tagihan dibuat) | `MENUNGGU` | `null` | `MENUNGGU_PEMBAYARAN` |
| Simulasi gagal | `GAGAL` | `null` | tetap |
| Buat ulang QRIS | `MENUNGGU` | `null` | tetap |
| Simulasi berhasil | `BERHASIL` | `HELD` (Dana ditahan) | `SIAP_DIKERJAKAN` |
| UMKM menyetujui hasil | `BERHASIL` | `RELEASED` (Dana diteruskan) | `SELESAI` |
| Project dibatalkan sebelum bayar | `DIBATALKAN` | `null` | `DIBATALKAN` |

Untuk tampilan pakai `display_status`: `MENUNGGU_PEMBAYARAN`, `GAGAL`, `DANA_DITAHAN`, `SELESAI`, `DIBATALKAN`
(label di `GET /enums/payment_display_statuses`).

## `GET /projects/{id}/payment`

Detail tagihan, status, sekaligus data bukti pembayaran. UMKM pemilik dan freelancer terpilih.

```json
{
  "id": "…", "transaction_number": "TMK-20261110-88492",
  "status": "BERHASIL", "status_label": "Pembayaran berhasil",
  "fund_status": "HELD", "fund_status_label": "Dana ditahan",
  "display_status": "DANA_DITAHAN", "display_status_label": "Dana Ditahan",
  "payment_method": "QRIS_SIMULATION", "payment_method_label": "QRIS (simulasi)", "is_simulation": true,
  "gross_amount": 1500000, "platform_fee_amount": 75000, "freelancer_amount": 1425000, "total_amount": 1500000,
  "commission_percent": 5,
  "expires_at": null, "seconds_remaining": null,
  "paid_at": "2026-11-10T07:32:00.000Z", "released_at": null, "created_at": "2026-11-10T07:20:00.000Z",
  "project": { "id": "…", "title": "Desain Rebranding Logo & Kemasan Pouch Kopi", "status": "SIAP_DIKERJAKAN", "status_label": "Siap Dikerjakan" },
  "agreement": { "scope_of_work": "…", "agreed_price": 1500000, "agreed_deadline": "2026-11-24", "duration_days": 14 },
  "umkm": { "id": "…", "name": "Rina Pratiwi", "subtitle": "Kedai Kopi Senja", "...": "…" },
  "freelancer": { "id": "…", "name": "Andi Ramadhan", "subtitle": "Desainer Grafis", "average_rating": 4.9, "...": "…" },
  "attempts": [{ "attempt_number": 1, "status": "SUCCEEDED", "failure_reason": null, "attempted_at": "…" }]
}
```

- `expires_at` / `seconds_remaining` hanya terisi saat `MENUNGGU` (countdown "Selesaikan dalam 14:52").
- `transaction_number` (format `TMK-YYYYMMDD-NNNNN`, tanggal WIB) terisi setelah berhasil.

## `POST /projects/{id}/payment/simulate` (Bayar (simulasi))

Hanya UMKM pemilik. Body opsional: `{ "outcome": "SUCCESS" }` (default) atau `"FAILED"` untuk demo gagal.
Header opsional **`Idempotency-Key`** (8-64 karakter `A-Z a-z 0-9 - _ : .`), disarankan UUID baru per tekan tombol.

| Kondisi | Hasil | Message |
|---|---|---|
| berhasil | `200`, data detail pembayaran | `Pembayaran berhasil, dana ditahan TEMUKARYA` |
| `outcome: FAILED` | `200`, `status: GAGAL` | `Pembayaran gagal, silakan coba lagi` |
| sudah berhasil sebelumnya | `200`, data lama, tidak ada transaksi baru | `Pembayaran sudah berhasil sebelumnya` |
| `Idempotency-Key` sama dikirim ulang | `200`, hasil percobaan yang sama | sesuai status |

Berhasil = dalam **satu transaksi DB**: pembayaran `BERHASIL` + dana `HELD` + saldo tertahan freelancer bertambah
(wallet dibuat otomatis saat pembayaran pertama) + project `SIAP_DIKERJAKAN` + notifikasi UMKM & freelancer.
Dua permintaan bersamaan hanya menghasilkan satu pembayaran (baris dikunci; diuji di MySQL).

## `POST /projects/{id}/payment/qris` (buat ulang QRIS)

Hanya UMKM pemilik, tanpa body. Dipakai setelah simulasi gagal atau QRIS kedaluwarsa: status kembali `MENUNGGU`,
masa berlaku baru 15 menit.

## `GET /payments/history` (Riwayat Transaksi UMKM)

Query: `group` = `ALL` (default) | `PENDING` | `HELD` (Dana Ditahan) | `COMPLETED` (Selesai) | `CANCELLED` (Dibatalkan/Refund),
`search` (judul project / nomor transaksi / nama freelancer, maks. 100), `limit`, `offset`.

```json
{
  "items": [{
    "payment_id": "…", "transaction_number": "TMK-20261024-88492",
    "project_id": "…", "project_title": "Desain Rebranding Logo & Kemasan…",
    "freelancer_id": "…", "freelancer_name": "Andi Ramadhan",
    "amount": 1500000, "status": "BERHASIL", "fund_status": "HELD",
    "display_status": "DANA_DITAHAN", "display_status_label": "Dana Ditahan",
    "paid_at": "…", "created_at": "…", "occurred_at": "…"
  }],
  "limit": 20, "offset": 0, "has_more": false,
  "counts": { "ALL": 4, "PENDING": 0, "HELD": 2, "COMPLETED": 2, "CANCELLED": 0 }
}
```

Urut terbaru dulu. Pengelompokan per bulan ("Oktober 2026, 3 Transaksi") dilakukan Android dari `occurred_at` (konversi ke WIB).

## `GET /wallet` (Dompet Freelancer)

```json
{ "available_balance": 2850000, "held_balance": 1500000, "total_balance": 4350000 }
```

Freelancer yang belum pernah dibayar mendapat semua `0`.

## `GET /wallet/transactions` (Riwayat dompet)

Query: `type` = `ALL` (default) | `HELD` (dana yang masih ditahan) | `INCOME` (pemasukan project), `limit`, `offset`.

```json
{
  "items": [
    { "id": "…", "type": "FUND_RELEASED", "type_label": "Pemasukan project", "direction": "IN", "amount": 950000,
      "payment_id": "…", "project_id": "…", "project_title": "Foto Katalog Menu Warung Kopi",
      "still_held": false, "created_at": "…" },
    { "id": "…", "type": "FUND_HELD", "type_label": "Dana ditahan", "direction": "IN", "amount": 1425000,
      "payment_id": "…", "project_id": "…", "project_title": "Rebranding Pouch Kopi",
      "still_held": true, "created_at": "…" }
  ],
  "limit": 20, "offset": 0, "has_more": false
}
```

`FUND_HELD` = "Ditahan sejak …", `FUND_RELEASED` = "Pemasukan project, + Rp…".

## Skenario error

| Endpoint | Kondisi | Status | Pesan / code |
|---|---|---|---|
| semua | tanpa token | 401 | `Silakan login terlebih dahulu` |
| `/projects/{id}/payment…` | bukan UMKM pemilik / freelancer terpilih | 404 | `Proyek tidak ditemukan` |
| | kesepakatan belum final (tagihan belum ada) | 404 | `Tagihan pembayaran belum tersedia, kesepakatan belum final` |
| `simulate`, `qris` | freelancer mencoba membayar | 403 | `Hanya UMKM pemilik yang dapat membayar proyek` |
| | project / tagihan dibatalkan | 409 | `Proyek sudah dibatalkan, tagihan tidak dapat dibayar` |
| `simulate` | percobaan sebelumnya `GAGAL` | 409 | `code: QRIS_REFRESH_REQUIRED` |
| | QRIS kedaluwarsa (> 15 menit) | 409 | `code: QRIS_EXPIRED` |
| | `Idempotency-Key` format salah | 400 | `Idempotency-Key harus 8-64 karakter …` |
| | `Idempotency-Key` pernah dipakai untuk project lain | 409 | `Idempotency-Key sudah dipakai untuk pembayaran lain` |
| | `outcome` bukan SUCCESS/FAILED | 422 | `errors[]` |
| `qris` | sudah dibayar | 409 | `code: PAYMENT_ALREADY_PAID` |
| `GET /payments/history` | bukan UMKM | 403 | `Riwayat transaksi hanya untuk UMKM` |
| | `group` tidak dikenal, `limit`/`offset` salah | 422 | `errors[]` |
| `/wallet…` | bukan freelancer | 403 | `Dompet hanya untuk freelancer` |

## Keputusan yang perlu dicek

| # | Hal | Keputusan | Alasan |
|---|---|---|---|
| P1 | Pencairan dana, rekening bank (Figma: Cairkan Dana, Ajukan Pencairan, Rekening Pencairan) | **Tidak dibuat.** Saldo tersedia hanya ditampilkan | PRD Analisis Sistem: "Tidak terdapat proses pengajuan pencairan atau transfer ke rekening bank"; CLAUDE.md & jobdesk (F-21..F-23, A-08 tidak termasuk). Perlu tabel baru bila mau dibuat |
| P2 | Nilai "Saldo tertahan" | Hak freelancer (net, setelah komisi), bukan nilai kotor | PRD: "Rp950.000 menjadi saldo tertahan" untuk project Rp1.000.000. Figma dompet menampilkan Rp1.500.000 (kotor) |
| P3 | Hasil simulasi | Default langsung `SUCCESS`; `FAILED` tersedia untuk demo | Notulen 9 Nov: "kalau berhasil dibayar langsung PEMBAYARAN BERHASIL"; PRD: pilih berhasil/gagal |
| P4 | Masa berlaku QRIS | 15 menit, disimpan di `payments.expires_at` (migrasi baru); lewat waktu → buat ulang QRIS | Figma "Selesaikan dalam 14:52 menit" |
| P5 | Nomor transaksi | `TMK-YYYYMMDD-NNNNN` (tanggal bayar WIB + 5 digit acak, unik di DB), kolom baru `payments.transaction_number` | Format Figma Bukti Pembayaran |
| P6 | Waktu pengakuan komisi | Saat pembayaran berhasil (bukan saat dana dilepas) | PRD A-07: komisi "dari setiap project yang berhasil dibayar"; sama dengan statistik admin Faruqi |
| P7 | Tab "Dibatalkan / Refund" | Berisi tagihan `DIBATALKAN` (sebelum bayar). Refund setelah bayar tidak ada | PRD: pembatalan setelah pembayaran & refund di luar cakupan |
| P8 | Freelancer boleh melihat detail pembayaran | Ya (read-only) | Layar freelancer menampilkan "Dana ditahan Rp…" |
