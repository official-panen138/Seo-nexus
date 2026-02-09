# Troubleshooting Guide

Common issues and their solutions for SEO-NOC V3.

## Table of Contents

1. [Application Issues](#1-application-issues)
2. [API Errors](#2-api-errors)
3. [Authentication Issues](#3-authentication-issues)
4. [Database Issues](#4-database-issues)
5. [Monitoring Issues](#5-monitoring-issues)
6. [Frontend Issues](#6-frontend-issues)
7. [Nginx/SSL Issues](#7-nginxssl-issues)
8. [Docker Issues](#8-docker-issues)

---

## 1. Application Issues

### App Not Loading / Blank Page

**Symptoms:**
- White screen
- Page loads but shows nothing
- JavaScript errors in console

**Solutions:**

1. **Check browser console (F12)**
   ```
   Look for red errors, especially:
   - "Failed to fetch"
   - "CORS error"
   - "Module not found"
   ```

2. **Verify frontend build**
   ```bash
   # Check if build files exist
   ls -la frontend/dist/
   
   # Rebuild if needed
   cd frontend
   yarn install
   yarn build
   ```

3. **Check backend is running**
   ```bash
   curl http://localhost:8001/api/health
   # Should return: {"status": "ok"}
   ```

4. **Check REACT_APP_BACKEND_URL**
   ```bash
   # In frontend/.env or at build time
   echo $REACT_APP_BACKEND_URL
   # Must match your domain exactly (with https://)
   ```

### API Returns 502 Bad Gateway

**Symptoms:**
- Frontend loads but shows "Failed to fetch"
- Nginx returns 502

**Solutions:**

1. **Check backend is running**
   ```bash
   # Docker
   docker compose ps
   docker compose logs backend
   
   # Systemd
   sudo systemctl status seo-noc-backend
   sudo journalctl -u seo-noc-backend -n 50
   ```

2. **Check backend port**
   ```bash
   # Verify backend is listening
   netstat -tlnp | grep 8001
   # or
   ss -tlnp | grep 8001
   ```

3. **Check Nginx upstream**
   ```nginx
   # In nginx config, verify:
   location /api {
       proxy_pass http://127.0.0.1:8001;  # Must match backend port
   }
   ```

4. **Restart services**
   ```bash
   sudo systemctl restart seo-noc-backend
   sudo systemctl reload nginx
   ```

---

## 2. API Errors

### 500 Internal Server Error

**Diagnosis:**
```bash
# View detailed error
docker compose logs backend | tail -50

# Or for systemd
sudo journalctl -u seo-noc-backend -n 50
```

**Common causes:**

1. **Missing environment variable**
   ```bash
   # Check .env file
   cat backend/.env
   
   # Required variables:
   # - MONGO_URL
   # - DB_NAME
   # - JWT_SECRET
   ```

2. **Database connection failure**
   ```bash
   # Test MongoDB connection
   mongosh "$MONGO_URL" --eval "db.runCommand('ping')"
   ```

3. **Import error**
   ```bash
   # Check Python imports
   cd backend
   source venv/bin/activate
   python -c "from server import app; print('OK')"
   ```

### 422 Validation Error

**Symptoms:**
- API returns 422 Unprocessable Entity
- "detail" field shows validation errors

**Solutions:**
```bash
# The error response tells you what's wrong:
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}

# Fix: Ensure all required fields are sent
curl -X POST "https://example.com/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "secret", "name": "Test"}'
```

### 403 Forbidden - Brand Access

**Symptoms:**
- "Access denied for this brand."

**Causes:**
- User trying to access data from a brand they don't have access to
- `brand_scope_ids` doesn't include the requested brand

**Solutions:**
```bash
# Check user's brand scope
mongosh seo_noc --eval "db.users.findOne({email: 'user@example.com'}, {brand_scope_ids: 1})"

# Update user's brand scope (as Super Admin)
curl -X PUT "https://example.com/api/users/{user_id}" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"brand_scope_ids": ["brand-id-1", "brand-id-2"]}'
```

---

## 3. Authentication Issues

### JWT Token Invalid/Expired

**Symptoms:**
- "Not authenticated"
- "Token expired"
- "Invalid token"

**Solutions:**

1. **Re-login**
   - Clear browser localStorage
   - Login again

2. **Check JWT_SECRET consistency**
   ```bash
   # Must be same across restarts
   grep JWT_SECRET backend/.env
   ```

3. **Extend token expiration**
   ```bash
   # In backend/.env
   JWT_EXPIRATION=604800  # 7 days in seconds
   ```

### Login Fails but Credentials Are Correct

**Solutions:**

1. **Check password hash**
   ```bash
   # Verify user exists
   mongosh seo_noc --eval "db.users.findOne({email: 'test@example.com'}, {password: 0})"
   ```

2. **Reset password manually**
   ```bash
   # Generate new hash (Python)
   python3 << 'EOF'
   import bcrypt
   password = "new_password"
   hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
   print(f"New hash: {hashed}")
   EOF
   
   # Update in database
   mongosh seo_noc --eval "db.users.updateOne({email: 'test@example.com'}, {\$set: {password: 'NEW_HASH_HERE'}})"
   ```

---

## 4. Database Issues

### MongoDB Connection Failed

**Symptoms:**
- "ServerSelectionTimeoutError"
- "Connection refused"

**Solutions:**

1. **Check MongoDB is running**
   ```bash
   sudo systemctl status mongod
   # or
   docker compose ps mongodb
   ```

2. **Check connection string**
   ```bash
   # Format:
   # mongodb://[user:pass@]host:port/database?authSource=database
   
   # Test connection
   mongosh "mongodb://localhost:27017/seo_noc"
   ```

3. **Check authentication**
   ```bash
   # If auth enabled, include credentials
   mongosh "mongodb://user:pass@localhost:27017/seo_noc?authSource=seo_noc"
   ```

4. **Check network binding**
   ```bash
   # In /etc/mongod.conf, bindIp should include 127.0.0.1
   grep bindIp /etc/mongod.conf
   ```

### MongoDB Authentication Failed

**Solutions:**

1. **Verify user exists**
   ```bash
   mongosh admin -u admin -p --eval "db.system.users.find({user: 'seonoc_app'})"
   ```

2. **Create user if missing**
   ```bash
   mongosh admin -u admin -p << 'EOF'
   use seo_noc
   db.createUser({
     user: "seonoc_app",
     pwd: "your_password",
     roles: [{role: "readWrite", db: "seo_noc"}]
   })
   EOF
   ```

### ObjectId Serialization Error

**Symptoms:**
- "Object of type ObjectId is not JSON serializable"

**Solution:**
This is handled in the backend. If you see this error, there's a bug in the API response. Check that all MongoDB queries exclude `_id`:

```python
# Correct way
await db.collection.find({}, {"_id": 0}).to_list()

# Or convert to string
doc["id"] = str(doc.pop("_id"))
```

---

## 5. Monitoring Issues

### Telegram Alerts Not Sending

**Diagnosis:**
```bash
# Check Telegram settings
mongosh seo_noc --eval "db.settings.findOne({key: 'telegram'})"

# Test Telegram API directly
curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -d "chat_id=<CHAT_ID>&text=Test message"
```

**Solutions:**

1. **Verify bot token**
   - Message @BotFather to verify token
   - Create new token if needed

2. **Verify chat ID**
   - Message @userinfobot to get your chat ID
   - For groups, bot must be a member

3. **Check bot permissions**
   - Bot must have permission to send messages
   - For groups, bot must not be restricted

4. **Network issues**
   ```bash
   # Test outbound connection
   curl -I https://api.telegram.org
   ```

### Monitoring Jobs Not Running

**Symptoms:**
- Domains not being checked
- No new alerts

**Diagnosis:**
```bash
# Check backend logs for monitoring activity
docker compose logs backend | grep -i "monitoring\|expiration\|availability"
```

**Solutions:**

1. **Check monitoring is enabled**
   ```bash
   mongosh seo_noc --eval "db.monitoring_settings.findOne({key: 'monitoring_config'})"
   ```

2. **Restart backend**
   ```bash
   docker compose restart backend
   # or
   sudo systemctl restart seo-noc-backend
   ```

3. **Manual trigger**
   ```bash
   curl -X POST "https://example.com/api/v3/monitoring/check-availability" \
     -H "Authorization: Bearer $TOKEN"
   ```

### Domain Shows Wrong Status

**Solutions:**

1. **Force re-check**
   ```bash
   curl -X POST "https://example.com/api/v3/monitoring/check-domain/<domain_id>" \
     -H "Authorization: Bearer $TOKEN"
   ```

2. **Check domain configuration**
   ```bash
   mongosh seo_noc --eval "db.asset_domains.findOne({id: '<domain_id>'})"
   # Verify monitoring_enabled: true
   ```

---

## 6. Frontend Issues

### Graph Links Not Rendering

**Symptoms:**
- Nodes appear but no lines between them
- D3 graph incomplete

**Causes:**
- `target_entry_id` not set correctly
- Node IDs mismatch

**Diagnosis:**
```bash
# Check structure entries
curl "https://example.com/api/v3/structure?network_id=<id>" \
  -H "Authorization: Bearer $TOKEN" | jq '.[] | {id, node_label, target_entry_id}'
```

**Solutions:**

1. **Verify target_entry_id points to valid entry**
   - Must be an entry ID in the same network
   - Cannot point to itself

2. **Check link color (might be too dark)**
   - In `/frontend/src/index.css`, `.graph-link` stroke color

3. **Force refresh**
   - Click "Refresh" button on network detail page

### CORS Errors

**Symptoms:**
- "Access-Control-Allow-Origin" errors in console
- API calls fail from browser

**Solutions:**

1. **Check FRONTEND_URL matches exactly**
   ```bash
   # Must match origin exactly
   # ❌ https://seo-noc.example.com/  (trailing slash)
   # ❌ http://seo-noc.example.com    (wrong protocol)
   # ✅ https://seo-noc.example.com   (correct)
   ```

2. **Backend CORS configuration**
   ```python
   # In server.py, verify origins list
   origins = [
       os.environ.get("REACT_APP_BACKEND_URL"),
       "http://localhost:3000",  # For development
   ]
   ```

---

## 7. Nginx/SSL Issues

### SSL Certificate Errors

**Solutions:**

1. **Check certificate validity**
   ```bash
   sudo certbot certificates
   ```

2. **Renew certificate**
   ```bash
   sudo certbot renew --force-renewal
   sudo systemctl reload nginx
   ```

3. **Fix permissions**
   ```bash
   sudo chmod 755 /etc/letsencrypt/live/
   sudo chmod 755 /etc/letsencrypt/archive/
   ```

### Nginx Won't Start

**Diagnosis:**
```bash
sudo nginx -t  # Test configuration
```

**Common fixes:**
```bash
# Check for duplicate listen directives
grep -r "listen 443" /etc/nginx/sites-enabled/

# Remove default site if conflicting
sudo rm /etc/nginx/sites-enabled/default
```

---

## 8. Docker Issues

### Container Won't Start

**Diagnosis:**
```bash
docker compose logs <service>
docker inspect <container_id>
```

**Common solutions:**

1. **Port conflict**
   ```bash
   # Find what's using the port
   sudo lsof -i :8001
   ```

2. **Volume permissions**
   ```bash
   # Fix ownership
   sudo chown -R 1000:1000 ./data
   ```

3. **Out of disk space**
   ```bash
   docker system prune -a  # Clean up
   df -h  # Check space
   ```

### Database Container Unhealthy

```bash
# Check MongoDB logs
docker compose logs mongodb

# Common issues:
# - Insufficient memory (increase in docker-compose.yml)
# - Corrupted data (restore from backup)
# - Wrong credentials (check MONGO_* env vars)
```

---

## Quick Reference: Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| 400 | Bad Request | Check request body/parameters |
| 401 | Unauthorized | Login or refresh token |
| 403 | Forbidden | Check brand/role permissions |
| 404 | Not Found | Verify resource exists |
| 422 | Validation Error | Check required fields |
| 500 | Server Error | Check backend logs |
| 502 | Bad Gateway | Backend not running |
| 503 | Service Unavailable | Service overloaded |

---

## Getting Help

If issues persist:

1. **Collect logs**
   ```bash
   docker compose logs > /tmp/seo-noc-logs.txt 2>&1
   ```

2. **Check system resources**
   ```bash
   free -m
   df -h
   ```

3. **Verify configuration**
   ```bash
   cat backend/.env | grep -v PASSWORD | grep -v SECRET
   ```
