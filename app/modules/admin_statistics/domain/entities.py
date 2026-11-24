from dataclasses import dataclass
from datetime import date, datetime


# ============================================================
# 1. ADMIN ACTOR
# ============================================================

@dataclass(frozen=True, slots=True)
class AdminActor:
    """
    Representasi Admin yang telah diautentikasi.

    user_id dan role harus berasal dari
    autentikasi JWT yang sudah diverifikasi.
    """

    user_id: str
    role: str


# ============================================================
# 2. ADMIN USER SUMMARY
# ============================================================

@dataclass(frozen=True, slots=True)
class AdminUserSummary:
    """
    Informasi dasar pengguna untuk daftar Admin.

    password_hash tidak boleh ditampilkan.
    """

    id: str
    name: str
    email: str
    role: str
    created_at: datetime


# ============================================================
# 3. ADMIN UMKM PROFILE
# ============================================================

@dataclass(frozen=True, slots=True)
class AdminUMKMProfile:
    """
    Informasi profil pengguna dengan role UMKM.
    """

    business_name: str
    business_category: str
    business_address: str
    city: str


# ============================================================
# 4. ADMIN FREELANCER PROFILE
# ============================================================

@dataclass(frozen=True, slots=True)
class AdminFreelancerProfile:
    """
    Informasi profil Freelancer.
    """

    professional_title: str
    bio: str | None
    city: str

    service_price_min: int | None
    service_price_max: int | None

    availability_status: str


# ============================================================
# 5. ADMIN USER DETAIL
# ============================================================

@dataclass(frozen=True, slots=True)
class AdminUserDetail:
    """
    Detail pengguna beserta profilnya.

    UMKM:
        Menggunakan umkm_profile.

    Freelancer:
        Menggunakan freelancer_profile.

    Profile boleh None jika belum dibuat.
    """

    user: AdminUserSummary

    umkm_profile: AdminUMKMProfile | None = None

    freelancer_profile: AdminFreelancerProfile | None = None


# ============================================================
# 6. ADMIN PROJECT SUMMARY
# ============================================================

@dataclass(frozen=True, slots=True)
class AdminProjectSummary:
    """
    Ringkasan proyek pada halaman Admin.

    assigned_freelancer_id dapat bernilai None
    jika proyek belum memiliki Freelancer.
    """

    id: str
    title: str
    category_id: str

    umkm_id: str
    umkm_name: str | None

    assigned_freelancer_id: str | None
    assigned_freelancer_name: str | None

    budget: int
    deadline: date
    status: str

    created_at: datetime


# ============================================================
# 7. ADMIN PROJECT DETAIL
# ============================================================

@dataclass(frozen=True, slots=True)
class AdminProjectDetail:
    """
    Detail proyek untuk Admin.

    project.budget:
        Budget awal dari UMKM.

    agreed_price:
        Nominal hasil kesepakatan jika sudah
        terdapat project agreement.
    """

    project: AdminProjectSummary

    description: str
    agreed_price: int | None

    published_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None


# ============================================================
# 8. ADMIN SYSTEM STATISTICS
# ============================================================

@dataclass(frozen=True, slots=True)
class AdminSystemStatistics:
    """
    Ringkasan statistik dashboard Admin.

    total_transactions:
        Jumlah transaksi pembayaran sesuai
        definisi statistik yang disepakati.

    platform_income:
        Total pendapatan komisi platform
        dalam Rupiah.

    Nilai uang disimpan sebagai integer.
    """

    total_umkm: int
    total_freelancers: int

    total_projects: int
    completed_projects: int

    total_transactions: int
    platform_income: int