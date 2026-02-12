# Production Deployment Guide

Detailed production deployment configurations for SEO-NOC V3.

## Table of Contents

1. [Deployment Architecture](#1-deployment-architecture)
2. [Docker Production Setup](#2-docker-production-setup)
3. [Non-Docker Production Setup](#3-non-docker-production-setup)
4. [Load Balancing](#4-load-balancing)
5. [High Availability](#5-high-availability)
6. [Scaling Considerations](#6-scaling-considerations)

---

## 1. Deployment Architecture

### Recommended Production Architecture

```
                    ┌─────────────────┐
                    │   CloudFlare    │
                    │   (CDN + WAF)   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │     Nginx       │
                    │  (Reverse Proxy)│
                    │   + SSL/TLS     │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼───────┐ ┌────▼────┐ ┌───────▼───────┐
     │    Backend     │ │ Backend │ │   Frontend    │
     │   (uvicorn)    │ │ Worker  │ │   (static)    │
     │   Port 8001    │ │ Port 80 │ │   Port 3000   │
     └────────┬───────┘ └────┬────┘ └───────────────┘
              │              │
              └──────────────┼──────────────┐
                             │              │
                    ┌────────▼────────┐     │
                    │    MongoDB      │◄────┘
                    │   (Primary)     │
                    └─────────────────┘
```

### Component Responsibilities

| Component | Purpose |
|-----------|---------|
| CloudFlare | CDN, DDoS protection, WAF |
| Nginx | SSL termination, reverse proxy, rate limiting |
| Backend | API server + monitoring services |
| Frontend | React SPA (static files) |
| MongoDB | Document database |

---

## Default Super Admin Setup

On fresh deployment or migration, a default Super Admin account is automatically created if no Super Admin exists.

### Default Credentials

| Field | Default Value |
|-------|---------------|
| Email | `admin@seonoc.com` |
| Password | `Admin@123!` |
| Name | `Super Admin` |

### Customize Default Admin (Environment Variables)

Add these to your `backend/.env` file BEFORE first deployment:

```bash
# Optional: Customize default super admin credentials
DEFAULT_ADMIN_EMAIL=youradmin@yourdomain.com
DEFAULT_ADMIN_PASSWORD=YourSecurePassword123!
DEFAULT_ADMIN_NAME=Your Admin Name
```

### Manual Seeding (Optional)

You can also run the seed script manually:

```bash
cd backend
python migrations/seed_default_admin.py
```

### Security Notes

1. **Change the default password immediately** after first login
2. The system auto-creates Super Admin only if:
   - No Super Admin user exists in the database
3. If you upgrade an existing user to Super Admin, their password remains unchanged
4. Logs will show the default password on first creation - secure your deployment logs

---

## 2. Docker Production Setup

### 2.1 Production docker-compose.yml

```yaml
version: '3.8'

services:
  mongodb:
    image: mongo:6.0
    container_name: seo-noc-mongodb
    restart: always
    environment:
      MONGO_INITDB_ROOT_USERNAME: ${MONGO_ROOT_USER}
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_ROOT_PASSWORD}
    volumes:
      - mongodb_data:/data/db
      - mongodb_config:/data/configdb
      - ./backups:/backups
    networks:
      - internal
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 512M
    healthcheck:
      test: echo 'db.runCommand("ping").ok' | mongosh localhost:27017/test --quiet
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 40s
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    container_name: seo-noc-backend
    restart: always
    environment:
      - MONGO_URL=mongodb://${MONGO_APP_USER}:${MONGO_APP_PASSWORD}@mongodb:27017/${DB_NAME}?authSource=${DB_NAME}
      - DB_NAME=${DB_NAME}
      - JWT_SECRET=${JWT_SECRET}
      - ENVIRONMENT=production
    depends_on:
      mongodb:
        condition: service_healthy
    networks:
      - internal
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 256M
    healthcheck:
      test: curl -f http://localhost:8001/api/health || exit 1
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "10"

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
      args:
        - REACT_APP_BACKEND_URL=${FRONTEND_URL}
    container_name: seo-noc-frontend
    restart: always
    depends_on:
      - backend
    networks:
      - internal
    deploy:
      resources:
        limits:
          memory: 256M

  nginx:
    image: nginx:alpine
    container_name: seo-noc-nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.prod.conf:/etc/nginx/nginx.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
      - ./nginx/logs:/var/log/nginx
    depends_on:
      - backend
      - frontend
    networks:
      - internal
      - external
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"

volumes:
  mongodb_data:
    driver: local
  mongodb_config:
    driver: local

networks:
  internal:
    internal: true
  external:
    driver: bridge
```

### 2.2 Production Backend Dockerfile

```dockerfile
# backend/Dockerfile.prod
FROM python:3.10-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# Production image
FROM python:3.10-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy wheels and install
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Production settings
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8001

# Use gunicorn for production
CMD ["gunicorn", "server:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8001", "--access-logfile", "-", "--error-logfile", "-"]
```

### 2.3 Production Frontend Dockerfile

```dockerfile
# frontend/Dockerfile.prod
FROM node:18-alpine as builder

WORKDIR /app

# Install dependencies
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --production=false

# Copy source
COPY . .

# Build arguments
ARG REACT_APP_BACKEND_URL
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

# Build
RUN yarn build

# Production image with nginx
FROM nginx:alpine

# Copy build artifacts
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.prod.conf /etc/nginx/conf.d/default.conf

# Security: run as non-root
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
```

### 2.4 Deployment Commands

```bash
# Pull latest changes
git pull origin main

# Build and deploy
docker compose -f docker-compose.yml down
docker compose -f docker-compose.yml build --no-cache
docker compose -f docker-compose.yml up -d

# Check status
docker compose ps
docker compose logs -f --tail=100

# Health check
curl -f http://localhost:8001/api/health
```

---

## 3. Non-Docker Production Setup

### 3.1 Production Backend with Gunicorn

Install gunicorn:
```bash
source /home/deploy/seo-noc/backend/venv/bin/activate
pip install gunicorn
```

Create gunicorn config:
```bash
cat > /home/deploy/seo-noc/backend/gunicorn.conf.py << 'EOF'
# Gunicorn configuration
import multiprocessing

# Server socket
bind = "127.0.0.1:8001"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 120
keepalive = 5

# Logging
accesslog = "/var/log/seo-noc/access.log"
errorlog = "/var/log/seo-noc/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "seo-noc-backend"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Restart workers gracefully
graceful_timeout = 30
max_requests = 1000
max_requests_jitter = 50

# Preload app for better memory usage
preload_app = True
EOF
```

Create log directory:
```bash
sudo mkdir -p /var/log/seo-noc
sudo chown deploy:deploy /var/log/seo-noc
```

### 3.2 Updated systemd Service

```ini
[Unit]
Description=SEO-NOC Backend API (Production)
After=network.target mongod.service
Wants=mongod.service

[Service]
Type=notify
User=deploy
Group=deploy
WorkingDirectory=/home/deploy/seo-noc/backend
Environment="PATH=/home/deploy/seo-noc/backend/venv/bin"
EnvironmentFile=/home/deploy/seo-noc/backend/.env
ExecStart=/home/deploy/seo-noc/backend/venv/bin/gunicorn server:app -c gunicorn.conf.py
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=5
KillMode=mixed
TimeoutStopSec=30

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/deploy/seo-noc /var/log/seo-noc

[Install]
WantedBy=multi-user.target
```

### 3.3 Log Rotation

```bash
sudo nano /etc/logrotate.d/seo-noc
```

```
/var/log/seo-noc/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 deploy deploy
    sharedscripts
    postrotate
        systemctl reload seo-noc-backend > /dev/null 2>&1 || true
    endscript
}
```

---

## 4. Load Balancing

### 4.1 Nginx Load Balancer Configuration

For multiple backend instances:

```nginx
upstream backend_servers {
    least_conn;
    server 127.0.0.1:8001 weight=3;
    server 127.0.0.1:8002 weight=3;
    server 127.0.0.1:8003 weight=3;
    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name seo-noc.yourdomain.com;

    location /api {
        proxy_pass http://backend_servers;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Health checks
        proxy_next_upstream error timeout http_502 http_503;
        proxy_next_upstream_tries 3;
    }
}
```

---

## 5. High Availability

### 5.1 MongoDB Replica Set

For production HA, configure MongoDB replica set:

```bash
# Initialize replica set
mongosh << 'EOF'
rs.initiate({
  _id: "seonoc-rs",
  members: [
    { _id: 0, host: "mongo1:27017", priority: 2 },
    { _id: 1, host: "mongo2:27017", priority: 1 },
    { _id: 2, host: "mongo3:27017", priority: 1 }
  ]
})
EOF
```

Update connection string:
```
MONGO_URL=mongodb://user:pass@mongo1:27017,mongo2:27017,mongo3:27017/seo_noc?replicaSet=seonoc-rs&authSource=seo_noc
```

---

## 6. Scaling Considerations

### 6.1 Horizontal Scaling

| Component | Scaling Strategy |
|-----------|-----------------|
| Frontend | CDN + multiple static servers |
| Backend | Multiple instances behind load balancer |
| MongoDB | Replica set (read scaling) or sharding |
| Monitoring | Single instance (uses internal scheduler) |

### 6.2 Resource Estimates

| Users | Backend Instances | MongoDB RAM | Total RAM |
|-------|-------------------|-------------|-----------|
| < 100 | 1 | 1 GB | 4 GB |
| 100-500 | 2 | 2 GB | 8 GB |
| 500-2000 | 4 | 4 GB | 16 GB |
| 2000+ | 8+ | 8+ GB | 32+ GB |

### 6.3 Database Optimization

For large deployments:
```javascript
// Add these indexes for performance
db.asset_domains.createIndex({ brand_id: 1, status: 1 });
db.asset_domains.createIndex({ monitoring_enabled: 1, last_checked_at: 1 });
db.seo_structure_entries.createIndex({ network_id: 1, domain_role: 1 });
db.activity_logs.createIndex({ created_at: -1 }, { expireAfterSeconds: 7776000 }); // 90 days TTL
```

---

## Zero-Downtime Deployment

### Rolling Update Script

```bash
#!/bin/bash
# deploy.sh - Zero-downtime deployment

set -e

echo "Starting deployment..."

# Pull latest code
git pull origin main

# Build new containers
docker compose build --no-cache backend frontend

# Rolling restart
docker compose up -d --no-deps backend
sleep 10

# Health check
if curl -sf http://localhost:8001/api/health > /dev/null; then
    echo "Backend healthy"
else
    echo "Backend unhealthy, rolling back"
    docker compose rollback backend
    exit 1
fi

# Restart frontend
docker compose up -d --no-deps frontend

echo "Deployment complete!"
```

Make executable:
```bash
chmod +x deploy.sh
```
