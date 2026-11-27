"""Buat akun yang langsung terverifikasi (tanpa email verifikasi): admin, akun demo, akun uji.

    python -m app.scripts.create_user --role UMKM --name "Rina" --email rina@demo.id --phone 081234567890
    echo 'rahasia123' | python -m app.scripts.create_user --role FREELANCER ... --password-stdin
"""

import argparse
import sys
from collections.abc import Callable, Sequence
from getpass import getpass
from typing import TextIO

from pydantic import BaseModel, ValidationError

from app.core.error_handlers import validation_message
from app.modules.auth.presentation.schemas import Email, Name, NewPassword, PhoneNumber
from app.modules.users.application.dto import CreateVerifiedUserInput
from app.modules.users.domain.entities import UserRole

_FIELD_LABELS = {"name": "--name", "email": "--email", "phone_number": "--phone", "password": "Password"}


class InvalidArguments(Exception):
    pass


class _AccountFields(BaseModel):
    """Aturan sama dengan `POST /auth/register`, supaya akun CLI tidak lolos dari validasi API."""

    name: Name
    email: Email
    phone_number: PhoneNumber | None = None
    password: NewPassword


def build_parser(fixed_role: UserRole | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Buat akun TEMUKARYA yang emailnya sudah terverifikasi")
    if fixed_role is None:
        parser.add_argument("--role", required=True, type=str.upper, choices=[role.value for role in UserRole])
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--phone", help="Nomor WhatsApp, wajib untuk UMKM/FREELANCER (contoh 081234567890)")
    parser.add_argument(
        "--password-stdin", action="store_true", help="Baca password dari stdin (untuk docker compose exec -T)"
    )
    parser.set_defaults(role=fixed_role.value if fixed_role else None)
    return parser


def _read_password(args: argparse.Namespace, prompt: Callable[[str], str], stdin: TextIO) -> str:
    if args.password_stdin:
        return stdin.readline().rstrip("\r\n")
    password = prompt("Password: ")
    if password != prompt("Konfirmasi password: "):
        raise InvalidArguments("Konfirmasi password tidak sama dengan password")
    return password


def build_input(
    args: argparse.Namespace,
    prompt: Callable[[str], str] = getpass,
    stdin: TextIO = sys.stdin,
) -> CreateVerifiedUserInput:
    role = UserRole(args.role)
    if role != UserRole.ADMIN and not (args.phone or "").strip():
        raise InvalidArguments(f"--phone wajib diisi untuk role {role.value}")

    password = _read_password(args, prompt, stdin)
    try:
        fields = _AccountFields(name=args.name, email=args.email, phone_number=args.phone, password=password)
    except ValidationError as exc:
        messages = [f"{_FIELD_LABELS.get(str(err['loc'][0]), err['loc'][0])}: {validation_message(err)}" for err in exc.errors()]
        raise InvalidArguments("; ".join(messages)) from exc

    return CreateVerifiedUserInput(
        name=fields.name,
        email=fields.email,
        password=fields.password,
        role=role,
        phone_number=fields.phone_number,
    )


def main(argv: Sequence[str] | None = None, fixed_role: UserRole | None = None) -> None:
    from app.core.database import SessionLocal
    from app.core.dependencies import SqlAlchemyUnitOfWork
    from app.core.exceptions import AppError
    from app.core.security import ScryptPasswordHasher
    from app.modules.users.application.use_cases import CreateVerifiedUser
    from app.modules.users.infrastructure.repositories import SqlAlchemyUserRepository

    args = build_parser(fixed_role).parse_args(argv)
    try:
        data = build_input(args)
    except InvalidArguments as exc:
        sys.exit(f"Gagal membuat akun: {exc}")

    with SessionLocal() as session:
        use_case = CreateVerifiedUser(
            SqlAlchemyUserRepository(session),
            ScryptPasswordHasher(),
            SqlAlchemyUnitOfWork(session),
        )
        try:
            user = use_case.execute(data)
        except AppError as exc:
            sys.exit(f"Gagal membuat akun: {exc.message}")

    print(f"Akun {user.role.value} {user.email} (terverifikasi) berhasil dibuat dengan id {user.id}")


if __name__ == "__main__":
    main()
