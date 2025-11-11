# Changelog — IFS SEC Account Planning

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2025-11-11

### Major Changes
**Account Planning Framework Restructure** - Transformed from strategic overview to comprehensive account planning methodology.

### Added
- **Documentation Suite:**
  - Created `ACTIVE_WORK.md` for session handoffs between Claude conversations
  - Created `docs/ARCHITECTURE.md` - Technical stack and system architecture
  - Created `docs/DEPLOYMENT.md` - Production deployment guide
  - Created `docs/CONTENT_GUIDE.md` - Slide content organization and editing
  - Created `docs/DEVELOPMENT.md` - Development workflow and guidelines
  - Created `docs/TROUBLESHOOTING.md` - Common issues and solutions
  - Created `ROADMAP.md` - Future enhancements and planned features
  - Created `CHANGELOG.md` - This file

- **New Presentation Structure (5 sections, 25 slides):**
  - Section 1: Strategic Foundation (6 slides)
  - Section 2: Solution & Commercial (6 slides) - HIGH PRIORITY
  - Section 3: Go-to-Market Execution (7 slides)
  - Section 4: De-Risking & Validation (4 slides)
  - Section 5: Execution Plan (2 slides)

- **High-Priority Content:**
  - Bill of Materials - Software (detailed SKU breakdown)
  - Bill of Materials - Services (implementation services)
  - 3-Year Consumption Plan (user ramp: 50→500, assets: 5k→25k)
  - Partner Go-to-Market Strategy (SBM co-selling)
  - Revenue Projections (SAR 45M TCV, SAR 11.2M Y3 ARR)

### Changed
- **CLAUDE.md:** Optimized from 350 lines → 145 lines
  - Removed historical/outdated content
  - Added references to docs/ files
  - Updated with current structure (5 sections, 25 slides)
  - Added SKU validation guidelines
  - Added session handoff instructions

- **SKU Validation (00d1239):**
  - IC12920 → IC12408 (Service Management Core) - 5 occurrences
  - IC12922 → IC19000 (IFS.ai - AI Activation Pass) - 2 occurrences
  - SCH6000 → IC12917 (Maintenance Planning and Scheduling) - 1 occurrence
  - Updated in Solution Mapping Matrix and Bill of Materials

- **Stakeholder Information (6554fcb):**
  - Updated SEC executive names and titles with actual stakeholders
  - Refreshed organizational chart

### Removed
- Old 7-section structure (consolidated to 5 sections)
- 10 slides removed from old structure
- Placeholder SKU codes (replaced with validated codes)
- Historical issue logs from CLAUDE.md (moved to CHANGELOG.md)

---

## [1.2.0] - 2025-11-11

### Added
- Comprehensive `CLAUDE.md` documentation (ae2baf1)
  - Project overview and architecture
  - Build and deployment instructions
  - Development workflow
  - Critical issues and solutions
  - Git workflow guidelines

### Fixed
- Official IFS logo integration (e23523d)
  - Replaced custom SVG with official PNG from ifs-benchmarking project
  - Logo dimensions: 2095×974 pixels, 46KB
  - Updated `IFSLogo` component to use `/ifs-logo.png`

---

## [1.1.0] - 2025-11-11

### Added
- UX improvements package (cfda57d)
  - IFS and SEC logos in header
  - Improved navigation UX
  - Slide reordering in Executive Summary section
  - Better sidebar indentation (ml-8 for slides)
  - Reduced section spacing

### Changed
- Executive Summary slide order:
  - Slide 1: Market Context (Saudi Arabia's Power Market Dynamics)
  - Slide 2: Saudi Electricity Company (Strategic Account Plan)

---

## [1.0.1] - 2025-11-11

### Fixed
- Critical layout issue (aadb557)
  - Upgraded react-scripts from 3.0.1 to 5.0.1
  - Fixed Tailwind CSS compilation (PostCSS 8 support)
  - Layout now renders correctly
  - CSS file size: 448 bytes → 6.09 KB (gzipped)

**Root Cause:** react-scripts 3.0.1 doesn't support PostCSS 8 (required by Tailwind CSS 3)

---

## [1.0.0] - 2025-11-11

### Added
**Initial Release** - Complete UX/UI remediation (6e24022)

- **Dark Mode:**
  - System preference detection on load
  - localStorage persistence
  - Toggle button in header (Sun/Moon icon)
  - Full dark mode support across all sections
  - Dark mode script in `public/index.html`

- **Navigation System:**
  - Left sidebar with collapsible section navigation
  - Section progress bar with tooltips in header
  - Previous/Next buttons with ARIA labels
  - Keyboard navigation support
  - Visual progress indicators (dots per section)
  - All sections collapsed by default

- **Responsive Design:**
  - Mobile-first approach
  - Breakpoints: `md:` (768px+) for tablets/desktops
  - Sidebar collapses on mobile (hamburger menu)
  - Touch-friendly navigation buttons
  - Grid layouts: 1 column mobile, 2-3 columns desktop

- **Accessibility:**
  - ARIA labels on all interactive elements
  - Focus indicators (`focus:ring-2 focus:ring-purple-500`)
  - Semantic HTML structure
  - Keyboard navigation (Tab, Enter, Arrow keys)
  - Screen reader support

- **Branding:**
  - IFS purple theme (`#6f2c91`)
  - Inter font (Google Fonts, weights 300-800)
  - Custom Tailwind configuration
  - IFS and SEC logos

- **Initial Content (7 sections, 15 slides):**
  1. Executive Summary (2 slides)
  2. Strategic Imperatives (2 slides)
  3. Stakeholder Landscape (2 slides)
  4. IFS Solution Overview (4 slides)
  5. Value Proposition (2 slides)
  6. Implementation Approach (1 slide)
  7. Next Steps (2 slides)

- **Technical Stack:**
  - React 18.3.1 with Create React App
  - Tailwind CSS 3.4.13 (dark mode enabled)
  - lucide-react 0.446.0 (icons)
  - Node v22.17.0
  - Build optimization (66 KB JS gzipped)

- **Deployment:**
  - Docker container (nginx:alpine)
  - nginx-proxy with SSL/TLS (Let's Encrypt)
  - Production domain: https://ifs-sec-planning.v4value.ai/
  - Deployment path: `/home/Davrine/docker/ifs-sec-planning/`

---

## Version History Summary

| Version | Date       | Description                                    | Slides |
|---------|------------|------------------------------------------------|--------|
| 2.0.0   | 2025-11-11 | Account Planning Framework + Documentation     | 25     |
| 1.2.0   | 2025-11-11 | CLAUDE.md documentation, Official IFS logo     | 15     |
| 1.1.0   | 2025-11-11 | UX improvements, logo integration              | 15     |
| 1.0.1   | 2025-11-11 | Critical layout fix (react-scripts upgrade)    | 15     |
| 1.0.0   | 2025-11-11 | Initial release (UX/UI remediation)            | 15     |

---

## Git Commit References

**Recent commits:**
- `00d1239` - Validate and update SKU references with actual IFS product codes
- `6554fcb` - feat(presentation): Update stakeholder information with actual SEC executives
- `ae2baf1` - Add comprehensive CLAUDE.md documentation
- `6a7ef03` - Transform SEC presentation into comprehensive Account Planning Framework
- `e23523d` - Use official IFS logo from ifs-benchmarking project
- `cfda57d` - Implement UX improvements: logos, navigation, and slide reordering
- `aadb557` - Fix critical layout issue - upgrade react-scripts to v5
- `6e24022` - Complete UX/UI remediation: dark mode, responsive design, accessibility

---

## Upgrade Notes

### 1.x → 2.0
**Breaking Changes:**
- Presentation structure changed from 7 sections to 5 sections
- Slide count increased from 15 to 25
- Some content reorganized across sections

**Migration:**
- No code changes required
- Content automatically restructured
- Review new slides for accuracy
- Verify SKU codes are correct

### 0.x → 1.0
**Breaking Changes:**
- Complete redesign (if migrating from earlier prototype)
- New component structure
- Dark mode required throughout

**Migration:**
- Full rebuild required
- No backward compatibility

---

## Known Issues

### Current
None.

### Resolved
- ✅ Tailwind CSS not compiling (fixed in 1.0.1)
- ✅ IFS logo not official branding (fixed in 1.2.0)
- ✅ Placeholder SKU codes (fixed in 2.0.0)
- ✅ Outdated stakeholder information (fixed in 2.0.0)
- ✅ Unorganized documentation (fixed in 2.0.0)

---

## Contributors

- **Claude Code** - AI-assisted development
- **Davrine** - Project owner, deployment infrastructure

---

**Last Updated:** 2025-11-11
**Changelog Maintained By:** Claude Code
