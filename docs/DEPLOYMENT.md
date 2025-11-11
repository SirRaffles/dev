# Deployment — IFS SEC Account Planning

## Production Environment

**Production URL:** https://ifs-sec-planning.v4value.ai/
**Server:** DavrineNAS (192.168.50.171)
**Deployment Path:** `/home/Davrine/docker/ifs-sec-planning/`
**Container Name:** `ifs-sec-planning`

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Internet (HTTPS)                                        │
│ ↓                                                       │
│ Namecheap DNS (CNAME)                                   │
│ ifs-sec-planning.v4value.ai → v4value.ai                │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ nginx-proxy (Let's Encrypt SSL/TLS)                     │
│ Port: 80/443                                            │
│ ↓                                                       │
│ Proxy to: http://127.0.0.1:8300                         │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Docker Container: ifs-sec-planning                      │
│ Image: nginx:alpine                                     │
│ Internal Port: 80 → External: 8300                      │
│ Serves: /usr/share/nginx/html (static build/)           │
└─────────────────────────────────────────────────────────┘
```

## Deployment Process

### 1. Build Production Bundle

**From development environment (`/home/user/dev`):**

```bash
# Standard build (react-scripts 5+)
npm run build

# If OpenSSL errors occur (Node 22 + webpack 4)
NODE_OPTIONS=--openssl-legacy-provider npm run build
```

**Expected Output:**
```
Creating an optimized production build...
Compiled successfully.

File sizes after gzip:
  66 kB    build/static/js/main.f6c6785e.js
  6.09 kB  build/static/css/main.d1054227.css
  1.77 kB  build/static/js/453.7954c228.chunk.js
```

### 2. Set Build Permissions

```bash
chmod -R 755 build/
```

**Why:** nginx container needs read permissions for all build files.

### 3. Copy to Production Server

**Option A: Direct copy (if on same server):**
```bash
rsync -av build/ /home/Davrine/docker/ifs-sec-planning/build/
```

**Option B: SCP (remote server):**
```bash
scp -r build/* user@192.168.50.171:/home/Davrine/docker/ifs-sec-planning/build/
```

### 4. Restart Docker Container

```bash
docker restart ifs-sec-planning
```

**Verify restart:**
```bash
docker ps | grep ifs-sec-planning
docker logs ifs-sec-planning
```

### 5. Verify Deployment

**Browser Test:**
1. Navigate to https://ifs-sec-planning.v4value.ai/
2. Hard refresh: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)
3. Check all 5 sections, 25 slides load correctly
4. Test dark mode toggle
5. Test responsive design (mobile/tablet/desktop)

**Command Line Test:**
```bash
curl -I https://ifs-sec-planning.v4value.ai/
# Expected: HTTP/2 200
```

## Docker Configuration

### Dockerfile

**Location:** `/home/Davrine/docker/ifs-sec-planning/Dockerfile`

```dockerfile
FROM nginx:alpine
COPY build/ /usr/share/nginx/html
EXPOSE 80
```

### Build Docker Image (if needed)

```bash
cd /home/Davrine/docker/ifs-sec-planning/
docker build -t ifs-sec-planning:latest .
```

### Run Container (if recreating)

```bash
docker run -d \
  --name ifs-sec-planning \
  --restart unless-stopped \
  -p 8300:80 \
  ifs-sec-planning:latest
```

## nginx-proxy Configuration

### Location
`/home/Davrine/docker/nginx-proxy/nginx.conf`

### Configuration Block
```nginx
server {
    listen 80;
    server_name ifs-sec-planning.v4value.ai;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ifs-sec-planning.v4value.ai;

    # SSL certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/ifs-sec-planning.v4value.ai/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ifs-sec-planning.v4value.ai/privkey.pem;

    # Proxy to container
    location / {
        proxy_pass http://127.0.0.1:8300;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        proxy_pass http://127.0.0.1:8300;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### Reload nginx-proxy

```bash
docker exec nginx-proxy nginx -s reload
```

## DNS Configuration

### Provider: Namecheap

**Record Type:** CNAME
**Host:** `ifs-sec-planning`
**Value:** `v4value.ai`
**TTL:** Automatic (300s)

**Full Domain Resolution:**
```
ifs-sec-planning.v4value.ai (CNAME) → v4value.ai (A) → 192.168.50.171
```

## SSL/TLS Certificate

### Let's Encrypt (Certbot)

**Initial Setup:**
```bash
certbot certonly --webroot \
  -w /var/www/letsencrypt \
  -d ifs-sec-planning.v4value.ai
```

**Auto-renewal:**
```bash
# Cron job (runs daily)
0 3 * * * certbot renew --quiet && docker exec nginx-proxy nginx -s reload
```

**Check Certificate:**
```bash
certbot certificates | grep ifs-sec-planning
```

**Manual Renewal:**
```bash
certbot renew --cert-name ifs-sec-planning.v4value.ai
docker exec nginx-proxy nginx -s reload
```

## Rollback Procedure

### Quick Rollback

1. **Identify last working commit:**
   ```bash
   git log --oneline
   ```

2. **Checkout previous version:**
   ```bash
   git checkout <commit-hash>
   ```

3. **Rebuild and deploy:**
   ```bash
   npm run build
   chmod -R 755 build/
   rsync -av build/ /home/Davrine/docker/ifs-sec-planning/build/
   docker restart ifs-sec-planning
   ```

### Emergency Rollback (Keep Old Build)

**Before deploying new version:**
```bash
cd /home/Davrine/docker/ifs-sec-planning/
cp -r build build.backup.$(date +%Y%m%d_%H%M%S)
```

**Rollback:**
```bash
cd /home/Davrine/docker/ifs-sec-planning/
rm -rf build
cp -r build.backup.YYYYMMDD_HHMMSS build
docker restart ifs-sec-planning
```

## Monitoring & Logs

### Container Logs
```bash
# View recent logs
docker logs ifs-sec-planning

# Follow logs in real-time
docker logs -f ifs-sec-planning

# Last 100 lines
docker logs --tail 100 ifs-sec-planning
```

### nginx-proxy Logs
```bash
docker logs nginx-proxy
docker logs nginx-proxy | grep ifs-sec-planning
```

### Access Logs (if configured)
```bash
docker exec nginx-proxy cat /var/log/nginx/access.log | grep ifs-sec-planning
```

## Troubleshooting Deployment

### Site Shows 502 Bad Gateway
**Cause:** Container not running or port 8300 not accessible
**Fix:**
```bash
docker ps -a | grep ifs-sec-planning
docker start ifs-sec-planning
docker logs ifs-sec-planning
```

### Site Shows 403 Forbidden
**Cause:** Build directory permissions or missing files
**Fix:**
```bash
chmod -R 755 /home/Davrine/docker/ifs-sec-planning/build/
docker restart ifs-sec-planning
```

### Site Shows Old Version (Caching)
**Cause:** Browser cache or CDN cache
**Fix:**
- Hard refresh: `Cmd+Shift+R` / `Ctrl+Shift+R`
- Clear browser cache
- Check build hash in filename: `main.f6c6785e.js`

### SSL Certificate Expired
**Cause:** Certbot auto-renewal failed
**Fix:**
```bash
certbot renew --cert-name ifs-sec-planning.v4value.ai --force-renewal
docker exec nginx-proxy nginx -s reload
```

## Deployment Checklist

**Pre-Deployment:**
- [ ] All changes committed and pushed to git
- [ ] Build successful locally (`npm run build`)
- [ ] No console errors in dev mode
- [ ] All 25 slides render correctly
- [ ] Dark mode works
- [ ] Responsive design tested

**Deployment:**
- [ ] Set build permissions (`chmod -R 755 build/`)
- [ ] Copy build to production server
- [ ] Restart container (`docker restart ifs-sec-planning`)
- [ ] Check container is running (`docker ps`)

**Post-Deployment:**
- [ ] Site loads at https://ifs-sec-planning.v4value.ai/
- [ ] Hard refresh clears cache
- [ ] All sections/slides work
- [ ] Dark mode toggle works
- [ ] Mobile responsive
- [ ] SSL certificate valid

---

**Last Updated:** 2025-11-11
**Deployment Version:** 2.0 (Documentation Restructure)
