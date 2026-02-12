# SEO-NOC User Manual Documentation

## Struktur Folder

```
/app/documentation/
├── README.md                     # File ini - panduan penggunaan
├── USER_MANUAL_SEO_NOC.md       # Dokumentasi utama (Markdown)
├── USER_MANUAL_SEO_NOC.html     # Dokumentasi dalam format HTML (bisa export ke PDF)
├── IMAGE_MAPPING.md             # Mapping gambar ke section dokumentasi
└── images/                      # Folder untuk menyimpan screenshot
    └── (screenshot files)
```

## Cara Menggunakan Dokumentasi

### 1. Membaca Online (Markdown)
- Buka file `USER_MANUAL_SEO_NOC.md` langsung di browser atau text editor
- Format Markdown mudah dibaca dan di-navigate

### 2. Export ke PDF
Ada beberapa cara untuk mengexport ke PDF:

**Cara 1: Via Browser (HTML)**
1. Buka file `USER_MANUAL_SEO_NOC.html` di browser
2. Tekan `Ctrl+P` (Print)
3. Pilih "Save as PDF"
4. Klik Save

**Cara 2: Via VS Code**
1. Install extension "Markdown PDF"
2. Buka `USER_MANUAL_SEO_NOC.md`
3. Klik kanan → "Markdown PDF: Export (pdf)"

**Cara 3: Via Pandoc (Command Line)**
```bash
pandoc USER_MANUAL_SEO_NOC.md -o USER_MANUAL_SEO_NOC.pdf
```

### 3. Export ke DOCX (Word)

**Via Pandoc:**
```bash
pandoc USER_MANUAL_SEO_NOC.md -o USER_MANUAL_SEO_NOC.docx
```

**Via Online Converter:**
1. Upload file MD ke https://cloudconvert.com/md-to-docx
2. Download hasil konversi

## Daftar Screenshot yang Diperlukan

Screenshot sudah diambil selama proses pembuatan dokumentasi. Berikut daftar screenshot yang diperlukan beserta section-nya:

| No | Screenshot | Section | Deskripsi |
|----|------------|---------|-----------|
| 01 | Login Page | A.3.1 | Halaman Login |
| 02 | Register Page | A.4.1 | Halaman Registrasi |
| 03 | Dashboard | C.1.1 | Dashboard Overview |
| 04 | Asset Domains | C.2.1 | Tabel Domain |
| 05 | SEO Networks | C.3.1 | Daftar Network |
| 06 | Network Detail | C.3.3 | Visual Graph |
| 07 | Alert Center | C.5.1 | SEO Conflicts Dashboard |
| 08 | Settings | C.11.1 | Settings Branding |
| 09 | Users | C.10.1 | User Management |
| 10 | Brands | C.9.1 | Brands Page |
| 11 | Reports | C.7.1 | Reports Dashboard |
| 12 | SEO Notifications | C.11.3 | Telegram Settings |
| 13 | Monitoring | C.6 | Monitoring Settings |
| 14 | Categories | C.9.2 | Domain Categories |
| 15 | Quarantine | C.9.5 | Quarantine Categories |
| 16 | Team Eval | C.8.1 | Team Evaluation |
| 17 | Audit Logs | C.12.1 | Audit Logs |

## Cara Menambahkan Screenshot ke Dokumentasi

1. Simpan screenshot di folder `/app/documentation/images/`
2. Gunakan naming convention: `XX-nama-fitur.png`
3. Di Markdown, tambahkan reference:
   ```markdown
   ![Gambar X - Deskripsi](images/XX-nama-fitur.png)
   ```

## Konten Dokumentasi

### Bagian A: Getting Started
- Overview aplikasi
- System requirements
- Login & Logout
- Registrasi akun
- Navigasi menu
- Glossary istilah

### Bagian B: Role & Permissions
- Jenis role (Super Admin, Admin, Viewer)
- Perbandingan hak akses
- Brand scoping
- Menu access control
- Handling permission errors

### Bagian C: Modul Utama
- Dashboard
- Asset Domains
- SEO Networks
- Optimizations
- SEO Conflicts (Alert Center)
- Domain Monitoring
- Reports
- Team Evaluation
- Master Data Management
- User Management
- Settings
- Audit Logs

### Bagian D: Troubleshooting & FAQ
- Common issues dan solusinya

### Bagian E: Appendix
- Glossary lengkap
- Contoh notifikasi Telegram
- Template variables
- Checklist operasional

## Catatan Pembaruan

| Tanggal | Versi | Perubahan |
|---------|-------|-----------|
| Feb 2026 | 1.0 | Initial release |

## Kontributor

- Dokumentasi dibuat menggunakan Emergent Agent
- Review oleh tim SEO-NOC
