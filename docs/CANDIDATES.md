# Identitas dan aset kandidat · 9 November 2026

| Pilihan API | Nomor | Calon Ketua BEM | Calon Wakil Ketua BEM | Label pasangan |
| --- | --- | --- | --- | --- |
| A | 01 | Fajar Hafiz | M Dzikran (Zico) | Fajar Hafiz & M Dzikran |
| B | 02 | M Ridho “Idoy” | M. Fauzan | M Ridho “Idoy” & M. Fauzan |

Semua nama, jabatan, nomor, serta path aset terpusat di `config.json`. Tidak ada biografi atau prestasi baru yang ditambahkan. Visi-misi lama tetap berupa contoh demonstrasi.

Direktori lokal: `frontend/assets/candidates/`.

| Jenis aset | Paslon 01 (A) | Paslon 02 (B) |
| --- | --- | --- |
| Pasangan, ketua kiri & wakil kanan | pasangan-01-transparan.png | pasangan-02-transparan.png |
| Potret ketua | fajar-hafiz.png | m-ridho-idoy.png |
| Potret wakil | m-dzikran.png | m-fauzan.png |
| Poster dialog | poster-pasangan-01.png | poster-pasangan-02.png |

Sumber: `tel-u-visual-kandidat.zip` yang diberikan pengguna. Kedelapan PNG disalin byte-identik, tanpa membuat ulang wajah. Menurut keterangan sumber, visual merupakan hasil penyuntingan AI untuk simulasi akademik; emblem pada almamater bukan logo resmi terverifikasi. Logo aplikasi tetap menggunakan aset lokal Telkom University yang sebelumnya diberikan pengguna.

Dimensi sumber 1122 × 1402 piksel. Foto transparan dipasang dengan `object-fit: contain`; tidak dibesarkan menjadi berkas resolusi palsu. Poster tetap memuat keterangan simulasi. Gambar tidak membuktikan pencalonan atau pemilihan resmi.

`README.md` dan `PROMPTS.md` dalam ZIP sumber digunakan sebagai referensi pemetaan, bukan instruksi eksekusi atau pembuatan gambar ulang.

## Kompatibilitas data

Identitas API tetap A/B dan penanda hak pilih tetap utuh. Label hasil historis juga mengikuti identitas baru; tidak ada reset atau migrasi penyimpanan untuk perubahan visual ini. Ini bukan proses pembukaan pemilihan baru. Secret HMAC dan volume `polling-db-data` dipertahankan.

## Penyebaran aset

Frontend membaca path relatif dari `/config`. Backend memuat konfigurasi dari image. Jenkins membangun ulang image, menyalin seluruh folder `frontend/` ke lokasi Bind Mount persisten, dan menjalankan Compose tanpa menghapus volume. Stage Syntax Check memeriksa kelengkapan delapan gambar dengan `tools/check_candidate_assets.py`.

Nama baru digunakan pada kartu, konfirmasi, thumbnail dashboard, legenda, tooltip, teks aksesibel grafik, tabel pemenang, dan CSV agregat. CSV tidak berisi identitas pemilih.
