# Development Guide — IFS SEC Account Planning

## Development Workflow

### 1. Start Development Server

```bash
cd /home/user/dev
npm start
```

**Expected Output:**
```
Compiled successfully!

You can now view exit-readiness-assessment in the browser.

  Local:            http://localhost:3000
  On Your Network:  http://192.168.x.x:3000
```

**Features:**
- Hot module reload (changes reflect immediately)
- Error overlay in browser
- Source maps for debugging
- React DevTools support

---

### 2. Make Changes

**Primary File:** `src/App.js` (2435 lines)

**Common Change Types:**

**A. Edit Slide Content:**
```javascript
// Navigate to sections array (line ~90)
const sections = [
  {
    title: "Strategic Foundation",
    slides: [
      {
        title: "Market Context",
        content: (
          <div className="space-y-6">
            {/* Edit content here */}
          </div>
        )
      }
    ]
  }
];
```

**B. Add New Slide:**
```javascript
// Insert into slides array
{
  title: "New Slide Title",
  subtitle: "Optional subtitle",
  content: (
    <div className="space-y-6">
      <h3 className="text-2xl font-bold text-purple-700 dark:text-purple-400">
        Heading
      </h3>
      <p className="text-gray-700 dark:text-gray-300">
        Content with dark mode support
      </p>
    </div>
  )
}
```

**C. Update Financial Data:**
```javascript
// Bill of Materials (Section 2, Slide 3, ~line 670)
<tr className="border-b border-gray-300">
  <td className="p-2 font-semibold">Product Name</td>
  <td className="p-2 font-mono text-purple-700">IC12408</td>
  <td className="p-2">Named User</td>
  <td className="p-2">200 users</td>
  <td className="p-2 text-gray-600">Dependency SKU</td>
  <td className="p-2 font-semibold">Y1</td>
  <td className="p-2 text-right font-semibold">2,400,000</td>
</tr>
```

**D. Add New Icon:**
```javascript
// 1. Import from lucide-react
import { Target, TrendingUp, Users, NewIcon } from 'lucide-react';

// 2. Use in section
{
  title: "Section Name",
  icon: NewIcon,
  color: "text-purple-700",
  slides: [ ... ]
}
```

---

### 3. Test Changes

**Browser Testing:**
1. Open http://localhost:3000
2. Navigate through all affected slides
3. Toggle dark mode (Sun/Moon icon)
4. Test responsive design:
   - Desktop: Full width
   - Tablet: Chrome DevTools → iPad Pro
   - Mobile: Chrome DevTools → iPhone 12

**Console Checks:**
```javascript
// Open browser console (F12)
// Should see NO errors or warnings
```

**Accessibility Checks:**
```bash
# Use browser accessibility tools
# Chrome: Lighthouse → Accessibility audit
# Firefox: Accessibility Inspector
```

---

### 4. Build Production

```bash
npm run build
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

**Verify Build:**
```bash
ls -lh build/static/js/
ls -lh build/static/css/

# Test build locally
npx serve -s build
# Opens on http://localhost:3000
```

---

### 5. Commit Changes

**Check Status:**
```bash
git status
git diff src/App.js
```

**Stage Changes:**
```bash
git add src/App.js
# or
git add -A  # all changes
```

**Commit:**
```bash
git commit -m "$(cat <<'EOF'
<type>(<scope>): <description>

- Detailed change 1
- Detailed change 2
- Detailed change 3

Fixes #issue-number (if applicable)
EOF
)"
```

**Commit Types:**
- `feat` - New feature or slide
- `fix` - Bug fix
- `docs` - Documentation only
- `style` - Code style (formatting, no logic change)
- `refactor` - Code restructure (no behavior change)
- `perf` - Performance improvement
- `test` - Add tests
- `chore` - Build process, dependencies

**Examples:**
```bash
git commit -m "feat(content): Add risk mitigation slide to Section 4"
git commit -m "fix(sku): Replace placeholder IC12920 with actual IC12408"
git commit -m "docs(claude): Update CLAUDE.md with new slide structure"
```

---

### 6. Push Changes

```bash
git push -u origin <branch-name>
```

**If push rejected:**
```bash
git fetch origin <branch-name>
git pull --rebase origin <branch-name>
git push -u origin <branch-name>
```

---

### 7. Deploy to Production

See [docs/DEPLOYMENT.md](DEPLOYMENT.md) for full deployment guide.

**Quick Deploy:**
```bash
# 1. Build
npm run build
chmod -R 755 build/

# 2. Copy to production
rsync -av build/ /home/Davrine/docker/ifs-sec-planning/build/

# 3. Restart container
docker restart ifs-sec-planning

# 4. Verify
curl -I https://ifs-sec-planning.v4value.ai/
```

---

## Styling Guidelines

### Tailwind CSS Conventions

**1. Always Include Dark Mode Variants:**
```javascript
// Wrong
<div className="bg-white text-gray-900">

// Correct
<div className="bg-white dark:bg-gray-800 text-gray-900 dark:text-white">
```

**2. Use IFS Purple for Brand:**
```javascript
// Headings
<h3 className="text-purple-700 dark:text-purple-400">

// Accents
<span className="text-purple-600 dark:text-purple-300">

// Backgrounds
<div className="bg-purple-50 dark:bg-purple-900/20">
```

**3. Responsive Grid Patterns:**
```javascript
// 1 column → 2 columns
<div className="grid grid-cols-1 md:grid-cols-2 gap-4">

// 1 column → 3 columns
<div className="grid grid-cols-1 md:grid-cols-3 gap-4">

// 2 columns → 4 columns
<div className="grid grid-cols-2 md:grid-cols-4 gap-4">
```

**4. Consistent Spacing:**
```javascript
// Slide container (top-level)
<div className="space-y-6">

// Section/card (internal)
<div className="space-y-4">

// List items
<div className="space-y-2">
```

**5. Card Pattern:**
```javascript
<div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border border-blue-300 dark:border-blue-700">
  <div className="text-3xl font-bold text-blue-800 dark:text-blue-300">
    Metric Value
  </div>
  <div className="text-sm text-gray-600 dark:text-gray-400">
    Metric Label
  </div>
</div>
```

**6. Table Pattern:**
```javascript
<table className="w-full text-xs border-collapse">
  <thead>
    <tr className="bg-purple-700 dark:bg-purple-900 text-white">
      <th className="p-2 text-left border border-purple-600">Header</th>
    </tr>
  </thead>
  <tbody className="bg-white dark:bg-gray-800">
    <tr className="border-b border-gray-300 dark:border-gray-700">
      <td className="p-2 text-gray-900 dark:text-white">Data</td>
    </tr>
  </tbody>
</table>
```

**7. Button Pattern:**
```javascript
<button className="px-4 py-2 bg-purple-700 hover:bg-purple-800 text-white rounded-lg transition-colors focus:ring-2 focus:ring-purple-500">
  Button Text
</button>
```

---

## Git Conventions

### Branch Naming
```
claude/<project-name>-<session-id>
```

**Example:**
```
claude/ifs-sec-account-planning-011CUrxGbfHkHate85z9puN9
```

**Rules:**
- Always start with `claude/`
- Must end with matching session ID
- Otherwise push will fail with 403 error

### Commit Message Format

```
<type>(<scope>): <short description>

<detailed description>
- Bullet point 1
- Bullet point 2

<footer>
```

**Example:**
```
feat(content): Add Bill of Materials slides with SKU breakdown

Created comprehensive BOM structure:
- Software SKU breakdown with dependencies
- Services breakdown (implementation, training, support)
- 3-year financial projections
- Validated all SKU codes against IFS catalog

Updated SKUs:
- IC12920 → IC12408 (Service Management Core)
- IC12922 → IC19000 (IFS.ai)
- SCH6000 → IC12917 (Maintenance Planning)
```

### Pull Request Guidelines

**When ready for PR:**
```bash
# 1. Ensure branch is up to date
git fetch origin
git rebase origin/main  # or master

# 2. Push branch
git push -u origin <branch-name>

# 3. Create PR (if gh CLI available)
gh pr create --title "Title" --body "Description"
```

**PR Checklist:**
- [ ] All tests pass (if applicable)
- [ ] Build successful (`npm run build`)
- [ ] No console errors
- [ ] Dark mode tested
- [ ] Responsive design tested
- [ ] Documentation updated
- [ ] ACTIVE_WORK.md updated

---

## Code Quality

### ESLint

**Check for issues:**
```bash
npm run lint  # if script exists
```

**Common Warnings:**
```javascript
// Unused variables
import { Award, Globe } from 'lucide-react';  // Remove if unused

// Unused imports
import React from 'react';  // Remove if not using React.Something

// Missing dependencies in useEffect
useEffect(() => {
  // ...
}, [isDarkMode]);  // Include all used variables
```

### Manual Code Review

**Before committing, check:**
1. No console.log() statements
2. No commented-out code blocks
3. No hardcoded sensitive data
4. All strings properly quoted
5. Consistent indentation (2 spaces)
6. No trailing whitespace

---

## Testing Checklist

### Pre-Commit Testing
- [ ] `npm start` - Dev server runs without errors
- [ ] `npm run build` - Production build succeeds
- [ ] All 25 slides render correctly
- [ ] Dark mode toggle works
- [ ] Navigation (prev/next) works
- [ ] Sidebar expand/collapse works
- [ ] No console errors
- [ ] No browser warnings

### Cross-Browser Testing
- [ ] Chrome/Edge (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest) - if on Mac

### Responsive Testing
- [ ] Desktop (1920×1080)
- [ ] Tablet (768×1024)
- [ ] Mobile (375×667)

### Accessibility Testing
- [ ] Tab navigation works
- [ ] ARIA labels present
- [ ] Focus indicators visible
- [ ] Color contrast WCAG AA

---

## Development Tips

### 1. Use React DevTools
```bash
# Install Chrome extension
# https://chrome.google.com/webstore/detail/react-developer-tools/
```

### 2. Enable Source Maps
```javascript
// Already enabled in Create React App
// View original source in browser DevTools
```

### 3. Quick Debugging
```javascript
// Temporary debugging (remove before commit)
console.log('Current section:', currentSection);
console.log('Sections data:', sections);
```

### 4. Hot Reload Not Working?
```bash
# Restart dev server
Ctrl+C
npm start
```

### 5. Fast Iteration
```javascript
// Edit content → Save → See changes instantly
// No need to rebuild for dev changes
```

### 6. Validate SKUs
```javascript
// Before committing, grep for placeholder SKUs
grep -r "IC12920\|IC12922\|SCH6000" src/
// Should return no results
```

---

## Common Development Tasks

### Add New Section
```javascript
// 1. Add to sections array
{
  title: "New Section",
  icon: Briefcase,
  color: "text-purple-700",
  slides: [
    {
      title: "First Slide",
      subtitle: "Subtitle",
      content: ( <div>Content</div> )
    }
  ]
}

// 2. Update CONTENT_GUIDE.md with new section
// 3. Test navigation
// 4. Commit
```

### Update Branding Colors
```javascript
// 1. Edit tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        'ifs': {
          purple: '#6f2c91',
          'purple-light': '#8a3db8',
          'purple-dark': '#5a2375',
        },
      }
    }
  }
}

// 2. Rebuild
npm run build
```

### Add External Dependency
```bash
# Install package
npm install package-name

# Update package.json is automatic

# Commit package.json and package-lock.json
git add package.json package-lock.json
git commit -m "chore(deps): Add package-name for X feature"
```

---

**Last Updated:** 2025-11-11
**Version:** 2.0
