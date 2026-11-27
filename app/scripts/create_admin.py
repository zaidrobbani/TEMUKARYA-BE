"""Alias lama: sama dengan `python -m app.scripts.create_user --role ADMIN ...`."""

from app.modules.users.domain.entities import UserRole
from app.scripts.create_user import main

if __name__ == "__main__":
    main(fixed_role=UserRole.ADMIN)
