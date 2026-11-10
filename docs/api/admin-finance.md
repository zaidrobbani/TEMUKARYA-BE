# Kontrak API Admin Keuangan (A-06, A-07, A-09, A-10)

Base URL `http://localhost:8000/api/v1`, semua endpoint **khusus ADMIN** (token dari `POST /auth/admin/login`).
Statistik user/project (A-02 s/d A-05, A-11) ada di modul `admin_statistics` milik Faruqi.

Pendapatan TEMUKARYA = komisi 5% (`platform_fee_amount`) dari pembayaran berstatus `BERHASIL`, diakui pada `paid_at`.
Tanggal filter dan pengelompokan grafik memakai kalender **WIB**.

## `GET /admin/finance/summary` (Dashboard Income)

```json
{
  "total_income": 125000, "income_this_month": 75000, "commission_percent": 5,
  "total_paid_amount": 2500000, "held_amount": 950000, "released_amount": 1425000,
  "successful_transactions": 2, "pending_transactions": 0, "failed_transactions": 1,
  "cancelled_transactions": 1, "total_transactions": 4
}
```

`held_amount` / `released_amount` = hak freelancer yang masih ditahan / sudah diteruskan.

## `GET /admin/finance/transactions` (Data Transaksi)

Query: `status` (`MENUNGGU` | `BERHASIL` | `GAGAL` | `DIBATALKAN`), `fund_status` (`HELD` | `RELEASED`),
`search` (judul project, nomor transaksi, nama UMKM/usaha/freelancer), `date_from`, `date_to` (`YYYY-MM-DD`, tanggal bayar WIB),
`limit` 1-100, `offset`.

```json
{
  "items": [{
    "payment_id": "…", "transaction_number": "TMK-20261024-88492",
    "project_id": "…", "project_title": "…", "project_status": "SELESAI", "project_status_label": "Selesai",
    "umkm_id": "…", "umkm_name": "Rina Pratiwi", "umkm_business_name": "Kedai Kopi Senja",
    "freelancer_id": "…", "freelancer_name": "Andi Ramadhan",
    "gross_amount": 1500000, "platform_fee_amount": 75000, "freelancer_amount": 1425000,
    "payment_method": "QRIS_SIMULATION", "status": "BERHASIL", "status_label": "Pembayaran berhasil",
    "fund_status": "RELEASED", "fund_status_label": "Dana diteruskan",
    "display_status": "SELESAI", "display_status_label": "Selesai",
    "created_at": "…", "paid_at": "…", "released_at": "…"
  }],
  "total": 4, "limit": 20, "offset": 0, "has_more": false
}
```

`GET /admin/finance/transactions/{payment_id}` = satu transaksi + `attempts` (riwayat percobaan bayar).

## `GET /admin/finance/commissions` (Komisi)

Query: `date_from`, `date_to`, `limit`, `offset`. Isi `items` sama dengan transaksi (hanya `BERHASIL`), ditambah
`total_commission`, `total_gross_amount`, `commission_percent` untuk rentang tanggal tersebut.

## `GET /admin/finance/income-chart` (Grafik Income)

Query: `period` = `DAY` (default, 30 hari terakhir) | `MONTH` (default 12 bulan terakhir), `date_from`, `date_to`.
Maks. 366 titik harian / 60 titik bulanan. Periode tanpa transaksi tetap muncul dengan nilai 0.

```json
{
  "period": "DAY", "date_from": "2026-11-09", "date_to": "2026-11-12", "total_income": 125000,
  "points": [
    { "period_start": "2026-11-09", "label": "9 Nov", "income": 0, "gross_amount": 0, "transactions": 0 },
    { "period_start": "2026-11-10", "label": "10 Nov", "income": 75000, "gross_amount": 1500000, "transactions": 1 }
  ]
}
```

## Skenario error

| Kondisi | Status | Pesan |
|---|---|---|
| tanpa token | 401 | `Silakan login terlebih dahulu` |
| role UMKM / FREELANCER | 403 | `Anda tidak memiliki akses ke fitur ini` |
| `status` / `fund_status` / `period` tidak dikenal, format tanggal salah, `limit`/`offset` di luar batas | 422 | `errors[]` |
| `date_from` setelah `date_to` | 400 | `date_from tidak boleh setelah date_to` |
| rentang grafik terlalu panjang | 400 | `Rentang harian maksimal 366 hari` / `Rentang bulanan maksimal 60 bulan` |
| transaksi tidak ada | 404 | `Transaksi tidak ditemukan` |

## Keputusan yang perlu dicek

| # | Hal | Keputusan | Alasan |
|---|---|---|---|
| A1 | Data pencairan (A-08) | Tidak dibuat | Pencairan dana di luar scope (lihat payments.md P1) |
| A2 | Zona waktu laporan | Hari/bulan WIB | Admin & pengguna di Indonesia; DB menyimpan UTC |
| A3 | `total_transactions` | Semua tagihan (termasuk menunggu, gagal, batal) | Sama dengan definisi statistik admin Faruqi (`COUNT(*) payments`) |
