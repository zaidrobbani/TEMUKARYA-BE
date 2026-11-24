"""Maintenance-only orphan cleanup; dry-run by default, no database writes."""
import argparse
import os
import re
import time

from sqlalchemy import text

from app.modules.profiles.infrastructure.media_storage import KEY_PATTERN, LocalImageStorage


def cleanup_orphans(storage, referenced_keys, *, apply=False, minimum_age=86400):
    if minimum_age < 86400:
        raise ValueError("Orphan grace period must be at least 24 hours")
    candidates = []
    cutoff = time.time() - minimum_age
    for path in storage.root.iterdir():
        if path.is_symlink() or not path.is_file() or path.name in referenced_keys:
            continue
        if not (KEY_PATTERN.fullmatch(path.name) or re.fullmatch(r"\.(?:upload|normalized)-[A-Za-z0-9_-]+", path.name)):
            continue
        if path.stat().st_mtime >= cutoff:
            continue
        candidates.append(path.name)
        if apply:
            if KEY_PATTERN.fullmatch(path.name):
                storage.delete(path.name)
            else:
                path.unlink()  # Errors propagate; no silent failed cleanup.
    return sorted(candidates)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--maintenance-window", action="store_true",
                        help="Confirm media/portfolio writes are stopped across all workers")
    args = parser.parse_args()
    if args.apply and not args.maintenance_window:
        parser.error("--apply requires --maintenance-window and stopped writers")
    from app.core.database import engine
    with engine.connect() as connection:
        connection.exec_driver_sql("START TRANSACTION READ ONLY")
        try:
            referenced = set(connection.scalars(text("SELECT storage_key FROM portfolio_media")))
        finally:
            connection.rollback()
    storage = LocalImageStorage(os.environ.get("PORTFOLIO_STORAGE_ROOT", "/app/storage/portfolios"))
    for key in cleanup_orphans(storage, referenced, apply=args.apply):
        print(f"{'deleted' if args.apply else 'candidate'} {key}")


if __name__ == "__main__":
    main()
