# TEMUKARYA Backend

REST API untuk TEMUKARYA (marketplace UMKM & freelancer).
Stack: FastAPI, MySQL 8.4, SQLAlchemy 2.0, Alembic, Pydantic v2.

## Prasyarat

- Docker + Docker Compose v2 (Docker Desktop di Windows/macOS, Docker Engine di Linux)

Python tidak perlu di-install di laptop; semuanya jalan di dalam container.

## Menjalankan di device baru

```bash
git clone <repo-url> temukarya-BE
cd temukarya-BE
cp .env.example .env        # Windows (PowerShell): copy .env.example .env
docker compose up -d --build
```

Lalu buka:

| URL | Isi |
|-----|-----|
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/health | Cek API + koneksi database |

Kode di-mount ke container, jadi setiap file `.py` yang diubah langsung reload otomatis.

## Perintah yang sering dipakai

```bash
docker compose logs -f api                # lihat log API
docker compose ps                         # status container
docker compose down                       # stop (data MySQL tetap aman)
docker compose down -v                    # stop + HAPUS data MySQL
docker compose up -d --build              # rebuild setelah ubah requirements.txt

# Migrasi database (Alembic)
docker compose exec api alembic revision --autogenerate -m "create users table"
docker compose exec api alembic upgrade head
docker compose exec api alembic downgrade -1

# GUI database (Adminer) di http://localhost:8080
# server: db, user/password sesuai .env
docker compose --profile tools up -d
```

Migrasi juga otomatis dijalankan setiap container API start (`RUN_MIGRATIONS=true` di `.env`).

## Troubleshooting

- **Port 3306 / 8000 sudah dipakai**: ubah `DB_HOST_PORT` atau `API_PORT` di `.env`.
- **Linux, error permission saat generate migrasi**: UID user kamu bukan 1000.
  Jalankan `UID=$(id -u) GID=$(id -g) docker compose up -d --build`.
- **`entrypoint.sh: not found` di Windows**: file ter-convert ke CRLF. Pastikan `.gitattributes` ikut ter-clone, lalu `git rm --cached -r . && git reset --hard`.

## Struktur folder

```
app/
├── main.py                    # buat app, daftarkan error handler & router modul
├── core/
│   ├── config.py, database.py
│   ├── exceptions.py          # AppError, NotFoundError, ConflictError, ... (bebas framework)
│   ├── error_handlers.py      # AppError -> HTTP status
│   ├── unit_of_work.py        # port transaksi (commit)
│   ├── security.py            # PasswordHasher
│   └── dependencies.py        # implementasi konkret core untuk Depends()
└── modules/
    └── users/                 # contoh modul, salin polanya untuk fitur baru
        ├── domain/            # entities, repository interface (ABC), exceptions domain
        ├── application/       # use cases + DTO input
        ├── infrastructure/    # model SQLAlchemy + implementasi repository
        └── presentation/      # router, schema Pydantic, wiring Depends()
alembic/                       # migrasi database
docker/                        # entrypoint container
tests/                         # test use case pakai fake repository (tanpa DB)
```

### Aturan dependency

```
presentation ──► application ──► domain ◄── infrastructure
```

- **domain** & **application** tidak boleh import FastAPI, SQLAlchemy, atau Pydantic.
- Use case hanya kenal interface (`UserRepository`, `UnitOfWork`, `PasswordHasher`), bukan implementasinya.
- Implementasi konkret dirakit di `presentation/dependencies.py` (composition root modul).
- Use case yang mengubah data wajib memanggil `uow.commit()`; tanpa itu perubahan di-rollback.
- Error bisnis di-raise sebagai subclass `AppError`; jangan raise `HTTPException` dari use case.

### Menambah modul baru

1. `domain/`: entity (dataclass), interface repository, exception.
2. `application/`: use case yang menerima interface lewat constructor.
3. `infrastructure/`: model SQLAlchemy + repository, lalu import model-nya di `alembic/env.py`.
4. `presentation/`: schema, dependencies, router; daftarkan router di `app/main.py`.
5. Test use case di `tests/modules/<modul>/` pakai fake repository.

```bash
docker compose exec api python -m pytest
```
