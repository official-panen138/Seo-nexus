# VPS Installation Guide

Complete step-by-step guide to deploy SEO-NOC V3 on a fresh Ubuntu VPS.

## Table of Contents

1. [VPS Requirements](#1-vps-requirements)
2. [Initial Server Setup](#2-initial-server-setup)
3. [Option 1: Docker Deployment (Recommended)](#3-option-1-docker-deployment-recommended)
4. [Option 2: Manual Deployment](#4-option-2-manual-deployment)
5. [Database Setup](#5-database-setup)
6. [Reverse Proxy + SSL](#6-reverse-proxy--ssl)
7. [Background Jobs Setup](#7-background-jobs-setup)
8. [Initial Admin Setup](#8-initial-admin-setup)
9. [Verification](#9-verification)

---

## 1. VPS Requirements

### Minimum Specifications
| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 1 vCPU | 2+ vCPU |
| RAM | 2 GB | 4 GB |
| Storage | 20 GB SSD | 50 GB SSD |
| OS | Ubuntu 20.04 LTS | Ubuntu 22.04 LTS |

### Required Ports
| Port | Service | Notes |
|------|---------|-------|
| 22 | SSH | Restrict to your IP |
| 80 | HTTP | Redirect to HTTPS |
| 443 | HTTPS | Main application |
| 27017 | MongoDB | Internal only (127.0.0.1) |

### DNS Requirements
Create an A record pointing your domain to your VPS IP:
```
seo-noc.yourdomain.com  →  YOUR_VPS_IP
```

---

## 2. Initial Server Setup

### 2.1 Connect to Your VPS
```bash
ssh root@YOUR_VPS_IP
```

### 2.2 Update System Packages
```bash
apt update && apt upgrade -y
```

### 2.3 Create Deploy User
```bash
# Create user
adduser deploy
usermod -aG sudo deploy

# Setup SSH key (copy from your local machine)
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys

# Switch to deploy user
su - deploy
```

### 2.4 Configure Firewall (UFW)
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

### 2.5 Install Fail2ban (Recommended)
```bash
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## 3. Option 1: Docker Deployment (Recommended)

### 3.1 Install Docker
```bash
# Install dependencies
sudo apt install apt-transport-https ca-certificates curl software-properties-common -y

# Add Docker GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin -y

# Add user to docker group
sudo usermod -aG docker deploy
newgrp docker
```

### 3.2 Clone Repository
```bash
cd /home/deploy
git clone https://github.com/your-org/seo-noc.git
cd seo-noc
```

### 3.3 Create docker-compose.yml
```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  mongodb:
    image: mongo:6.0
    container_name: seo-noc-mongodb
    restart: unless-stopped
    environment:
      MONGO_INITDB_ROOT_USERNAME: seonoc_admin
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_PASSWORD}
    volumes:
      - mongodb_data:/data/db
      - ./backups:/backups
    networks:
      - seo-noc-network
    healthcheck:
      test: echo 'db.runCommand("ping").ok' | mongosh localhost:27017/test --quiet
      interval: 30s
      timeout: 10s
      retries: 3

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: seo-noc-backend
    restart: unless-stopped
    environment:
      - MONGO_URL=mongodb://seonoc_admin:${MONGO_PASSWORD}@mongodb:27017
      - DB_NAME=seo_noc
      - JWT_SECRET=${JWT_SECRET}
    depends_on:
      mongodb:
        condition: service_healthy
    networks:
      - seo-noc-network
    healthcheck:
      test: curl -f http://localhost:8001/api/health || exit 1
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        - REACT_APP_BACKEND_URL=${FRONTEND_URL}
    container_name: seo-noc-frontend
    restart: unless-stopped
    depends_on:
      - backend
    networks:
      - seo-noc-network

  nginx:
    image: nginx:alpine
    container_name: seo-noc-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - backend
      - frontend
    networks:
      - seo-noc-network

volumes:
  mongodb_data:
    driver: local

networks:
  seo-noc-network:
    driver: bridge
EOF
```

### 3.4 Create Backend Dockerfile
```bash
cat > backend/Dockerfile << 'EOF'
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8001

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
EOF
```

### 3.5 Create Frontend Dockerfile
```bash
cat > frontend/Dockerfile << 'EOF'
FROM node:18-alpine as builder

WORKDIR /app

# Copy package files
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

# Copy source and build
COPY . .
ARG REACT_APP_BACKEND_URL
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL
RUN yarn build

# Production image
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
EOF
```

### 3.6 Create Environment File
```bash
cat > .env << 'EOF'
# Database
MONGO_PASSWORD=your_secure_mongo_password_here

# JWT (generate with: openssl rand -hex 32)
JWT_SECRET=your_jwt_secret_here

# Frontend URL (your domain with https)
FRONTEND_URL=https://seo-noc.yourdomain.com
EOF

# Secure the file
chmod 600 .env
```

### 3.7 Build and Run
```bash
docker compose up -d --build

# Check status
docker compose ps
docker compose logs -f
```

---

## 4. Option 2: Manual Deployment

### 4.1 Install System Dependencies
```bash
# Python 3.10+
sudo apt install python3.10 python3.10-venv python3-pip -y

# Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install nodejs -y

# Yarn
sudo npm install -g yarn

# MongoDB
curl -fsSL https://pgp.mongodb.com/server-6.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-6.0.gpg --dearmor
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list
sudo apt update
sudo apt install mongodb-org -y
sudo systemctl enable mongod
sudo systemctl start mongod
```

### 4.2 Clone Repository
```bash
cd /home/deploy
git clone https://github.com/your-org/seo-noc.git
cd seo-noc
```

### 4.3 Setup Backend
```bash
cd backend

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file
cat > .env << 'EOF'
MONGO_URL=mongodb://localhost:27017
DB_NAME=seo_noc
JWT_SECRET=your_jwt_secret_here
EOF

# Test backend
python -c "from server import app; print('Backend OK')"
```

### 4.4 Setup Frontend
```bash
cd ../frontend

# Install dependencies
yarn install

# Create .env file
cat > .env << 'EOF'
REACT_APP_BACKEND_URL=https://seo-noc.yourdomain.com
EOF

# Build for production
yarn build
```

---

## 5. Database Setup

### 5.1 Secure MongoDB
```bash
# Connect to MongoDB
mongosh

# Create admin user
use admin
db.createUser({
  user: "seonoc_admin",
  pwd: "your_secure_password",
  roles: [
    { role: "userAdminAnyDatabase", db: "admin" },
    { role: "readWriteAnyDatabase", db: "admin" }
  ]
})

# Create application database and user
use seo_noc
db.createUser({
  user: "seonoc_app",
  pwd: "your_app_password",
  roles: [{ role: "readWrite", db: "seo_noc" }]
})

exit
```

### 5.2 Enable Authentication
```bash
sudo nano /etc/mongod.conf
```

Add/modify:
```yaml
security:
  authorization: enabled

net:
  bindIp: 127.0.0.1
```

Restart MongoDB:
```bash
sudo systemctl restart mongod
```

### 5.3 Update Connection String
Update your backend `.env`:
```
MONGO_URL=mongodb://seonoc_app:your_app_password@localhost:27017/seo_noc?authSource=seo_noc
```

### 5.4 Create Indexes
```bash
mongosh -u seonoc_app -p your_app_password --authenticationDatabase seo_noc seo_noc << 'EOF'
// Performance indexes
db.asset_domains.createIndex({ brand_id: 1 });
db.asset_domains.createIndex({ domain_name: 1 }, { unique: true });
db.asset_domains.createIndex({ monitoring_enabled: 1, ping_status: 1 });
db.asset_domains.createIndex({ expiration_date: 1 });

db.seo_networks.createIndex({ brand_id: 1 });
db.seo_structure_entries.createIndex({ network_id: 1 });
db.seo_structure_entries.createIndex({ asset_domain_id: 1 });
db.seo_structure_entries.createIndex({ target_entry_id: 1 });

db.users.createIndex({ email: 1 }, { unique: true });
db.users.createIndex({ brand_scope_ids: 1 });

db.activity_logs.createIndex({ created_at: -1 });
db.activity_logs.createIndex({ entity_type: 1, entity_id: 1 });

db.alerts.createIndex({ created_at: -1 });
db.alerts.createIndex({ acknowledged: 1, alert_type: 1 });

print("Indexes created successfully");
EOF
```

---

## 6. Reverse Proxy + SSL

### 6.1 Install Nginx
```bash
sudo apt install nginx -y
sudo systemctl enable nginx
```

### 6.2 Create Nginx Configuration
```bash
sudo nano /etc/nginx/sites-available/seo-noc
```

```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=general_limit:10m rate=30r/s;

server {
    listen 80;
    server_name seo-noc.yourdomain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name seo-noc.yourdomain.com;

    # SSL Configuration (will be added by certbot)
    ssl_certificate /etc/letsencrypt/live/seo-noc.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/seo-noc.yourdomain.com/privkey.pem;
    
    # SSL Security
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_stapling on;
    ssl_stapling_verify on;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    gzip_min_length 1000;

    # Client max body size (for imports)
    client_max_body_size 50M;

    # API endpoints
    location /api {
        limit_req zone=api_limit burst=20 nodelay;
        
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts for long-running operations
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Frontend (static files)
    location / {
        limit_req zone=general_limit burst=50 nodelay;
        
        # For Docker deployment:
        # proxy_pass http://127.0.0.1:3000;
        
        # For manual deployment:
        root /home/deploy/seo-noc/frontend/dist;
        try_files $uri $uri/ /index.html;
        
        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # Health check endpoint
    location /health {
        access_log off;
        return 200 "OK";
        add_header Content-Type text/plain;
    }
}
```

### 6.3 Enable Site
```bash
sudo ln -s /etc/nginx/sites-available/seo-noc /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### 6.4 Install SSL Certificate (Let's Encrypt)
```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx -y

# Get certificate
sudo certbot --nginx -d seo-noc.yourdomain.com

# Test renewal
sudo certbot renew --dry-run
```

---

## 7. Background Jobs Setup

### 7.1 Create systemd Service for Backend
```bash
sudo nano /etc/systemd/system/seo-noc-backend.service
```

```ini
[Unit]
Description=SEO-NOC Backend API
After=network.target mongod.service
Wants=mongod.service

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/home/deploy/seo-noc/backend
Environment="PATH=/home/deploy/seo-noc/backend/venv/bin"
EnvironmentFile=/home/deploy/seo-noc/backend/.env
ExecStart=/home/deploy/seo-noc/backend/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/home/deploy/seo-noc

[Install]
WantedBy=multi-user.target
```

### 7.2 Enable and Start Services
```bash
sudo systemctl daemon-reload
sudo systemctl enable seo-noc-backend
sudo systemctl start seo-noc-backend
sudo systemctl status seo-noc-backend
```

### 7.3 Monitoring Jobs (Built-in)
The SEO-NOC backend includes built-in monitoring services that start automatically:
- **ExpirationMonitoringService:** Runs hourly, alerts on expiring domains
- **AvailabilityMonitoringService:** Runs every 5 minutes (configurable)

These are started in the FastAPI lifespan and don't require separate services.

### 7.4 View Logs
```bash
# Backend logs
sudo journalctl -u seo-noc-backend -f

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log
```

---

## 8. Initial Admin Setup

### 8.1 Create First Super Admin
```bash
# Using curl (replace with your domain)
curl -X POST https://seo-noc.yourdomain.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@yourdomain.com",
    "password": "your_secure_password",
    "name": "Admin User"
  }'
```

The first registered user automatically becomes Super Admin.

### 8.2 Configure Telegram Alerts
1. Create a Telegram bot via [@BotFather](https://t.me/BotFather)
2. Get your chat ID via [@userinfobot](https://t.me/userinfobot)
3. Login to SEO-NOC and go to Settings
4. Enter bot token and chat ID

### 8.3 Create Initial Brand
```bash
# Login to get token
TOKEN=$(curl -s -X POST https://seo-noc.yourdomain.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@yourdomain.com","password":"your_password"}' \
  | jq -r '.access_token')

# Create brand
curl -X POST https://seo-noc.yourdomain.com/api/brands \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Brand",
    "description": "Main brand"
  }'
```

---

## 9. Verification

### 9.1 Check All Services
```bash
# Check backend
curl -s https://seo-noc.yourdomain.com/api/health

# Check frontend
curl -s -o /dev/null -w "%{http_code}" https://seo-noc.yourdomain.com/

# Check MongoDB
mongosh --eval "db.runCommand('ping')"

# Check systemd services
sudo systemctl status seo-noc-backend
sudo systemctl status nginx
sudo systemctl status mongod
```

### 9.2 Test Login
1. Open https://seo-noc.yourdomain.com in browser
2. Login with your admin credentials
3. Verify dashboard loads with no errors
4. Check browser console for any JavaScript errors

### 9.3 Test Monitoring
```bash
# Trigger manual availability check
curl -X POST https://seo-noc.yourdomain.com/api/v3/monitoring/check-availability \
  -H "Authorization: Bearer $TOKEN"

# Trigger manual expiration check
curl -X POST https://seo-noc.yourdomain.com/api/v3/monitoring/check-expiration \
  -H "Authorization: Bearer $TOKEN"
```

---

## Next Steps

- [Configure environment variables](./CONFIGURATION.md)
- [Setup production hardening](./SECURITY.md)
- [Configure backups](./OPERATIONS.md)
- [Review API documentation](./API.md)
