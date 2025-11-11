# Roadmap — IFS SEC Account Planning

## Current Version: 2.0
**Account Planning Framework** - 5 sections, 25 slides

---

## Planned Enhancements

### Phase 1: Export & Sharing (Priority: High)

#### PDF Export
- **Description:** Generate PDF version of presentation for offline sharing
- **Use Case:** Email to stakeholders, print for meetings
- **Technical Approach:**
  - Library: react-to-pdf or jsPDF
  - Capture each slide as canvas
  - Maintain formatting and dark mode support
- **Estimated Effort:** 2-3 days

#### PowerPoint Export
- **Description:** Export to PPTX format for editing
- **Use Case:** Customize presentation for specific audiences
- **Technical Approach:**
  - Library: pptxgenjs
  - Convert slide JSX to PowerPoint objects
  - Preserve IFS branding
- **Estimated Effort:** 3-4 days

#### Share Link Generator
- **Description:** Generate shareable links with specific slide focus
- **Use Case:** Deep link to specific section/slide
- **Technical Approach:**
  - URL params: `?section=2&slide=3`
  - Auto-navigate on load
  - Share button in header
- **Estimated Effort:** 1 day

---

### Phase 2: Enhanced User Experience (Priority: Medium)

#### Slide Transitions
- **Description:** Smooth animations between slides
- **Options:**
  - Fade in/out
  - Slide left/right
  - Zoom in/out
- **Technical Approach:**
  - Framer Motion or React Spring
  - Configurable transition speed
  - Respect prefers-reduced-motion
- **Estimated Effort:** 2 days

#### Speaker Notes
- **Description:** Add presenter notes (not visible to audience)
- **Use Case:** Talking points for presentations
- **Technical Approach:**
  - Add `notes` property to slide objects
  - Toggle view with keyboard shortcut
  - Separate presenter mode window
- **Estimated Effort:** 2-3 days

#### Print-Optimized Layout
- **Description:** CSS optimized for printing
- **Features:**
  - All slides on single printout
  - Remove navigation/interactive elements
  - Optimize for black & white printing
- **Technical Approach:**
  - @media print CSS
  - Print stylesheet
  - Print preview mode
- **Estimated Effort:** 1-2 days

---

### Phase 3: Content Management (Priority: Medium)

#### Slide Templates
- **Description:** Reusable slide templates
- **Templates:**
  - Title slide
  - 2-column comparison
  - 3-column metrics
  - Timeline
  - Table layout
- **Technical Approach:**
  - Component library
  - Props-based customization
  - Storybook for preview
- **Estimated Effort:** 3-4 days

#### Content Versioning
- **Description:** Track presentation versions
- **Features:**
  - Version selector
  - What's new highlights
  - Rollback capability
- **Technical Approach:**
  - JSON content separation from code
  - Version metadata
  - Git tag integration
- **Estimated Effort:** 4-5 days

#### Multi-Language Support
- **Description:** Arabic and English versions
- **Use Case:** Present to Arabic-speaking stakeholders
- **Technical Approach:**
  - i18n library (react-i18next)
  - RTL layout support
  - Language toggle button
- **Estimated Effort:** 5-7 days

---

### Phase 4: Analytics & Insights (Priority: Low)

#### View Tracking
- **Description:** Track which slides are viewed most
- **Metrics:**
  - Time spent per slide
  - Most/least viewed slides
  - Navigation patterns
- **Technical Approach:**
  - Google Analytics 4 events
  - Privacy-compliant tracking
  - Dashboard visualization
- **Estimated Effort:** 2-3 days

#### Feedback Collection
- **Description:** Gather stakeholder feedback on slides
- **Features:**
  - Rating per slide
  - Comment system
  - Export feedback report
- **Technical Approach:**
  - Firebase or simple backend API
  - Feedback modal
  - Admin dashboard
- **Estimated Effort:** 5-6 days

---

### Phase 5: Advanced Features (Priority: Low)

#### Mobile App Version
- **Description:** Native iOS/Android app
- **Use Case:** Offline presentations, better mobile UX
- **Technical Approach:**
  - React Native
  - Offline storage
  - App store distribution
- **Estimated Effort:** 3-4 weeks

#### Interactive Charts
- **Description:** Live data visualizations
- **Features:**
  - Animated charts (Chart.js, Recharts)
  - Drill-down capabilities
  - Export chart images
- **Technical Approach:**
  - Chart library integration
  - Data props per slide
  - Responsive chart sizing
- **Estimated Effort:** 3-4 days

#### Video Embedding
- **Description:** Embed videos in slides
- **Use Case:** Demo videos, customer testimonials
- **Technical Approach:**
  - YouTube/Vimeo embed
  - Video playback controls
  - Autoplay on slide enter
- **Estimated Effort:** 1-2 days

---

## Content Updates Needed

### Financial Data (Q1 2025)
- [ ] Update 3-year revenue projections
- [ ] Refresh ROI calculations
- [ ] Update currency exchange rates (SAR/USD)
- [ ] Verify pricing for 2025 SKUs

### Market Data (Q1 2025)
- [ ] Latest SEC performance metrics
- [ ] Saudi Arabia electricity consumption trends
- [ ] Vision 2030 progress statistics
- [ ] Renewable energy capacity updates

### Competitive Analysis (Q2 2025)
- [ ] SAP latest pricing and capabilities
- [ ] Oracle Utilities market positioning
- [ ] IBM Maximo recent wins/losses
- [ ] New competitors in Saudi market

### Stakeholder Information (Ongoing)
- [ ] Verify SEC executive names/titles
- [ ] Update organizational chart
- [ ] Refresh stakeholder contact information
- [ ] Add new decision-makers

### SKU Catalog (Ongoing)
- [ ] Validate all SKU codes against latest IFS catalog
- [ ] Add new IFS products (IFS Cloud 24R2+)
- [ ] Update SKU dependencies
- [ ] Verify pricing and licensing models

---

## Technical Debt

### High Priority
- [ ] Add unit tests for slide navigation
- [ ] Implement error boundaries for slide content
- [ ] Add automated accessibility testing
- [ ] Set up CI/CD pipeline

### Medium Priority
- [ ] Refactor App.js (2435 lines → split into components)
- [ ] Extract slide content into separate JSON files
- [ ] Add PropTypes or TypeScript
- [ ] Implement code splitting per section

### Low Priority
- [ ] Migrate from Create React App to Vite
- [ ] Add service worker for offline capability
- [ ] Implement lazy loading for slide images
- [ ] Add performance monitoring

---

## Completed Features ✅

### Version 2.0 (Nov 2024)
- [x] Account Planning Framework restructure (5 sections, 25 slides)
- [x] Bill of Materials with SKU breakdown
- [x] 3-Year Consumption Plan
- [x] SKU validation and actual code replacement
- [x] Documentation restructure (docs/ organization)
- [x] ACTIVE_WORK.md for session handoffs

### Version 1.0 (Nov 2024)
- [x] Dark mode support
- [x] Responsive design (mobile/tablet/desktop)
- [x] Official IFS logo integration
- [x] Collapsible sidebar navigation
- [x] Section progress indicators
- [x] Keyboard navigation
- [x] Accessibility (ARIA labels, focus indicators)
- [x] Tailwind CSS upgrade (3.4.13)
- [x] react-scripts upgrade (5.0.1)

---

## Feature Requests

**How to submit:**
1. Create GitHub issue
2. Label as `enhancement` or `feature-request`
3. Describe use case and expected behavior
4. Provide mockups/examples if applicable

**Current requests:** None

---

**Last Updated:** 2025-11-11
**Next Review:** Q1 2025
