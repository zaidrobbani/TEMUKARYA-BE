"""Pengelompokan Swagger (/docs) per sudut pandang pengguna: Umum, UMKM, Freelancer, Admin.

Tag bawaan router modul diganti di sini supaya urutan di Swagger mengikuti alur aplikasi.
Endpoint yang dipakai lebih dari satu role muncul di beberapa grup. Endpoint baru wajib
didaftarkan di GROUPS (dicek oleh tests/api/test_openapi_groups.py).
"""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.core.config import API_PREFIX

DESCRIPTION = f"""
REST API aplikasi TEMUKARYA. Base path `{API_PREFIX}`.

Endpoint dikelompokkan per **sudut pandang pengguna**:
**Umum** (semua orang), **UMKM**, **Freelancer**, dan **Admin**. Nomor grup mengikuti urutan alur di aplikasi.
Endpoint yang dipakai lebih dari satu role muncul di beberapa grup.

Cara mencoba: login lewat `POST {API_PREFIX}/auth/login` (admin: `{API_PREFIX}/auth/admin/login`),
salin `data.access_token`, lalu klik **Authorize**.
"""

# (nama tag, deskripsi, daftar "METHOD /path" tanpa prefix /api/v1)
GROUPS: list[tuple[str, str, list[str]]] = [
    (
        "Umum · Sistem & Master Data",
        "Cek server, daftar enum (status + label Indonesia), master skill dan kategori project.",
        ["GET /health", "GET /enums", "GET /enums/{name}", "GET /skills", "GET /project-categories"],
    ),
    (
        "Umum · Autentikasi",
        "Registrasi UMKM/Freelancer, login, verifikasi email, lupa password, akun saya, logout.",
        [
            "POST /auth/register",
            "POST /auth/login",
            "POST /auth/google",
            "POST /auth/email/verify",
            "POST /auth/email/resend",
            "POST /auth/password/forgot",
            "POST /auth/password/reset",
            "GET /auth/me",
            "POST /auth/logout",
            "GET /users/{user_id}",
        ],
    ),
    (
        "UMKM · 1. Profil Usaha",
        "Buat, lihat, dan ubah profil usaha.",
        ["POST /profiles/umkm", "GET /profiles/umkm/me", "PUT /profiles/umkm/me"],
    ),
    (
        "UMKM · 2. Kelola Project",
        "Buat project, Project Saya, ubah/hapus project, lampiran brief.",
        [
            "POST /projects",
            "GET /projects/mine",
            "GET /workflow/projects",
            "GET /projects/{project_id}",
            "PUT /projects/{project_id}",
            "DELETE /projects/{project_id}",
            "POST /projects/{project_id}/attachments",
            "GET /projects/{project_id}/attachments",
            "GET /projects/{project_id}/attachments/{attachment_id}/file",
            "DELETE /projects/{project_id}/attachments/{attachment_id}",
        ],
    ),
    (
        "UMKM · 3. Cari Freelancer & Rekomendasi",
        "Cari & filter freelancer, profil freelancer beserta ulasan, rekomendasi freelancer untuk project.",
        [
            "GET /freelancers",
            "GET /freelancers/{freelancer_id}",
            "GET /freelancers/{freelancer_id}/reviews",
            "GET /projects/{project_id}/recommendations/freelancers",
        ],
    ),
    (
        "UMKM · 4. Pengajuan & Kesepakatan",
        "Daftar pengajuan, pilih freelancer, negosiasi, tinjau rencana pengerjaan, Lanjut Project / Minta Ubah, batalkan.",
        [
            "GET /projects/{project_id}/applications",
            "POST /projects/{project_id}/agreement",
            "GET /projects/{project_id}/workflow",
            "GET /projects/{project_id}/agreement",
            "PATCH /projects/{project_id}/agreement",
            "GET /projects/{project_id}/milestones",
            "PUT /projects/{project_id}/milestones",
            "POST /projects/{project_id}/agreement/request-changes",
            "POST /projects/{project_id}/agreement/approve",
            "POST /projects/{project_id}/cancel",
        ],
    ),
    (
        "UMKM · 5. Pembayaran",
        "Detail pembayaran QRIS (simulasi), bayar, buat ulang QRIS, bukti pembayaran, riwayat transaksi.",
        [
            "GET /projects/{project_id}/payment",
            "POST /projects/{project_id}/payment/simulate",
            "POST /projects/{project_id}/payment/qris",
            "GET /payments/history",
        ],
    ),
    (
        "UMKM · 6. Pantau Progres & Review Hasil",
        "Progres milestone, risiko keterlambatan, lihat/unduh hasil, minta revisi, setujui & selesai, beri ulasan.",
        [
            "GET /projects/{project_id}/workflow",
            "GET /projects/{project_id}/milestones/progress",
            "GET /projects/{project_id}/milestones/delay-risk",
            "GET /projects/{project_id}/submissions",
            "GET /projects/{project_id}/submissions/{submission_id}",
            "GET /projects/{project_id}/submissions/{submission_id}/files/{file_id}",
            "POST /projects/{project_id}/submissions/{submission_id}/request-revision",
            "POST /projects/{project_id}/submissions/{submission_id}/approve",
            "POST /projects/{project_id}/review",
            "GET /projects/{project_id}/review",
        ],
    ),
    (
        "Freelancer · 1. Profil, Skill & Portofolio",
        "Profil profesional, skill, pengalaman, portofolio beserta media.",
        [
            "POST /profiles/freelancer",
            "GET /profiles/freelancer/me",
            "PUT /profiles/freelancer/me",
            "GET /profiles/freelancer/skills",
            "PUT /profiles/freelancer/skills",
            "GET /profiles/freelancer/experiences",
            "POST /profiles/freelancer/experiences",
            "PUT /profiles/freelancer/experiences/{experience_id}",
            "DELETE /profiles/freelancer/experiences/{experience_id}",
            "POST /profiles/freelancer/portfolios",
            "GET /profiles/freelancer/portfolios",
            "GET /profiles/freelancer/portfolios/{portfolio_id}",
            "PUT /profiles/freelancer/portfolios/{portfolio_id}",
            "DELETE /profiles/freelancer/portfolios/{portfolio_id}",
            "POST /profiles/freelancer/portfolios/{portfolio_id}/media",
            "GET /profiles/freelancer/portfolios/{portfolio_id}/media",
            "GET /profiles/freelancer/portfolios/{portfolio_id}/media/{media_id}/file",
            "PATCH /profiles/freelancer/portfolios/{portfolio_id}/media/{media_id}/cover",
            "PATCH /profiles/freelancer/portfolios/{portfolio_id}/media/order",
            "DELETE /profiles/freelancer/portfolios/{portfolio_id}/media/{media_id}",
            "GET /freelancers/{freelancer_id}/reviews",
        ],
    ),
    (
        "Freelancer · 2. Cari Project & Rekomendasi",
        "Cari & filter project terbuka, detail project, rekomendasi project sesuai skill.",
        [
            "GET /projects",
            "GET /projects/{project_id}",
            "GET /freelancers/me/recommendations/projects",
        ],
    ),
    (
        "Freelancer · 3. Pengajuan & Kesepakatan",
        "Ajukan penawaran, status pengajuan, negosiasi, susun rencana pengerjaan, Lanjut Project, batalkan.",
        [
            "POST /projects/{project_id}/applications",
            "GET /applications/mine",
            "GET /workflow/projects",
            "GET /projects/{project_id}/workflow",
            "GET /projects/{project_id}/agreement",
            "PATCH /projects/{project_id}/agreement",
            "GET /projects/{project_id}/milestones",
            "PUT /projects/{project_id}/milestones",
            "POST /projects/{project_id}/agreement/approve",
            "POST /projects/{project_id}/cancel",
        ],
    ),
    (
        "Freelancer · 4. Pengerjaan & Kirim Hasil",
        "Status pembayaran, mulai pengerjaan, tandai milestone selesai, kirim hasil/revisi, lihat ulasan.",
        [
            "GET /projects/{project_id}/payment",
            "POST /projects/{project_id}/start",
            "GET /projects/{project_id}/milestones/progress",
            "GET /projects/{project_id}/milestones/delay-risk",
            "PATCH /projects/{project_id}/milestones/{milestone_id}/complete",
            "POST /projects/{project_id}/submissions",
            "GET /projects/{project_id}/submissions",
            "GET /projects/{project_id}/submissions/{submission_id}",
            "GET /projects/{project_id}/submissions/{submission_id}/files/{file_id}",
            "GET /projects/{project_id}/review",
        ],
    ),
    (
        "Freelancer · 5. Dompet",
        "Saldo tersedia, saldo tertahan, dan riwayat dana masuk.",
        ["GET /wallet", "GET /wallet/transactions"],
    ),
    (
        "UMKM & Freelancer · Chat",
        "Daftar percakapan, buka percakapan, kirim pesan, riwayat pesan, tandai dibaca.",
        [
            "POST /conversations",
            "GET /conversations",
            "GET /conversations/{conversation_id}",
            "POST /conversations/{conversation_id}/messages",
            "GET /conversations/{conversation_id}/messages",
            "PATCH /conversations/{conversation_id}/read",
        ],
    ),
    (
        "UMKM & Freelancer · Notifikasi",
        "Daftar notifikasi per kategori, jumlah belum dibaca, tandai dibaca.",
        [
            "GET /notifications",
            "GET /notifications/unread-count",
            "PATCH /notifications/{notification_id}/read",
            "PATCH /notifications/read-all",
        ],
    ),
    (
        "Admin · Autentikasi",
        "Login admin (web dashboard), akun saya, logout.",
        ["POST /auth/admin/login", "GET /auth/me", "POST /auth/logout"],
    ),
    (
        "Admin · Pengguna & Project",
        "Data dan detail user (UMKM/Freelancer), data dan detail project.",
        [
            "GET /admin/users",
            "GET /admin/users/{user_id}",
            "GET /users/{user_id}",
            "GET /admin/projects",
            "GET /admin/projects/{project_id}",
        ],
    ),
    (
        "Admin · Statistik & Keuangan",
        "Statistik sistem, dashboard income, transaksi, komisi 5%, grafik income.",
        [
            "GET /admin/statistics",
            "GET /admin/finance/summary",
            "GET /admin/finance/transactions",
            "GET /admin/finance/transactions/{payment_id}",
            "GET /admin/finance/commissions",
            "GET /admin/finance/income-chart",
        ],
    ),
]

UNGROUPED_TAG = "Lainnya (belum dikelompokkan)"


def operation_tags() -> dict[str, list[str]]:
    tags: dict[str, list[str]] = {}
    for name, _, operations in GROUPS:
        for operation in operations:
            tags.setdefault(operation, []).append(name)
    return tags


def install_openapi(app: FastAPI) -> None:
    def build_schema() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, description=DESCRIPTION, routes=app.routes)
        tags = operation_tags()
        for path, operations in schema.get("paths", {}).items():
            for method, operation in operations.items():
                key = f"{method.upper()} {path.removeprefix(API_PREFIX)}"
                operation["tags"] = tags.get(key, [UNGROUPED_TAG])
        schema["tags"] = [{"name": name, "description": description} for name, description, _ in GROUPS]
        app.openapi_schema = schema
        return schema

    app.openapi = build_schema
