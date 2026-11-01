# Portfolio Media MVP

## Changed files for this implementation

New application files:

- [domain/media.py](../app/modules/profiles/domain/media.py)
- [application/media_use_cases.py](../app/modules/profiles/application/media_use_cases.py)
- [infrastructure/media_repository.py](../app/modules/profiles/infrastructure/media_repository.py)
- [infrastructure/media_storage.py](../app/modules/profiles/infrastructure/media_storage.py)
- [infrastructure/media_cleanup.py](../app/modules/profiles/infrastructure/media_cleanup.py)
- [presentation/media_router.py](../app/modules/profiles/presentation/media_router.py)
- [presentation/media_upload.py](../app/modules/profiles/presentation/media_upload.py)

Updated integration/configuration files:

- [presentation/dependencies.py](../app/modules/profiles/presentation/dependencies.py)
- [presentation/router.py](../app/modules/profiles/presentation/router.py)
- [requirements.txt](../requirements.txt), [Dockerfile](../Dockerfile),
  [docker-compose.yml](../docker-compose.yml), [.gitignore](../.gitignore),
  [.dockerignore](../.dockerignore)

New tests:

- [test_media_storage.py](../tests/modules/profiles/test_media_storage.py)
- [test_media_service.py](../tests/modules/profiles/test_media_service.py)
- [test_media_router.py](../tests/modules/profiles/test_media_router.py)
- [test_media_mysql_integration.py](../tests/modules/profiles/test_media_mysql_integration.py)

Updated test fixtures/regressions:

- [conftest.py](../tests/modules/profiles/conftest.py)
- [test_portfolio_router.py](../tests/modules/profiles/test_portfolio_router.py)
- [test_portfolio_mysql_integration.py](../tests/modules/profiles/test_portfolio_mysql_integration.py)
- [test_security_regressions.py](../tests/modules/profiles/test_security_regressions.py)

This document is new. Existing changes to app/main.py predate the media task;
the media implementation does not change app/main.py, app/core, users, auth, or migrations.

## Scope and configuration

Private JPEG, PNG and WebP images only. No static mount, public URLs, external
storage, video, PDF, SVG, or authentication changes. Profiles auth still returns
401 until JWT integration; examples below describe the contract after that work.

`PORTFOLIO_STORAGE_ROOT` defaults to `/app/storage/portfolios`. Compose mounts the
`portfolio_uploads` named volume at `/app/storage`; keep custom roots beneath that
directory for persistence. Other absolute roots require an explicitly provisioned
private persistent mount with correct ownership. The image prepares the default
directory for its non-root `app` user. Host `/storage/` uploads are excluded from
Git and Docker build context.

Install the pinned Pillow dependency by rebuilding the API image. Do not delete
volumes. A Compose recreate is needed to apply the new volume configuration.
Neither startup code nor these tests create/alter the MySQL schema.

## Architecture and validation

- [Domain contracts](../app/modules/profiles/domain/media.py): media entity,
  repository/storage interfaces, limits, framework-independent failures.
- [Application service](../app/modules/profiles/application/media_use_cases.py):
  ownership, count limit, cover/order, transaction boundary and file compensation.
- Infrastructure: SQLAlchemy queries and local storage/Pillow decoder.
- Presentation: bounded streaming multipart parser and six authenticated routes.

The multipart endpoint deliberately uses `Request.stream()` instead of
`UploadFile`, which would spool the complete multipart file before endpoint
validation. Exactly one `file` part is accepted, with bounded headers/framing.
The parser stops at more than 5 MiB of file bytes (or 5 MiB + 64 KiB total framing).
Input is staged in the volume, never under a client-selected path. The storage
layer independently reads in 64 KiB chunks and enforces the same limit.

Pillow verifies and decodes the actual image, rejects corrupt/animated images,
decompression bombs and dimensions above 4096x4096. Only one decoder per worker
process runs at a time, bounding concurrent pixel allocations. EXIF orientation
is applied, then a fresh pixel-only image is encoded without EXIF, ICC or XMP.
Normalized output is also limited to 5 MiB. MIME and size describe stored bytes,
not client claims. PNG bytes named `photo.jpg` with a spoofed Content-Type are
accepted as PNG. Unsupported signatures return 415; recognizable corrupt images
return 422. Empty files and invalid dimensions also return 422.

Final keys are random UUID-based opaque relative filenames. No client filename,
path, `storage_key`, MIME, size or ownership is trusted. File operations reject
traversal and symlinks. Storage directories must remain writable only by trusted
application/operators; external root/administrator mutation is outside this model.

## API

All paths below have prefix `/profiles/freelancer/portfolios/{portfolio_id}/media`.

| Method | Suffix | Success |
|---|---|---|
| POST | empty | 201, metadata for the uploaded image |
| GET | empty | 200, ordered metadata array |
| GET | `/{media_id}/file` | 200, authorized image bytes |
| PATCH | `/{media_id}/cover` | 200, updated metadata array |
| PATCH | `/order` | 200, updated metadata array |
| DELETE | `/{media_id}` | 204, empty body |

```sh
curl -X POST "$API/profiles/freelancer/portfolios/$PORTFOLIO_ID/media" \
  -H "Authorization: Bearer $TOKEN" -F 'file=@image.png'
curl -X PATCH "$API/profiles/freelancer/portfolios/$PORTFOLIO_ID/media/order" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"media_ids":["second-media-uuid","first-media-uuid"]}'
```

Example upload response (storage key is never returned):

```json
{
  "id": "server-generated-media-uuid",
  "portfolio_id": "owned-portfolio-uuid",
  "mime_type": "image/png",
  "file_size_bytes": 8421,
  "uploaded_at": "2026-11-01T10:00:00.123",
  "sort_order": 0,
  "is_cover": true
}
```

Errors: 401 unauthenticated, 403 non-Freelancer, 404 missing/foreign portfolio or
media not belonging to that portfolio, 409 five-image limit, 413 excessive raw or
normalized size, 415 unsupported type, 422 malformed input/image/order, 503 storage
unavailable or committed deletion with pending file cleanup. Database failures use
the existing server error behavior; they are not converted into successful uploads.

Downloads return `Cache-Control: private, no-store` and `X-Content-Type-Options:
nosniff`. File streams are opened only after authorization and always closed.
There is no static file URL. Send the same authenticated request for image bytes.

## Ownership, locks and consistency

The parent portfolio is looked up by both ID and authenticated freelancer ID.
Writers acquire `SELECT ... FOR UPDATE` on that parent before listing/modifying
media. Locking reads avoid stale REPEATABLE READ snapshots. All media writers and
the HTTP parent-delete path follow the same parent lock order. This serializes
uploads, count checks, order, cover changes and deletes per portfolio in MySQL.
The first upload becomes cover; deleting a cover selects the first remaining
image in `(sort_order, id)` order. Reordering requires all current IDs exactly once.
The application preserves one cover, but the schema has no corresponding unique
constraint: direct SQL writers must obey the same protocol.

Input and normalized staging files live on the same volume. Normalized output is
flushed/fsynced and atomically renamed before metadata insert and UoW commit.
An insert/commit exception triggers removal of the newly created file. A failed
compensation is logged with its key and returns 503 for operator cleanup. The
request's existing session teardown rolls back uncommitted metadata.

Delete commits metadata first, then unlinks files. A DB failure leaves the files
intact. A file failure after commit is logged, returns 503, and leaves an orphan
for cleanup; metadata is already gone and retrying the media ID can return 404.
Parent DELETE uses the same strategy and snapshots all media keys before removing
metadata. MySQL cascade alone cannot clean files. Direct DB parent deletion can
therefore leave orphan files too.

Filesystem and MySQL are **not an atomic transaction**. Process termination can
leave staging files or unreferenced final files. An ambiguous network failure
during commit can also require manual reconciliation of missing referenced files.
Backup and restore both the database and volume together.

## Orphan cleanup

Dry-run (read-only database query, no deletion):

```sh
docker compose exec -T api python -m app.modules.profiles.infrastructure.media_cleanup
```

After stopping portfolio/media writes on **all workers**, inspect candidates and
run in a maintenance window:

```sh
docker compose exec -T api python -m app.modules.profiles.infrastructure.media_cleanup \
  --apply --maintenance-window
```

Only recognized generated keys/staging filenames older than 24 hours and absent
from `portfolio_media.storage_key` are eligible. Symlinks, unknown files and
referenced keys are preserved. Errors propagate. Maintenance mode is an operator
confirmation, not an automatic write lock; do not apply concurrently with writers.
Schedule this process operationally after deployment; no background deletion job
is silently enabled by the application.

## Tests and remaining integration

```sh
docker compose exec -T api python -m pytest -q
docker compose exec -T -e TEMUKARYA_MYSQL_INTEGRATION=1 api python -m pytest -q -rP
```

Tests use temporary directories, dependency overrides only on test applications,
and isolated SQLite tables. Opt-in MySQL tests create random UUID users/profiles/
portfolios/media in an outer rollback-only transaction, test locks with a second
connection, and verify all four tables contain zero test rows after rollback.
Their UoW flushes without committing, so true multi-writer committed visibility
and crash recovery still need dedicated deployment/load tests.

After JWT integration: test authenticated mobile file loading and token expiry,
set request deadlines/rate limits and decoder worker/memory budgets, configure
volume backups, monitor 503/cleanup logs, schedule maintenance cleanup, and test
concurrent writes/crash recovery. Auth remains fail-closed in the meantime.
