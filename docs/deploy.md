# Panduan Deploy Backend TEMUKARYA

Panduan untuk menjalankan backend di server BCC (`temukarya.bccdev.id`) memakai Docker Compose.
File yang dipakai: `docker-compose.prod.yml`, `docker/nginx.conf`, `.env.production.example`.

## Gambaran

```
Android / Admin web
        │  https://temukarya.bccdev.id
        ▼
Proxy BCC (proxy.bccdev.id)          ← satu-satunya jalan masuk dari internet
        │  http → port 80 VM
        ▼
VM 10.202.0.82 (Ubuntu 24.04)
 └─ Docker Compose "temukarya-prod"
     ├─ nginx  :80               reverse proxy, WebSocket, batas upload 60 MB
     ├─ api    127.0.0.1:8000    FastAPI (uvicorn, 1 worker), migrasi otomatis saat start
     ├─ db     127.0.0.1:3306    MySQL 8.4 (volume mysql_data)
     └─ mailpit 127.0.0.1:8025   opsional, kalau belum ada SMTP asli
```

VM tidak punya IP publik. Dari luar hanya bisa lewat domain (HTTP) dan SSH lewat `proxy.bccdev.id:11119`.
MySQL, API langsung, dan Mailpit sengaja hanya di-bind ke `127.0.0.1`; aksesnya dari laptop lewat SSH tunnel.

| Item | Nilai |
|---|---|
| SSH | `ssh dev@proxy.bccdev.id -p 11119` |
| OS | Ubuntu 24.04 LTS, disk 28,5 GB |
| IP internal | `10.202.0.82` |
| Domain | `temukarya.bccdev.id` |
| Base URL Android | `https://temukarya.bccdev.id/api/v1/` |
| WebSocket chat | `wss://temukarya.bccdev.id/api/v1/conversations/{id}/ws` |
| Swagger | `https://temukarya.bccdev.id/docs` |

## 0. Siapkan dulu di laptop

- Akses SSH ke server (perintah di atas).
- Akses repo GitHub `zaidrobbani/TEMUKARYA-BE` (kalau private, lihat langkah 4).
- **Akun SMTP** untuk email verifikasi & reset password. Paling gampang Gmail + App Password:
  aktifkan 2-Step Verification, lalu buat di https://myaccount.google.com/apppasswords (16 huruf).
  Login di aplikasi **wajib** verifikasi email dulu, jadi tanpa SMTP user baru tidak bisa login
  (alternatifnya Mailpit, lihat [Email tanpa SMTP asli](#email-tanpa-smtp-asli-mailpit)).
- `secrets/firebase-service-account.json` (push notifikasi FCM). Boleh menyusul; tanpa file ini push nonaktif, fitur lain tetap jalan.
- `GOOGLE_CLIENT_ID` (Web client ID yang sama dengan yang dipakai Android untuk Google Sign-In). Boleh kosong kalau login Google belum dipakai.

Opsional, supaya perintah SSH lebih pendek, tambahkan ke `~/.ssh/config` di laptop:

```
Host temukarya
    HostName proxy.bccdev.id
    Port 11119
    User dev
```

Setelah itu cukup `ssh temukarya`. Contoh perintah di bawah memakai alias ini.

## 1. Masuk ke server & update paket

Langkah 1–9 dijalankan **di dalam server** (prompt `dev@fe-zaid-pg:~$`), bukan di laptop,
kecuali yang ditulis "dari laptop". `apt-get` hanya ada di server (Ubuntu).

```bash
ssh temukarya
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl git openssl netcat-openbsd
```

## 2. Install Docker Engine + Compose

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker $USER
exit            # logout, lalu ssh lagi supaya grup docker aktif
```

Cek setelah login ulang:

```bash
docker run --rm hello-world
docker compose version
```

## 3. Pastikan domain diteruskan ke port 80 VM

Port 80 di VM harus kosong:

```bash
sudo ss -tlnp | grep ':80 '      # tidak ada output = kosong
```

Kalau terisi (misalnya nginx/apache bawaan), matikan: `sudo systemctl disable --now nginx` (atau `apache2`).

Hasil uji 2026-11-27: proxy mengarah ke **port 80** dan meloloskan upload 55 MB. Langkah ini hanya perlu diulang kalau BCC mengubah konfigurasi proxy.

Yang sudah diketahui: proxy BCC (openresty) mengalihkan `http://` → `https://` dan menangani TLS sendiri,
jadi `PUBLIC_BASE_URL=https://temukarya.bccdev.id`. Selama belum ada aplikasi yang mendengarkan di VM,
domain menjawab **`502 Bad Gateway`**; itu normal sebelum deploy.

Uji port mana yang dituju proxy dengan menyalakan server uji di beberapa port sekaligus (di server):

```bash
for p in 80 3000 5000 8000 8080; do
  mkdir -p /tmp/cek/$p && echo "port $p" > /tmp/cek/$p/index.html
  sudo nohup python3 -m http.server $p --bind 0.0.0.0 --directory /tmp/cek/$p >/dev/null 2>&1 &
done
sleep 1 && sudo ss -tlnp | grep python3
```

Dari laptop:

```bash
curl -s https://temukarya.bccdev.id/
```

- Keluar `port 80` → sesuai default, `HTTP_PORT=80`.
- Keluar `port <N>` lain → isi `HTTP_PORT=<N>` di `.env` (langkah 5).
- Masih `502` → proxy mengarah ke port di luar daftar itu, atau firewall VM menutupnya (`sudo ufw status`).
  Tanyakan port tujuan ke admin BCC.

Matikan server uji: `sudo pkill -f "http.server"`.

## 4. Clone repo

```bash
cd ~
git clone https://github.com/zaidrobbani/TEMUKARYA-BE.git temukarya-BE
cd temukarya-BE
git checkout main          # branch yang di-deploy
```

Kalau repo **private**, pakai deploy key (read-only, tidak perlu token pribadi):

```bash
ssh-keygen -t ed25519 -C "temukarya-server" -f ~/.ssh/temukarya_deploy -N ""
cat ~/.ssh/temukarya_deploy.pub
```

Tempel public key itu di GitHub: repo → Settings → Deploy keys → Add deploy key (jangan centang write access). Lalu:

```bash
cat >> ~/.ssh/config <<'EOF'
Host github.com
    IdentityFile ~/.ssh/temukarya_deploy
    IdentitiesOnly yes
EOF
git clone git@github.com:zaidrobbani/TEMUKARYA-BE.git ~/temukarya-BE
```

Kalau port 22 ke GitHub diblokir, tambahkan `HostName ssh.github.com` dan `Port 443` di blok `Host github.com` tadi.

## 5. Buat `.env` produksi

```bash
cd ~/temukarya-BE
cp .env.production.example .env
sed -i \
  -e "s/^DB_PASSWORD=.*/DB_PASSWORD=$(openssl rand -hex 24)/" \
  -e "s/^DB_ROOT_PASSWORD=.*/DB_ROOT_PASSWORD=$(openssl rand -hex 24)/" \
  -e "s/^JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$(openssl rand -hex 32)/" \
  .env
chmod 600 .env
nano .env
```

Yang masih perlu diisi manual di `nano`:

| Variabel | Isi |
|---|---|
| `PUBLIC_BASE_URL` | `https://temukarya.bccdev.id` (pakai `http://` kalau di langkah 3 https tidak jalan). Dipakai untuk tautan di email. |
| `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM` | Alamat Gmail + App Password 16 huruf (tanpa spasi). |
| `GOOGLE_CLIENT_ID` | Web client ID Google Sign-In, atau kosongkan. |
| `HTTP_PORT` | Biarkan `80`, kecuali admin BCC menyebut port lain. |

Catatan penting:
- `COMPOSE_FILE=docker-compose.prod.yml` di `.env` membuat semua `docker compose ...` di folder ini otomatis memakai file produksi.
  **Jangan** jalankan `docker-compose.yml` (dev) di server: itu memakai `--reload` dan membuka port MySQL.
- `DB_PASSWORD` / `DB_ROOT_PASSWORD` hanya dipakai MySQL saat **pertama kali** volume dibuat. Mengubahnya belakangan tidak mengganti password di DB.
- Simpan salinan `.env` server di tempat aman (password manager). Jangan di-commit.

Cek koneksi SMTP dari server (kadang port keluar diblokir):

```bash
nc -vz smtp.gmail.com 587     # harus "succeeded"
```

## 6. Upload kredensial Firebase (opsional)

Dari **laptop**, di folder repo:

```bash
ssh temukarya "mkdir -p ~/temukarya-BE/secrets"
scp secrets/firebase-service-account.json temukarya:~/temukarya-BE/secrets/
ssh temukarya "chmod 600 ~/temukarya-BE/secrets/firebase-service-account.json && id -u"
```

Container berjalan sebagai UID 1000. Kalau `id -u` di server bukan `1000`, pakai `chmod 644` supaya file tetap bisa dibaca container.
Folder `secrets/` di-mount read-only ke `/app/secrets` dan tidak ikut masuk image (`.dockerignore`).

## 7. Jalankan

```bash
cd ~/temukarya-BE
docker compose up -d --build --wait
docker compose ps
```

`--wait` menunggu sampai `db`, `api`, dan `nginx` sehat. Migrasi Alembic jalan otomatis saat container `api` start
(lihat `docker compose logs api | head -30`; harus ada "Menjalankan migrasi database..." tanpa error).

## 8. Verifikasi

Di server:

```bash
curl -s http://127.0.0.1:8000/api/v1/health      # langsung ke API
curl -s http://127.0.0.1/api/v1/health           # lewat nginx
```

Dari laptop / HP:

```bash
curl -s https://temukarya.bccdev.id/api/v1/health
# {"success":true,"message":"API berjalan","data":{"env":"production","database":"connected"}}
```

Lalu buka `https://temukarya.bccdev.id/docs` dan coba alur singkat:
1. `POST /api/v1/auth/register` dengan email asli → cek email verifikasi masuk, klik tautannya.
2. `POST /api/v1/auth/login` → dapat token.
3. Kalau sempat, tes chat real-time dari Android (WebSocket lewat proxy BCC).

## 9. Buat akun (admin, UMKM, freelancer)

Akun dari script ini **langsung terverifikasi**: tidak perlu klik email, bisa langsung login. Cocok untuk admin,
akun demo, dan akun uji tim Android. Validasinya sama dengan register (format email, nomor WA dinormalisasi ke `+62…`,
password minimal 8 karakter); UMKM/freelancer juga tercatat sudah menyetujui S&K.

```bash
# Admin (login di admin web: POST /api/v1/auth/admin/login)
docker compose exec api python -m app.scripts.create_user --role ADMIN --name "Admin" --email admin@temukarya.id

# UMKM / freelancer (login di aplikasi: POST /api/v1/auth/login), --phone wajib
docker compose exec api python -m app.scripts.create_user --role UMKM --name "Rina Pratiwi" --email umkm@demo.id --phone 081234567890
docker compose exec api python -m app.scripts.create_user --role FREELANCER --name "Dimas Saputra" --email freelancer@demo.id --phone 081298765432
```

Password diminta interaktif (dua kali). Untuk membuat banyak akun sekaligus, kirim password lewat stdin (perhatikan `-T`):

```bash
echo 'Demo12345' | docker compose exec -T api python -m app.scripts.create_user \
  --role FREELANCER --name "Freelancer 2" --email freelancer2@demo.id --phone 081200000002 --password-stdin
```

Perintah lama `python -m app.scripts.create_admin --name ... --email ...` masih bisa dipakai (sama dengan `--role ADMIN`).
Profil UMKM/freelancer (bio, skill, dsb.) diisi setelah login lewat aplikasi, sama seperti akun hasil register.

| Pesan | Arti |
|---|---|
| `Gagal membuat akun: Email ... sudah terdaftar` | Email sudah dipakai akun lain. |
| `Gagal membuat akun: --phone wajib diisi untuk role UMKM` | UMKM/FREELANCER wajib punya nomor WA. |
| `Gagal membuat akun: --email: Format email tidak valid ...` | Pesan validasi sama dengan API register; beberapa error digabung dengan `;`. |
| `Gagal membuat akun: Konfirmasi password tidak sama dengan password` | Ketik ulang password. |
| `argument --role: invalid choice` | Role hanya `ADMIN`, `UMKM`, `FREELANCER` (huruf besar/kecil bebas). |

## 10. CI/CD (GitHub Actions)

Workflow: `.github/workflows/ci-cd.yml`.

| Kejadian | Yang jalan |
|---|---|
| Pull request (ke branch mana pun) | **Test** (migrasi + seluruh test termasuk integrasi MySQL, di MySQL 8.0 seperti server) dan **build image**. |
| Push/merge ke `main` | Test + build, lalu kalau lolos **deploy** ke server lewat SSH (`docker/deploy.sh`). |
| Manual (tab Actions → CI/CD → Run workflow, branch `main`) | Sama dengan push ke `main`. |

`docker/deploy.sh` di server: backup DB + upload → `git pull --ff-only` branch `main` → `docker compose up -d --build`
→ tunggu API `healthy` (maks 3 menit, kalau gagal log API ditampilkan di Actions) → hapus image lama.

### Setup sekali

**a. Di laptop**, buat key khusus GitHub Actions (jangan pakai key pribadi):

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/temukarya_actions -N ""
ssh-keyscan -p 11119 proxy.bccdev.id 2>/dev/null     # simpan outputnya untuk DEPLOY_KNOWN_HOSTS
```

**b. Di server**, izinkan key itu **hanya** untuk menjalankan deploy (kalau key bocor, orang tidak dapat shell):

```bash
echo 'command="bash $HOME/temukarya-BE/docker/deploy.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ISI_DENGAN_ISI_temukarya_actions.pub' >> ~/.ssh/authorized_keys
```

Ganti `ISI_DENGAN_ISI_temukarya_actions.pub` dengan satu baris isi `~/.ssh/temukarya_actions.pub`.
Pastikan juga repo di server mengikuti branch `main` (`git checkout main`) dan `main` sudah berisi file produksi.

**c. Di GitHub**: repo → Settings → Secrets and variables → Actions → **New repository secret**:

| Secret | Isi |
|---|---|
| `DEPLOY_SSH_KEY` | Seluruh isi `~/.ssh/temukarya_actions` (private key, termasuk baris `BEGIN`/`END`). |
| `DEPLOY_KNOWN_HOSTS` | Output `ssh-keyscan` di langkah a. |

Opsional (tab **Variables**), kalau server pindah: `DEPLOY_HOST` (default `proxy.bccdev.id`), `DEPLOY_PORT` (`11119`),
`DEPLOY_USER` (`dev`), `DEPLOY_PATH` (`~/temukarya-BE`).

**d. Uji**: tab Actions → CI/CD → Run workflow → branch `main`. Job **Deploy ke server** harus hijau dan
langkah "Cek dari internet" menampilkan respons `/health`.

Kalau langkah Deploy gagal `Connection timed out`, berarti port SSH proxy BCC tidak bisa diakses dari server GitHub.
Alternatifnya pasang **self-hosted runner** di VM (repo → Settings → Actions → Runners → New self-hosted runner,
ikuti perintahnya di server), lalu ubah `runs-on` job `deploy` menjadi `self-hosted` dan ganti langkah SSH dengan
`bash ~/temukarya-BE/docker/deploy.sh`.

## Update ke versi terbaru

Normalnya otomatis: merge ke `main` → CI/CD deploy (lihat langkah 10). Deploy manual (kalau Actions bermasalah):

```bash
ssh temukarya
cd ~/temukarya-BE
bash docker/deploy.sh
```

Kalau perubahan hanya di `.env`, cukup `docker compose up -d` (tanpa build).
Kalau `docker/nginx.conf` berubah: `docker compose restart nginx`.

## Operasional harian

```bash
docker compose ps                         # status
docker compose logs -f api                # log API (Ctrl+C keluar)
docker compose logs --since 1h nginx      # log akses nginx
docker compose restart api                # restart API saja
docker compose down                       # stop semua (data aman)
docker system df                          # pemakaian disk Docker
```

**Jangan** pakai `docker compose down -v` di server: `-v` menghapus volume database dan file upload.

### Akses database dari laptop

```bash
ssh -N -L 3307:127.0.0.1:3306 temukarya
```

Biarkan terminal itu terbuka, lalu konek DBeaver/MySQL Workbench ke `127.0.0.1:3307` dengan `DB_USER` / `DB_PASSWORD` dari `.env` server.

### Backup

```bash
~/temukarya-BE/docker/backup.sh
```

Skrip ini membuat dua file di `~/backups`: dump database (`db-*.sql.gz`) dan arsip file upload
(foto profil, portofolio, lampiran, hasil kerja, chat; `uploads-*.tar.gz`).

Unduh ke laptop: `scp temukarya:~/backups/db-2026-11-27-0100.sql.gz .`

Jadwalkan harian:

```bash
mkdir -p ~/backups
crontab -e
# tambahkan baris:
0 19 * * * $HOME/temukarya-BE/docker/backup.sh >> $HOME/backups/backup.log 2>&1 && find $HOME/backups -name '*.gz' -mtime +7 -delete
```

(`19:00 UTC` = 02:00 WIB; backup lebih dari 7 hari dihapus.)

### Restore database

```bash
cd ~/temukarya-BE
gunzip -c ~/backups/db-XXXX.sql.gz \
  | docker compose exec -T db sh -c 'mysql -u root -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'
```

## Rollback

```bash
cd ~/temukarya-BE
git log --oneline -10
```

- **Versi baru tidak menambah migrasi**: `git checkout <commit-lama>` lalu `docker compose up -d --build --wait`.
- **Versi baru menambah migrasi**: turunkan dulu migrasinya **sebelum** checkout (file migrasinya masih ada di versi baru):
  `docker compose exec api alembic downgrade -1`, lalu checkout + build seperti di atas.
  Kalau downgrade gagal, restore dari backup.

Kembali ke branch setelah masalah selesai: `git checkout main && git pull`.

## Email tanpa SMTP asli (Mailpit)

Untuk demo internal kalau belum ada akun SMTP. Email tidak benar-benar terkirim, tapi ditangkap Mailpit dan bisa dibuka manual.

Ubah `.env`:

```
COMPOSE_PROFILES=mailpit
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=false
```

Jalankan `docker compose up -d`, lalu dari laptop:

```bash
ssh -N -L 8025:127.0.0.1:8025 temukarya
```

Buka http://localhost:8025, klik tautan verifikasi di email (tautannya tetap ke `PUBLIC_BASE_URL`, jadi bisa dibuka dari mana saja).

## Troubleshooting

| Gejala | Penyebab & solusi |
|---|---|
| `permission denied ... docker.sock` | Belum logout-login setelah `usermod -aG docker`. |
| `db` unhealthy, log `Fatal glibc error: CPU does not support x86-64-v2` | CPU VM tidak mendukung x86-64-v2 (wajib untuk `mysql:8.4`). Isi `MYSQL_IMAGE=mysql:8.0-debian` di `.env`, lalu `docker compose down -v && docker compose up -d` (hanya `-v` kalau DB belum berisi data). Alternatif tanpa ubah image: minta admin mengganti tipe CPU VM ke `host`. |
| `curl 127.0.0.1/api/v1/health` OK, tapi domain 502/timeout | Proxy BCC tidak mengarah ke port `HTTP_PORT`. Ulangi langkah 3 / tanya admin BCC. |
| Domain 502 dari nginx (`Server: nginx`) | API belum sehat. `docker compose ps`, `docker compose logs api`. |
| API restart terus, log `JWT_SECRET_KEY` | Nilainya kosong / kurang dari 32 karakter. |
| `Access denied for user 'temukarya'` | `DB_PASSWORD` diubah setelah volume MySQL dibuat. Kembalikan nilai lama, atau ganti password user di MySQL. |
| Register sukses tapi email tidak masuk | `docker compose logs api | grep -i smtp`. Cek App Password, `SMTP_USE_TLS=true`, `nc -vz smtp.gmail.com 587`. Cek folder spam. Darurat: Mailpit. |
| Tautan di email mengarah ke `localhost` | `PUBLIC_BASE_URL` belum diisi domain. Ubah lalu `docker compose up -d`. |
| Upload besar gagal `413` | Batas nginx 60 MB. Kalau di bawah itu tetap `413` dan header bukan dari nginx kita, batasnya di proxy BCC. |
| Chat real-time tidak tersambung, REST jalan | Proxy BCC mungkin tidak meneruskan header WebSocket. Cek dengan admin BCC; sementara Android bisa fallback polling REST. |
| Push notifikasi tidak muncul | `docker compose logs api | grep -i firebase`. Cek path `FIREBASE_CREDENTIALS_FILE` dan izin file (langkah 6). |
| Disk penuh | `docker system df`, `docker image prune -a -f`, hapus backup lama di `~/backups`. |

## Keputusan yang perlu dicek

| Keputusan | Alasan / dampak |
|---|---|
| Proxy BCC meneruskan `temukarya.bccdev.id` ke **port 80** VM; TLS (https) dan redirect http→https ditangani proxy. | **Terverifikasi 2026-11-27** dengan server uji (langkah 3). |
| nginx dijalankan sebagai container di compose, bukan di-install di host. | Konfigurasi ikut versi di repo (`docker/nginx.conf`), server cukup punya Docker. |
| Uvicorn **1 worker**. | Hub WebSocket chat dan dispatcher push masih in-memory per proses; multi-worker membuat pesan real-time tidak sampai ke semua koneksi. |
| MySQL, API langsung, dan Mailpit hanya di `127.0.0.1`. | Tidak ada akses DB dari luar selain SSH tunnel. |
| Server `temukarya.bccdev.id` memakai **MySQL 8.0 (`mysql:8.0-debian`)**, bukan 8.4 seperti dev. | CPU VM tidak mendukung x86-64-v2. Sudah dicek di 8.0.46 (2026-11-27): `alembic upgrade head` dari nol + seluruh test termasuk integrasi MySQL lolos. MySQL 8.0 sudah EOL (April 2026); kembali ke 8.4 kalau tipe CPU VM bisa diganti admin. |
| Akun admin/demo/uji dibuat lewat `app.scripts.create_user` dan langsung terverifikasi; admin tidak diberi `terms_accepted_at`. | Admin tidak melewati layar S&K aplikasi. UMKM/freelancer dari script setara akun hasil register + verifikasi email. |
| Swagger `/docs` tetap terbuka di produksi. | Memudahkan tim Android & admin web. Bisa ditutup belakangan kalau perlu. |
| **Belum ada CORS middleware** di `app/main.py`. | Android tidak terpengaruh, tetapi admin web yang berjalan di browser dengan origin lain akan diblokir browser. Perlu ditambah begitu origin admin web diketahui. |
| Email produksi via Gmail SMTP (App Password), cadangan Mailpit. | Verifikasi email wajib sebelum login (keputusan auth), jadi SMTP harus jalan sebelum Android dites ke server. |
| CI/CD GitHub Actions: test di MySQL 8.0 (sama dengan server) di setiap PR dan push ke `main`; deploy otomatis hanya dari `main` lewat SSH dengan key yang dikunci `command=` ke `docker/deploy.sh`. | Server tetap menarik kode dari GitHub (tidak ada registry image); deploy selalu backup dulu. **Belum terverifikasi** apakah port SSH proxy BCC bisa diakses runner GitHub, cadangannya self-hosted runner. |
| Batas body nginx 60 MB (hasil kerja maks 50 MB). | Proxy BCC **terverifikasi** meloloskan body 55 MB (2026-11-27). |
| Kredensial Firebase di-mount dari `secrets/` dan dikeluarkan dari image (`.dockerignore`). | Secret tidak ikut tersimpan di layer image. |
