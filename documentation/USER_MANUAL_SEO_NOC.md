# USER MANUAL SEO-NOC
## Panduan Lengkap Penggunaan Sistem SEO Network Operations Center

**Versi:** 1.0  
**Tanggal:** Februari 2026  
**Bahasa:** Indonesia

---

# DAFTAR ISI

1. [BAGIAN A: GETTING STARTED](#bagian-a-getting-started)
   - A.1 Overview Aplikasi
   - A.2 System Requirements
   - A.3 Login & Logout
   - A.4 Registrasi Akun Baru
   - A.5 Navigasi Menu
   - A.6 Glossary

2. [BAGIAN B: ROLE & PERMISSIONS](#bagian-b-role--permissions)
   - B.1 Jenis Role
   - B.2 Perbandingan Hak Akses
   - B.3 Brand Scoping
   - B.4 Menu Access Control
   - B.5 Menangani Error Permission

3. [BAGIAN C: MODUL UTAMA](#bagian-c-modul-utama)
   - C.1 Dashboard
   - C.2 Asset Domains
   - C.3 SEO Networks
   - C.4 Optimizations
   - C.5 SEO Conflicts (Alert Center)
   - C.6 Domain Monitoring
   - C.7 Reports
   - C.8 Team Evaluation
   - C.9 Master Data Management
   - C.10 User Management
   - C.11 Settings
   - C.12 Audit & Activity Logs

4. [BAGIAN D: TROUBLESHOOTING & FAQ](#bagian-d-troubleshooting--faq)

5. [BAGIAN E: APPENDIX](#bagian-e-appendix)

---

# BAGIAN A: GETTING STARTED

## A.1 Overview Aplikasi SEO-NOC

### Apa itu SEO-NOC?

**SEO-NOC (SEO Network Operations Center)** adalah sistem manajemen domain dan jaringan SEO yang komprehensif. Aplikasi ini dirancang untuk membantu tim SEO dalam:

- **Mengelola Asset Domain** - Tracking semua domain yang dimiliki perusahaan
- **Memantau SEO Networks** - Visualisasi dan pengelolaan struktur jaringan SEO
- **Monitoring Domain** - Memantau status availability dan expiration domain
- **Mendeteksi SEO Conflicts** - Identifikasi otomatis masalah konfigurasi SEO
- **Tracking Optimizations** - Manajemen tugas dan optimasi SEO
- **Evaluasi Tim** - Metrics performa tim SEO

### Fitur Utama

| Fitur | Deskripsi |
|-------|-----------|
| Asset Domains | Database lengkap semua domain dengan status lifecycle |
| SEO Networks | Visualisasi graph struktur jaringan SEO (Tier 1, 2, 3, dst) |
| Alert Center | Dashboard konflik SEO dengan metrik resolusi |
| Domain Monitoring | Monitoring availability (UP/DOWN) dan expiration domain |
| Telegram Alerts | Notifikasi otomatis via Telegram untuk event penting |
| Team Evaluation | Scoring performa tim berdasarkan optimizations |
| Multi-Brand Support | Pengelolaan multiple brand dalam satu sistem |

---

## A.2 System Requirements

### Browser yang Didukung

| Browser | Versi Minimum | Status |
|---------|---------------|--------|
| Google Chrome | 90+ | Direkomendasikan |
| Mozilla Firefox | 88+ | Didukung |
| Microsoft Edge | 90+ | Didukung |
| Safari | 14+ | Didukung |

### Persyaratan Lainnya

- **Koneksi Internet**: Minimum 1 Mbps (direkomendasikan 5 Mbps+)
- **Resolusi Layar**: Minimum 1280x720 (direkomendasikan 1920x1080)
- **JavaScript**: Harus diaktifkan
- **Cookies**: Harus diaktifkan

### Akun yang Diperlukan

Untuk menggunakan SEO-NOC, Anda memerlukan:
1. Akun user yang terdaftar di sistem
2. Approval dari Super Admin (untuk akun baru)
3. Telegram account (opsional, untuk menerima notifikasi)

---

## A.3 Login & Logout

### A.3.1 Cara Login

**Tujuan:** Masuk ke dalam sistem SEO-NOC

**Langkah-langkah:**

1. Buka browser dan akses URL aplikasi SEO-NOC
2. Anda akan melihat halaman login dengan form:
   - **Email Address**: Masukkan email yang terdaftar
   - **Password**: Masukkan password Anda
3. Klik tombol **"Sign In"**
4. Jika berhasil, Anda akan diarahkan ke Dashboard

**Expected Result:** Halaman Dashboard muncul dengan pesan "Welcome back, [Nama Anda]"

**Troubleshooting:**
- **"Invalid credentials"**: Periksa kembali email dan password. Password bersifat case-sensitive.
- **Tidak bisa login**: Pastikan akun Anda sudah di-approve oleh Super Admin.
- **Halaman tidak loading**: Coba refresh browser atau clear cache.

> **Gambar 1 - Halaman Login SEO-NOC**
> Form login dengan field Email Address dan Password

---

### A.3.2 Cara Logout

**Tujuan:** Keluar dari sistem dengan aman

**Langkah-langkah:**

1. Lihat sidebar menu di sebelah kiri
2. Scroll ke bawah hingga menemukan nama user Anda
3. Klik tombol **"Logout"** di bawah nama user
4. Anda akan diarahkan kembali ke halaman Login

**Catatan Penting:**
- Selalu logout setelah selesai menggunakan aplikasi, terutama di komputer bersama
- Session akan otomatis expired setelah periode tidak aktif tertentu

---

## A.4 Registrasi Akun Baru

### A.4.1 Membuat Akun Baru

**Tujuan:** Mendaftar sebagai user baru di SEO-NOC

**Langkah-langkah:**

1. Di halaman Login, klik link **"Create Account"**
2. Isi form registrasi:
   - **Full Name**: Nama lengkap Anda
   - **Email Address**: Email yang akan digunakan untuk login
   - **Telegram Username** (opsional): Username Telegram tanpa @
   - **Password**: Minimal 8 karakter
   - **Confirm Password**: Ulangi password
3. Klik tombol **"Create Account"**
4. Tunggu approval dari Super Admin

**Expected Result:** Pesan konfirmasi muncul bahwa akun sedang menunggu approval

**Catatan Penting:**
- User pertama yang mendaftar akan otomatis menjadi **Super Admin**
- User selanjutnya harus menunggu approval dan akan mendapat role **Viewer** secara default

> **Gambar 2 - Halaman Registrasi**
> Form registrasi dengan field Full Name, Email, Telegram Username, Password

---

### A.4.2 Approval Flow

**Untuk Super Admin:**

1. Login ke sistem
2. Buka menu **"Users"**
3. Klik tab **"Pending Approvals"**
4. Review data user yang mendaftar
5. Klik tombol **"Approve"** atau **"Reject"**
6. Jika approve, tentukan:
   - **Role**: Super Admin / Admin / Viewer
   - **Brand Access**: Brand mana saja yang bisa diakses

---

## A.5 Navigasi Menu & Struktur Sidebar

### Struktur Menu Utama

Sidebar menu di sebelah kiri layar berisi semua menu navigasi:

| Menu | Ikon | Deskripsi | Hak Akses |
|------|------|-----------|-----------|
| Dashboard | Grid | Ringkasan data dan statistik | Semua |
| Asset Domains | Globe | Manajemen database domain | Semua |
| SEO Networks | Network | Visualisasi jaringan SEO | Semua |
| Alert Center | Bell | Dashboard konflik SEO | Semua |
| Reports | Chart | Laporan dan analytics | Semua |
| Team Evaluation | Users | Evaluasi performa tim | Admin+ |
| Brands | Tag | Master data brand | Admin+ |
| Categories | Folder | Master data kategori domain | Admin+ |
| Registrars | Building | Master data registrar | Admin+ |
| Users | Users | Manajemen user | Super Admin |
| Audit Logs | Activity | Log aktivitas sistem | Super Admin |
| Metrics | BarChart | Metrik konflik resolusi | Admin+ |
| V3 Activity | Clock | Log perubahan SEO | Admin+ |
| Monitoring | Radar | Pengaturan monitoring | Admin+ |
| Activity Types | Bolt | Master data activity type | Admin+ |
| Scheduler | Calendar | Jadwal job sistem | Super Admin |
| Quarantine Categories | Shield | Kategori karantina domain | Super Admin |
| Settings | Gear | Pengaturan sistem | Super Admin |

### Brand Switcher

Di bagian atas sidebar terdapat **Brand Switcher**:
- **All Brands**: Melihat data dari semua brand
- **[Nama Brand]**: Filter data untuk brand tertentu saja

> **Gambar 3 - Dashboard dengan Sidebar Menu**
> Tampilan dashboard lengkap dengan sidebar menu di sebelah kiri

---

## A.6 Glossary - Istilah Penting

| Istilah | Definisi |
|---------|----------|
| **Asset Domain** | Domain yang dimiliki dan dikelola oleh perusahaan |
| **SEO Network** | Struktur jaringan domain untuk keperluan SEO (PBN, supporting sites) |
| **Tier** | Level dalam struktur SEO Network (Tier 1 = langsung ke Money Site) |
| **Money Site** | Website utama yang menjadi target SEO |
| **LP (Landing Page)** | Halaman yang menerima traffic langsung |
| **Node** | Satu entry domain dalam SEO Network |
| **Orphan Node** | Node yang tidak terhubung ke struktur utama |
| **Canonical** | URL utama yang diakui oleh search engine |
| **301 Redirect** | Permanent redirect dari satu URL ke URL lain |
| **Noindex** | Tag yang memberitahu search engine untuk tidak mengindex halaman |
| **Lifecycle** | Status siklus hidup domain (Active/Released/Quarantined/Not Renewed) |
| **Monitoring Toggle** | Switch untuk mengaktifkan/menonaktifkan monitoring domain |
| **Availability** | Status ketersediaan domain (UP/DOWN/Soft Blocked) |
| **Expiration** | Tanggal berakhirnya registrasi domain |
| **Optimization** | Task atau tugas optimasi SEO yang perlu dikerjakan |
| **Conflict** | Masalah atau inkonsistensi dalam konfigurasi SEO |
| **Brand Scope** | Batasan akses user terhadap brand tertentu |

---

# BAGIAN B: ROLE & PERMISSIONS

## B.1 Jenis Role

SEO-NOC memiliki 3 jenis role utama:

### Super Admin
- **Deskripsi**: Administrator tertinggi dengan akses penuh ke seluruh sistem
- **Kemampuan**:
  - Akses ke semua menu dan fitur
  - Mengelola user (approve, edit role, delete)
  - Mengatur brand scope untuk user lain
  - Mengakses Audit Logs dan Scheduler
  - Mengonfigurasi semua settings sistem
  - Mengirim Complaint pada optimizations

### Admin (Manager)
- **Deskripsi**: Manager yang dapat mengelola network dan optimizations
- **Kemampuan**:
  - Melihat dan mengelola SEO Networks yang di-assign
  - Membuat dan menyelesaikan optimizations
  - Melihat reports dan team evaluation
  - Merespons complaints dari Super Admin
  - Tidak bisa mengelola users atau system settings

### Viewer
- **Deskripsi**: User dengan akses read-only
- **Kemampuan**:
  - Melihat Dashboard, Asset Domains, SEO Networks
  - Melihat reports (terbatas)
  - Tidak bisa membuat atau edit data apapun

---

## B.2 Perbandingan Hak Akses per Role

| Fitur | Super Admin | Admin | Viewer |
|-------|:-----------:|:-----:|:------:|
| View Dashboard | ✅ | ✅ | ✅ |
| View Asset Domains | ✅ | ✅ | ✅ |
| Add/Edit Domain | ✅ | ✅ | ❌ |
| View SEO Networks | ✅ | ✅ | ✅ |
| Create/Edit Network | ✅ | ✅ (assigned only) | ❌ |
| Add/Edit Nodes | ✅ | ✅ (assigned only) | ❌ |
| View Alert Center | ✅ | ✅ | ✅ |
| Create Optimization | ✅ | ✅ | ❌ |
| Send Complaint | ✅ | ❌ | ❌ |
| Respond to Complaint | ❌ | ✅ | ❌ |
| View Reports | ✅ | ✅ | ✅ (limited) |
| View Team Evaluation | ✅ | ✅ | ❌ |
| Manage Users | ✅ | ❌ | ❌ |
| View Audit Logs | ✅ | ❌ | ❌ |
| Configure Settings | ✅ | ❌ | ❌ |
| Manage Master Data | ✅ | ✅ | ❌ |

---

## B.3 Brand Scoping - Pembatasan Akses per Brand

### Konsep Brand Scoping

Brand Scoping membatasi user untuk hanya dapat mengakses data dari brand tertentu saja.

**Contoh:**
- User A di-assign ke brand "PANEN77" dan "Panen138"
- User A hanya bisa melihat dan mengelola domain/network dari 2 brand tersebut
- Data dari brand lain tidak akan muncul untuk User A

### Cara Mengatur Brand Scope (Super Admin Only)

1. Buka menu **"Users"**
2. Cari user yang akan diatur
3. Klik ikon **Edit** (pensil)
4. Di bagian **"Brand Access"**, pilih brand yang diizinkan
5. Klik **"Save Changes"**

**Catatan Penting:**
- Super Admin dengan "All Brands" access dapat melihat semua data
- User tanpa brand scope tidak bisa mengakses data apapun

---

## B.4 Menu Access Control

### Konsep Menu Access Control

Selain role, akses ke menu tertentu juga bisa diatur per-user melalui Menu Access Control.

**Langkah-langkah (Super Admin Only):**

1. Buka menu **"Users"**
2. Cari user yang akan diatur
3. Klik ikon **Menu (...)** → **"Manage Menu Access"**
4. Toggle ON/OFF untuk setiap menu yang diizinkan
5. Klik **"Save"**

### Reset Menu Access

Untuk mengembalikan ke pengaturan default berdasarkan role:
1. Buka dialog Menu Access
2. Klik tombol **"Reset to Default"**

---

## B.5 Menangani Error Permission (403 Forbidden)

### Penyebab Error 403

Error 403 muncul ketika user mencoba mengakses fitur yang tidak diizinkan.

**Penyebab umum:**
1. Role tidak memiliki akses ke fitur tersebut
2. User tidak memiliki brand scope yang sesuai
3. Menu access dinonaktifkan untuk user tersebut

### Cara Mengatasi

**Jika Anda adalah user biasa:**
- Hubungi Super Admin untuk meminta akses
- Jelaskan fitur apa yang perlu diakses dan alasannya

**Jika Anda adalah Super Admin:**
1. Periksa role user - apakah sudah sesuai?
2. Periksa brand scope - apakah user punya akses ke brand tersebut?
3. Periksa menu access control - apakah menu tersebut diaktifkan?

---

# BAGIAN C: MODUL UTAMA

## C.1 Dashboard

### C.1.1 Overview Dashboard

**Tujuan:** Melihat ringkasan data dan statistik sistem secara keseluruhan

**Akses:** Semua Role

Dashboard menampilkan 6 widget utama:

| Widget | Deskripsi |
|--------|-----------|
| **DOMAINS** | Total jumlah domain di database |
| **NETWORKS** | Total jumlah SEO Network |
| **MONITORED** | Jumlah domain yang dimonitoring (UP/DOWN) |
| **INDEX RATE** | Persentase domain yang ter-index di search engine |
| **ACTIVE ALERTS** | Jumlah alert yang aktif (expiration + monitoring) |
| **BRANDS** | Total jumlah brand yang dikonfigurasi |

### C.1.2 Panel Domains by Brand

Menampilkan distribusi domain per brand:
- Nama brand
- Jumlah domain untuk masing-masing brand
- Total keseluruhan domain

### C.1.3 Panel Monitoring Status

Visualisasi donut chart status monitoring:
- **Hijau (Up)**: Domain yang accessible
- **Merah (Down)**: Domain yang tidak accessible
- **Abu-abu (Unknown)**: Domain yang belum dicek

### C.1.4 Panel Recent Alerts

Menampilkan alert terbaru dengan badge severity:
- **Critical** (Merah): Alert sangat penting, perlu tindakan segera
- **High** (Orange): Alert penting
- **Low** (Abu-abu): Alert informasional

**Jenis Alert:**
- **Expiration**: Domain akan/sudah expired
- **Monitoring**: Domain DOWN atau mengalami masalah

### C.1.5 Filter Brand

Di sudut kanan atas Dashboard:
- Dropdown **"All Brands"**: Filter data berdasarkan brand tertentu
- Tombol **Refresh**: Reload data terbaru

> **Gambar 4 - Dashboard Overview**
> Dashboard dengan semua widget: Domains, Networks, Monitored, Index Rate, Active Alerts, Brands

---

## C.2 Asset Domains

### C.2.1 Tampilan Halaman Asset Domains

**Tujuan:** Mengelola database semua domain yang dimiliki

**Akses:** Semua Role (Edit: Admin+)

**Komponen Halaman:**

1. **Header Section**
   - Judul "Asset Domains" dengan badge versi (V3)
   - Total domain count
   - Tombol: Refresh, Export, Import CSV, Add Domain

2. **SEO Monitoring Coverage Panel**
   - Domains in SEO: Jumlah domain yang ada di SEO Networks
   - Monitored: Domain dengan monitoring aktif
   - Unmonitored: Domain tanpa monitoring
   - Coverage %: Persentase coverage monitoring
   - Released: Domain yang sudah released
   - Quarantined: Domain yang dikarantina
   - Root Missing: Domain tanpa root structure

3. **Tab Navigation**
   - All Domains
   - Unmonitored in SEO
   - Released
   - Quarantined
   - Not Renewed

4. **Search & Filter**
   - Search box untuk mencari domain
   - Tombol Filters untuk filter lanjutan

5. **Domain Table**
   - Kolom: Domain, Brand, Category, Domain Active Status, Monitoring Status, Lifecycle, Quarantine, SEO Networks, Monitoring Toggle, Expiration, Actions

> **Gambar 5 - Halaman Asset Domains**
> Tabel domain dengan semua kolom dan filter

---

### C.2.2 Menambah Domain Baru (Manual)

**Tujuan:** Menambahkan domain baru ke database

**Hak Akses:** Admin, Super Admin

**Langkah-langkah:**

1. Klik tombol **"+ Add Domain"** di kanan atas
2. Isi form Add Domain:
   - **Domain Name** (wajib): Nama domain tanpa http/https
   - **Brand** (wajib): Pilih brand yang sesuai
   - **Category**: Pilih kategori domain
   - **Registrar**: Pilih registrar domain
   - **Expiration Date**: Tanggal expired domain
   - **Auto Renew**: Toggle jika domain auto-renew
   - **Purchase Date**: Tanggal pembelian domain
   - **Purchase Price**: Harga pembelian
   - **Notes**: Catatan tambahan
3. Klik **"Save"**

**Expected Result:** Domain baru muncul di tabel dengan status default

**Catatan Penting:**
- Domain Name harus unik (tidak boleh duplikat)
- Format domain: example.com (tanpa www atau protokol)

---

### C.2.3 Import Domain via CSV

**Tujuan:** Menambah multiple domain sekaligus melalui file CSV

**Hak Akses:** Admin, Super Admin

**Langkah-langkah:**

1. Klik tombol **"Import CSV"**
2. Dialog Import muncul dengan 2 tahap:

**Tahap 1 - Upload & Preview:**
1. Klik area upload atau drag-drop file CSV
2. Sistem akan memvalidasi file dan menampilkan preview:
   - **New domains**: Domain yang akan ditambahkan
   - **Updated domains**: Domain yang akan diupdate
   - **Errors**: Baris dengan error yang akan diskip
3. Review data di tabel preview
4. Jika sudah benar, klik **"Confirm Import"**

**Tahap 2 - Confirmation:**
1. Sistem memproses import
2. Hasil ditampilkan:
   - Jumlah domain berhasil ditambahkan
   - Jumlah domain diupdate
   - Jumlah error (jika ada)

**Format CSV yang Didukung:**
```
domain,brand,category,registrar,expiration_date,purchase_date,purchase_price,auto_renew,notes
example.com,PANEN77,FRESH DOMAIN,Namecheap,2026-12-31,2024-01-15,10.99,true,Test domain
```

**Catatan Penting:**
- Kolom wajib: domain, brand
- Brand harus sesuai dengan yang sudah ada di sistem
- Domain duplikat akan di-update, bukan error

---

### C.2.4 Export Domain ke CSV

**Tujuan:** Mengekspor data domain ke file CSV

**Hak Akses:** Semua Role

**Langkah-langkah:**

1. (Opsional) Terapkan filter yang diinginkan
2. Klik tombol **"Export"**
3. File CSV akan otomatis didownload

**Catatan Penting:**
- Export akan mengikuti filter yang sedang aktif
- Jika tidak ada filter, semua domain akan diekspor

---

### C.2.5 Edit Domain

**Tujuan:** Mengubah data domain yang sudah ada

**Hak Akses:** Admin, Super Admin

**Langkah-langkah:**

1. Di tabel domain, cari domain yang akan diedit
2. Klik ikon **Edit** (pensil) di kolom Actions
3. Atau klik baris domain untuk membuka Detail Panel
4. Ubah field yang diperlukan
5. Klik **"Save Changes"**

**Field yang Dapat Diedit:**
- Brand
- Category
- Registrar
- Expiration Date
- Auto Renew toggle
- Purchase Date
- Purchase Price
- Notes
- Lifecycle Status
- Quarantine Category (jika Quarantined)

---

### C.2.6 Memahami Status Domain

#### Domain Active Status
Status aktif domain berdasarkan tanggal expiration:

| Status | Warna | Keterangan |
|--------|-------|------------|
| **Active** | Hijau | Domain masih aktif (belum expired) |
| **Expired** | Merah | Domain sudah melewati tanggal expiration |

#### Monitoring Status
Status hasil pemeriksaan availability domain:

| Status | Warna | Keterangan |
|--------|-------|------------|
| **Up** | Hijau | Domain accessible dan berjalan normal |
| **Down** | Merah | Domain tidak accessible |
| **Soft Blocked** | Kuning | Domain ter-block oleh WAF/CDN |
| **JS Challenge** | Kuning | Domain menampilkan JS challenge (Cloudflare) |
| **Captcha** | Kuning | Domain menampilkan captcha |
| **Unknown** | Abu-abu | Domain belum pernah dicek atau monitoring OFF |

#### Lifecycle Status
Siklus hidup domain dalam pengelolaan:

| Status | Keterangan |
|--------|------------|
| **Active** | Domain aktif dan digunakan |
| **Released** | Domain sudah di-release/dilepas |
| **Quarantined** | Domain dikarantina karena masalah tertentu |
| **Not Renewed** | Domain tidak diperpanjang dan akan/sudah expired |

---

### C.2.7 Quarantine Domain

**Tujuan:** Memasukkan domain ke karantina dengan alasan tertentu

**Hak Akses:** Admin, Super Admin

**Kapan Domain Perlu Dikarantina:**
- Domain terkena spam atau penalty dari search engine
- Domain terkena DMCA takedown
- Domain di-hack atau compromised
- Domain perlu evaluasi sebelum digunakan lagi

**Langkah-langkah:**

1. Edit domain yang akan dikarantina
2. Ubah **Lifecycle Status** menjadi **"Quarantined"**
3. Pilih **Quarantine Category**:
   - Spam (Pure Spam)
   - DMCA
   - Manual Penalty
   - Rollback / Restore
   - Penalized
   - Hacked Site
   - Other
4. Klik **"Save Changes"**

**Catatan Penting:**
- Domain yang dikarantina akan muncul di tab "Quarantined"
- Monitoring untuk domain karantina sebaiknya dinonaktifkan

---

### C.2.8 Filter, Search, Sorting & Pagination

#### Search
- Ketik nama domain di search box
- Pencarian akan filter domain yang mengandung kata kunci

#### Filters
Klik tombol **"Filters"** untuk filter lanjutan:
- **Brand**: Filter berdasarkan brand
- **Category**: Filter berdasarkan kategori
- **Lifecycle**: Filter berdasarkan status lifecycle
- **Monitoring Status**: Filter berdasarkan status monitoring
- **Domain Active Status**: Filter Active/Expired
- **Monitoring Toggle**: Filter ON/OFF
- **Has SEO Networks**: Filter domain yang ada/tidak ada di SEO Networks

#### Sorting
- Klik header kolom untuk sort ascending
- Klik lagi untuk sort descending

#### Pagination
- Gunakan tombol Previous/Next di bawah tabel
- Pilih jumlah item per halaman (10/25/50/100)

---

## C.3 SEO Networks

### C.3.1 Daftar Network

**Tujuan:** Melihat dan mengelola semua SEO Network

**Akses:** Semua Role (Create/Edit: Admin+)

**Tampilan:**
- Card view untuk setiap network
- Informasi: Nama, Brand, Visibility, Manager, Node count
- Badge: Ranking status, Expired count, Quarantined count

> **Gambar 6 - Daftar SEO Networks**
> Tampilan card view semua network dengan informasi ringkas

---

### C.3.2 Membuat Network Baru

**Tujuan:** Membuat SEO Network baru

**Hak Akses:** Admin, Super Admin

**Langkah-langkah:**

1. Di halaman SEO Networks, klik **"+ Add Network"**
2. Isi form Create Network:
   - **Network Name** (wajib): Nama network
   - **Brand** (wajib): Pilih brand
   - **Description**: Deskripsi network
   - **Visibility Mode**: Brand Based / Network Specific
   - **Main Target URL**: URL money site
3. Klik **"Create"**

---

### C.3.3 Network Detail Page

Setelah klik "View" pada network card, Anda masuk ke halaman detail dengan beberapa tab:

| Tab | Deskripsi |
|-----|-----------|
| **Visual Graph** | Visualisasi struktur network dalam bentuk graph |
| **Domain List** | Daftar semua node/domain dalam network |
| **Change History** | Log perubahan yang terjadi pada network |
| **Optimizations** | Daftar optimization terkait network ini |
| **Complaints** | Daftar complaint untuk network ini |
| **Managers** | Pengelolaan manager network |
| **Settings** | Pengaturan network |

---

### C.3.4 Visual Graph

**Cara Membaca Visual Graph:**

- **Warna Node berdasarkan Tier:**
  - Merah/Orange: LP/Money Site (target utama)
  - Kuning: Tier 1 (langsung ke money site)
  - Hijau Tua: Tier 2
  - Hijau Muda: Tier 3
  - Biru: Tier 4
  - Abu-abu: Tier 5+
  - Ungu: Noindex

- **Arrow/Panah**: Menunjukkan arah link (dari → ke)
- **Node Size**: Berdasarkan jumlah incoming links

**Interaksi:**
- Klik node untuk melihat detail
- Drag untuk menggeser posisi
- Scroll untuk zoom in/out

---

### C.3.5 Menambah Node

**Tujuan:** Menambahkan domain/entry baru ke SEO Network

**Hak Akses:** Manager/Admin yang di-assign ke network, Super Admin

**Langkah-langkah:**

1. Di halaman Network Detail, klik **"+ Add Node"**
2. Isi form Add Node:
   - **Domain/URL**: Pilih domain dari database atau masukkan URL
   - **Tier**: Pilih tier (LP/Money Site, Tier 1, 2, 3, dst)
   - **Parent Node**: Node yang menjadi parent (untuk struktur hierarki)
   - **Link Type**: Jenis link (Backlink, Redirect, etc)
   - **Anchor Text**: Text anchor yang digunakan
   - **Index Status**: Status index di search engine
3. Klik **"Save"**

---

### C.3.6 Change History

Tab ini menampilkan log semua perubahan pada network:
- Create/Update/Delete node
- Siapa yang melakukan
- Kapan dilakukan
- Detail perubahan

---

### C.3.7 Managers Tab

**Tujuan:** Mengelola siapa saja yang bisa mengelola network ini

**Hak Akses:** Super Admin

**Langkah-langkah Assign Manager:**

1. Buka tab **"Managers"**
2. Klik **"+ Add Manager"**
3. Pilih user dari dropdown
4. Klik **"Add"**

**Visibility Mode:**
- **Brand Based**: Semua user dengan akses ke brand bisa melihat
- **Network Specific**: Hanya assigned managers yang bisa melihat

---

## C.4 Optimizations

### C.4.1 Apa itu Optimization?

Optimization adalah task atau tugas optimasi SEO yang perlu dikerjakan. Setiap optimization melacak:
- Apa yang perlu dilakukan (Activity Type)
- Alasan/context (Reason Note)
- Status progress
- Scope (network, domain, keywords)
- Report URLs dan tanggal

---

### C.4.2 Membuat Optimization Baru

**Tujuan:** Membuat task optimization baru

**Hak Akses:** Admin, Super Admin

**Langkah-langkah:**

1. Di halaman SEO Network atau dari menu Optimizations
2. Klik **"Create Optimization"** atau tombol serupa
3. Isi form:
   - **Activity Type**: Pilih jenis aktivitas (Backlink, Onpage, Content, dll)
   - **Network**: Pilih network terkait
   - **Reason Note**: Jelaskan alasan/context optimization
   - **Scope**: Domain/page yang terkena dampak
   - **Keywords**: Target keywords (opsional)
   - **Report URLs**: Link ke report/dokumentasi
   - **Due Date**: Target penyelesaian
4. Klik **"Create"**

---

### C.4.3 Status Optimization

| Status | Warna | Keterangan |
|--------|-------|------------|
| **Planned** | Biru | Optimization baru dibuat, belum dikerjakan |
| **In Progress** | Kuning | Sedang dikerjakan |
| **Completed** | Hijau | Sudah selesai dikerjakan |
| **Reverted** | Merah | Di-rollback karena ada masalah |
| **Blocked** | Abu-abu | Terblokir dan tidak bisa dilanjutkan |

---

### C.4.4 Complaint Flow

#### Mengirim Complaint (Super Admin Only)

**Tujuan:** Memberikan feedback/komplain pada optimization yang bermasalah

**Langkah-langkah:**

1. Buka detail Optimization
2. Klik tombol **"File Complaint"**
3. Isi form complaint:
   - **Complaint Type**: Jenis komplain
   - **Description**: Detail masalah
4. Klik **"Submit"**

**Expected Result:** 
- Status optimization berubah menjadi "Under Review"
- Manager akan menerima notifikasi

#### Merespons Complaint (Manager Only)

**Langkah-langkah:**

1. Buka Optimization yang memiliki complaint
2. Di panel **"Team Responses"**, klik **"Add Response"**
3. Isi response:
   - **Response**: Penjelasan tindakan yang dilakukan
   - **Evidence URLs**: Link bukti perbaikan (opsional)
4. Klik **"Submit Response"**

#### Resolving Complaint (Super Admin Only)

Setelah manager merespons:
1. Review response dari manager
2. Jika sudah memuaskan, klik **"Resolve Complaint"**
3. Status kembali ke normal

**Catatan Penting:**
- Optimization dengan complaint aktif tidak bisa di-close/complete
- Harus resolve complaint dulu sebelum mark as completed

---

### C.4.5 Mark as Completed

**Langkah-langkah:**

1. Buka detail Optimization
2. Di panel **"Final Closure"**
3. Isi **Final Note** (opsional)
4. Klik **"Mark as Completed"**

**Syarat:**
- Tidak ada complaint yang belum resolved
- User harus punya permission (Manager/Admin+)

---

## C.5 SEO Conflicts (Alert Center)

### C.5.1 Apa itu SEO Conflict?

SEO Conflict adalah masalah atau inkonsistensi yang terdeteksi secara otomatis dalam konfigurasi SEO Network. Sistem akan mendeteksi berbagai jenis masalah dan menampilkannya di Alert Center.

---

### C.5.2 Tipe Conflict

| Tipe | Deskripsi | Cara Memperbaiki |
|------|-----------|------------------|
| **Orphan Node** | Node yang tidak terhubung ke struktur utama | Hubungkan ke node parent atau hapus |
| **Tier Inversion** | Child node memiliki tier lebih tinggi dari parent | Perbaiki tier assignment |
| **Canonical Mismatch** | URL canonical tidak konsisten | Perbaiki canonical tags |
| **Redirect Chain** | Terlalu banyak redirect berurutan | Simplifikasi redirect |
| **Missing Backlink** | Backlink yang direncanakan tidak ada | Buat backlink atau hapus dari plan |
| **Broken Link** | Link yang mengarah ke halaman error | Perbaiki atau hapus link |

---

### C.5.3 Severity Level

| Level | Warna | Urgensi |
|-------|-------|---------|
| **Critical** | Merah | Perlu tindakan segera, berdampak besar |
| **High** | Orange | Penting, perlu ditangani dalam waktu dekat |
| **Medium** | Kuning | Perlu perhatian, tidak urgent |
| **Low** | Hijau | Informasional, bisa ditangani nanti |

---

### C.5.4 Dashboard Metrics

Halaman Alert Center menampilkan metrics:

| Metric | Deskripsi |
|--------|-----------|
| **Total Conflicts** | Jumlah total konflik (resolved + open) |
| **Resolution Rate** | Persentase konflik yang sudah diselesaikan |
| **Avg Resolution Time** | Rata-rata waktu penyelesaian konflik |
| **Recurring Conflicts** | Konflik yang muncul kembali setelah resolved |
| **False Resolution Rate** | Persentase konflik yang muncul lagi dalam 7 hari |

---

### C.5.5 Tracked Conflicts Table

Tabel menampilkan semua konflik dengan informasi:
- **Type**: Jenis konflik
- **Severity**: Tingkat keparahan
- **Status**: Detected/In Progress/Approved/Resolved
- **Node**: Node yang terdampak
- **Network**: Network terkait
- **Detected**: Tanggal terdeteksi
- **Resolved**: Tanggal diselesaikan
- **Action**: Tombol View Task

**Tab Filter:**
- **All**: Semua konflik
- **Detected**: Baru terdeteksi
- **In Progress**: Sedang ditangani
- **Resolved**: Sudah diselesaikan

---

### C.5.6 Create Optimization Tasks

**Tujuan:** Membuat optimization task dari konflik yang terdeteksi

**Langkah-langkah:**

1. Di Alert Center, klik tombol **"Create Optimization Tasks"**
2. Sistem akan:
   - Memproses konflik yang statusnya "Detected"
   - Membuat optimization task untuk setiap konflik
   - Menghubungkan konflik dengan optimization
3. Hasil ditampilkan: "Processed X conflicts, created Y optimizations"

---

### C.5.7 View Task

**Tujuan:** Melihat optimization yang terhubung dengan konflik

**Langkah-langkah:**

1. Di tabel konflik, klik tombol **"View Task"**
2. Anda akan diarahkan ke halaman Optimization Detail
3. Di sini Anda bisa:
   - Melihat detail optimization
   - Update status
   - Add responses
   - Mark as completed

> **Gambar 7 - Alert Center / SEO Conflicts**
> Dashboard konflik dengan metrics dan tabel tracked conflicts

---

## C.6 Domain Monitoring

### C.6.1 Konsep Monitoring

Domain Monitoring memantau 2 aspek utama:

1. **Availability Monitoring**: Memeriksa apakah domain UP atau DOWN
2. **Expiration Monitoring**: Memberikan alert sebelum domain expired

---

### C.6.2 Mengaktifkan Monitoring Toggle

**Tujuan:** Mengaktifkan atau menonaktifkan monitoring untuk domain tertentu

**Langkah-langkah:**

1. Di halaman Asset Domains, cari domain
2. Di kolom **"Monitoring Toggle"**, klik switch ON/OFF
3. Status monitoring akan berubah

**Atau via Edit Domain:**
1. Edit domain yang diinginkan
2. Toggle field **"Enable Monitoring"**
3. Save changes

**Catatan Penting:**
- Domain dengan monitoring OFF tidak akan dicek availability-nya
- Domain tanpa tanggal expiration tidak akan mendapat expiration alerts

---

### C.6.3 Monitoring Intervals

**Expiration Monitoring:**
| Waktu ke Expiry | Frekuensi Alert |
|-----------------|-----------------|
| 30+ hari | Sekali |
| 14 hari | Sekali |
| 7 hari | Sekali |
| 3 hari | Sekali |
| 1 hari | Sekali |
| < 1 hari | 2x sehari |
| Expired | Sekali |

**Availability Monitoring:**
| Domain Type | Check Interval |
|-------------|----------------|
| Money Site / LP | 5 menit |
| Tier 1 | 15 menit |
| Tier 2+ | 1 jam |
| Non-SEO Domain | 6 jam |

---

### C.6.4 Status Monitoring

| Status | Indikator | Artinya |
|--------|-----------|---------|
| **Up** | Hijau | Domain accessible dengan status 200 |
| **Down** | Merah | Domain tidak bisa diakses (timeout, error) |
| **Soft Blocked** | Kuning | Domain ter-block oleh firewall/CDN |
| **JS Challenge** | Kuning | Cloudflare JS challenge aktif |
| **Captcha** | Kuning | Captcha challenge muncul |
| **Unknown** | Abu-abu | Belum pernah dicek atau monitoring OFF |

---

### C.6.5 SEO Context Enrichment

Untuk domain yang ada di SEO Network, alert akan diperkaya dengan informasi:
- Tier domain dalam network
- Parent node (jika ada)
- Impact ke money site
- Struktur SEO yang terdampak

---

### C.6.6 Test Alerts

**Tujuan:** Menguji apakah alert dikirim dengan benar

**Lokasi:** Settings > Domain Monitoring > Test Alerts tab

**Langkah-langkah:**

1. Buka halaman Monitoring Settings
2. Klik tab **"Test Alerts"**
3. Pilih jenis alert yang ingin ditest:
   - **Test Expiration Alert**: Kirim test alert expiration
   - **Test Domain Down Alert**: Kirim test alert domain down
4. Klik tombol test yang sesuai
5. Cek Telegram untuk menerima test message

> **Gambar 8 - Monitoring Settings**
> Halaman pengaturan monitoring dengan tab Expiration, Availability, Test Alerts

---

## C.7 Reports

### C.7.1 Overview Reports

**Tujuan:** Melihat analytics dan laporan performa

**Akses:** Semua Role (terbatas untuk Viewer)

**Komponen:**

1. **Export Data**
   - Pilih network atau All Networks
   - Export JSON atau CSV

2. **Tier Distribution**
   - Bar chart distribusi domain per tier
   - LP/Money Site, Tier 1, 2, 3, dst

3. **Index Status**
   - Donut chart status index
   - Indexed vs Noindex

4. **Brand Health Overview**
   - Tabel health score per brand
   - Total, Indexed, Noindex, Health Score %

5. **Orphan Domains**
   - Daftar domain yang orphan (tidak terhubung)

> **Gambar 9 - Reports Dashboard**
> Halaman reports dengan Tier Distribution chart, Index Status, dan Brand Health

---

## C.8 Team Evaluation

### C.8.1 Overview Team Evaluation

**Tujuan:** Melihat performa tim SEO berdasarkan optimization

**Akses:** Admin, Super Admin

**Komponen:**

1. **Summary Metrics**
   - Total Optimizations
   - Completed
   - Total Complaints
   - Reverted

2. **Top Contributors**
   - Ranking tim berdasarkan performa
   - Score: Berdasarkan completed/complaints ratio
   - Status: Excellent, Good, Needs Improvement

3. **Status Distribution**
   - Pie chart distribusi status optimization
   - Completed, In Progress, Planned, Reverted

4. **Activity Types**
   - Bar chart jenis aktivitas yang paling banyak dikerjakan

5. **Attention Required**
   - Daftar user dengan complaints yang perlu direview

> **Gambar 10 - Team Evaluation**
> Dashboard evaluasi tim dengan metrics, top contributors, dan charts

---

## C.9 Master Data Management

### C.9.1 Brands

**Tujuan:** Mengelola master data brand

**Akses:** Admin, Super Admin

**Langkah-langkah Menambah Brand:**

1. Buka menu **"Brands"**
2. Klik **"+ Add Brand"**
3. Isi:
   - **Brand Name**: Nama brand (wajib, unik)
   - **Description**: Deskripsi brand
4. Klik **"Save"**

---

### C.9.2 Categories

**Tujuan:** Mengelola kategori domain

**Akses:** Admin, Super Admin

**Kategori Default:**
- FRESH DOMAIN
- AGED DOMAIN
- REDIRECT DOMAIN
- AMP Domain
- MONEY SITE
- SUBDOMAIN MS
- PBN
- PARKING

---

### C.9.3 Registrars

**Tujuan:** Mengelola daftar registrar domain

**Akses:** Admin, Super Admin

---

### C.9.4 Activity Types

**Tujuan:** Mengelola jenis aktivitas optimization

**Akses:** Admin, Super Admin

**Activity Types Default:**
- Backlink
- Onpage
- Content
- Technical
- Conflict Resolution

---

### C.9.5 Quarantine Categories

**Tujuan:** Mengelola kategori alasan karantina domain

**Akses:** Super Admin

**Lokasi:** Menu Quarantine Categories

**Kategori Default:**
- Spam (Pure Spam)
- DMCA
- Manual Penalty
- Rollback / Restore
- Penalized
- Hacked Site
- Other

> **Gambar 11 - Quarantine Categories**
> Halaman pengelolaan kategori karantina

---

## C.10 User Management

### C.10.1 Daftar Users

**Tujuan:** Melihat dan mengelola semua user

**Akses:** Super Admin

**Komponen:**
- Tab **"All Users"**: Semua user terdaftar
- Tab **"Pending Approvals"**: User yang menunggu approval

**Kolom Tabel:**
- User (nama dan avatar)
- Email
- Telegram
- Role
- Status (Active/Rejected)
- Brand Access
- Joined Date
- Actions

---

### C.10.2 User Approval

**Langkah-langkah:**

1. Klik tab **"Pending Approvals"**
2. Review data user
3. Klik **"Approve"** atau **"Reject"**
4. Jika approve, tentukan:
   - Role (Super Admin/Admin/Viewer)
   - Brand Access

---

### C.10.3 Edit User

**Langkah-langkah:**

1. Di daftar user, klik ikon **Edit**
2. Update field yang diperlukan:
   - Name
   - Role
   - Brand Access
   - Status
3. Klik **"Save"**

> **Gambar 12 - User Management**
> Halaman users dengan tabel dan tab pending approvals

---

## C.11 Settings

### C.11.1 Branding

**Tujuan:** Mengkustomisasi tampilan aplikasi

**Akses:** Super Admin

**Field yang dapat diatur:**
- **Site Title**: Judul yang muncul di tab browser dan sidebar
- **Tagline**: Deskripsi singkat di halaman login
- **Site Description**: Meta description
- **Logo**: Upload logo custom (PNG, JPEG, SVG, WebP)

---

### C.11.2 Timezone

**Tujuan:** Mengatur timezone sistem

**Akses:** Super Admin

---

### C.11.3 SEO Notifications (Telegram)

**Tujuan:** Mengonfigurasi notifikasi Telegram untuk event SEO

**Akses:** Super Admin

**Field yang perlu diisi:**

1. **Bot Token**: Token dari BotFather Telegram
2. **Chat ID**: ID grup atau channel Telegram
3. **Forum Topic Routing** (opsional): 
   - Routing notifikasi ke topic berbeda berdasarkan jenis

**Global SEO Leaders:**
- Telegram username yang akan di-tag di semua notifikasi
- Format: username tanpa @

---

### C.11.4 Domain Monitoring Telegram

**Tujuan:** Mengonfigurasi notifikasi Telegram khusus untuk monitoring

**Akses:** Super Admin

**Catatan:** Bisa menggunakan channel/grup yang berbeda dari SEO Notifications

---

### C.11.5 Performance Alerts

**Tujuan:** Mengatur threshold untuk alert performa tim

**Akses:** Super Admin

**Threshold yang dapat diatur:**
- Minimum completion rate
- Maximum complaint rate
- Alert interval

---

### C.11.6 Templates

**Tujuan:** Mengkustomisasi template pesan notifikasi

**Akses:** Super Admin

**Jenis Template:**
- Domain Expiration Alert
- Domain Down Alert
- SEO Change Notification
- Optimization Created
- Complaint Filed

**Cara Edit Template:**

1. Buka tab **"Templates"**
2. Pilih template yang ingin diedit
3. Modifikasi text template
4. Gunakan placeholder/variable yang tersedia
5. Klik **"Save"**
6. Untuk reset ke default, klik **"Reset to Default"**

> **Gambar 13 - Settings - SEO Notifications**
> Halaman pengaturan notifikasi Telegram

---

## C.12 Audit & Activity Logs

### C.12.1 Audit Logs

**Tujuan:** Melihat log semua event sistem

**Akses:** Super Admin

**Informasi yang ditampilkan:**
- Timestamp
- Actor (System/User)
- Event Type
- Resource
- Severity
- Status
- Details

**Filter yang tersedia:**
- Event Type
- Severity
- Status

---

### C.12.2 V3 Activity Logs

**Tujuan:** Melihat log perubahan SEO Network

**Akses:** Admin, Super Admin

**Jenis aktivitas yang ditrack:**
- Node created/updated/deleted
- Network created/updated/deleted
- Optimization created/completed
- Complaint filed/resolved

> **Gambar 14 - Audit Logs**
> Halaman audit logs dengan filter dan tabel events

---

# BAGIAN D: TROUBLESHOOTING & FAQ

## D.1 Kenapa Monitoring Status masih "Unknown"?

**Penyebab:**
1. Monitoring Toggle dalam keadaan OFF
2. Domain baru ditambahkan dan belum dicek
3. Scheduler monitoring belum berjalan

**Solusi:**
1. Pastikan Monitoring Toggle ON untuk domain tersebut
2. Tunggu hingga interval check berikutnya
3. Atau gunakan tombol "Check Availability" di Monitoring Settings untuk manual check

---

## D.2 Kenapa tidak bisa Save/Edit (Permission Error)?

**Penyebab:**
1. Role tidak memiliki permission edit
2. User tidak memiliki akses ke brand terkait
3. Menu access dinonaktifkan

**Solusi:**
1. Hubungi Super Admin untuk update permission
2. Minta akses ke brand yang diperlukan

---

## D.3 Kenapa Conflict tidak muncul di Alert Center?

**Penyebab:**
1. Conflict detection belum dijalankan
2. Filter aktif yang menyembunyikan conflict

**Solusi:**
1. Klik tombol Refresh di Alert Center
2. Reset semua filter
3. Periksa apakah network memiliki struktur yang valid

---

## D.4 Kenapa Notifikasi Telegram tidak terkirim?

**Penyebab:**
1. Bot Token tidak valid
2. Chat ID salah
3. Bot belum di-add ke grup
4. Notifikasi dinonaktifkan

**Solusi:**
1. Verifikasi Bot Token di BotFather
2. Pastikan Chat ID benar (bisa negatif untuk grup)
3. Add bot ke grup dan jadikan admin
4. Cek toggle "Aktifkan Notifikasi" sudah ON
5. Gunakan tombol "Kirim Test" untuk verifikasi

---

## D.5 Cara Cek Topic ID Telegram

**Langkah-langkah:**

1. Buka grup Telegram yang memiliki Forum/Topics
2. Buka topic yang diinginkan
3. Di URL, cari angka setelah "/"
   - Format: `https://t.me/c/XXXXXXXXX/TOPIC_ID`
4. TOPIC_ID adalah angka yang Anda butuhkan

---

## D.6 Cara Test Alert sebelum Production

**Langkah-langkah:**

1. Buka Settings > Domain Monitoring
2. Klik tab "Test Alerts"
3. Pilih jenis alert:
   - "Test Expiration Alert"
   - "Test Domain Down Alert"
4. Klik tombol yang sesuai
5. Cek Telegram untuk menerima pesan test

---

## D.7 Domain sudah Expired tapi Lifecycle masih Active?

**Penjelasan:**
- **Domain Active Status** (Active/Expired) otomatis berdasarkan tanggal expiration
- **Lifecycle Status** (Active/Released/Quarantined/Not Renewed) adalah status manual yang diatur user

**Solusi:**
Jika domain memang sudah tidak digunakan:
1. Edit domain
2. Ubah Lifecycle Status menjadi "Not Renewed" atau "Released"
3. Save changes

---

## D.8 Error "Invalid Credentials" saat Login

**Penyebab:**
1. Email atau password salah
2. Akun belum di-approve
3. Akun di-reject atau suspended

**Solusi:**
1. Pastikan email benar (case-sensitive)
2. Pastikan password benar (case-sensitive)
3. Hubungi Super Admin untuk cek status akun

---

# BAGIAN E: APPENDIX

## E.1 Daftar Istilah (Glossary Lengkap)

| Istilah | Definisi |
|---------|----------|
| Asset Domain | Domain yang dimiliki dan dikelola oleh perusahaan |
| Availability | Status ketersediaan domain (UP/DOWN) |
| Backlink | Link dari satu website ke website lain |
| Brand | Unit bisnis atau portfolio dalam sistem |
| Brand Scope | Batasan akses user terhadap brand tertentu |
| Canonical | URL utama yang diakui oleh search engine |
| Conflict | Masalah/inkonsistensi dalam konfigurasi SEO |
| Domain Active Status | Status aktif domain berdasarkan expiration (Active/Expired) |
| Expiration | Tanggal berakhirnya registrasi domain |
| Index Rate | Persentase domain yang ter-index di search engine |
| Lifecycle | Siklus hidup domain (Active/Released/Quarantined/Not Renewed) |
| LP (Landing Page) | Halaman yang menerima traffic langsung |
| Manager | User dengan akses mengelola network tertentu |
| Money Site | Website utama yang menjadi target SEO |
| Monitoring Toggle | Switch untuk mengaktifkan/menonaktifkan monitoring |
| Node | Satu entry domain dalam SEO Network |
| Noindex | Tag yang memberitahu search engine untuk tidak mengindex |
| Optimization | Task/tugas optimasi SEO |
| Orphan Node | Node yang tidak terhubung ke struktur utama |
| PBN | Private Blog Network |
| Quarantine | Status karantina untuk domain bermasalah |
| Redirect | Pengalihan dari satu URL ke URL lain |
| SEO Network | Struktur jaringan domain untuk keperluan SEO |
| Tier | Level dalam struktur SEO Network |
| Viewer | Role user dengan akses read-only |

---

## E.2 Contoh Format Notifikasi Telegram

### Notifikasi Domain Expiration

```
⚠️ DOMAIN EXPIRATION ALERT

📛 Domain: example.com
🏷️ Brand: PANEN77
📅 Expires: Feb 15, 2026 (3 days)
🔴 Priority: High

🧭 STRUKTUR SEO TERKINI:
├─ Network: Test Network V5
├─ Tier: Tier 1
└─ Parent: moneysite.com

💡 Tindakan: Perpanjang domain sebelum expired

@leader1
```

### Notifikasi Domain Down

```
🔴 DOMAIN DOWN ALERT

📛 Domain: tier1-site1.com
🏷️ Brand: Panen138
⏰ Down Since: Feb 10, 2026, 09:56 PM
🔍 Status: Connection Timeout

🧭 STRUKTUR SEO TERKINI:
├─ Network: TESTER2 Updated
├─ Tier: Tier 1
└─ Impact: Money Site may be affected

💡 Tindakan: Periksa server dan DNS

@leader1
```

### Notifikasi SEO Change

```
📝 SEO NETWORK UPDATE

🔄 Action: Node Created
📛 Domain: new-tier2.com
🌐 Network: Test Network V5
👤 By: Test Manager

📊 Details:
├─ Tier: Tier 2
├─ Parent: tier1-site1.com
└─ Index Status: Pending

@leader1
```

---

## E.3 Template Variables Reference

### Domain Expiration Template

| Variable | Deskripsi |
|----------|-----------|
| `{domain}` | Nama domain |
| `{brand}` | Nama brand |
| `{expiration_date}` | Tanggal expiration |
| `{days_until_expiry}` | Hari sampai expired |
| `{priority}` | Level prioritas |
| `{network_name}` | Nama network (jika ada) |
| `{tier}` | Tier dalam network |
| `{parent_node}` | Parent node (jika ada) |

### Domain Monitoring Template

| Variable | Deskripsi |
|----------|-----------|
| `{domain}` | Nama domain |
| `{brand}` | Nama brand |
| `{status}` | Status monitoring |
| `{down_since}` | Waktu mulai down |
| `{error_message}` | Pesan error |
| `{network_name}` | Nama network |
| `{tier}` | Tier dalam network |
| `{impact}` | Dampak ke money site |

### SEO Change Template

| Variable | Deskripsi |
|----------|-----------|
| `{action}` | Jenis aksi (Create/Update/Delete) |
| `{domain}` | Nama domain |
| `{network}` | Nama network |
| `{user}` | User yang melakukan |
| `{timestamp}` | Waktu perubahan |
| `{details}` | Detail perubahan |

---

## E.4 Checklist Operasional

### Checklist Harian

- [ ] Cek Dashboard untuk alert aktif
- [ ] Review Recent Alerts
- [ ] Proses domain yang akan expired dalam 7 hari
- [ ] Cek domain DOWN dan tindak lanjuti
- [ ] Review optimization yang masuk

### Checklist Mingguan

- [ ] Review semua konflik di Alert Center
- [ ] Create optimization tasks untuk konflik baru
- [ ] Review Team Evaluation metrics
- [ ] Update domain yang statusnya berubah
- [ ] Backup data penting

### Checklist Bulanan

- [ ] Audit semua SEO Networks
- [ ] Review dan update struktur network
- [ ] Evaluasi performa tim
- [ ] Review domain yang di-quarantine
- [ ] Update master data (brands, categories)

---

## E.5 Kontak Support

Jika mengalami masalah yang tidak bisa diselesaikan:

1. **Dokumentasi Internal**: Cek wiki/dokumentasi tim
2. **Super Admin**: Hubungi Super Admin untuk masalah akses
3. **IT Support**: Untuk masalah teknis sistem

---

**--- AKHIR DOKUMEN ---**

*Dokumen ini dibuat untuk SEO-NOC versi 1.0*
*Terakhir diupdate: Februari 2026*
