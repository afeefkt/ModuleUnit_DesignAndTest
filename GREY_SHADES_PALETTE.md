# 🎨 Grey Shades Color Palette

## Updated: February 10, 2026

All frontend pages and HTML reports now use **different shades of grey** for professional visual hierarchy.

---

## Frontend Pages Color Palette

### Body & Backgrounds
```css
Body background:          bg-gray-100    (#f3f4f6)  ← Main background
Primary cards:            bg-white       (#ffffff)  ← Important content
Secondary cards:          bg-gray-50     (#f9fafb)  ← Less emphasis
Tertiary sections:        bg-gray-200    (#e5e7eb)  ← Supporting content
```

### Navigation & Headers
```css
Header text (dark):       text-gray-900  (#111827)  ← Titles
Header text (medium):     text-gray-800  (#1f2937)  ← Subtitles
Body text:                text-gray-700  (#374151)  ← Regular text
Secondary text:           text-gray-600  (#4b5563)  ← Descriptions
Muted text:               text-gray-500  (#6b7280)  ← Labels
```

### Buttons & Interactive Elements
```css
Primary button:           bg-gray-800 → hover:bg-gray-900  (#1f2937 → #111827)
Secondary button:         bg-gray-700 → hover:bg-gray-800  (#374151 → #1f2937)
Tertiary button:          bg-gray-600 → hover:bg-gray-700  (#4b5563 → #374151)
Light button:             bg-gray-300 → hover:bg-gray-400  (#d1d5db → #9ca3af)
Subtle button:            bg-gray-200 → hover:bg-gray-300  (#e5e7eb → #d1d5db)
```

### Borders & Dividers
```css
Strong border:            border-gray-400  (#9ca3af)
Medium border:            border-gray-300  (#d1d5db)
Light border:             border-gray-200  (#e5e7eb)
```

### Stat Cards (Different Shades for Hierarchy)
```css
Card 1 (lightest):        bg-gray-200  border-gray-400  (#e5e7eb / #9ca3af)
Card 2 (medium):          bg-gray-300  border-gray-500  (#d1d5db / #6b7280)
Card 3 (darker):          bg-gray-400  border-gray-600  (#9ca3af / #4b5563)
Card 4 (darkest):         bg-gray-500  border-gray-700  (#6b7280 / #374151)
```

---

## HTML Test Reports Color Palette

### Backgrounds
```css
Page background:          #e5e7eb  (medium-light grey)
Container:                #fafafa  (off-white)
Header:                   #374151  (dark grey)
Footer:                   #e5e7eb  (medium-light grey)
```

### Info Cards (3 Different Shades)
```css
Info card 1:              #f3f4f6  border: #d1d5db  ← Lightest
Info card 2:              #e5e7eb  border: #b8bcc3  ← Medium
Info card 3:              #d1d5db  border: #9ca3af  ← Darker
```

### Stat Cards (4 Different Shades)
```css
Stat card 1:              #d1d5db  border: #9ca3af  ← Base shade
Stat card 2:              #e5e7eb  border: #b8bcc3  ← Light (success)
Stat card 3:              #c7cbd1  border: #9ca3af  ← Medium (warning)
Stat card 4:              #9ca3af  border: #6b7280  ← Dark (emphasis)
```

### Text Colors
```css
Primary text:             #1f2937  (dark grey)
Secondary text:           #6b7280  (medium grey)
Section titles:           #374151  (dark grey)
Labels:                   #6b7280  (medium grey)
```

### Borders & Sections
```css
Header border:            #4b5563  (dark grey - 3px solid)
Section borders:          #9ca3af  (medium grey - 3px solid)
Card borders:             #d1d5db  (light grey - 2px solid)
Footer border:            #9ca3af  (medium grey - 2px solid)
```

### Status Colors (Kept for Clarity)
```css
✅ Pass:    #22c55e  (green)  ← Kept for readability
❌ Fail:    #ef4444  (red)    ← Kept for readability
⚠️  Warning: #f59e0b  (orange) ← Kept for readability
```

---

## Visual Hierarchy Strategy

### Level 1 - Most Important
- **bg-white** with **border-gray-300**
- **text-gray-900** for headings
- Used for: Main content cards, headers

### Level 2 - Important
- **bg-gray-50** with **border-gray-200**
- **text-gray-800** for subheadings
- Used for: Navigation, secondary cards

### Level 3 - Supporting
- **bg-gray-200** with **border-gray-400**
- **text-gray-700** for body text
- Used for: Information boxes, stat cards

### Level 4 - Background
- **bg-gray-100**
- **text-gray-600** for labels
- Used for: Page background, muted text

### Level 5 - Subtle
- **bg-gray-300** or darker
- **text-gray-500** for hints
- Used for: Borders, dividers, subtle elements

---

## Benefits of Different Shades

✅ **Clear Visual Hierarchy**
- Different shades guide the eye to important content first
- Users can quickly distinguish between content levels

✅ **Professional Appearance**
- Corporate-friendly grey tones
- Suitable for business environments
- Print-friendly

✅ **Better Readability**
- Contrast between different sections
- Text stands out against backgrounds
- Reduces eye strain

✅ **Depth & Dimension**
- Layered appearance without colors
- Creates visual interest
- Modern, clean design

---

## Page-Specific Implementations

### Dashboard (index.html)
- **Body**: bg-gray-100
- **Header card**: bg-white + border-gray-200
- **Navigation**: bg-gray-50 + border-gray-300
- **Quick action cards**: bg-white, bg-gray-50, bg-gray-200 (3 shades)
- **Buttons**: Different grey shades (gray-700, gray-600, gray-800)

### Analyze (analyze.html)
- **Body**: bg-gray-100
- **Project selection**: bg-gray-50 + border-gray-300
- **Stat cards**: bg-gray-200, bg-gray-300, bg-gray-400 (graduated)
- **File/Function lists**: bg-white + border-gray-300

### Generate (generate.html)
- **Body**: bg-gray-100
- **Form sections**: bg-gray-50 + border-gray-300
- **Info box**: bg-gray-200 + border-gray-400
- **Stat cards**: 4 different shades (gray-200 to gray-500)
- **Code output**: bg-gray-900 (terminal effect)

### Reports (reports.html)
- **Body**: bg-gray-100
- **Navigation**: bg-gray-50 + border-gray-300
- **Report cards**: bg-white with grey borders
- **Stat badges**: Different grey backgrounds

### HTML Test Reports
- **Page background**: #e5e7eb
- **Container**: #fafafa + border #d1d5db
- **Header**: #374151 (dark grey)
- **Multiple info cards**: 3 different grey shades
- **Multiple stat cards**: 4 different grey shades
- **Footer**: #e5e7eb

---

## How to Use This Palette

### When Adding New Components

1. **Choose the hierarchy level** (1-5)
2. **Select appropriate shade** from that level
3. **Add borders** 1-2 shades darker
4. **Use text colors** that contrast well

### Examples

**High-importance card:**
```html
<div class="bg-white border border-gray-300 rounded-lg p-6">
  <h2 class="text-gray-900">Title</h2>
  <p class="text-gray-700">Content</p>
</div>
```

**Medium-importance card:**
```html
<div class="bg-gray-50 border border-gray-300 rounded-lg p-6">
  <h2 class="text-gray-800">Title</h2>
  <p class="text-gray-600">Content</p>
</div>
```

**Low-importance card:**
```html
<div class="bg-gray-200 border border-gray-400 rounded-lg p-4">
  <h3 class="text-gray-700">Label</h3>
  <p class="text-gray-600">Value</p>
</div>
```

---

## Testing Checklist

When Docker is running, verify the new grey shades:

### Dashboard
- [ ] Body has light grey background (not white)
- [ ] Navigation uses different shade than header
- [ ] Three quick action cards use different grey shades
- [ ] Buttons are various shades of grey

### Analyze Page
- [ ] Stat cards use 3 different grey shades
- [ ] Project selector has grey background
- [ ] File/function lists have white backgrounds

### Generate Page
- [ ] Stat cards use 4 graduated grey shades
- [ ] Info box has grey background
- [ ] Success/failure sections maintain contrast

### Reports Page
- [ ] Report cards have white background
- [ ] Navigation bar is light grey
- [ ] Buttons use dark grey

### HTML Reports
- [ ] Page background is medium-light grey
- [ ] Container is off-white (not pure white)
- [ ] Info cards use 3 different shades
- [ ] Stat cards use 4 different shades
- [ ] Header is dark grey (not blue-grey)
- [ ] Footer has grey background

---

## Summary

**Before:** All backgrounds were the same shade (bg-gray-50 / #f5f5f5)
**After:** 5+ different grey shades create visual hierarchy

**Result:**
- More professional appearance
- Better visual organization
- Clearer content hierarchy
- Corporate-friendly design
- Improved user experience

🎉 **All pages now use different shades of grey for optimal visual hierarchy!**
