# Troubleshooting — IFS SEC Account Planning

## Build Issues

### Issue: Build Fails with OpenSSL Error

**Error Message:**
```
Error: error:0308010C:digital envelope routines::unsupported
opensslErrorStack: [ 'error:03000086:digital envelope routines::initialization error' ]
```

**Root Cause:** Node 22 + webpack 4 incompatibility with OpenSSL 3

**Solution 1:** Use legacy OpenSSL provider
```bash
NODE_OPTIONS=--openssl-legacy-provider npm run build
```

**Solution 2:** Upgrade to react-scripts 5+ (already done)
```bash
npm install react-scripts@5.0.1
npm run build  # Should work without NODE_OPTIONS
```

---

### Issue: Tailwind CSS Not Compiling

**Symptoms:**
- Layout completely broken
- CSS file only 448 bytes
- No utility classes applied

**Root Cause:** react-scripts 3.0.1 doesn't support PostCSS 8 (required by Tailwind CSS 3)

**Solution:** Upgrade react-scripts
```bash
npm install react-scripts@5.0.1
rm -rf node_modules package-lock.json
npm install
npm run build
```

**Verify Fix:**
```bash
# CSS should be ~6 KB gzipped
ls -lh build/static/css/
```

---

### Issue: Build Succeeds but Site Crashes

**Symptoms:**
- Build completes successfully
- Browser shows blank page
- Console shows React errors

**Diagnosis:**
```bash
# Check for errors in build output
npm run build 2>&1 | grep -i error

# Test locally first
npm start
```

**Common Causes:**
1. **JSX syntax error** in `src/App.js`
2. **Missing closing tags** in sections array
3. **Undefined variables** in content JSX
4. **Import errors** for icons

**Solution:**
```bash
# Check console for specific error
# Fix JSX syntax
# Rebuild
npm run build
```

---

### Issue: Build Warnings about Unused Imports

**Warning:**
```
Line 12:3: 'Award' is defined but never used no-unused-vars
Line 13:3: 'Globe' is defined but never used no-unused-vars
```

**Solution:** Remove unused imports
```javascript
// Before
import { Award, Globe, Target, ... } from 'lucide-react';

// After
import { Target, TrendingUp, Users, ... } from 'lucide-react';
```

---

## Development Issues

### Issue: Dark Mode Not Working

**Symptoms:**
- Toggle button doesn't work
- Dark mode styles not applied
- Theme preference not saved

**Diagnosis Checklist:**
1. Check `public/index.html` has dark mode script
2. Check `src/index.css` has dark mode base styles
3. Check components use `dark:` variants
4. Check localStorage for theme setting

**Solution 1:** Add dark mode script to `public/index.html`
```html
<script>
  if (localStorage.theme === 'dark' ||
      (!('theme' in localStorage) &&
       window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.classList.add('dark')
  }
</script>
```

**Solution 2:** Verify Tailwind config
```javascript
// tailwind.config.js
module.exports = {
  darkMode: 'class',  // Must be 'class' not 'media'
  // ...
}
```

**Solution 3:** Check component className
```javascript
// Wrong
<div className="bg-white text-gray-900">

// Correct
<div className="bg-white dark:bg-gray-800 text-gray-900 dark:text-white">
```

---

### Issue: Changes Not Appearing in Browser

**Symptoms:**
- Code changes made
- Build successful
- Browser still shows old version

**Solution 1:** Hard refresh browser
```
Mac: Cmd + Shift + R
Windows: Ctrl + Shift + R
Linux: Ctrl + Shift + R
```

**Solution 2:** Clear browser cache
```
Chrome: Settings → Privacy → Clear browsing data
Firefox: Settings → Privacy → Clear Data
Safari: Develop → Empty Caches
```

**Solution 3:** Check build hash changed
```bash
# Build creates new hash in filename
ls build/static/js/
# Should see different hash: main.f6c6785e.js → main.a1b2c3d4.js
```

**Solution 4:** Disable service worker (if enabled)
```javascript
// src/index.js
// Change from:
serviceWorker.register();
// To:
serviceWorker.unregister();
```

---

### Issue: npm start Fails

**Error:**
```
Error: Cannot find module 'react-scripts/package.json'
```

**Solution:**
```bash
rm -rf node_modules package-lock.json
npm install
npm start
```

---

## Deployment Issues

### Issue: Production Site Shows HTTP 403

**Symptoms:**
- Local build works
- Production shows "403 Forbidden"
- nginx logs show permission denied

**Root Cause:** Build directory missing permissions

**Solution:**
```bash
chmod -R 755 build/
rsync -av build/ /home/Davrine/docker/ifs-sec-planning/build/
docker restart ifs-sec-planning
```

**Verify:**
```bash
ls -la /home/Davrine/docker/ifs-sec-planning/build/
# All files should be readable (r--r--r--)
```

---

### Issue: Production Site Shows HTTP 502

**Symptoms:**
- "502 Bad Gateway" error
- nginx-proxy can't connect to container

**Diagnosis:**
```bash
# Check container is running
docker ps | grep ifs-sec-planning

# Check container logs
docker logs ifs-sec-planning

# Check port 8300 is listening
netstat -tulpn | grep 8300
```

**Solution 1:** Start container
```bash
docker start ifs-sec-planning
```

**Solution 2:** Recreate container
```bash
docker stop ifs-sec-planning
docker rm ifs-sec-planning
docker run -d --name ifs-sec-planning -p 8300:80 ifs-sec-planning:latest
```

**Solution 3:** Check nginx-proxy config
```bash
docker exec nginx-proxy nginx -t
# Should show: configuration file /etc/nginx/nginx.conf test is successful
```

---

### Issue: SSL Certificate Error

**Symptoms:**
- "Your connection is not private"
- Certificate expired or invalid

**Diagnosis:**
```bash
certbot certificates | grep ifs-sec-planning
# Check expiry date
```

**Solution:** Renew certificate
```bash
certbot renew --cert-name ifs-sec-planning.v4value.ai
docker exec nginx-proxy nginx -s reload
```

**Force renewal:**
```bash
certbot renew --cert-name ifs-sec-planning.v4value.ai --force-renewal
docker exec nginx-proxy nginx -s reload
```

---

## Content Issues

### Issue: SKU Validation Errors

**Symptoms:**
- Placeholder SKUs (IC12920, IC12922, SCH6000) in presentation
- Build warnings or errors

**Solution:** Replace with actual IFS SKUs
```javascript
// Wrong
<td className="font-mono">IC12920</td>

// Correct
<td className="font-mono">IC12408</td>
```

**Validated SKUs:**
- IC12408 (Service Management Core)
- IC12406 (Mobile Work Order)
- IC11200 (Advanced Optimization)
- IC12917 (Maintenance Planning and Scheduling)
- IC19000 (IFS.ai - AI Activation Pass)
- COPPERLEAF (partner product)

---

### Issue: Slide Content Not Rendering

**Symptoms:**
- Blank slide
- Console error: "Cannot read property 'content' of undefined"

**Diagnosis:**
```javascript
// Check sections array structure
const sections = [
  {
    title: "...",
    icon: IconComponent,
    color: "...",
    slides: [
      {
        title: "...",
        subtitle: "...",
        content: ( ... )  // Must be JSX
      }
    ]
  }
];
```

**Common Errors:**
1. Missing comma between slides
2. Missing closing bracket `}`
3. Invalid JSX syntax in content
4. Missing `content:` property

---

### Issue: Table Not Displaying Correctly

**Symptoms:**
- Table layout broken in dark mode
- Missing borders
- Misaligned columns

**Solution:** Ensure dark mode variants
```javascript
<table className="w-full border-collapse">
  <thead>
    <tr className="bg-purple-700 dark:bg-purple-900 text-white">
      <th className="p-2 border border-purple-600">Header</th>
    </tr>
  </thead>
  <tbody className="bg-white dark:bg-gray-800">
    <tr className="border-b border-gray-300 dark:border-gray-700">
      <td className="p-2 text-gray-900 dark:text-white">Data</td>
    </tr>
  </tbody>
</table>
```

---

## Git Issues

### Issue: Git Push Rejected

**Error:**
```
! [rejected] claude/ifs-sec-account-planning-... -> ... (fetch first)
error: failed to push some refs
```

**Root Cause:** Remote has commits not in local branch

**Solution:**
```bash
# Fetch remote changes
git fetch origin <branch-name>

# Rebase local commits on top of remote
git pull --rebase origin <branch-name>

# Push
git push -u origin <branch-name>
```

**If rebase conflicts:**
```bash
# Resolve conflicts in files
git add <resolved-files>
git rebase --continue

# Or abort and merge instead
git rebase --abort
git merge origin/<branch-name>
git push -u origin <branch-name>
```

---

### Issue: Merge Conflict

**Symptoms:**
- Git shows conflict markers in files
- Build fails with syntax errors

**Solution:**
```bash
# Check conflict status
git status

# Edit conflicted files
# Look for markers:
<<<<<<< HEAD
Your changes
=======
Their changes
>>>>>>> commit-hash

# Resolve by choosing correct code
# Remove conflict markers

# Mark as resolved
git add <file>

# Complete merge/rebase
git commit  # or git rebase --continue
```

---

## Performance Issues

### Issue: Site Loads Slowly

**Diagnosis:**
```bash
# Check build size
ls -lh build/static/js/
ls -lh build/static/css/

# Expected:
# JS: ~66 KB (gzipped)
# CSS: ~6 KB (gzipped)
```

**Solution 1:** Verify gzip compression
```bash
# Check nginx compression
curl -H "Accept-Encoding: gzip" -I https://ifs-sec-planning.v4value.ai/
# Should see: Content-Encoding: gzip
```

**Solution 2:** Optimize images
```bash
# Check logo sizes
ls -lh public/*.png public/*.svg
# IFS logo should be ~46 KB
```

**Solution 3:** Enable browser caching
```nginx
# In nginx config
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

---

## Quick Diagnostic Commands

```bash
# Check all systems
docker ps | grep ifs-sec-planning          # Container running?
docker logs ifs-sec-planning --tail 50     # Recent logs
curl -I https://ifs-sec-planning.v4value.ai/  # Site accessible?
npm run build                               # Build works?
git status                                  # Clean working tree?

# Full health check
echo "Container:" && docker ps | grep ifs-sec-planning && \
echo "Build:" && ls -lh build/static/js/ && \
echo "Git:" && git status --short && \
echo "Site:" && curl -I https://ifs-sec-planning.v4value.ai/ 2>&1 | head -1
```

---

**Last Updated:** 2025-11-11
**Version:** 2.0
