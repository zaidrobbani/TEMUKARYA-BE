import io

import pytest

from app.modules.users.domain.entities import UserRole
from app.scripts.create_user import InvalidArguments, build_input, build_parser

PASSWORD = "rahasia123"


def parse(*argv: str, fixed_role: UserRole | None = None):
    return build_parser(fixed_role).parse_args(list(argv))


def prompt_with(*answers: str):
    replies = iter(answers)
    return lambda _label: next(replies)


def umkm_args(*extra: str):
    return parse("--role", "umkm", "--name", " Rina ", "--email", "Rina@Demo.ID", "--phone", "0812-3456-7890", *extra)


def test_valid_umkm_is_normalized_like_register():
    data = build_input(umkm_args(), prompt=prompt_with(PASSWORD, PASSWORD))

    assert data.role == UserRole.UMKM
    assert data.name == "Rina"
    assert data.email == "rina@demo.id"
    assert data.phone_number == "+6281234567890"
    assert data.password == PASSWORD


def test_password_stdin_skips_prompt():
    def no_prompt(_label):
        raise AssertionError("tidak boleh bertanya password")

    data = build_input(umkm_args("--password-stdin"), prompt=no_prompt, stdin=io.StringIO(f"{PASSWORD}\r\n"))

    assert data.password == PASSWORD


@pytest.mark.parametrize("role", ["UMKM", "FREELANCER"])
def test_phone_is_required_for_app_roles(role):
    args = parse("--role", role, "--name", "Rina", "--email", "rina@demo.id")

    with pytest.raises(InvalidArguments, match=f"--phone wajib diisi untuk role {role}"):
        build_input(args, prompt=prompt_with(PASSWORD, PASSWORD))


def test_admin_without_phone_is_allowed():
    data = build_input(parse("--role", "ADMIN", "--name", "Admin", "--email", "admin@temukarya.id"), prompt=prompt_with(PASSWORD, PASSWORD))

    assert data.role == UserRole.ADMIN
    assert data.phone_number is None


def test_fixed_role_parser_for_create_admin():
    args = parse("--name", "Admin", "--email", "admin@temukarya.id", fixed_role=UserRole.ADMIN)

    assert build_input(args, prompt=prompt_with(PASSWORD, PASSWORD)).role == UserRole.ADMIN


def test_unknown_role_is_rejected_by_parser():
    with pytest.raises(SystemExit):
        parse("--role", "SUPERADMIN", "--name", "X", "--email", "x@demo.id")


def test_password_confirmation_mismatch():
    with pytest.raises(InvalidArguments, match="Konfirmasi password tidak sama"):
        build_input(umkm_args(), prompt=prompt_with(PASSWORD, "beda12345"))


@pytest.mark.parametrize(
    ("argv", "password", "message"),
    [
        (("--email", "rina@demo"), PASSWORD, "--email: Format email tidak valid"),
        (("--phone", "12345"), PASSWORD, "--phone: Nomor WhatsApp tidak valid"),
        (("--name", "   "), PASSWORD, "--name: Wajib diisi"),
        ((), "pendek", "Password: Minimal 8 karakter"),
    ],
)
def test_invalid_fields_use_register_messages(argv, password, message):
    base = {"--role": "UMKM", "--name": "Rina", "--email": "rina@demo.id", "--phone": "081234567890"}
    base.update(dict(zip(argv[::2], argv[1::2])))
    args = parse(*[part for pair in base.items() for part in pair])

    with pytest.raises(InvalidArguments, match=message):
        build_input(args, prompt=prompt_with(password, password))
