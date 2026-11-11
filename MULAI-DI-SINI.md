# Mulai memakai Tel-U Campus Vote

1. Buka Docker Desktop dan tunggu hingga siap.
2. Buka terminal di folder proyek, lalu jalankan:

```sh
python tools/setup_secrets.py
docker compose up -d --build --wait
```

3. Buka [login](http://localhost:8097/login.html) atau [dashboard publik](http://localhost:8097/dashboard.html).

Username: NIM 12 digit, diawali **1010**, lalu delapan angka. Contoh: **101012345678**. Password: **12345678**.

Satu NIM hanya dapat memilih sekali. Sesudah memilih, pesan terima kasih dan tanggal/jam WIB muncul, serta tombol dikunci. Logout/login ulang tidak menghapus status itu.

Nama panggilan opsional hanya untuk tinjauan lokal. NIM asli tidak disimpan atau ditampilkan pada dashboard. Semua pilihan lokasi telah dibatasi ke Telkom University Bandung.

Simpan file `.env` secara privat dan pertahankan key NIM yang sama. File itu tidak masuk ZIP. Jangan menggantinya untuk memakai volume lama.

Untuk menghentikan aplikasi tanpa menghilangkan data:

```sh
docker compose stop
```

Pengelolaan dan seed demo memerlukan token operator yang berbeda dari password pemilih. Petunjuk lengkap, konfigurasi Jenkins, dan batasan login ada di [README](README.md).

made by: Steven Romallo
