FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependency dulu supaya layer ini ter-cache selama requirements.txt tidak berubah
COPY requirements.txt .
RUN pip install -r requirements.txt

# User non-root; UID disamakan dengan user host agar file hasil bind mount
# (misal file migrasi Alembic) tidak jadi milik root
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} app && useradd -m -u ${UID} -g ${GID} app

COPY --chown=app:app . .
RUN chmod +x docker/entrypoint.sh

USER app

EXPOSE 8000

ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
