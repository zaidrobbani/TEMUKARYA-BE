from app.core.email import EmailMessage
from app.modules.users.domain.entities import User


def email_verification_message(user: User, link: str) -> EmailMessage:
    intro = "Buka tautan di bawah untuk memverifikasi email akun TEMUKARYA kamu."
    note = "Tautan berlaku 24 jam. Abaikan email ini kalau kamu tidak merasa mendaftar."
    return EmailMessage(
        to=user.email,
        subject="Verifikasi email akun TEMUKARYA",
        text=f"Halo {user.name},\n\n{intro}\n\n{link}\n\n{note}\n",
    )


def password_reset_message(user: User, link: str) -> EmailMessage:
    intro = "Buka tautan di bawah untuk membuat kata sandi baru akun TEMUKARYA kamu."
    note = "Tautan berlaku 30 menit. Abaikan email ini kalau kamu tidak memintanya."
    return EmailMessage(
        to=user.email,
        subject="Atur ulang kata sandi TEMUKARYA",
        text=f"Halo {user.name},\n\n{intro}\n\n{link}\n\n{note}\n",
    )
