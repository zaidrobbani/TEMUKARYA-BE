import argparse
import sys
from getpass import getpass

from app.core.database import SessionLocal
from app.core.dependencies import SqlAlchemyUnitOfWork
from app.core.exceptions import AppError
from app.core.security import ScryptPasswordHasher
from app.modules.users.application.dto import CreateAdminInput
from app.modules.users.application.use_cases import CreateAdmin
from app.modules.users.infrastructure.repositories import SqlAlchemyUserRepository

MIN_PASSWORD_LENGTH = 8


def main() -> None:
    parser = argparse.ArgumentParser(description="Buat akun admin TEMUKARYA")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    password = getpass("Password: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        parser.error(f"Password minimal {MIN_PASSWORD_LENGTH} karakter")
    if password != getpass("Konfirmasi password: "):
        parser.error("Konfirmasi password tidak sama dengan password")

    with SessionLocal() as session:
        use_case = CreateAdmin(
            SqlAlchemyUserRepository(session),
            ScryptPasswordHasher(),
            SqlAlchemyUnitOfWork(session),
        )
        try:
            admin = use_case.execute(
                CreateAdminInput(name=args.name, email=args.email, password=password)
            )
        except AppError as exc:
            sys.exit(f"Gagal membuat admin: {exc.message}")

    print(f"Admin {admin.email} berhasil dibuat dengan id {admin.id}")


if __name__ == "__main__":
    main()
