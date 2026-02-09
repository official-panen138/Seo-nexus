# Configuration Reference

Complete guide to all environment variables and configuration options.

## Table of Contents

1. [Environment Variables](#1-environment-variables)
2. [Backend Configuration](#2-backend-configuration)
3. [Frontend Configuration](#3-frontend-configuration)
4. [Monitoring Configuration](#4-monitoring-configuration)
5. [Telegram Configuration](#5-telegram-configuration)
6. [Sample .env Files](#6-sample-env-files)

---

## 1. Environment Variables

### Complete .env.example

```bash
# =============================================================================
# SEO-NOC V3 Configuration
# =============================================================================

# -----------------------------------------------------------------------------
# DATABASE
# -----------------------------------------------------------------------------

# MongoDB connection string
# Format: mongodb://[username:password@]host[:port]/database[?options]
MONGO_URL=mongodb://localhost:27017

# Database name
DB_NAME=seo_noc

# -----------------------------------------------------------------------------
# AUTHENTICATION
# -----------------------------------------------------------------------------

# JWT secret key (REQUIRED - generate with: openssl rand -hex 32)
# IMPORTANT: Keep this secret and never commit to version control
JWT_SECRET=your_64_character_hex_string_here

# JWT token expiration (in seconds, default: 86400 = 24 hours)
JWT_EXPIRATION=86400

# -----------------------------------------------------------------------------
# APPLICATION
# -----------------------------------------------------------------------------

# Environment mode: development | production
ENVIRONMENT=production

# Enable debug mode (set to false in production)
DEBUG=false

# CORS allowed origins (comma-separated)
# Leave empty to allow configured FRONTEND_URL only
CORS_ORIGINS=

# -----------------------------------------------------------------------------
# FRONTEND
# -----------------------------------------------------------------------------

# Public URL of the application (used for API calls from frontend)
# Must include protocol (https://) and NOT have trailing slash
REACT_APP_BACKEND_URL=https://seo-noc.yourdomain.com

# -----------------------------------------------------------------------------
# MONITORING - EXPIRATION
# -----------------------------------------------------------------------------

# Enable domain expiration monitoring
EXPIRATION_MONITORING_ENABLED=true

# Days before expiration to start alerting (default: 7)
EXPIRATION_ALERT_WINDOW_DAYS=7

# Include domains with auto-renew enabled in alerts
EXPIRATION_INCLUDE_AUTO_RENEW=false

# -----------------------------------------------------------------------------
# MONITORING - AVAILABILITY
# -----------------------------------------------------------------------------

# Enable availability (ping/HTTP) monitoring
AVAILABILITY_MONITORING_ENABLED=true

# Default check interval in seconds (default: 300 = 5 minutes)
AVAILABILITY_CHECK_INTERVAL=300

# HTTP timeout for availability checks (seconds)
AVAILABILITY_TIMEOUT=15

# Alert on domain going DOWN (UP -> DOWN transition)
AVAILABILITY_ALERT_ON_DOWN=true

# Alert on domain recovery (DOWN -> UP transition)
AVAILABILITY_ALERT_ON_RECOVERY=false

# Follow HTTP redirects when checking
AVAILABILITY_FOLLOW_REDIRECTS=true

# -----------------------------------------------------------------------------
# TELEGRAM ALERTS
# -----------------------------------------------------------------------------

# Enable Telegram alerts
TELEGRAM_ENABLED=true

# Telegram bot token (get from @BotFather)
TELEGRAM_BOT_TOKEN=

# Telegram chat ID (get from @userinfobot or @getidsbot)
TELEGRAM_CHAT_ID=

# -----------------------------------------------------------------------------
# LOGGING
# -----------------------------------------------------------------------------

# Log level: DEBUG | INFO | WARNING | ERROR | CRITICAL
LOG_LEVEL=INFO

# Log format: json | text
LOG_FORMAT=json
```

---

## 2. Backend Configuration

### 2.1 Server Settings

Located in `backend/server.py`:

```python
# CORS configuration (auto-configured from FRONTEND_URL)
origins = [
    os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:3000"),
]

# JWT settings
JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION = int(os.environ.get("JWT_EXPIRATION", 86400))
```

### 2.2 Database Connection

```python
# MongoDB connection
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "seo_noc")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
```

### 2.3 Gunicorn Settings (Production)

Located in `backend/gunicorn.conf.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `workers` | CPU * 2 + 1 | Number of worker processes |
| `worker_class` | uvicorn.workers.UvicornWorker | Worker type |
| `timeout` | 120 | Worker timeout (seconds) |
| `keepalive` | 5 | Keep-alive connections |
| `max_requests` | 1000 | Requests before worker restart |

---

## 3. Frontend Configuration

### 3.1 Environment Variables

Located in `frontend/.env`:

```bash
# Backend API URL
REACT_APP_BACKEND_URL=https://seo-noc.yourdomain.com
```

### 3.2 Build-time Variables

These variables are embedded at build time:

| Variable | Description |
|----------|-------------|
| `REACT_APP_BACKEND_URL` | API base URL for all fetch calls |

### 3.3 Runtime Configuration

Browser-side storage keys:

| Key | Purpose |
|-----|---------|
| `seo_nexus_token` | JWT authentication token |
| `seo_nexus_selected_brand` | Selected brand ID (Super Admin only) |

---

## 4. Monitoring Configuration

### 4.1 Expiration Monitoring Settings

Configured via API: `PUT /api/v3/monitoring/settings`

```json
{
  "expiration": {
    "enabled": true,
    "alert_window_days": 7,
    "alert_thresholds": [30, 14, 7, 3, 1, 0],
    "include_auto_renew": false
  }
}
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | boolean | true | Enable expiration monitoring |
| `alert_window_days` | integer | 7 | Days before expiration to alert |
| `alert_thresholds` | array | [30,14,7,3,1,0] | Days to send alerts |
| `include_auto_renew` | boolean | false | Include auto-renew domains |

### 4.2 Availability Monitoring Settings

```json
{
  "availability": {
    "enabled": true,
    "default_interval_seconds": 300,
    "alert_on_down": true,
    "alert_on_recovery": false,
    "timeout_seconds": 15,
    "follow_redirects": true
  }
}
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | boolean | true | Enable availability monitoring |
| `default_interval_seconds` | integer | 300 | Check interval (5 min) |
| `alert_on_down` | boolean | true | Alert on UP→DOWN |
| `alert_on_recovery` | boolean | false | Alert on DOWN→UP |
| `timeout_seconds` | integer | 15 | HTTP request timeout |
| `follow_redirects` | boolean | true | Follow HTTP redirects |

### 4.3 Per-Domain Monitoring

Each domain can have individual settings:

```json
{
  "monitoring_enabled": true,
  "monitoring_interval": "5min"  // Options: 5min, 15min, 1hour, daily
}
```

---

## 5. Telegram Configuration

### 5.1 Setup Steps

1. **Create Bot:**
   - Message [@BotFather](https://t.me/BotFather)
   - Send `/newbot`
   - Follow prompts to create bot
   - Copy the bot token

2. **Get Chat ID:**
   - Message your bot
   - Visit: `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - Find your `chat_id` in the response

3. **Configure in SEO-NOC:**
   - Go to Settings page
   - Enter bot token and chat ID
   - Test with "Send Test Alert"

### 5.2 Telegram Alert Format

**Expiration Alert:**
```
🟡 DOMAIN EXPIRATION ALERT

Domain: example.com
Brand: MyBrand
Registrar: GoDaddy

Status: Expires in 7 days
Expiration Date: 2026-02-15
Auto-Renew: ❌ No

Severity: MEDIUM
Checked: 2026-02-08 15:30 UTC
```

**Down Alert:**
```
🔴 DOMAIN DOWN ALERT

Domain: example.com
Brand: MyBrand
Category: Money Sites

Issue: Connection Timeout
Previous Status: UP → DOWN
HTTP Code: N/A

SEO Context:
  Network: Main Network
  Role: Main
  Tier: LP/Money Site

Severity: CRITICAL
Checked: 2026-02-08 15:30 UTC
```

---

## 6. Sample .env Files

### 6.1 Development .env

```bash
# backend/.env (development)
MONGO_URL=mongodb://localhost:27017
DB_NAME=seo_noc_dev
JWT_SECRET=dev_secret_key_not_for_production_use_only
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
```

```bash
# frontend/.env (development)
REACT_APP_BACKEND_URL=http://localhost:8001
```

### 6.2 Production .env

```bash
# backend/.env (production)
MONGO_URL=mongodb://seonoc_app:secure_password@localhost:27017/seo_noc?authSource=seo_noc
DB_NAME=seo_noc
JWT_SECRET=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
```

```bash
# frontend/.env (production)
REACT_APP_BACKEND_URL=https://seo-noc.yourdomain.com
```

### 6.3 Docker .env

```bash
# .env (Docker root)
# Database
MONGO_ROOT_USER=admin
MONGO_ROOT_PASSWORD=secure_root_password
MONGO_APP_USER=seonoc_app
MONGO_APP_PASSWORD=secure_app_password
DB_NAME=seo_noc

# Application
JWT_SECRET=your_64_character_hex_secret_here
FRONTEND_URL=https://seo-noc.yourdomain.com

# Monitoring (optional - can also configure via UI)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

---

## Configuration Validation

### Check Configuration Script

```bash
#!/bin/bash
# check-config.sh

echo "Checking SEO-NOC configuration..."

# Check required variables
required_vars=(
    "MONGO_URL"
    "DB_NAME"
    "JWT_SECRET"
)

missing=0
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Missing: $var"
        missing=1
    else
        echo "✅ $var is set"
    fi
done

# Check JWT secret length
if [ ${#JWT_SECRET} -lt 32 ]; then
    echo "⚠️  Warning: JWT_SECRET should be at least 32 characters"
fi

# Check MongoDB connection
if mongosh --eval "db.runCommand('ping')" > /dev/null 2>&1; then
    echo "✅ MongoDB connection OK"
else
    echo "❌ MongoDB connection failed"
    missing=1
fi

if [ $missing -eq 1 ]; then
    echo ""
    echo "Configuration incomplete. Please check your .env file."
    exit 1
fi

echo ""
echo "Configuration OK!"
```

Make executable and run:
```bash
chmod +x check-config.sh
source .env && ./check-config.sh
```
