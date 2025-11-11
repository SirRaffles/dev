# Architecture — IFS SEC Account Planning

## Technology Stack

### Frontend Framework
- **React:** 18.3.1
- **Build Tool:** Create React App (react-scripts 5.0.1)
- **Node Version:** v22.17.0

### Styling
- **CSS Framework:** Tailwind CSS 3.4.13
- **Dark Mode:** Class-based strategy (`darkMode: 'class'`)
- **PostCSS:** 8.x (requires react-scripts 5+)
- **Configuration:** `tailwind.config.js`, `postcss.config.js`

### UI Components
- **Icons:** lucide-react 0.446.0
- **Fonts:** Inter (Google Fonts, weights 300-800)
- **Logo Images:** PNG (IFS) and SVG (SEC)

### Build System
- **Bundler:** Webpack 5 (via react-scripts)
- **Transpiler:** Babel (via react-scripts)
- **Optimizer:** Terser, CSS minimizer
- **Legacy Support:** OpenSSL legacy provider for Node 22

## Project Structure

```
/home/user/dev/                          # Development environment
├── .claude/
│   └── CLAUDE.md                        # Project instructions for Claude
├── docs/
│   ├── ARCHITECTURE.md                  # This file
│   ├── DEPLOYMENT.md                    # Deployment guide
│   ├── CONTENT_GUIDE.md                 # Content organization
│   ├── DEVELOPMENT.md                   # Development workflow
│   └── TROUBLESHOOTING.md               # Common issues
├── public/
│   ├── index.html                       # HTML template with dark mode script
│   ├── ifs-logo.png                     # Official IFS logo (2095×974, 46KB)
│   ├── sec-logo.svg                     # SEC logo (custom SVG)
│   └── manifest.json                    # PWA manifest
├── src/
│   ├── App.js                           # Main component (2435 lines)
│   ├── index.css                        # Global CSS + Tailwind directives
│   └── index.js                         # React root
├── build/                               # Production build (gitignored)
├── tailwind.config.js                   # Tailwind configuration
├── postcss.config.js                    # PostCSS configuration
├── package.json                         # Dependencies
├── ACTIVE_WORK.md                       # Current session status
├── ROADMAP.md                           # Future enhancements
└── CHANGELOG.md                         # Historical changes
```

## Application Architecture

### Component Hierarchy

```
App (SECAccountPlanning)
├── Header
│   ├── IFSLogo
│   ├── SECLogo
│   ├── Progress Bar
│   └── Dark Mode Toggle
├── Sidebar (collapsible)
│   └── Section Navigation
│       └── Slide List (per section)
├── Main Content Area
│   └── Current Slide
│       └── Dynamic JSX Content
└── Footer Navigation
    ├── Previous Button
    └── Next Button
```

### State Management

**React Hooks (useState):**
```javascript
const [currentSection, setCurrentSection] = useState(0);
const [currentSlide, setCurrentSlide] = useState(0);
const [isSidebarOpen, setIsSidebarOpen] = useState(true);
const [expandedSections, setExpandedSections] = useState([]);
const [isDarkMode, setIsDarkMode] = useState(() => {
  const saved = localStorage.getItem('theme');
  if (saved) return saved === 'dark';
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
});
```

**Key State:**
- `currentSection`: 0-4 (5 sections)
- `currentSlide`: 0-based index within section
- `isSidebarOpen`: Sidebar visibility
- `expandedSections`: Array of expanded section indices
- `isDarkMode`: Dark mode toggle state

**Side Effects (useEffect):**
```javascript
useEffect(() => {
  localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
  if (isDarkMode) {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
}, [isDarkMode]);
```

### Data Structure

**Sections Array:**
```javascript
const sections = [
  {
    title: "Strategic Foundation",
    icon: Target,
    color: "text-purple-700",
    slides: [
      {
        title: "Slide Title",
        subtitle: "Optional subtitle",
        content: <JSX />
      },
      // ... more slides
    ]
  },
  // ... more sections
];
```

**Current Structure:**
- 5 sections
- 25 total slides
- Icons from lucide-react
- Dynamic content rendering

## Performance Characteristics

### Build Output (Gzipped)
- **Main JS:** 66 kB
- **Main CSS:** 6.09 kB
- **Chunk JS:** 1.77 kB
- **Total:** ~72 kB (gzipped)

### Load Performance
- **First Contentful Paint:** < 1s
- **Time to Interactive:** < 2s
- **Bundle Size:** Optimized with code splitting

### Optimization Techniques
- Tailwind CSS purge/tree-shaking
- React production build minification
- Gzip compression via nginx
- Static asset caching

## Dark Mode Implementation

### System Preference Detection
```javascript
// In public/index.html
<script>
  if (localStorage.theme === 'dark' ||
      (!('theme' in localStorage) &&
       window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.classList.add('dark')
  }
</script>
```

### Tailwind Configuration
```javascript
// tailwind.config.js
module.exports = {
  darkMode: 'class',
  // ...
}
```

### Component Usage
```javascript
// Dark mode variants
className="bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
```

## Responsive Design

### Breakpoints (Tailwind)
- **Default:** Mobile-first (< 768px)
- **md:** 768px+ (tablets, desktops)
- **Patterns:** `grid-cols-1 md:grid-cols-2`, `md:grid-cols-3`

### Mobile Adaptations
- Sidebar collapses (hamburger menu)
- Single-column layouts
- Touch-friendly navigation buttons
- Reduced padding/margins

## Browser Compatibility

### Supported Browsers
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile: iOS Safari 14+, Chrome Mobile 90+

### Required Features
- CSS Grid
- Flexbox
- CSS Custom Properties
- localStorage
- ES6+ (transpiled via Babel)

## Accessibility

### WCAG 2.1 Features
- **ARIA Labels:** All interactive elements
- **Keyboard Navigation:** Tab, arrow keys, Enter
- **Focus Indicators:** `focus:ring-2 focus:ring-purple-500`
- **Semantic HTML:** `<header>`, `<main>`, `<nav>`, `<button>`
- **Color Contrast:** WCAG AA compliant (purple on white/gray)

### Screen Reader Support
- Descriptive button labels
- Section headings hierarchy
- Alt text for logos

## Security Considerations

### Client-Side Only
- No backend API
- No user authentication
- No sensitive data storage
- Static file serving via nginx

### Content Security
- All content embedded in React bundle
- No external API calls (except Google Fonts CDN)
- No user-generated content

---

**Last Updated:** 2025-11-11
**Architecture Version:** 2.0 (Account Planning Framework)
