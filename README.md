# IFS SEC Account Planning

A state-of-the-art HTML presentation showcasing IFS.ai's strategic account plan for Saudi Electricity Company (SEC).

## Overview

This interactive presentation transforms comprehensive account planning data into a visually stunning, professional presentation using IFS.ai marketing layout, design, and branding.

## Features

- **7 Major Sections**: Executive Summary, Strategic Imperatives, Stakeholder Landscape, IFS Solution Portfolio, Business Case, Proof Points & SWOT, Next Steps
- **Multiple Slides per Section**: Each section contains detailed slides covering different aspects
- **Modern UI/UX**:
  - Beautiful gradient backgrounds with IFS brand colors
  - Smooth transitions and animations
  - Responsive design
  - Backdrop blur effects for glassmorphism
- **Interactive Navigation**:
  - Tab-based section navigation
  - Slide indicators and controls
  - Keyboard-friendly Previous/Next buttons
- **Professional Content Organization**:
  - Market context and industry mega-trends
  - Strategic imperatives and change management
  - Stakeholder mapping and personas
  - Comprehensive use cases with ROI timelines
  - Competitive advantages
  - Financial impact and implementation roadmap
  - SWOT analysis and ESG alignment
  - Proof points and success stories

## Technology Stack

- React 18
- Tailwind CSS for styling
- Lucide React for icons
- Modern JavaScript (ES6+)

## Key Sections

### 1. Executive Summary
- SEC overview with key metrics (11.2M customers, 70.7 GW peak load, $133B assets)
- Market context and Vision 2030 alignment
- Saudi Arabia power market dynamics

### 2. Strategic Imperatives
- Industry mega-trends (decarbonization, digital grid, DER, EVs, etc.)
- Strategic change imperatives with FROM→TO transformations
- KPIs and success metrics

### 3. Stakeholder Landscape
- Executive leadership profiles (CEO, CFO, COO, CIO)
- Operational leaders (EVP Generation, Transmission, Distribution)
- Pain points and IFS value propositions

### 4. IFS Solution Portfolio
- 8 comprehensive use cases with ROI horizons
- Competitive advantages vs SAP, Oracle, and others
- Proof points (414% ROI, best-in-class scheduling, etc.)

### 5. Business Case
- Financial impact breakdown (SAR 2B O&M savings, SAR 2B capex optimization)
- 5-year ROI summary (4:1+ return)
- 24-month phased implementation roadmap

### 6. Proof Points & SWOT
- Real customer success stories
- Comprehensive SWOT analysis
- ESG alignment (Environmental, Social, Governance)

### 7. Next Steps
- Engagement strategy with immediate actions
- Why now? Why IFS? positioning
- Call to action

## Getting Started

### Prerequisites

- Node.js 14+
- npm or yarn

### Installation

```bash
npm install
```

### Running the Application

```bash
npm start
```

The app will open at [http://localhost:3000](http://localhost:3000)

### Building for Production

```bash
npm run build
```

## Design Principles

- **IFS.ai Branding**: Blue and purple gradient color schemes throughout
- **Professional Tech Aesthetic**: Modern, clean, corporate presentation style
- **Data Visualization**: Clear metrics, statistics, and visual hierarchies
- **Content Density**: Balanced information density with readability
- **Accessibility**: High contrast, clear typography, intuitive navigation

## Content Organization

The presentation is organized into a logical flow:
1. Set context (market, SEC overview)
2. Establish challenges (strategic imperatives, stakeholder needs)
3. Present solution (IFS portfolio and competitive advantages)
4. Prove value (business case, ROI, proof points)
5. Enable decision (SWOT, ESG alignment)
6. Call to action (next steps)

## Customization

The presentation content is defined in the `sections` array within `App.js`. Each section contains:
- Title
- Icon (from Lucide React)
- Color scheme (Tailwind gradient classes)
- Slides array with title, subtitle, and content

To modify content, edit the relevant section/slide in the `sections` array.

## Deployment

This project is configured for Netlify deployment:

```bash
npm run build
# Deploy the build folder to your hosting service
```

## License

Confidential & Proprietary - © 2024 IFS.ai

## Contact

Account Executive: Mark Marawy
Local Partner: Saudi Business Machines (SBM)
