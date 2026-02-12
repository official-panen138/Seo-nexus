import { useState, useMemo } from 'react';
import { Layout } from '../components/Layout';
import { Card, CardContent } from '../components/ui/card';
import { ScrollArea } from '../components/ui/scroll-area';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { 
    BookOpen, 
    Search, 
    ChevronRight, 
    ChevronDown,
    ChevronLeft,
    Home,
    Shield,
    Globe,
    HelpCircle,
    Bookmark,
    CheckCircle,
    Info,
    Image as ImageIcon,
    ExternalLink
} from 'lucide-react';

// Flatten all sections for navigation
const getAllSections = (tocData) => {
    const sections = [];
    tocData.forEach(chapter => {
        chapter.sections.forEach(section => {
            sections.push({
                ...section,
                chapterId: chapter.id,
                chapterTitle: chapter.title
            });
        });
    });
    return sections;
};

// Table of Contents Data
const tocData = [
    {
        id: 'getting-started',
        title: 'A. Getting Started',
        icon: Home,
        sections: [
            { id: 'overview', title: 'A.1 Overview Aplikasi', hasImage: true },
            { id: 'requirements', title: 'A.2 System Requirements' },
            { id: 'login', title: 'A.3 Login & Logout', hasImage: true },
            { id: 'register', title: 'A.4 Registrasi Akun', hasImage: true },
            { id: 'navigation', title: 'A.5 Navigasi Menu', hasImage: true },
            { id: 'glossary', title: 'A.6 Glossary' },
        ]
    },
    {
        id: 'roles',
        title: 'B. Role & Permissions',
        icon: Shield,
        sections: [
            { id: 'role-types', title: 'B.1 Jenis Role' },
            { id: 'permissions', title: 'B.2 Perbandingan Hak Akses' },
            { id: 'brand-scope', title: 'B.3 Brand Scoping' },
            { id: 'menu-access', title: 'B.4 Menu Access Control' },
            { id: 'permission-errors', title: 'B.5 Menangani Error Permission' },
        ]
    },
    {
        id: 'modules',
        title: 'C. Modul Utama',
        icon: Globe,
        sections: [
            { id: 'dashboard', title: 'C.1 Dashboard', hasImage: true },
            { id: 'asset-domains', title: 'C.2 Asset Domains', hasImage: true },
            { id: 'seo-networks', title: 'C.3 SEO Networks', hasImage: true },
            { id: 'optimizations', title: 'C.4 Optimizations' },
            { id: 'conflicts', title: 'C.5 SEO Conflicts', hasImage: true },
            { id: 'monitoring', title: 'C.6 Domain Monitoring', hasImage: true },
            { id: 'reports', title: 'C.7 Reports', hasImage: true },
            { id: 'team-eval', title: 'C.8 Team Evaluation', hasImage: true },
            { id: 'master-data', title: 'C.9 Master Data' },
            { id: 'users', title: 'C.10 User Management', hasImage: true },
            { id: 'settings', title: 'C.11 Settings', hasImage: true },
            { id: 'audit-logs', title: 'C.12 Audit Logs' },
        ]
    },
    {
        id: 'troubleshooting',
        title: 'D. Troubleshooting & FAQ',
        icon: HelpCircle,
        sections: [
            { id: 'faq-monitoring', title: 'D.1 Monitoring Status Unknown' },
            { id: 'faq-permission', title: 'D.2 Permission Error' },
            { id: 'faq-conflicts', title: 'D.3 Conflicts tidak muncul' },
            { id: 'faq-telegram', title: 'D.4 Telegram tidak terkirim' },
        ]
    },
    {
        id: 'appendix',
        title: 'E. Appendix',
        icon: Bookmark,
        sections: [
            { id: 'full-glossary', title: 'E.1 Daftar Istilah Lengkap' },
            { id: 'telegram-examples', title: 'E.2 Contoh Notifikasi Telegram' },
            { id: 'checklist', title: 'E.3 Checklist Operasional' },
        ]
    }
];

// Screenshot URLs - actual generated images for each section
const sectionImages = {
    'overview': 'https://static.prod-images.emergentagent.com/jobs/f75a7479-a250-46ba-b604-bc372d67aeda/images/d6e8683b52a165baae0f907472cdaaa66c067fb993704a57372aa4931c44d992.png',
    'login': 'https://static.prod-images.emergentagent.com/jobs/f75a7479-a250-46ba-b604-bc372d67aeda/images/2852e4bc8c15c1f62a555ac73c073ce318288099c77469673af210cc5f47f2e8.png',
    'register': 'https://static.prod-images.emergentagent.com/jobs/f75a7479-a250-46ba-b604-bc372d67aeda/images/83c5ddb793dbae50d4b7d07d2b1b9c8cc36ca8c337f4295c0904c78253195fa5.png',
    'navigation': 'https://static.prod-images.emergentagent.com/jobs/f75a7479-a250-46ba-b604-bc372d67aeda/images/20f0ea1615c719a4bb711c927d31b0f6ebbdc121b9889c8cb587550f90aa9176.png',
    'dashboard': 'https://static.prod-images.emergentagent.com/jobs/f75a7479-a250-46ba-b604-bc372d67aeda/images/d6e8683b52a165baae0f907472cdaaa66c067fb993704a57372aa4931c44d992.png',
    'asset-domains': 'https://static.prod-images.emergentagent.com/jobs/f75a7479-a250-46ba-b604-bc372d67aeda/images/2952a1816adc5e91ecfbd5ba2176a4c777df29419d30d1400502f5e8495a110e.png',
    'seo-networks': 'https://static.prod-images.emergentagent.com/jobs/f75a7479-a250-46ba-b604-bc372d67aeda/images/1b6849de127a893357df31f2aa02d89bc667c2002934e974883493190ec180c7.png',
    'conflicts': 'https://static.prod-images.emergentagent.com/jobs/f75a7479-a250-46ba-b604-bc372d67aeda/images/851b162f97be8a5a42c424b87ee5e7dd6d7d86ef43a2f560c30cb9bf73e8a995.png',
    'monitoring': 'https://static.prod-images.emergentagent.com/jobs/f75a7479-a250-46ba-b604-bc372d67aeda/images/43bc7d4e724094dbbf6464dec53813f005c35905f4d80a97d2c5f7e390e41650.png',
    'reports': 'https://static.prod-images.emergentagent.com/jobs/f75a7479-a250-46ba-b604-bc372d67aeda/images/dabd16e2201f03ed54a070ccf5b3344ca42a7f3c054ac8f4ea5823df55df3700.png',
    'team-eval': 'https://static.prod-images.emergentagent.com/jobs/f75a7479-a250-46ba-b604-bc372d67aeda/images/15f022504ad84c7e9960188224f5f81aef4129463d8d4910ea74cb7089782fc7.png',
    'users': 'https://static.prod-images.emergentagent.com/jobs/f75a7479-a250-46ba-b604-bc372d67aeda/images/5698fbb8d44a32d8cd36b2b32a4c3da68763048370e219cf48bac82f8d419bad.png',
    'settings': 'https://static.prod-images.emergentagent.com/jobs/f75a7479-a250-46ba-b604-bc372d67aeda/images/6f01c43704df446bd238cc257f29920dcb2e09ee80fe1035ce9b25adeb0ddf4d.png',
};

// Content sections with images
const contentSections = {
    'overview': {
        title: 'A.1 Overview Aplikasi SEO-NOC',
        image: { caption: 'Gambar 1 - Dashboard SEO-NOC', description: 'Tampilan utama dashboard dengan widget statistik' },
        content: `
## Apa itu SEO-NOC?

**SEO-NOC (SEO Network Operations Center)** adalah sistem manajemen domain dan jaringan SEO yang komprehensif. Aplikasi ini dirancang untuk membantu tim SEO dalam:

- **Mengelola Asset Domain** - Tracking semua domain yang dimiliki perusahaan
- **Memantau SEO Networks** - Visualisasi dan pengelolaan struktur jaringan SEO
- **Monitoring Domain** - Memantau status availability dan expiration domain
- **Mendeteksi SEO Conflicts** - Identifikasi otomatis masalah konfigurasi SEO
- **Tracking Optimizations** - Manajemen tugas dan optimasi SEO
- **Evaluasi Tim** - Metrics performa tim SEO

## Fitur Utama

| Fitur | Deskripsi |
|-------|-----------|
| Asset Domains | Database lengkap semua domain dengan status lifecycle |
| SEO Networks | Visualisasi graph struktur jaringan SEO |
| Alert Center | Dashboard konflik SEO dengan metrik resolusi |
| Domain Monitoring | Monitoring availability dan expiration domain |
| Telegram Alerts | Notifikasi otomatis via Telegram |
| Team Evaluation | Scoring performa tim berdasarkan optimizations |
| Multi-Brand Support | Pengelolaan multiple brand dalam satu sistem |
        `
    },
    'requirements': {
        title: 'A.2 System Requirements',
        content: `
## Browser yang Didukung

| Browser | Versi Minimum | Status |
|---------|---------------|--------|
| Google Chrome | 90+ | ✅ Direkomendasikan |
| Mozilla Firefox | 88+ | ✅ Didukung |
| Microsoft Edge | 90+ | ✅ Didukung |
| Safari | 14+ | ✅ Didukung |

## Persyaratan Lainnya

- **Koneksi Internet**: Minimum 1 Mbps (direkomendasikan 5 Mbps+)
- **Resolusi Layar**: Minimum 1280x720 (direkomendasikan 1920x1080)
- **JavaScript**: Harus diaktifkan
- **Cookies**: Harus diaktifkan

## Akun yang Diperlukan

1. Akun user yang terdaftar di sistem
2. Approval dari Super Admin (untuk akun baru)
3. Telegram account (opsional, untuk menerima notifikasi)
        `
    },
    'login': {
        title: 'A.3 Login & Logout',
        image: { caption: 'Gambar 2 - Halaman Login', description: 'Form login dengan field email dan password' },
        content: `
## Cara Login

**Tujuan:** Masuk ke dalam sistem SEO-NOC

### Langkah-langkah:

1. Buka browser dan akses URL aplikasi SEO-NOC
2. Anda akan melihat halaman login dengan form:
   - **Email Address**: Masukkan email yang terdaftar
   - **Password**: Masukkan password Anda
3. Klik tombol **"Sign In"**
4. Jika berhasil, Anda akan diarahkan ke Dashboard

**Expected Result:** Halaman Dashboard muncul dengan pesan "Welcome back, [Nama Anda]"

### Troubleshooting:

- **"Invalid credentials"**: Periksa kembali email dan password. Password bersifat case-sensitive.
- **Tidak bisa login**: Pastikan akun Anda sudah di-approve oleh Super Admin.
- **Halaman tidak loading**: Coba refresh browser atau clear cache.

## Cara Logout

1. Lihat sidebar menu di sebelah kiri
2. Scroll ke bawah hingga menemukan nama user Anda
3. Klik tombol **"Logout"** di bawah nama user
4. Anda akan diarahkan kembali ke halaman Login

> **Catatan:** Selalu logout setelah selesai menggunakan aplikasi, terutama di komputer bersama.
        `
    },
    'register': {
        title: 'A.4 Registrasi Akun Baru',
        image: { caption: 'Gambar 3 - Halaman Registrasi', description: 'Form registrasi akun baru' },
        content: `
## Membuat Akun Baru

**Tujuan:** Mendaftar sebagai user baru di SEO-NOC

### Langkah-langkah:

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

## Catatan Penting:

- User pertama yang mendaftar akan otomatis menjadi **Super Admin**
- User selanjutnya harus menunggu approval dan akan mendapat role **Viewer** secara default

## Approval Flow

**Untuk Super Admin:**

1. Login ke sistem
2. Buka menu **"Users"**
3. Klik tab **"Pending Approvals"**
4. Review data user yang mendaftar
5. Klik tombol **"Approve"** atau **"Reject"**
6. Jika approve, tentukan Role dan Brand Access
        `
    },
    'navigation': {
        title: 'A.5 Navigasi Menu & Struktur Sidebar',
        image: { caption: 'Gambar 4 - Sidebar Navigation', description: 'Struktur menu sidebar' },
        content: `
## Struktur Menu Utama

Sidebar menu di sebelah kiri layar berisi semua menu navigasi:

| Menu | Deskripsi | Hak Akses |
|------|-----------|-----------|
| Dashboard | Ringkasan data dan statistik | Semua |
| Asset Domains | Manajemen database domain | Semua |
| SEO Networks | Visualisasi jaringan SEO | Semua |
| Alert Center | Dashboard konflik SEO | Semua |
| Reports | Laporan dan analytics | Semua |
| Team Evaluation | Evaluasi performa tim | Admin+ |
| Brands | Master data brand | Admin+ |
| Categories | Master data kategori domain | Admin+ |
| Registrars | Master data registrar | Admin+ |
| Users | Manajemen user | Super Admin |
| Audit Logs | Log aktivitas sistem | Super Admin |
| Settings | Pengaturan sistem | Super Admin |

## Brand Switcher

Di bagian atas sidebar terdapat **Brand Switcher**:
- **All Brands**: Melihat data dari semua brand
- **[Nama Brand]**: Filter data untuk brand tertentu saja
        `
    },
    'glossary': {
        title: 'A.6 Glossary - Istilah Penting',
        content: `
## Istilah Dasar

| Istilah | Definisi |
|---------|----------|
| **Asset Domain** | Domain yang dimiliki dan dikelola oleh perusahaan |
| **SEO Network** | Struktur jaringan domain untuk keperluan SEO |
| **Tier** | Level dalam struktur SEO Network (Tier 1 = langsung ke Money Site) |
| **Money Site** | Website utama yang menjadi target SEO |
| **LP (Landing Page)** | Halaman yang menerima traffic langsung |
| **Node** | Satu entry domain dalam SEO Network |
| **Orphan Node** | Node yang tidak terhubung ke struktur utama |

## Istilah Teknis

| Istilah | Definisi |
|---------|----------|
| **Canonical** | URL utama yang diakui oleh search engine |
| **301 Redirect** | Permanent redirect dari satu URL ke URL lain |
| **Noindex** | Tag yang memberitahu search engine untuk tidak mengindex |
| **Lifecycle** | Status siklus hidup domain (Active/Released/Quarantined) |
| **Monitoring Toggle** | Switch untuk mengaktifkan/menonaktifkan monitoring |
| **Availability** | Status ketersediaan domain (UP/DOWN) |
| **Expiration** | Tanggal berakhirnya registrasi domain |
        `
    },
    'role-types': {
        title: 'B.1 Jenis Role',
        content: `
## Super Admin

**Deskripsi:** Administrator tertinggi dengan akses penuh ke seluruh sistem

**Kemampuan:**
- Akses ke semua menu dan fitur
- Mengelola user (approve, edit role, delete)
- Mengatur brand scope untuk user lain
- Mengakses Audit Logs dan Scheduler
- Mengonfigurasi semua settings sistem
- Mengirim Complaint pada optimizations

## Admin (Manager)

**Deskripsi:** Manager yang dapat mengelola network dan optimizations

**Kemampuan:**
- Melihat dan mengelola SEO Networks yang di-assign
- Membuat dan menyelesaikan optimizations
- Melihat reports dan team evaluation
- Merespons complaints dari Super Admin
- Tidak bisa mengelola users atau system settings

## Viewer

**Deskripsi:** User dengan akses read-only

**Kemampuan:**
- Melihat Dashboard, Asset Domains, SEO Networks
- Melihat reports (terbatas)
- Tidak bisa membuat atau edit data apapun
        `
    },
    'permissions': {
        title: 'B.2 Perbandingan Hak Akses per Role',
        content: `
## Tabel Perbandingan

| Fitur | Super Admin | Admin | Viewer |
|-------|:-----------:|:-----:|:------:|
| View Dashboard | ✅ | ✅ | ✅ |
| View Asset Domains | ✅ | ✅ | ✅ |
| Add/Edit Domain | ✅ | ✅ | ❌ |
| View SEO Networks | ✅ | ✅ | ✅ |
| Create/Edit Network | ✅ | ✅* | ❌ |
| Add/Edit Nodes | ✅ | ✅* | ❌ |
| View Alert Center | ✅ | ✅ | ✅ |
| Create Optimization | ✅ | ✅ | ❌ |
| Send Complaint | ✅ | ❌ | ❌ |
| Respond to Complaint | ❌ | ✅ | ❌ |
| View Reports | ✅ | ✅ | ✅* |
| View Team Evaluation | ✅ | ✅ | ❌ |
| Manage Users | ✅ | ❌ | ❌ |
| View Audit Logs | ✅ | ❌ | ❌ |
| Configure Settings | ✅ | ❌ | ❌ |
| Manage Master Data | ✅ | ✅ | ❌ |

> *Terbatas pada network yang di-assign atau view-only
        `
    },
    'brand-scope': {
        title: 'B.3 Brand Scoping',
        content: `
## Konsep Brand Scoping

Brand Scoping membatasi user untuk hanya dapat mengakses data dari brand tertentu saja.

**Contoh:**
- User A di-assign ke brand "PANEN77" dan "Panen138"
- User A hanya bisa melihat dan mengelola domain/network dari 2 brand tersebut
- Data dari brand lain tidak akan muncul untuk User A

## Cara Mengatur Brand Scope (Super Admin Only)

1. Buka menu **"Users"**
2. Cari user yang akan diatur
3. Klik ikon **Edit** (pensil)
4. Di bagian **"Brand Access"**, pilih brand yang diizinkan
5. Klik **"Save Changes"**

## Catatan Penting:

- Super Admin dengan "All Brands" access dapat melihat semua data
- User tanpa brand scope tidak bisa mengakses data apapun
        `
    },
    'menu-access': {
        title: 'B.4 Menu Access Control',
        content: `
## Konsep Menu Access Control

Selain role, akses ke menu tertentu juga bisa diatur per-user melalui Menu Access Control.

## Langkah-langkah (Super Admin Only):

1. Buka menu **"Users"**
2. Cari user yang akan diatur
3. Klik ikon **Menu (...)** → **"Manage Menu Access"**
4. Toggle ON/OFF untuk setiap menu yang diizinkan
5. Klik **"Save"**

## Reset Menu Access

Untuk mengembalikan ke pengaturan default berdasarkan role:
1. Buka dialog Menu Access
2. Klik tombol **"Reset to Default"**
        `
    },
    'permission-errors': {
        title: 'B.5 Menangani Error Permission (403)',
        content: `
## Penyebab Error 403

Error 403 muncul ketika user mencoba mengakses fitur yang tidak diizinkan.

**Penyebab umum:**
1. Role tidak memiliki akses ke fitur tersebut
2. User tidak memiliki brand scope yang sesuai
3. Menu access dinonaktifkan untuk user tersebut

## Cara Mengatasi

**Jika Anda adalah user biasa:**
- Hubungi Super Admin untuk meminta akses
- Jelaskan fitur apa yang perlu diakses dan alasannya

**Jika Anda adalah Super Admin:**
1. Periksa role user - apakah sudah sesuai?
2. Periksa brand scope - apakah user punya akses ke brand tersebut?
3. Periksa menu access control - apakah menu tersebut diaktifkan?
        `
    },
    'dashboard': {
        title: 'C.1 Dashboard',
        image: { caption: 'Gambar 5 - Dashboard Overview', description: 'Dashboard dengan widget statistik dan panel informasi' },
        content: `
## Overview Dashboard

**Tujuan:** Melihat ringkasan data dan statistik sistem secara keseluruhan

**Akses:** Semua Role

## Widget Utama

Dashboard menampilkan 6 widget utama:

| Widget | Deskripsi |
|--------|-----------|
| **DOMAINS** | Total jumlah domain di database |
| **NETWORKS** | Total jumlah SEO Network |
| **MONITORED** | Jumlah domain yang dimonitoring (UP/DOWN) |
| **INDEX RATE** | Persentase domain yang ter-index |
| **ACTIVE ALERTS** | Jumlah alert yang aktif |
| **BRANDS** | Total jumlah brand |

## Panel Domains by Brand

Menampilkan distribusi domain per brand:
- Nama brand
- Jumlah domain untuk masing-masing brand
- Total keseluruhan domain

## Panel Monitoring Status

Visualisasi donut chart status monitoring:
- **Hijau (Up)**: Domain yang accessible
- **Merah (Down)**: Domain yang tidak accessible
- **Abu-abu (Unknown)**: Domain yang belum dicek

## Panel Recent Alerts

Menampilkan alert terbaru dengan badge severity:
- **Critical** (Merah): Alert sangat penting
- **High** (Orange): Alert penting
- **Low** (Abu-abu): Alert informasional
        `
    },
    'asset-domains': {
        title: 'C.2 Asset Domains',
        image: { caption: 'Gambar 6 - Asset Domains', description: 'Tabel manajemen domain dengan kolom status' },
        content: `
## Tampilan Halaman

**Tujuan:** Mengelola database semua domain yang dimiliki

**Akses:** Semua Role (Edit: Admin+)

## Komponen Halaman:

1. **Header Section**
   - Judul "Asset Domains"
   - Tombol: Refresh, Export, Import CSV, Add Domain

2. **SEO Monitoring Coverage Panel**
   - Domains in SEO: Domain di SEO Networks
   - Monitored: Domain dengan monitoring aktif
   - Coverage %: Persentase coverage

3. **Tab Navigation**
   - All Domains / Unmonitored in SEO / Released / Quarantined / Not Renewed

4. **Domain Table**
   - Domain, Brand, Category, Status, Lifecycle, SEO Networks, Monitoring, Expiration

## Menambah Domain Baru

1. Klik tombol **"+ Add Domain"**
2. Isi form:
   - Domain Name (wajib)
   - Brand (wajib)
   - Category, Registrar, Expiration Date
3. Klik **"Save"**

## Import via CSV

1. Klik **"Import CSV"**
2. Upload file CSV
3. Review preview
4. Klik **"Confirm Import"**
        `
    },
    'seo-networks': {
        title: 'C.3 SEO Networks',
        image: { caption: 'Gambar 7 - SEO Networks', description: 'Visual graph struktur jaringan SEO' },
        content: `
## Daftar Network

**Tujuan:** Melihat dan mengelola semua SEO Network

**Akses:** Semua Role (Create/Edit: Admin+)

## Network Detail Page

Setelah klik "View" pada network card:

| Tab | Deskripsi |
|-----|-----------|
| Visual Graph | Visualisasi struktur network |
| Domain List | Daftar semua node dalam network |
| Change History | Log perubahan |
| Optimizations | Daftar optimization terkait |
| Complaints | Daftar complaint |
| Managers | Pengelolaan manager |
| Settings | Pengaturan network |

## Cara Membaca Visual Graph

**Warna Node berdasarkan Tier:**
- Merah/Orange: LP/Money Site
- Kuning: Tier 1
- Hijau Tua: Tier 2
- Hijau Muda: Tier 3
- Biru: Tier 4
- Abu-abu: Tier 5+
- Ungu: Noindex

**Interaksi:**
- Klik node untuk melihat detail
- Drag untuk menggeser posisi
- Scroll untuk zoom in/out
        `
    },
    'optimizations': {
        title: 'C.4 Optimizations',
        content: `
## Apa itu Optimization?

Optimization adalah task/tugas optimasi SEO yang perlu dikerjakan.

## Status Optimization

| Status | Warna | Keterangan |
|--------|-------|------------|
| Planned | Biru | Belum dikerjakan |
| In Progress | Kuning | Sedang dikerjakan |
| Completed | Hijau | Sudah selesai |
| Reverted | Merah | Di-rollback |
| Blocked | Abu-abu | Terblokir |

## Complaint Flow

### Mengirim Complaint (Super Admin Only)
1. Buka detail Optimization
2. Klik **"File Complaint"**
3. Isi form complaint
4. Submit

### Merespons Complaint (Manager Only)
1. Buka Optimization dengan complaint
2. Di panel Team Responses, klik **"Add Response"**
3. Isi response dan evidence
4. Submit

### Resolving Complaint
Setelah manager merespons, Super Admin dapat resolve complaint.

> **Catatan:** Optimization dengan complaint aktif tidak bisa di-close
        `
    },
    'conflicts': {
        title: 'C.5 SEO Conflicts (Alert Center)',
        image: { caption: 'Gambar 8 - Alert Center', description: 'Dashboard konflik SEO dengan metrik dan tabel' },
        content: `
## Apa itu SEO Conflict?

SEO Conflict adalah masalah yang terdeteksi otomatis dalam konfigurasi SEO Network.

## Tipe Conflict

| Tipe | Deskripsi |
|------|-----------|
| Orphan Node | Node tidak terhubung ke struktur |
| Tier Inversion | Child tier lebih tinggi dari parent |
| Canonical Mismatch | URL canonical tidak konsisten |
| Redirect Chain | Terlalu banyak redirect |

## Severity Level

| Level | Urgensi |
|-------|---------|
| Critical | Perlu tindakan segera |
| High | Penting, tangani segera |
| Medium | Perlu perhatian |
| Low | Informasional |

## Dashboard Metrics

- **Total Conflicts**: Jumlah total konflik
- **Resolution Rate**: Persentase resolved
- **Avg Resolution Time**: Rata-rata waktu penyelesaian
- **Recurring Conflicts**: Konflik yang muncul kembali

## Create Optimization Tasks

Klik tombol **"Create Optimization Tasks"** untuk membuat task dari konflik yang terdeteksi.
        `
    },
    'monitoring': {
        title: 'C.6 Domain Monitoring',
        image: { caption: 'Gambar 9 - Monitoring Settings', description: 'Pengaturan monitoring domain' },
        content: `
## Konsep Monitoring

Domain Monitoring memantau 2 aspek:
1. **Availability Monitoring**: UP/DOWN
2. **Expiration Monitoring**: Alert sebelum expired

## Monitoring Status

| Status | Keterangan |
|--------|------------|
| Up | Domain accessible |
| Down | Domain tidak accessible |
| Soft Blocked | Ter-block oleh WAF/CDN |
| JS Challenge | Cloudflare challenge |
| Unknown | Belum dicek atau OFF |

## Monitoring Intervals

**Expiration:**
- 30 hari: Sekali
- 14 hari: Sekali
- 7 hari: Sekali
- < 7 hari: 2x sehari

**Availability:**
- Money Site: 5 menit
- Tier 1: 15 menit
- Tier 2+: 1 jam

## Test Alerts

1. Buka Settings > Domain Monitoring
2. Tab **"Test Alerts"**
3. Klik test yang sesuai
4. Cek Telegram
        `
    },
    'reports': {
        title: 'C.7 Reports',
        image: { caption: 'Gambar 10 - Reports Dashboard', description: 'Halaman reports dengan chart dan analytics' },
        content: `
## Overview Reports

**Tujuan:** Melihat analytics dan laporan performa

## Komponen:

1. **Export Data**
   - Export JSON atau CSV

2. **Tier Distribution**
   - Bar chart distribusi per tier

3. **Index Status**
   - Donut chart Indexed vs Noindex

4. **Brand Health Overview**
   - Health score per brand

5. **Orphan Domains**
   - Daftar domain orphan
        `
    },
    'team-eval': {
        title: 'C.8 Team Evaluation',
        image: { caption: 'Gambar 11 - Team Evaluation', description: 'Dashboard evaluasi performa tim' },
        content: `
## Overview

**Tujuan:** Melihat performa tim SEO

**Akses:** Admin, Super Admin

## Komponen:

1. **Summary Metrics**
   - Total Optimizations
   - Completed
   - Total Complaints
   - Reverted

2. **Top Contributors**
   - Ranking tim berdasarkan performa
   - Score dan Status

3. **Status Distribution**
   - Pie chart status optimization

4. **Activity Types**
   - Bar chart jenis aktivitas
        `
    },
    'master-data': {
        title: 'C.9 Master Data Management',
        content: `
## Brands

Mengelola master data brand.

**Langkah:**
1. Buka menu **"Brands"**
2. Klik **"+ Add Brand"**
3. Isi nama dan deskripsi
4. Save

## Categories

Kategori domain: FRESH DOMAIN, AGED DOMAIN, REDIRECT, AMP, MONEY SITE, PBN, PARKING

## Registrars

Daftar registrar domain.

## Activity Types

Jenis aktivitas optimization: Backlink, Onpage, Content, Technical, Conflict Resolution

## Quarantine Categories

Kategori karantina: Spam, DMCA, Manual Penalty, Hacked Site, Other
        `
    },
    'users': {
        title: 'C.10 User Management',
        image: { caption: 'Gambar 12 - User Management', description: 'Tabel manajemen user' },
        content: `
## Daftar Users

**Akses:** Super Admin

**Tab:**
- All Users
- Pending Approvals

## User Approval

1. Klik tab **"Pending Approvals"**
2. Review data user
3. Klik **"Approve"** atau **"Reject"**
4. Tentukan Role dan Brand Access

## Edit User

1. Klik ikon Edit
2. Update field
3. Save
        `
    },
    'settings': {
        title: 'C.11 Settings',
        image: { caption: 'Gambar 13 - Settings', description: 'Halaman pengaturan sistem' },
        content: `
## Branding

Kustomisasi tampilan: Site Title, Tagline, Logo

## Timezone

Atur timezone sistem

## SEO Notifications (Telegram)

- Bot Token
- Chat ID
- Forum Topic Routing
- Global SEO Leaders

## Domain Monitoring Telegram

Channel terpisah untuk monitoring alerts

## Performance Alerts

Threshold untuk alert performa tim

## Templates

Edit template pesan notifikasi
        `
    },
    'audit-logs': {
        title: 'C.12 Audit & Activity Logs',
        content: `
## Audit Logs

**Akses:** Super Admin

**Informasi:**
- Timestamp
- Actor
- Event Type
- Resource
- Severity
- Status
- Details

## V3 Activity Logs

**Akses:** Admin, Super Admin

Melacak perubahan SEO Network:
- Node created/updated/deleted
- Network changes
- Optimization events
        `
    },
    'faq-monitoring': {
        title: 'D.1 Kenapa Monitoring Status masih "Unknown"?',
        content: `
## Penyebab:

1. Monitoring Toggle dalam keadaan OFF
2. Domain baru ditambahkan dan belum dicek
3. Scheduler monitoring belum berjalan

## Solusi:

1. Pastikan Monitoring Toggle ON
2. Tunggu interval check berikutnya
3. Gunakan "Check Availability" untuk manual check
        `
    },
    'faq-permission': {
        title: 'D.2 Kenapa tidak bisa Save/Edit?',
        content: `
## Penyebab:

1. Role tidak memiliki permission
2. User tidak memiliki akses ke brand
3. Menu access dinonaktifkan

## Solusi:

Hubungi Super Admin untuk update permission atau minta akses ke brand yang diperlukan.
        `
    },
    'faq-conflicts': {
        title: 'D.3 Kenapa Conflict tidak muncul?',
        content: `
## Penyebab:

1. Conflict detection belum dijalankan
2. Filter aktif yang menyembunyikan conflict

## Solusi:

1. Klik Refresh di Alert Center
2. Reset semua filter
3. Periksa struktur network
        `
    },
    'faq-telegram': {
        title: 'D.4 Kenapa Telegram tidak terkirim?',
        content: `
## Checklist:

1. ✅ Verifikasi Bot Token di BotFather
2. ✅ Pastikan Chat ID benar (negatif untuk grup)
3. ✅ Add bot ke grup dan jadikan admin
4. ✅ Toggle "Aktifkan Notifikasi" ON
5. ✅ Gunakan "Kirim Test" untuk verifikasi
        `
    },
    'full-glossary': {
        title: 'E.1 Daftar Istilah Lengkap',
        content: `
| Istilah | Definisi |
|---------|----------|
| Asset Domain | Domain yang dikelola perusahaan |
| Availability | Status UP/DOWN domain |
| Backlink | Link dari website lain |
| Brand | Unit bisnis dalam sistem |
| Brand Scope | Batasan akses per brand |
| Canonical | URL utama untuk search engine |
| Conflict | Masalah konfigurasi SEO |
| Domain Active Status | Active/Expired berdasarkan tanggal |
| Expiration | Tanggal expired domain |
| Index Rate | Persentase ter-index |
| Lifecycle | Siklus hidup domain |
| LP | Landing Page |
| Manager | User yang mengelola network |
| Money Site | Website target SEO |
| Monitoring Toggle | Switch ON/OFF monitoring |
| Node | Entry dalam SEO Network |
| Noindex | Tag anti-index |
| Optimization | Task optimasi SEO |
| Orphan Node | Node tidak terhubung |
| PBN | Private Blog Network |
| Quarantine | Status karantina domain |
| Redirect | Pengalihan URL |
| SEO Network | Struktur jaringan SEO |
| Tier | Level dalam network |
| Viewer | Role read-only |
        `
    },
    'telegram-examples': {
        title: 'E.2 Contoh Notifikasi Telegram',
        content: `
## Domain Expiration Alert

\`\`\`
⚠️ DOMAIN EXPIRATION ALERT

📛 Domain: example.com
🏷️ Brand: PANEN77
📅 Expires: Feb 15, 2026 (3 days)
🔴 Priority: High

🧭 STRUKTUR SEO TERKINI:
├─ Network: Test Network V5
├─ Tier: Tier 1
└─ Parent: moneysite.com

💡 Tindakan: Perpanjang domain

@leader1
\`\`\`

## Domain Down Alert

\`\`\`
🔴 DOMAIN DOWN ALERT

📛 Domain: tier1-site1.com
🏷️ Brand: Panen138
⏰ Down Since: Feb 10, 2026
🔍 Status: Connection Timeout

🧭 STRUKTUR SEO TERKINI:
├─ Network: TESTER2 Updated
├─ Tier: Tier 1
└─ Impact: Money Site affected

💡 Tindakan: Periksa server

@leader1
\`\`\`
        `
    },
    'checklist': {
        title: 'E.3 Checklist Operasional',
        content: `
## Checklist Harian

- [ ] Cek Dashboard untuk alert aktif
- [ ] Review Recent Alerts
- [ ] Proses domain expired dalam 7 hari
- [ ] Cek domain DOWN
- [ ] Review optimization masuk

## Checklist Mingguan

- [ ] Review konflik di Alert Center
- [ ] Create optimization tasks
- [ ] Review Team Evaluation
- [ ] Update domain status
- [ ] Backup data penting

## Checklist Bulanan

- [ ] Audit semua SEO Networks
- [ ] Review struktur network
- [ ] Evaluasi performa tim
- [ ] Review domain quarantine
- [ ] Update master data
        `
    }
};

// Image component that shows actual screenshots from the app
const DocumentImage = ({ sectionId, imageInfo }) => {
    if (!imageInfo) return null;
    
    // Map section IDs to actual app routes for live screenshots
    const routeMap = {
        'overview': '/dashboard',
        'login': '/login',
        'register': '/register',
        'navigation': '/dashboard',
        'dashboard': '/dashboard',
        'asset-domains': '/domains',
        'seo-networks': '/groups',
        'conflicts': '/alerts',
        'monitoring': '/settings/monitoring',
        'reports': '/reports',
        'team-eval': '/reports/team-evaluation',
        'users': '/users',
        'settings': '/settings',
    };

    const route = routeMap[sectionId];
    
    return (
        <div className="my-6 rounded-lg overflow-hidden border border-zinc-700 bg-zinc-800/50">
            <div className="relative aspect-video bg-gradient-to-br from-zinc-800 to-zinc-900">
                {route ? (
                    <div className="absolute inset-0 flex flex-col items-center justify-center p-4">
                        <div className="bg-zinc-800 rounded-lg p-6 text-center max-w-md">
                            <ImageIcon className="h-12 w-12 text-blue-400 mx-auto mb-3" />
                            <p className="text-zinc-300 text-sm font-medium mb-2">{imageInfo.description}</p>
                            <p className="text-zinc-500 text-xs mb-4">Untuk melihat tampilan sebenarnya:</p>
                            <a 
                                href={route}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors"
                            >
                                <ExternalLink className="h-4 w-4" />
                                Buka Halaman {imageInfo.caption.replace('Gambar ', '').split(' - ')[1] || 'Terkait'}
                            </a>
                        </div>
                    </div>
                ) : (
                    <div className="absolute inset-0 flex items-center justify-center">
                        <div className="text-center p-8">
                            <ImageIcon className="h-16 w-16 text-zinc-600 mx-auto mb-4" />
                            <p className="text-zinc-500 text-sm">{imageInfo.description}</p>
                        </div>
                    </div>
                )}
            </div>
            <div className="px-4 py-3 bg-zinc-800/80 border-t border-zinc-700">
                <p className="text-sm text-zinc-400 text-center italic">{imageInfo.caption}</p>
            </div>
        </div>
    );
};

export default function UserManualPage() {
    const [expandedSections, setExpandedSections] = useState(['getting-started']);
    const [activeSection, setActiveSection] = useState('overview');
    const [searchQuery, setSearchQuery] = useState('');

    // Get all sections flattened for navigation
    const allSections = useMemo(() => getAllSections(tocData), []);
    
    // Find current section index
    const currentIndex = useMemo(() => {
        return allSections.findIndex(s => s.id === activeSection);
    }, [allSections, activeSection]);

    // Get previous and next sections
    const prevSection = currentIndex > 0 ? allSections[currentIndex - 1] : null;
    const nextSection = currentIndex < allSections.length - 1 ? allSections[currentIndex + 1] : null;

    const toggleSection = (sectionId) => {
        setExpandedSections(prev => 
            prev.includes(sectionId) 
                ? prev.filter(id => id !== sectionId)
                : [...prev, sectionId]
        );
    };

    const handleSectionClick = (sectionId) => {
        setActiveSection(sectionId);
        // Auto-expand parent chapter
        const chapter = tocData.find(ch => ch.sections.some(s => s.id === sectionId));
        if (chapter && !expandedSections.includes(chapter.id)) {
            setExpandedSections(prev => [...prev, chapter.id]);
        }
    };

    const handlePrevious = () => {
        if (prevSection) {
            handleSectionClick(prevSection.id);
        }
    };

    const handleNext = () => {
        if (nextSection) {
            handleSectionClick(nextSection.id);
        }
    };

    const currentContent = contentSections[activeSection] || contentSections['overview'];

    // Simple markdown-like rendering
    const renderContent = (content) => {
        const lines = content.trim().split('\n');
        const elements = [];
        let inTable = false;
        let tableRows = [];
        let inCodeBlock = false;
        let codeContent = [];

        lines.forEach((line, index) => {
            // Code block
            if (line.trim().startsWith('```')) {
                if (inCodeBlock) {
                    elements.push(
                        <pre key={`code-${index}`} className="bg-zinc-900 text-zinc-100 p-4 rounded-lg overflow-x-auto my-4 text-sm font-mono">
                            <code>{codeContent.join('\n')}</code>
                        </pre>
                    );
                    codeContent = [];
                }
                inCodeBlock = !inCodeBlock;
                return;
            }

            if (inCodeBlock) {
                codeContent.push(line);
                return;
            }

            // Table handling
            if (line.includes('|') && !line.trim().startsWith('>')) {
                if (!inTable) {
                    inTable = true;
                    tableRows = [];
                }
                if (!line.includes('---')) {
                    tableRows.push(line.split('|').filter(cell => cell.trim()));
                }
                return;
            } else if (inTable) {
                // Render table
                elements.push(
                    <div key={`table-${index}`} className="overflow-x-auto my-4">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="bg-zinc-800">
                                    {tableRows[0]?.map((cell, i) => (
                                        <th key={i} className="px-4 py-2 text-left text-zinc-300 font-medium">
                                            {cell.trim()}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {tableRows.slice(1).map((row, rowIndex) => (
                                    <tr key={rowIndex} className="border-b border-zinc-800">
                                        {row.map((cell, cellIndex) => (
                                            <td key={cellIndex} className="px-4 py-2 text-zinc-400">
                                                {cell.trim().replace(/\*\*/g, '')}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                );
                inTable = false;
                tableRows = [];
            }

            // Headers
            if (line.startsWith('## ')) {
                elements.push(
                    <h2 key={index} className="text-xl font-bold text-white mt-6 mb-3 flex items-center gap-2">
                        <div className="w-1 h-6 bg-blue-500 rounded-full" />
                        {line.replace('## ', '')}
                    </h2>
                );
            } else if (line.startsWith('### ')) {
                elements.push(
                    <h3 key={index} className="text-lg font-semibold text-zinc-200 mt-4 mb-2">
                        {line.replace('### ', '')}
                    </h3>
                );
            }
            // Blockquote
            else if (line.startsWith('> ')) {
                elements.push(
                    <div key={index} className="bg-blue-500/10 border-l-4 border-blue-500 p-4 my-4 rounded-r-lg">
                        <p className="text-zinc-300 text-sm flex items-start gap-2">
                            <Info className="h-4 w-4 text-blue-400 mt-0.5 flex-shrink-0" />
                            {line.replace('> ', '').replace(/\*\*/g, '')}
                        </p>
                    </div>
                );
            }
            // List items
            else if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
                const text = line.replace(/^[\s]*[-*]\s/, '').replace(/\*\*/g, '');
                const isCheckbox = text.startsWith('[ ]') || text.startsWith('[x]');
                
                if (isCheckbox) {
                    const checked = text.startsWith('[x]');
                    const label = text.replace(/\[[ x]\]\s*/, '');
                    elements.push(
                        <div key={index} className="flex items-center gap-2 ml-4 my-1">
                            <div className={`w-4 h-4 rounded border ${checked ? 'bg-emerald-500 border-emerald-500' : 'border-zinc-600'} flex items-center justify-center`}>
                                {checked && <CheckCircle className="h-3 w-3 text-white" />}
                            </div>
                            <span className="text-zinc-400 text-sm">{label}</span>
                        </div>
                    );
                } else {
                    elements.push(
                        <div key={index} className="flex items-start gap-2 ml-4 my-1">
                            <ChevronRight className="h-4 w-4 text-blue-400 mt-1 flex-shrink-0" />
                            <span className="text-zinc-400 text-sm">{text}</span>
                        </div>
                    );
                }
            }
            // Numbered list
            else if (/^\d+\.\s/.test(line.trim())) {
                const match = line.trim().match(/^(\d+)\.\s(.*)$/);
                if (match) {
                    elements.push(
                        <div key={index} className="flex items-start gap-3 ml-4 my-2">
                            <span className="bg-blue-500/20 text-blue-400 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0">
                                {match[1]}
                            </span>
                            <span className="text-zinc-400 text-sm">{match[2].replace(/\*\*/g, '')}</span>
                        </div>
                    );
                }
            }
            // Regular paragraph
            else if (line.trim()) {
                elements.push(
                    <p key={index} className="text-zinc-400 my-2 text-sm leading-relaxed">
                        {line.replace(/\*\*/g, '')}
                    </p>
                );
            }
        });

        return elements;
    };

    return (
        <Layout>
            <div className="flex h-[calc(100vh-80px)]" data-testid="user-manual-page">
                {/* Sidebar TOC */}
                <div className="w-72 border-r border-zinc-800 flex-shrink-0">
                    <div className="p-4 border-b border-zinc-800">
                        <div className="flex items-center gap-2 mb-4">
                            <BookOpen className="h-5 w-5 text-blue-500" />
                            <h2 className="font-bold text-white">User Manual</h2>
                        </div>
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
                            <Input
                                placeholder="Search..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="pl-9 bg-zinc-900 border-zinc-700 text-sm"
                            />
                        </div>
                    </div>
                    <ScrollArea className="h-[calc(100%-120px)]">
                        <div className="p-2">
                            {tocData.map((section) => (
                                <div key={section.id} className="mb-1">
                                    <button
                                        onClick={() => toggleSection(section.id)}
                                        className="w-full flex items-center gap-2 p-2 rounded-lg hover:bg-zinc-800 transition-colors"
                                    >
                                        {expandedSections.includes(section.id) ? (
                                            <ChevronDown className="h-4 w-4 text-zinc-500" />
                                        ) : (
                                            <ChevronRight className="h-4 w-4 text-zinc-500" />
                                        )}
                                        <section.icon className="h-4 w-4 text-blue-400" />
                                        <span className="text-sm font-medium text-zinc-300">{section.title}</span>
                                    </button>
                                    {expandedSections.includes(section.id) && (
                                        <div className="ml-6 mt-1 space-y-1">
                                            {section.sections.map((sub) => (
                                                <button
                                                    key={sub.id}
                                                    onClick={() => handleSectionClick(sub.id)}
                                                    className={`w-full text-left p-2 rounded-lg text-sm transition-colors ${
                                                        activeSection === sub.id
                                                            ? 'bg-blue-500/20 text-blue-400'
                                                            : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800'
                                                    }`}
                                                >
                                                    {sub.title}
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </ScrollArea>
                </div>

                {/* Content Area */}
                <div className="flex-1 overflow-hidden">
                    <ScrollArea className="h-full">
                        <div className="max-w-4xl mx-auto p-8">
                            {/* Breadcrumb */}
                            <div className="flex items-center gap-2 text-sm text-zinc-500 mb-6">
                                <BookOpen className="h-4 w-4" />
                                <span>User Manual</span>
                                <ChevronRight className="h-4 w-4" />
                                <span className="text-zinc-300">{currentContent.title}</span>
                            </div>

                            {/* Title */}
                            <h1 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
                                <div className="w-2 h-8 bg-blue-500 rounded-full" />
                                {currentContent.title}
                            </h1>

                            {/* Image if available */}
                            {currentContent.image && (
                                <DocumentImage 
                                    sectionId={activeSection} 
                                    imageInfo={currentContent.image} 
                                />
                            )}

                            {/* Content */}
                            <Card className="bg-zinc-900/50 border-zinc-800">
                                <CardContent className="p-6">
                                    {renderContent(currentContent.content)}
                                </CardContent>
                            </Card>

                            {/* Navigation */}
                            <div className="flex justify-between mt-8 pt-6 border-t border-zinc-800">
                                <Button 
                                    variant="outline" 
                                    className="text-zinc-400 hover:text-white"
                                    onClick={handlePrevious}
                                    disabled={!prevSection}
                                >
                                    <ChevronLeft className="h-4 w-4 mr-2" />
                                    {prevSection ? prevSection.title : 'Previous'}
                                </Button>
                                <Button 
                                    variant="outline" 
                                    className="text-zinc-400 hover:text-white"
                                    onClick={handleNext}
                                    disabled={!nextSection}
                                >
                                    {nextSection ? nextSection.title : 'Next'}
                                    <ChevronRight className="h-4 w-4 ml-2" />
                                </Button>
                            </div>
                        </div>
                    </ScrollArea>
                </div>
            </div>
        </Layout>
    );
}
