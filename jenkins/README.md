# Jenkins khusus Tel-U Campus Vote

Instance baru pada **http://localhost:8082**, kontainer `telu-jenkins`. Jenkins lama pada port 8080/8081 tidak diubah. Volume akun/job/credential: `telu-jenkins-home`; volume staging deployment: `telu-jenkins-deploy`. Data suara aplikasi tetap berada pada volume terpisah `polling-db-data`.

## Menjalankan

Di folder `jenkins/`:

```sh
python bootstrap.py
docker compose up -d --build
```

Bootstrap hanya membuat/memakai volume deployment milik instance baru dan menulis path lokal tanpa secret ke `.env`. Tidak ada password hardcoded atau pengaturan yang menonaktifkan autentikasi. Image memiliki Java 21, Python 3, Git, Docker CLI/Compose, serta plugin Pipeline, GitHub, Credentials Binding, Timestamper, dan Stage View.

## Buat akun baru langsung di browser

1. Buka http://localhost:8082.
2. Untuk mendapatkan password awal, jalankan perintah berikut **di terminal komputer sendiri**:

   ```sh
   docker exec telu-jenkins cat /var/jenkins_home/secrets/initialAdminPassword
   ```

3. Masukkan hasilnya ke kolom Administrator password di halaman Unlock Jenkins. Jangan kirim hasilnya ke chat atau rekaman video.
4. Selesaikan pilihan plugin jika diminta. Plugin untuk proyek telah disertakan dalam image.
5. Pada Create First Admin User, buat username dan password baru sendiri. Simpan dalam pengelola password. Password ini untuk login Jenkins; berbeda dari PAT GitHub dan password pemilih.
6. Gunakan Jenkins URL `http://localhost:8082/` ketika diminta.

## Pengaturan job proyek

Ikuti README utama untuk credential `github-pat`, `telu-nim-hmac`, `telu-admin-token`, dan `telu-voter-password`. Pertahankan secret NIM yang sama dengan deployment aplikasi yang sedang dipakai.

- Repository: URL HTTPS repository kelompok, branch `*/main`, script path `Jenkinsfile`.
- **DEPLOY_DIR:** nilai bawaan Jenkinsfile sudah sesuai path yang dicetak `python bootstrap.py`, yaitu `/var/lib/docker/volumes/telu-jenkins-deploy/_data` pada daemon lokal yang diuji. Jika instalasi Docker berbeda, gunakan path yang dicetak bootstrap.
- APP_PORT: `8097`.
- HEALTH_BASE_URL: `http://frontend:80` (controller terhubung ke `app-net`).
- ENABLE_DEMO_TOOLS: `false` untuk penggunaan biasa.
- Ngrok untuk instance baru: `ngrok http 8082`. Payload webhook: `https://ALAMAT-NGROK/github-webhook/`.

Path deployment dibuat sama pada controller dan host daemon Docker. Ini mengatasi perbedaan path Windows dengan kontainer Linux: frontend tetap di-Bind Mount oleh Nginx dari folder pada host daemon. Staging bukan volume suara dan bukan tempat menyimpan data pemilih.

Docker socket memberi Jenkins kemampuan menjalankan deployment pada daemon lokal. Instance hanya dipublikasikan ke loopback komputer. Gunakan hanya repository/pipeline milik kelompok yang dipercaya. Autentikasi Jenkins tetap diperlukan, termasuk saat memakai ngrok.

**Status awal:** konfigurasi default tidak memasang Docker socket. Akun, dashboard Jenkins, Git, dan alat pipeline dapat disiapkan, tetapi stage Build Image/Automated Deployment belum dapat mengakses daemon host. Peninjauan persetujuan otomatis menolak aktivasi socket karena memberikan kendali luas atas kontainer pada komputer. File opsional `docker-compose.host-docker.yml` telah disediakan untuk ditinjau; jangan diaktifkan sebelum pemilik komputer mengizinkan akses ini secara eksplisit. Tidak ada perubahan keamanan pada Jenkins lama.

Untuk berhenti tanpa menghapus akun dan job:

```sh
docker compose stop
```

Jangan memakai `down --volumes` untuk pemeliharaan rutin.

Referensi: [Jenkins Docker](https://www.jenkins.io/doc/book/installing/docker/), [Docker Bind Mounts](https://docs.docker.com/engine/storage/bind-mounts/).
