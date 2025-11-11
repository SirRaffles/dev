# Claude Code Instructions — IFS SEC Account Planning

## Project Overview
Strategic Account Planning presentation for Saudi Electricity Company (SEC), showcasing IFS digital transformation capabilities.

**Live URL:** https://ifs-sec-planning.v4value.ai/
**Current Structure:** 5 sections, 25 slides (Account Planning Framework)

## Quick Start

### Build Commands
```bash
# Development
npm start

# Production build
npm run build

# Deploy
chmod -R 755 build/
docker restart ifs-sec-planning
```

**IMPORTANT:** If build fails with OpenSSL errors, use:
```bash
NODE_OPTIONS=--openssl-legacy-provider npm run build
```

### Tech Stack
- React 18.3.1 + Create React App
- Tailwind CSS 3.4.13 (dark mode enabled)
- react-scripts 5.0.1 (PostCSS 8 support)
- lucide-react 0.446.0 (icons)
- Node v22.17.0

## Key Conventions

### 1. Presentation Structure
**Current:** 5 sections, 25 slides (Account Planning Framework)
- Section 1: Strategic Foundation (6 slides)
- Section 2: Solution & Commercial (6 slides)
- Section 3: Go-to-Market Execution (7 slides)
- Section 4: De-Risking & Validation (4 slides)
- Section 5: Execution Plan (2 slides)

**Location:** All slides in `src/App.js` → `sections` array (starts ~line 90)

### 2. SKU Validation (CRITICAL)
- **ALWAYS use actual IFS SKU codes** from the validated list
- For missing SKUs: mark as `[TBD - Insert IFS SKU]`
- Never use placeholder SKUs (IC12920, IC12922, SCH6000 were replaced with actual codes)
- Verify SKUs against the official IFS product catalog

**Validated SKUs in use:**
- IC12408 (Service Management Core)
- IC12406 (Mobile Work Order)
- IC11200 (Advanced Optimization)
- IC12917 (Maintenance Planning and Scheduling - Large)
- IC19000 (IFS.ai - AI Activation Pass)
- COPPERLEAF (partner product, not IFS SKU)

### 3. Styling Guidelines
- **Dark mode:** Always include `dark:` variants for all colored elements
- **IFS purple:** Use `text-purple-700 dark:text-purple-400` for brand consistency
- **Responsive:** Use `grid-cols-1 md:grid-cols-2` pattern
- **Tailwind only:** No custom CSS, use utility classes

### 4. Branding
- **IFS Logo:** `/ifs-logo.png` (official 2095×974 PNG from ifs-benchmarking)
- **SEC Logo:** `/sec-logo.svg` (custom SVG)
- **Colors:** IFS purple `#6f2c91` (see `tailwind.config.js`)
- **Font:** Inter (Google Fonts, weights 300-800)

## Common Tasks

### Edit Slide Content
1. Open `src/App.js`
2. Find `sections` array (~line 90)
3. Locate section → slides array → edit content JSX
4. Build and deploy

### Add New Slide
```javascript
{
  title: "Slide Title",
  subtitle: "Optional subtitle",
  content: (
    <div className="space-y-6">
      {/* Your content with dark mode support */}
    </div>
  )
}
```

### Update Financial Data
- Bill of Materials: `src/App.js` Section 2, Slide 3 (~line 670)
- 3-Year Consumption Plan: Section 2, Slide 4
- Always verify SKU codes are actual IFS product codes

## Critical Gotchas

1. **Build fails:** Upgrade react-scripts to 5.0.1 (not 3.0.1)
2. **Tailwind not working:** Requires react-scripts 5+ for PostCSS 8
3. **Deployment path:** Production files in `/home/Davrine/docker/ifs-sec-planning/`
4. **Git branch:** Always work on `claude/ifs-sec-account-planning-*` branches
5. **SKU validation:** Never commit placeholder SKUs - verify against IFS catalog

## Documentation Structure

This project uses organized documentation for better maintainability:

- **ACTIVE_WORK.md** - Current session status, recent changes, next steps (for Claude handoffs)
- **docs/ARCHITECTURE.md** - Technical stack, project structure, state management
- **docs/DEPLOYMENT.md** - Docker, nginx, DNS configuration, deployment process
- **docs/CONTENT_GUIDE.md** - Slide breakdown, content organization, editing guide
- **docs/DEVELOPMENT.md** - Development workflow, styling guidelines, git conventions
- **docs/TROUBLESHOOTING.md** - Common issues, fixes, debugging tips
- **ROADMAP.md** - Future enhancements, planned improvements
- **CHANGELOG.md** - Historical changes, fixed issues, major commits

## Quick Links

- **Production:** https://ifs-sec-planning.v4value.ai/
- **Repo:** git@github.com:SirRaffles/dev.git
- **Main Code:** `src/App.js` (2435 lines)
- **Deployment:** `/home/Davrine/docker/ifs-sec-planning/` (DavrineNAS: 192.168.50.171)

## Session Handoff

**Before ending a session:**
1. Update `ACTIVE_WORK.md` with current status
2. Document any open issues or blockers
3. Update relevant docs/ files if architecture/content changed
4. Commit all changes with clear messages

**Starting a new session:**
1. Read `ACTIVE_WORK.md` for current status
2. Check recent commits in `CHANGELOG.md`
3. Review any TODOs or blockers

---

**Last Updated:** 2025-11-11
**Version:** 2.0.0 (Documentation Restructure)
