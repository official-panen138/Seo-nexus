# Operations Guide

Day-to-day operations, monitoring, backup/restore, and maintenance procedures.

## Table of Contents

1. [Service Management](#1-service-management)
2. [Log Management](#2-log-management)
3. [Monitoring Jobs](#3-monitoring-jobs)
4. [Backup and Restore](#4-backup-and-restore)
5. [Updates and Upgrades](#5-updates-and-upgrades)
6. [Health Checks](#6-health-checks)
7. [Performance Monitoring](#7-performance-monitoring)

---

## 1. Service Management

### 1.1 Docker Deployment

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Restart specific service
docker compose restart backend

# View running containers
docker compose ps

# View resource usage
docker stats
```

### 1.2 Systemd (Non-Docker)

```bash
# Backend service
sudo systemctl start seo-noc-backend
sudo systemctl stop seo-noc-backend
sudo systemctl restart seo-noc-backend
sudo systemctl status seo-noc-backend

# Nginx
sudo systemctl reload nginx
sudo systemctl restart nginx

# MongoDB
sudo systemctl restart mongod
sudo systemctl status mongod
```

### 1.3 Quick Health Check

```bash
# Check all services
curl -sf http://localhost:8001/api/health && echo "Backend: OK" || echo "Backend: FAIL"
curl -sf http://localhost/health && echo "Nginx: OK" || echo "Nginx: FAIL"
mongosh --eval "db.runCommand('ping')" && echo "MongoDB: OK" || echo "MongoDB: FAIL"
```

---

## 2. Log Management

### 2.1 Log Locations

| Component | Docker | Systemd |
|-----------|--------|---------|
| Backend | `docker logs seo-noc-backend` | `/var/log/seo-noc/*.log` |
| Frontend | `docker logs seo-noc-frontend` | N/A (static files) |
| Nginx | `docker logs seo-noc-nginx` | `/var/log/nginx/*.log` |
| MongoDB | `docker logs seo-noc-mongodb` | `/var/log/mongodb/*.log` |

### 2.2 View Logs

```bash
# Docker - real-time logs
docker compose logs -f backend
docker compose logs -f --tail=100 backend

# Systemd - real-time logs
sudo journalctl -u seo-noc-backend -f
sudo journalctl -u seo-noc-backend --since "1 hour ago"

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 2.3 Search Logs

```bash
# Find errors in backend logs
docker compose logs backend | grep -i error

# Find specific user activity
docker compose logs backend | grep "user@example.com"

# Find slow requests (>1s)
grep "1[0-9][0-9][0-9]ms" /var/log/nginx/access.log

# MongoDB slow queries
grep "COMMAND" /var/log/mongodb/mongod.log | grep -E "[0-9]{4}ms"
```

### 2.4 Log Rotation

Already configured via logrotate (see INSTALL_VPS.md). Manual rotation:

```bash
sudo logrotate -f /etc/logrotate.d/seo-noc
```

---

## 3. Monitoring Jobs

### 3.1 Built-in Monitoring Services

SEO-NOC runs two monitoring services automatically:

| Service | Function | Default Interval |
|---------|----------|------------------|
| ExpirationMonitoringService | Check domain expiration | Hourly (24h alert dedup) |
| AvailabilityMonitoringService | HTTP health checks | Per-domain (5min default) |

### 3.2 Check Monitoring Status

```bash
# Get monitoring stats
curl -X GET "https://seo-noc.yourdomain.com/api/v3/monitoring/stats" \
  -H "Authorization: Bearer $TOKEN" | jq

# Example response:
{
  "availability": {
    "total_monitored": 10,
    "up": 8,
    "down": 2,
    "unknown": 0
  },
  "expiration": {
    "expiring_7_days": 1,
    "expiring_30_days": 3,
    "expired": 0
  },
  "alerts": {
    "monitoring_unacknowledged": 2,
    "expiration_unacknowledged": 1
  }
}
```

### 3.3 Manual Trigger

```bash
# Trigger expiration check
curl -X POST "https://seo-noc.yourdomain.com/api/v3/monitoring/check-expiration" \
  -H "Authorization: Bearer $TOKEN"

# Trigger availability check
curl -X POST "https://seo-noc.yourdomain.com/api/v3/monitoring/check-availability" \
  -H "Authorization: Bearer $TOKEN"

# Check specific domain
curl -X POST "https://seo-noc.yourdomain.com/api/v3/monitoring/check-domain/{domain_id}" \
  -H "Authorization: Bearer $TOKEN"
```

### 3.4 View Monitoring Logs

```bash
# Filter monitoring logs
docker compose logs backend | grep -E "Expiration|Availability|monitoring"

# Example output:
# ExpirationMonitoringService - check complete: {'checked': 50, 'alerts_sent': 2, 'skipped': 48}
# AvailabilityMonitoringService - Checked example.com: up → down, HTTP=None
# Telegram alert sent successfully
```

---

## 4. Backup and Restore

### 4.1 MongoDB Backup

**Manual Backup:**
```bash
# Create backup directory
mkdir -p /home/deploy/backups

# Backup database
mongodump --uri="mongodb://user:pass@localhost:27017/seo_noc?authSource=seo_noc" \
  --out=/home/deploy/backups/$(date +%Y%m%d_%H%M%S)

# Compress backup
tar -czf /home/deploy/backups/seo_noc_$(date +%Y%m%d).tar.gz \
  -C /home/deploy/backups $(date +%Y%m%d_*)
```

**Docker Backup:**
```bash
docker exec seo-noc-mongodb mongodump \
  --uri="mongodb://admin:password@localhost:27017" \
  --db=seo_noc \
  --out=/backups/$(date +%Y%m%d_%H%M%S)
```

### 4.2 Automated Backup Script

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/home/deploy/backups"
MONGO_URI="mongodb://user:pass@localhost:27017/seo_noc?authSource=seo_noc"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)

echo "Starting backup: $DATE"

# Create backup
mongodump --uri="$MONGO_URI" --out="$BACKUP_DIR/$DATE" --quiet

if [ $? -eq 0 ]; then
    # Compress
    tar -czf "$BACKUP_DIR/seo_noc_$DATE.tar.gz" -C "$BACKUP_DIR" "$DATE"
    rm -rf "$BACKUP_DIR/$DATE"
    
    # Cleanup old backups
    find "$BACKUP_DIR" -name "seo_noc_*.tar.gz" -mtime +$RETENTION_DAYS -delete
    
    echo "Backup complete: seo_noc_$DATE.tar.gz"
else
    echo "Backup failed!"
    exit 1
fi
```

**Cron Schedule (daily at 2 AM):**
```bash
crontab -e
# Add:
0 2 * * * /home/deploy/seo-noc/backup.sh >> /var/log/seo-noc/backup.log 2>&1
```

### 4.3 Restore from Backup

```bash
# Extract backup
tar -xzf /home/deploy/backups/seo_noc_20260208.tar.gz -C /tmp

# Restore (will overwrite existing data!)
mongorestore --uri="mongodb://user:pass@localhost:27017/seo_noc?authSource=seo_noc" \
  --drop \
  /tmp/20260208_*/seo_noc

# Verify
mongosh seo_noc --eval "db.stats()"
```

### 4.4 Backup Verification

```bash
# List collections and counts
mongosh seo_noc --eval "
db.getCollectionNames().forEach(function(c) {
    print(c + ': ' + db[c].countDocuments());
})
"
```

---

## 5. Updates and Upgrades

### 5.1 Pre-Update Checklist

- [ ] Create database backup
- [ ] Note current version
- [ ] Review changelog for breaking changes
- [ ] Schedule maintenance window (if needed)

### 5.2 Standard Update (Docker)

```bash
cd /home/deploy/seo-noc

# Backup first
./backup.sh

# Pull latest code
git fetch origin
git pull origin main

# Rebuild and restart
docker compose down
docker compose build --no-cache
docker compose up -d

# Verify
docker compose ps
curl -sf http://localhost:8001/api/health
```

### 5.3 Standard Update (Systemd)

```bash
cd /home/deploy/seo-noc

# Backup first
./backup.sh

# Pull latest code
git fetch origin
git pull origin main

# Update backend
cd backend
source venv/bin/activate
pip install -r requirements.txt

# Update frontend
cd ../frontend
yarn install
yarn build

# Restart services
sudo systemctl restart seo-noc-backend
sudo systemctl reload nginx

# Verify
curl -sf http://localhost:8001/api/health
```

### 5.4 Zero-Downtime Update (Docker)

```bash
# Rolling update - one service at a time
docker compose up -d --no-deps --build backend
sleep 10
curl -sf http://localhost:8001/api/health || (docker compose rollback backend && exit 1)

docker compose up -d --no-deps --build frontend
```

### 5.5 Database Migration

If schema changes are needed:

```bash
# Run migration script (if provided)
cd /home/deploy/seo-noc/backend
source venv/bin/activate
python migrations/migrate_v3.py

# Or manual migration
mongosh seo_noc << 'EOF'
// Example: Add new field to all documents
db.asset_domains.updateMany(
  { new_field: { $exists: false } },
  { $set: { new_field: "default_value" } }
);
print("Migration complete");
EOF
```

### 5.6 Rollback Procedure

```bash
# Git rollback
git log --oneline -5  # Find previous commit
git checkout <previous_commit>

# Docker rollback
docker compose down
docker compose build --no-cache
docker compose up -d

# Or restore from backup
./restore.sh /home/deploy/backups/seo_noc_20260207.tar.gz
```

---

## 6. Health Checks

### 6.1 API Health Endpoint

```bash
# Basic health check
curl http://localhost:8001/api/health

# Detailed status (authenticated)
curl -X GET "https://seo-noc.yourdomain.com/api/v3/dashboard/stats" \
  -H "Authorization: Bearer $TOKEN"
```

### 6.2 Monitoring Script

```bash
#!/bin/bash
# healthcheck.sh

BACKEND_URL="http://localhost:8001/api/health"
FRONTEND_URL="http://localhost"
ALERT_EMAIL="admin@yourdomain.com"

check_service() {
    if curl -sf "$1" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# Check services
if ! check_service "$BACKEND_URL"; then
    echo "Backend DOWN at $(date)" >> /var/log/seo-noc/healthcheck.log
    # Optionally send alert
fi

if ! check_service "$FRONTEND_URL"; then
    echo "Frontend DOWN at $(date)" >> /var/log/seo-noc/healthcheck.log
fi
```

**Cron (every 5 minutes):**
```bash
*/5 * * * * /home/deploy/seo-noc/healthcheck.sh
```

---

## 7. Performance Monitoring

### 7.1 System Resources

```bash
# Overall system
htop

# Docker resources
docker stats

# Disk usage
df -h
du -sh /home/deploy/seo-noc/*

# MongoDB disk usage
mongosh seo_noc --eval "db.stats().dataSize / 1024 / 1024 + ' MB'"
```

### 7.2 MongoDB Performance

```bash
# Current operations
mongosh seo_noc --eval "db.currentOp()"

# Index usage
mongosh seo_noc --eval "db.asset_domains.aggregate([{$indexStats:{}}])"

# Slow queries (enable profiling)
mongosh seo_noc << 'EOF'
db.setProfilingLevel(1, { slowms: 100 })
// View slow queries
db.system.profile.find().sort({ts:-1}).limit(10)
EOF
```

### 7.3 Nginx Metrics

```bash
# Active connections
curl http://localhost/nginx_status

# Request rate (last 1000 requests)
awk '{print $4}' /var/log/nginx/access.log | tail -1000 | sort | uniq -c | sort -rn
```

### 7.4 Application Metrics

Access via dashboard or API:
- Total domains, networks, users
- Monitoring status (up/down counts)
- Alert counts
- Recent activity

```bash
# Quick stats via API
curl -s "https://seo-noc.yourdomain.com/api/v3/monitoring/stats" \
  -H "Authorization: Bearer $TOKEN" | jq
```
