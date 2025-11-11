# Claude Code House Rules — IFS SEC Account Planning

## Project Overview
Strategic Account Planning presentation for Saudi Electricity Company (SEC), showcasing IFS digital transformation capabilities.

**Live URL:** https://ifs-sec-planning.v4value.ai/

## Stack & Architecture

### Frontend
- **Framework:** React 18.3.1 with Create React App
- **Build Tool:** react-scripts 5.0.1 (upgraded from 3.0.1 for PostCSS 8 support)
- **Styling:** Tailwind CSS 3.4.13 with dark mode support
- **Icons:** lucide-react 0.446.0
- **Node Version:** v22.17.0 (requires `NODE_OPTIONS=--openssl-legacy-provider` for webpack 4 compatibility)

### Deployment
- **Container:** nginx:alpine serving static React build
- **Reverse Proxy:** nginx-proxy with SSL/TLS via Let's Encrypt
- **Port:** 8300 (internal)
- **Domain:** ifs-sec-planning.v4value.ai

### Build Commands
```bash
# Development
npm start

# Production build (IMPORTANT: Use legacy OpenSSL provider)
NODE_OPTIONS=--openssl-legacy-provider npm run build

# Or use the standard command (works with react-scripts 5+)
npm run build

# Deploy
chmod -R 755 build/
docker restart ifs-sec-planning
```

## Project Structure

```
/home/Davrine/docker/ifs-sec-planning/
├── public/
│   ├── ifs-logo.png          # Official IFS logo (2095×974, from ifs-benchmarking)
│   ├── sec-logo.svg          # SEC logo (custom SVG)
│   ├── index.html            # HTML template with dark mode script
│   └── manifest.json
├── src/
│   ├── App.js                # Main presentation component (1158 lines)
│   ├── index.css             # Global CSS + Tailwind directives
│   └── index.js              # React root
├── build/                    # Production build (gitignored)
├── tailwind.config.js        # Tailwind + IFS purple theme
├── postcss.config.js         # PostCSS with Tailwind plugin
└── package.json
```

## Key Features

### 1. Presentation Slides
- **12 Sections** with multiple slides each:
  1. Executive Summary (2 slides)
  2. Strategic Imperatives (2 slides)
  3. Stakeholder Landscape (2 slides)
  4. IFS Solution Overview (4 slides)
  5. Value Proposition (2 slides)
  6. Implementation Approach (3 slides)
  7. Commercial Model (2 slides)
  8. Risk Mitigation (2 slides)
  9. Success Metrics (2 slides)
  10. Timeline (1 slide)
  11. Competitive Differentiation (2 slides)
  12. Next Steps (1 slide)

### 2. Navigation System
- **Left Sidebar:** Collapsible section navigation with slide lists
  - Sections numbered (1, 2, 3...)
  - Better indentation (ml-8 for slides)
  - Reduced spacing for cleaner appearance
  - All sections collapsed by default
- **Header:** Section progress bar with tooltips
- **Keyboard:** Previous/Next buttons with ARIA labels
- **Progress Indicators:** Visual dots for slides within each section

### 3. Dark Mode
- System preference detection on load
- localStorage persistence
- Full dark mode support across all 12 sections
- Toggle button in header (Sun/Moon icon)

### 4. Responsive Design
- Mobile-first approach
- Breakpoints: `md:` (768px+) for 2-3 column grids
- Sidebar collapses on mobile
- Touch-friendly navigation

### 5. Accessibility
- ARIA labels on all interactive elements
- Focus indicators (`focus:ring-2 focus:ring-purple-500`)
- Semantic HTML structure
- Keyboard navigation support

## Branding & Design

### IFS Brand Colors
```javascript
colors: {
  'ifs': {
    purple: '#6f2c91',
    'purple-light': '#8a3db8',
    'purple-dark': '#5a2375',
  },
}
```

### Logos
- **IFS Logo:** `/ifs-logo.png` (official, from ifs-benchmarking project)
- **SEC Logo:** `/sec-logo.svg` (custom SVG with SEC branding)

### Typography
- **Font:** Inter (Google Fonts)
- **Weights:** 300, 400, 500, 600, 700, 800

## Content Organization

### Slide Order (Updated Nov 2024)
**Executive Summary Section:**
1. Market Context (Saudi Arabia's Power Market Dynamics)
2. Saudi Electricity Company (Strategic Account Plan)

### State Management
```javascript
const [currentSection, setCurrentSection] = useState(0);
const [currentSlide, setCurrentSlide] = useState(0);
const [isSidebarOpen, setIsSidebarOpen] = useState(true);
const [expandedSections, setExpandedSections] = useState([]); // Collapsed by default
const [isDarkMode, setIsDarkMode] = useState(() => {
  const saved = localStorage.getItem('theme');
  if (saved) return saved === 'dark';
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
});
```

## Development Workflow

### Making Changes to Presentation Content

1. **Edit slides in `src/App.js`:**
   - Find the `sections` array (starts around line 85)
   - Each section has: `title`, `icon`, `color`, `slides[]`
   - Each slide has: `title`, `subtitle`, `content` (JSX)

2. **Styling Guidelines:**
   - Use Tailwind utility classes
   - Always include dark mode variants: `dark:bg-gray-800`, `dark:text-white`
   - Maintain IFS purple theme: `text-purple-700 dark:text-purple-400`
   - Keep responsive breakpoints: `grid-cols-1 md:grid-cols-2`

3. **Build & Deploy:**
   ```bash
   npm run build
   chmod -R 755 build/
   docker restart ifs-sec-planning
   ```

4. **Commit Changes:**
   ```bash
   git add -A
   git commit -m "Description of changes"
   git push origin <branch-name>
   ```

### Common Tasks

**Add New Slide:**
```javascript
// In sections array, within a section's slides array
{
  title: "New Slide Title",
  subtitle: "Optional subtitle",
  content: (
    <div className="space-y-6">
      {/* Your content here */}
    </div>
  )
}
```

**Update Branding Colors:**
- Edit `tailwind.config.js` → `theme.extend.colors.ifs`
- Rebuild to regenerate CSS

**Change Logo:**
- Replace `/public/ifs-logo.png` or `/public/sec-logo.svg`
- No code changes needed (uses public URLs)

## Critical Issues & Solutions

### Issue 1: Tailwind CSS Not Compiling (FIXED)
**Problem:** Layout completely broken, CSS only 448 bytes
**Root Cause:** react-scripts 3.0.1 doesn't support PostCSS 8 (required by Tailwind 3)
**Solution:** Upgraded react-scripts 3.0.1 → 5.0.1
**Date Fixed:** November 11, 2025
**Commit:** aadb557

### Issue 2: Build Requires Legacy OpenSSL
**Problem:** `react-scripts build` fails with OpenSSL errors
**Workaround:** Use `NODE_OPTIONS=--openssl-legacy-provider npm run build`
**Permanent Fix:** react-scripts 5+ handles this automatically

### Issue 3: IFS Logo Not Official Branding
**Problem:** Custom SVG didn't match IFS branding
**Solution:** Copied official logo from `/home/Davrine/ifs-benchmarking/packages/web/public/images/ifs-logo.png`
**Date Fixed:** November 11, 2025
**Commit:** e23523d

## Docker Configuration

### Dockerfile (nginx:alpine)
```dockerfile
FROM nginx:alpine
COPY build/ /usr/share/nginx/html
EXPOSE 80
```

### nginx-proxy Configuration
```nginx
# /home/Davrine/docker/nginx-proxy/nginx.conf
server {
    listen 80;
    server_name ifs-sec-planning.v4value.ai;

    location / {
        proxy_pass http://127.0.0.1:8300;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### DNS Configuration (Namecheap)
- Type: CNAME
- Host: ifs-sec-planning
- Value: v4value.ai

## Troubleshooting

### Site Shows HTTP 403
**Cause:** Build directory missing or wrong permissions
**Fix:**
```bash
rm -rf build && npm run build
chmod -R 755 build/
docker restart ifs-sec-planning
```

### Tailwind Styles Not Applying
**Cause:** CSS not being compiled
**Fix:** Ensure react-scripts >= 5.0.1
```bash
npm install react-scripts@5.0.1
npm run build
```

### Dark Mode Not Working
**Check:**
1. `public/index.html` has dark mode script in `<head>`
2. `src/index.css` has dark mode base styles
3. All components use `dark:` variants in className

### Browser Shows Old Version
**Fix:** Hard refresh to bypass cache
- Mac: `Cmd + Shift + R`
- Windows: `Ctrl + Shift + R`
- Or clear browser cache for ifs-sec-planning.v4value.ai

## Git Workflow

### Current Branch
`claude/ifs-sec-account-planning-011CUrxGbfHkHate85z9puN9`

### Commit Message Format
```
<type>(<scope>): <description>

- Bullet point details
- More details

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Recent Major Commits
- `e23523d` - Use official IFS logo from ifs-benchmarking project
- `cfda57d` - Implement UX improvements: logos, navigation, and slide reordering
- `aadb557` - Fix critical layout issue - upgrade react-scripts to v5
- `6e24022` - Complete UX/UI remediation: dark mode, responsive design, accessibility

## Performance Metrics

### Build Size (Gzipped)
- Main JS: 58.83 kB
- Main CSS: 5.42 kB (includes all Tailwind utilities)
- Chunk JS: 1.77 kB

### Load Performance
- First Contentful Paint: < 1s
- Time to Interactive: < 2s
- Total Page Size: ~70 kB (gzipped)

## Future Enhancements

### Potential Improvements
- [ ] Add PDF export functionality
- [ ] Implement slide transitions/animations
- [ ] Add print-optimized CSS
- [ ] Create mobile app version
- [ ] Add speaker notes feature
- [ ] Implement slide templates for reuse

### Content Updates Needed
- [ ] Update financial projections for 2025
- [ ] Refresh competitive landscape analysis
- [ ] Add latest SEC performance metrics
- [ ] Update Vision 2030 alignment statistics

## Support & Maintenance

### Quick Links
- **Production:** https://ifs-sec-planning.v4value.ai/
- **Repo:** git@github.com:SirRaffles/dev.git
- **Container Logs:** `docker logs ifs-sec-planning`
- **nginx Logs:** `docker logs nginx-proxy`

### Emergency Contacts
- **Primary Admin:** Davrine (NAS)
- **Deployment Path:** `/home/Davrine/docker/ifs-sec-planning`
- **Production Server:** 192.168.50.171 (DavrineNAS)

### Backup & Recovery
- **Git:** All code versioned in GitHub
- **Docker:** Container recreatable from build/
- **Content:** All presentation content in `src/App.js`

---

**Last Updated:** November 11, 2025
**Maintained By:** Claude Code
**Version:** 1.0.0
