# Hasil verifikasi aktual

## Jenkins terpisah · 11 November 2026 (WIB)

- Jenkins 2.580.2 berbasis Java 21 dibangun dari image resmi dengan alat Python 3.13.5, Git, Docker CLI, Docker Compose 5.7.1, dan Buildx 0.38.1.
- Kontainer baru `telu-jenkins` healthy, dipublikasikan hanya pada `127.0.0.1:8082`. Halaman Unlock Jenkins mengembalikan HTTP 200 dan diperiksa di browser.
- Volume akun/job `telu-jenkins-home` dan staging `telu-jenkins-deploy` terpisah dari Jenkins lama dan `polling-db-data`. Jenkins lama 8080/8081 serta aplikasi voting tetap berjalan; tidak ada password lama yang diubah.
- `jenkins/bootstrap.py` dijalankan dan konfigurasi Compose valid. Lokasi staging host daemon disamakan dengan lokasi pada controller untuk Bind Mount deployment mendatang.
- Plugin Pipeline, Git, GitHub, Credentials Binding, Timestamper, dan Stage View disertakan dalam image. Keberadaan plugin Pipeline pada volume baru diperiksa.
- Konfigurasi default **tanpa Docker socket host**; ketidakhadirannya diperiksa di kontainer baru. Aktivasi socket sempat ditolak peninjauan persetujuan otomatis karena memberikan kendali luas atas daemon host. File override opsional tersedia, tetapi belum diaktifkan dan memerlukan persetujuan eksplisit pengguna.
- Password awal tidak dicetak ke chat, source, atau ZIP. Pembukaan kunci dan pembuatan username/password baru perlu dilakukan pengguna langsung di browser. Akun admin baru, job, PAT, webhook, ngrok, serta pipeline end-to-end belum selesai/dijalankan pada instance ini.

## Pembaruan kandidat · 9 November 2026 (WIB)

Nama, jabatan, nomor, serta path delapan foto terpusat di `config.json`. Opsi API tetap A/B. Visi-misi dan logika backend voting tidak diubah.

| Pemeriksaan yang dijalankan ulang | Hasil |
| --- | --- |
| Unit/integration Python | **30 lulus**, termasuk sesi, duplikasi bersamaan, HMAC, migrasi, persistensi, dan SSE |
| Sintaks JavaScript | `common.js`, `vote.js`, `dashboard.js`, dan `login.js` lulus `node --check` |
| Aset lokal | Delapan PNG sesuai konfigurasi; semua byte identik dengan lampiran ZIP |
| Nginx setelah deployment utama | Delapan URL PNG mengembalikan HTTP 200 dan byte yang sama dengan sumber |
| Konfigurasi kandidat backend | `/config` pada aplikasi utama sesuai konfigurasi baru |
| Compose | Valid; backend dibangun dan dibuat ulang, kedua layanan healthy |
| Data utama | SHA-256 `votes.json` identik sebelum/sesudah deployment; 0 suara dan 0 penanda hak pilih tetap utuh |
| Staging Jenkins | Helper `prepare_deploy.py` menyalin seluruh frontend termasuk PNG secara byte-identik ke direktori persisten uji; secret uji tetap sama |
| CSV unduhan browser | Nama/jabatan baru, kolom pemenang, agregat 72 suara A / 48 suara B; tidak memuat NIM atau digest pemilih |

Pemeriksaan browser menggunakan salinan Docker `telu-candidate-qa`, port 8137, jaringan `telu-candidate-qa-net-20261109`, dan volume `telu-candidate-qa-data-20261109`, dengan secret terpisah. Semua pengiriman suara uji dilakukan di sana.

- Kartu memuat foto pasangan sesuai nomor, ketua kiri dan wakil kanan. Nama/jabatan berupa HTML. Foto ditampilkan utuh dengan `object-fit: contain`.
- Kedua tombol poster membuka gambar yang tepat. Tombol tutup dan Escape berfungsi; fokus kembali ke tombol pembuka. Membuka poster tidak memilih radio kandidat.
- Pemilihan radio native, indikator centang, teks pilihan, dan tinjauan kedua kandidat berfungsi. Suara A dan B benar-benar dikirim melalui UI menggunakan dua NIM sintetis.
- Dashboard tab lain berubah dari 120 → 121 → 122 melalui SSE **tanpa reload**, dengan hasil 73 A / 49 B dan nama baru.
- Setelah memilih, pesan terima kasih, timestamp WIB dari server, dan tombol terkunci muncul. Login kembali tetap terkunci; penghapusan hanya dua UUID uji tidak membuka hak pilih. Fixture kembali 120 (72 A / 48 B), dan dashboard mengikuti penghapusan melalui SSE.
- Kartu, nama panjang, thumbnail dashboard, serta dialog poster diperiksa dalam bingkai same-origin **390 × 844**. Area konten efektif 375 px termasuk scrollbar, tanpa overflow horizontal dokumen. Nama dapat membungkus baris; foto dan teks tidak terpotong. Dialog poster muat pada lebar sekitar 341 px. Ini pemeriksaan bingkai responsif, bukan klaim perangkat ponsel fisik.
- Pratinjau hasil memakai fixture QA: [dashboard-demo.png](dashboard-demo.png). Pratinjau kartu: [candidates-preview.png](candidates-preview.png).
- Dashboard utama diperiksa sesudah deployment: LIVE, nama dan thumbnail baru, data kosong ditampilkan sebagai 0 tanpa grafik suara contoh.

Jenkinsfile tetap lima stage dan kini memeriksa kelengkapan aset kandidat di Syntax Check. Job Jenkins, PAT, webhook GitHub, dan ngrok aktual **belum dijalankan**; memerlukan akun/repository/job pengguna. Penyalinan aset helper dan deployment Compose lokal berhasil diuji, bukan bukti pipeline eksternal telah tersambung.

## Riwayat verifikasi login dan penyimpanan

Tanggal pemeriksaan: **4 November 2026 (WIB)**. Lingkungan: Windows, Python 3.12, Docker Desktop Linux engine, dan browser aplikasi. Pengujian mutasi memakai direktori sementara atau stack Docker QA yang terpisah.

## Pengujian yang dijalankan

| Pemeriksaan | Hasil |
| --- | --- |
| Unit/integration tests Python | **30 lulus** |
| Format NIM `1010` + 8 digit ASCII | Valid diterima; panjang/prefix/karakter salah ditolak; whitespace tepi dinormalisasi |
| Password salah / sesi tidak ada | Ditolak; POST suara tanpa sesi menghasilkan 401 |
| CSRF, Origin, expiry, logout | Diuji; token salah/cross-origin ditolak, logout/expiry membatalkan sesi |
| Cookie | HttpOnly dan SameSite=Lax; Secure diuji ketika HTTPS diaktifkan |
| Dua sesi HTTP, satu NIM, kirim bersamaan | Tepat satu 201 dan satu 409; hanya satu suara tersimpan |
| 20 penulisan bersamaan pada NIM sama | Satu keberhasilan, 19 duplikat; satu revisi perubahan |
| 40 NIM berbeda bersamaan | Semua suara dan ledger tersimpan tanpa kehilangan data |
| NIM pada body POST | Tidak dapat mengganti identitas sesi |
| Login ulang/perangkat lain | Mengembalikan status dan waktu pemilihan pertama |
| Restart backend | Login kembali tetap terkunci, waktu sama |
| Penghapusan catatan | Tidak menghapus ledger atau membuka hak pilih |
| Validasi gagal / disk write gagal | Tidak mencadangkan NIM dan tidak menaikkan revisi |
| File rusak / key berbeda | Dilaporkan tanpa reset atau penghapusan ledger |
| Migrasi list lama | Backup byte-identik dibuat; semua catatan dipertahankan |
| Histori luar Bandung | Tetap tersimpan, dikecualikan dari hasil; indeks asli dipertahankan |
| Privasi | NIM asli/nama tidak tersimpan; digest/key tidak bocor ke respons publik atau log |
| SSE | Add/delete memicu notifikasi; duplikat tidak mengubah revisi |
| Sintaks | Python helper dan empat berkas JavaScript diperiksa |
| Docker Compose | Konfigurasi valid; backend dan frontend utama healthy |
| Helper deployment | Folder persisten disiapkan, secret dipertahankan, Compose hasil staging valid |

## Pengujian browser dan Docker QA

Stack QA dibuat dengan nama proyek, jaringan, port, dan volume berbeda dari aplikasi utama. Ia berisi 120 fixture Bandung; data ini tidak dimasukkan ke volume utama.

- Membuka `/index.html` tanpa sesi mengalihkan ke login.
- Password salah menampilkan pesan kesalahan. Login dengan NIM sintetis berformat benar dan password bersama berhasil.
- Pengguna dapat mengisi fakultas/prodi/angkatan dan meninjau pilihan tanpa dropdown kampus.
- Setelah suara dikirim, pesan terima kasih sesuai permintaan muncul, waktu server ditampilkan dalam WIB, dan tombol sudah memilih tidak aktif.
- Dashboard tab lain berubah dari 120 menjadi 121 tanpa reload.
- Logout/login kembali mempertahankan waktu pemilihan pertama yang sama.
- Backend QA benar-benar dihapus dan dibuat ulang. Setelah login kembali, NIM tetap terkunci dan duplicate POST menghasilkan 409.
- Hanya UUID uji yang dihapus. Ledger tetap terkunci setelah penghapusan; fixture kembali 120.
- Pemulihan SSE setelah error proxy sementara diperbaiki. Tab dashboard kembali LIVE dan tersinkron ke 120 setelah backend dibuat ulang **tanpa reload halaman**. Retry hanya memulihkan transport saat EventSource CLOSED, bukan polling hasil.
- Nginx meneruskan Host beserta port agar validasi Origin browser benar.
- Font lokal Outfit dan Plus Jakarta Sans telah dimuat, diverifikasi melalui `document.fonts`.
- Kontrol/dropdown/grafik/pengelompokan lintas kampus tidak ada pada dashboard.
- Login dan keadaan terkunci diperiksa dalam bingkai same-origin berukuran **390 × 844**; area konten 375 piksel termasuk scrollbar. Lebar dokumen sama dengan area konten, tanpa overflow horizontal. Nama kedua kandidat tidak terpotong. Bingkai ini digunakan karena override viewport browser tidak mengubah ukuran tab pada lingkungan ini.
- Footer login/bilik/dashboard menggunakan `made by: Steven Romallo`.

## Kondisi data utama

Migrasi aplikasi utama berhasil ke schema 2 dan satu backup legacy dibuat. Pemeriksaan terakhir mencatat 0 suara dan 0 penanda hak pilih di volume utama; seluruh mutasi pengujian dilakukan pada storage terpisah. Secret lokal disiapkan sekali dan tidak dicetak.

Paket ZIP tidak memuat `.env`, `.env.next`, database aktual, backup aktual, atau bytecode. Font lokal beserta lisensinya disertakan. Gambar dashboard menggunakan fixture, dan gambar status sudah memilih berasal dari identitas sintetis QA.

## Yang belum dijalankan

- Job Jenkins aktual serta validasi Jenkinsfile oleh controller Jenkins.
- Checkout PAT milik kelompok, pengiriman GitHub webhook, dan tunnel ngrok akun pengguna.
- Uji HTTPS end-to-end melalui sertifikat/proxy publik; atribut Secure diuji melalui konfigurasi server.
- Integrasi verifikasi NIM ke sistem resmi kampus.

Jenkinsfile dan konfigurasi Credentials telah disiapkan. Keberhasilan perintah Docker lokal bukan bukti bahwa job Jenkins atau webhook sudah tersambung.
