# Content Guide — IFS SEC Account Planning

## Presentation Structure

**Framework:** Account Planning Methodology
**Total:** 5 sections, 25 slides
**Target Audience:** SEC executive stakeholders, IT leadership, procurement
**Purpose:** Strategic account plan for IFS digital transformation at Saudi Electricity Company

## Section Breakdown

### Section 1: Strategic Foundation (6 slides)
**Icon:** Target | **Color:** Purple

1. **Market Context** - Saudi Arabia's Power Market Dynamics
2. **Saudi Electricity Company** - Strategic Account Plan
3. **Stakeholder Landscape** - Executive Engagement Map
4. **Business Pain Points** - Current Challenges
5. **Proof Points** - IFS Track Record in Utilities
6. **ESG & Vision 2030** - Strategic Alignment

**Purpose:** Establish context, validate opportunity, demonstrate credibility

---

### Section 2: Solution & Commercial (6 slides)
**Icon:** DollarSign | **Color:** Green

**⚠️ HIGH PRIORITY SLIDES**

1. **IFS Solution Overview** - Asset Performance Management Platform
2. **Solution Mapping** - Pain Points → IFS Solutions Matrix
3. **Bill of Materials - Software** - Detailed SKU breakdown with ARR
4. **Bill of Materials - Services** - Implementation services breakdown
5. **3-Year Consumption Plan** - User ramp and asset coverage progression
6. **Revenue Projections** - 3-year financial model (SAR 45M TCV)

**Purpose:** Demonstrate solution fit, commercial clarity, financial planning

**Key Data:**
- **Year 1:** 50 users, 5,000 assets, SAR 12M
- **Year 2:** 200 users, 15,000 assets, SAR 18M
- **Year 3:** 500 users, 25,000 assets, SAR 15M
- **Total TCV:** SAR 45M
- **Year 3 ARR:** SAR 11.2M

---

### Section 3: Go-to-Market Execution (7 slides)
**Icon:** Users | **Color:** Blue

**⚠️ HIGH PRIORITY: PARTNER ENGAGEMENT**

1. **Executive Engagement** - Stakeholder mapping and engagement plan
2. **Account-Based Marketing (ABM) Strategy** - Targeted marketing approach
3. **ABM Execution** - Content, events, channels
4. **Partner Go-to-Market** - SBM (Saudi Business Machines) co-selling
5. **Partner Engagement Details** - Roles, responsibilities, incentives
6. **Competitive Landscape** - SAP, Oracle, Maximo positioning
7. **Competitive Differentiation** - IFS unique value propositions

**Purpose:** Define execution strategy, leverage partner ecosystem, address competition

**Critical Partner:** SBM required for government procurement approval

---

### Section 4: De-Risking & Validation (4 slides)
**Icon:** Shield | **Color:** Orange

1. **Implementation Approach** - Phased rollout strategy
2. **Risk Assessment** - Technical, organizational, commercial risks
3. **Risk Mitigation** - Mitigation strategies for each risk category
4. **Success Metrics** - KPIs and measurement framework

**Purpose:** Address stakeholder concerns, demonstrate planning rigor

**Key Risks:**
- Integration complexity (15+ legacy systems)
- Change management (8,000+ employees)
- Government procurement timeline
- Partner dependency (SBM critical path)

---

### Section 5: Execution Plan (2 slides)
**Icon:** CheckCircle | **Color:** Purple

1. **Timeline & Milestones** - 36-month deployment roadmap
2. **Next Steps** - Immediate actions and decision points

**Purpose:** Call to action, clear path forward

**Timeline:**
- **Q1 2025:** Executive alignment, RFP preparation
- **Q2 2025:** Vendor selection, contract negotiation
- **Q3-Q4 2025:** Phase 1 implementation (Generation division)
- **2026-2027:** Phases 2-3 rollout (Transmission, Distribution)

---

## Content Editing Guide

### Location
All content in: **`src/App.js`** → `sections` array (starts ~line 90)

### Structure
```javascript
const sections = [
  {
    title: "Section Title",
    icon: IconComponent,  // from lucide-react
    color: "text-color-700",
    slides: [
      {
        title: "Slide Title",
        subtitle: "Optional subtitle",
        content: (
          <div className="space-y-6">
            {/* Slide content JSX */}
          </div>
        )
      }
    ]
  }
];
```

### Editing Workflow

1. **Locate slide:**
   - Find section index (0-4)
   - Find slide index within section (0-based)
   - Example: Section 2, Slide 3 = Bill of Materials

2. **Edit content:**
   - Modify JSX within `content: ( ... )`
   - Maintain dark mode variants: `dark:bg-gray-800`
   - Use IFS purple: `text-purple-700 dark:text-purple-400`

3. **Build and test:**
   ```bash
   npm start  # Test locally
   npm run build  # Production build
   ```

### SKU Reference Guidelines

**⚠️ CRITICAL:** Always use actual IFS SKU codes

**Validated SKUs:**
- **IC12408** - Service Management Core (formerly IC12920)
- **IC12406** - Mobile Work Order Management
- **IC11200** - Advanced Optimization and Scheduling
- **IC12917** - Maintenance Planning and Scheduling - Large (formerly SCH6000)
- **IC19000** - IFS.ai - AI Activation Pass (formerly IC12922)
- **COPPERLEAF** - Asset Investment Planning (partner product)

**For new SKUs:**
- Check user-provided SKU list first
- If not found, mark as: `[TBD - Insert IFS SKU]`
- Never commit placeholder SKUs

**SKU Locations:**
- Solution Mapping Matrix: Section 2, Slide 2
- Bill of Materials - Software: Section 2, Slide 3
- Bill of Materials - Services: Section 2, Slide 4

### Financial Data Locations

**Bill of Materials (Section 2, Slide 3):**
```javascript
// Around line 670
<tbody className="bg-white dark:bg-gray-800">
  <tr>
    <td>Asset O&M Core</td>
    <td className="font-mono">IC12408</td>
    <td>Named User</td>
    <td>200 users</td>
    <td>None</td>
    <td>Y1</td>
    <td>2,400,000</td>
  </tr>
  // ... more rows
</tbody>
```

**3-Year Consumption Plan (Section 2, Slide 4):**
- User ramp: 50 → 200 → 500
- Asset coverage: 20% → 60% → 90%
- Total assets: 5,000 → 15,000 → 25,000

**Revenue Projections (Section 2, Slide 6):**
- Y1: SAR 12M
- Y2: SAR 18M
- Y3: SAR 15M
- **Total TCV:** SAR 45M
- **Year 3 ARR Run-rate:** SAR 11.2M

### Stakeholder Information

**Location:** Section 1, Slide 3

**Current Stakeholders (Updated Nov 2024):**
- **CEO:** Eng. Khaled bin Hamad Al Sultan
- **CIO:** Dr. Ahmed bin Mohammed Al-Subaey
- **CFO:** Ziyad bin Abdulrahman Al-Shiha
- **COO (Generation):** Eng. Fahad bin Ali Al-Ajlan
- **COO (Transmission):** Eng. Saad bin Nasser Al-Qahtani
- **COO (Distribution):** Eng. Turki bin Abdullah Al-Shehri

**Note:** Always verify stakeholder names/titles before presentations

### Competitive Information

**Location:** Section 3, Slides 6-7

**Main Competitors:**
1. **SAP S/4HANA** - ERP incumbent, high cost, complex
2. **Oracle Utilities** - Billing focus, weak on asset management
3. **IBM Maximo** - Asset-only, legacy architecture

**IFS Differentiators:**
- Cloud-native (competitors on-premise)
- Composable architecture (vs monolithic)
- Industry-specific (utilities-focused)
- Lower TCO (30-40% vs SAP)
- Faster time-to-value (6 months vs 18-24 months)

### Content Best Practices

**1. Dark Mode Compliance:**
```javascript
// Always include dark: variants
<div className="bg-white dark:bg-gray-800 text-gray-900 dark:text-white">
  <h3 className="text-purple-700 dark:text-purple-400">IFS Purple</h3>
  <p className="text-gray-700 dark:text-gray-300">Body text</p>
</div>
```

**2. Responsive Grid Patterns:**
```javascript
// 1 column mobile, 2-3 desktop
<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
```

**3. Consistent Spacing:**
```javascript
// Slide container
<div className="space-y-6">
  // Top-level spacing

  // Card/section
  <div className="space-y-4">
    // Internal spacing
  </div>
</div>
```

**4. Tables:**
```javascript
// Always include dark mode styles
<table className="w-full border-collapse">
  <thead>
    <tr className="bg-purple-700 dark:bg-purple-900 text-white">
      <th className="p-2 border border-purple-600">Header</th>
    </tr>
  </thead>
  <tbody className="bg-white dark:bg-gray-800">
    <tr className="border-b border-gray-300 dark:border-gray-700">
      <td className="p-2 text-gray-900 dark:text-white">Content</td>
    </tr>
  </tbody>
</table>
```

**5. Metric Cards:**
```javascript
<div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border border-blue-300 dark:border-blue-700">
  <div className="text-3xl font-bold text-blue-800 dark:text-blue-300">
    SAR 45M
  </div>
  <div className="text-sm text-gray-600 dark:text-gray-400">
    Total Contract Value
  </div>
</div>
```

## Content Validation Checklist

**Before committing content changes:**
- [ ] All SKU codes verified against IFS product catalog
- [ ] Financial figures cross-checked for consistency
- [ ] Stakeholder names/titles current
- [ ] Dark mode tested on all new content
- [ ] Responsive design tested (mobile, tablet, desktop)
- [ ] No console errors in browser
- [ ] All 25 slides render without issues
- [ ] Spelling/grammar checked
- [ ] IFS branding colors maintained

---

**Last Updated:** 2025-11-11
**Content Version:** 2.0 (Account Planning Framework - 5 sections, 25 slides)
