# SEO-NOC V3 - Technical Documentation

## Overview

SEO-NOC (SEO Network Operations Center) is an enterprise-grade SEO network management platform built with:
- **Backend:** Python 3.10+ / FastAPI
- **Frontend:** React 18 / Vite / Tailwind CSS
- **Database:** MongoDB 6.0+
- **Visualization:** D3.js for network graphs

## Key Features

### Multi-Brand Architecture
- Complete data isolation per brand
- Role-based access control (Super Admin, Admin, Viewer)
- Brand-scoped API enforcement

### SEO Network Management
- **Asset Domains:** Brand-owned domain inventory
- **SEO Networks:** Brand-scoped link building strategies
- **SEO Structure:** Node-based architecture (domain + path)
- **Derived Tiers:** Automatic tier calculation via BFS algorithm

### Domain Monitoring
- **Expiration Monitoring:** Daily alerts before domain expiration
- **Availability Monitoring:** HTTP health checks with UP/DOWN alerts
- **Telegram Integration:** Real-time alerts to your team

### Additional Features
- Registrar master data management
- Activity logging and audit trails
- Data export (CSV/JSON)
- Bulk import capabilities

## Documentation Index

| Document | Description |
|----------|-------------|
| [INSTALL_VPS.md](./INSTALL_VPS.md) | Step-by-step VPS installation guide |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Production deployment details |
| [CONFIGURATION.md](./CONFIGURATION.md) | Environment variables and settings |
| [OPERATIONS.md](./OPERATIONS.md) | Monitoring, logs, backup, updates |
| [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) | Common errors and fixes |
| [API.md](./API.md) | API endpoints reference |
| [SECURITY.md](./SECURITY.md) | Security architecture and hardening |

## Project Structure

```
/app
├── backend/
│   ├── server.py              # Main FastAPI application
│   ├── models_v3.py           # Pydantic models (V3)
│   ├── requirements.txt       # Python dependencies
│   ├── routers/
│   │   └── v3_router.py       # V3 API endpoints
│   └── services/
│       ├── tier_service.py    # Tier calculation (BFS)
│       ├── monitoring_service.py  # Expiration + Availability monitoring
│       └── activity_log_service.py
├── frontend/
│   ├── src/
│   │   ├── App.js             # React app entry
│   │   ├── pages/             # Page components
│   │   ├── components/        # Reusable components
│   │   ├── contexts/          # React contexts (Brand, Auth)
│   │   └── lib/               # Utilities
│   ├── package.json
│   └── vite.config.js
├── docs/                      # This documentation
└── memory/
    └── PRD.md                 # Product requirements
```

## Key Concepts

### 1. Node-Based SEO Structure
A **node** is a unique combination of:
- `asset_domain_id` (the domain)
- `optimized_path` (e.g., `/blog`, `/products`)

Nodes link to other nodes via `target_entry_id` (not domain ID).

### 2. Derived Tiers
Tiers are calculated automatically using BFS from the main node:
- **Tier 0 (LP/Money Site):** Main node
- **Tier 1:** Nodes pointing to Tier 0
- **Tier 2:** Nodes pointing to Tier 1
- And so on...

### 3. Brand Isolation
- Every entity belongs to exactly one brand
- Users have `brand_scope_ids` (null = Super Admin)
- All APIs enforce brand filtering

### 4. Monitoring Engines
Two independent services:
1. **ExpirationMonitoringService:** Checks domain expiration dates daily
2. **AvailabilityMonitoringService:** HTTP health checks at configurable intervals

## Quick Start

### Prerequisites
- Ubuntu 22.04 LTS (or 20.04)
- 2GB+ RAM, 2 vCPU
- Domain name with DNS configured

### Installation
```bash
# Clone repository
git clone https://github.com/your-org/seo-noc.git
cd seo-noc

# Option 1: Docker (recommended)
docker-compose up -d

# Option 2: Manual
# See INSTALL_VPS.md for detailed steps
```

### Default Credentials
After first run, register via `/register` endpoint or UI.
First user automatically becomes Super Admin.

## Support

For issues and feature requests, contact your system administrator or refer to [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).

---

**Version:** V3.0  
**Last Updated:** February 2026
