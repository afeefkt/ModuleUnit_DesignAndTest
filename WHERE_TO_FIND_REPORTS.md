# 📊 WHERE TO FIND YOUR TEST REPORTS

## Quick Answer: 3 Easy Ways

---

## ✅ Method 1: Use the Reports Navigation Link (EASIEST!)

### From ANY Page:

1. **Look at the top navigation bar**
2. **Click on "📊 Reports"**
3. **You'll see ALL your generated reports!**

```
┌─────────────────────────────────────────────────────────┐
│  Dashboard  |  Analyze  |  Generate  |  📊 Reports  |  History  │
└─────────────────────────────────────────────────────────┘
                                         ↑↑↑↑↑↑↑↑↑
                                      CLICK HERE!
```

### What You'll See:

```
📊 Test Reports
View and download HTML test reports generated from test runs

┌─────────────────────────────────────────┐
│ 📄 tests_20260210_143000               │
│ Generated: Feb 10, 2026 14:30          │
│ Report Size: 15.2 KB                    │
│                                         │
│ [View Report]  [Download]              │ ← Click either button!
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ 📄 tests_20260210_142500               │
│ Generated: Feb 10, 2026 14:25          │
│ Report Size: 16.8 KB                    │
│                                         │
│ [View Report]  [Download]              │
└─────────────────────────────────────────┘
```

---

## ✅ Method 2: After Running Tests

### On the Generate Page:

1. **Go to Generate page** (http://localhost:3000/generate.html)
2. **Generate tests** for a project
3. **Click "Build & Run Tests"**
4. **After tests complete, look for these buttons:**

```
┌───────────────────────────────────────────┐
│ ✅ All Tests Passed!                      │
│ Report saved to: tests_20260210_143000/   │
│                                           │
│ [View Report]  [Download Report]         │ ← These appear automatically!
└───────────────────────────────────────────┘
```

**What Each Button Does:**
- **View Report** → Opens report in new browser tab
- **Download Report** → Downloads HTML file to your computer

---

## ✅ Method 3: Find on Disk

### Navigate to This Folder:

```
D:\AI_Learnigns\cpputest_rag\generated_tests\
```

### Inside You'll Find:

```
generated_tests/
├── tests_20260210_143000/
│   ├── Test_add.cpp
│   ├── Makefile
│   └── test-report.html          ← YOUR REPORT!
│
├── tests_20260210_142500/
│   ├── Test_multiply.cpp
│   ├── Makefile
│   └── test-report.html          ← ANOTHER REPORT!
│
└── tests_20260210_141000/
    └── test-report.html          ← MORE REPORTS!
```

**Just double-click** any `test-report.html` file to open it in your browser!

---

## 🎯 Step-by-Step: Complete Flow

### Step 1: Generate Tests
```bash
1. Open browser → http://localhost:3000
2. Click "Generate" in navigation
3. Select a project from dropdown
4. Click "Generate CppUTest Cases"
5. Wait ~7-10 seconds
```

### Step 2: Run Tests
```bash
1. Click "Build & Run Tests"
2. Watch the build output
3. Wait for tests to complete
4. Report is AUTOMATICALLY generated!
```

### Step 3: View Your Report (Choose ONE)

**Option A: Click "View Report" button** (right there on the page!)
- Opens immediately in new tab
- Shows professional HTML report

**Option B: Click "Download Report" button** (next to View Report)
- Downloads as: `cpputest-report-{directory}.html`
- Save to any location
- Open anytime in any browser

**Option C: Click "📊 Reports" in navigation** (at the top!)
- See ALL your past reports
- Click View or Download on any report

**Option D: Open from disk** (if Docker isn't running)
- Navigate to `D:\AI_Learnigns\cpputest_rag\generated_tests\`
- Find your test directory
- Double-click `test-report.html`

---

## 🔍 Visual Navigation Guide

### Where is the Reports Link?

**Dashboard Page:**
```
┌────────────────────────────────────────────────────┐
│ CppUTest Generator                                 │
│                                                    │
│ [Dashboard] [Analyze] [Generate] [📊 Reports] [History]
│                                   ↑↑↑↑↑↑↑↑↑↑↑
│                                  HERE!
└────────────────────────────────────────────────────┘
```

**Analyze Page:**
```
┌────────────────────────────────────────────────────┐
│ CppUTest Generator                                 │
│                          [🏠 Home] [📊 Reports] [📜 History]
│                                    ↑↑↑↑↑↑↑↑↑
│                                   HERE!
└────────────────────────────────────────────────────┘
```

**Generate Page:**
```
┌────────────────────────────────────────────────────┐
│ CppUTest Generator                                 │
│                  [🏠 Home] [🔍 Analyze] [📊 Reports]
│                                        ↑↑↑↑↑↑↑↑↑
│                                       HERE!
└────────────────────────────────────────────────────┘
```

---

## ❓ Troubleshooting

### "I don't see the 📊 Reports link!"

**Solution:**
1. Hard refresh your browser: **Ctrl + Shift + R**
2. Clear cache if needed
3. Restart Docker: `docker-compose restart frontend`

---

### "Reports page is empty!"

**This means:**
- No test reports have been generated yet
- You need to run tests first!

**Solution:**
1. Go to Generate page
2. Select a project
3. Click "Generate CppUTest Cases"
4. Click "Build & Run Tests"
5. Report will auto-generate
6. Now check Reports page again!

---

### "I don't see View/Download buttons after tests!"

**Possible causes:**
1. ❌ Docker not running
2. ❌ Frontend not updated
3. ❌ Browser cache

**Solution:**
```bash
# 1. Restart Docker
docker-compose restart frontend

# 2. Refresh browser (Ctrl + Shift + R)

# 3. Try again
```

---

## 📝 Summary: Where Reports Are

### 🌐 In the Web Interface:
1. **Reports Page** → Click "📊 Reports" in navigation (ALL pages)
2. **Generate Page** → View/Download buttons after test run

### 💾 On Your Computer:
- **Location**: `D:\AI_Learnigns\cpputest_rag\generated_tests\`
- **Filename**: `test-report.html` (inside each test directory)

### ✅ When Reports Are Created:
- **Automatically** after every "Build & Run Tests"
- **Saved** in the test directory
- **Listed** on the Reports page
- **Accessible** via View/Download buttons

---

## 🎉 You Can't Miss Them!

Reports are now accessible from **EVERY PAGE** via the navigation bar!

Just click **"📊 Reports"** at the top of any page! 🎯

---

## Quick Links

When Docker is running:

- **Dashboard**: http://localhost:3000/
- **Generate**: http://localhost:3000/generate.html
- **Reports**: http://localhost:3000/reports.html ← **GO HERE!**

---

**Need help?** Just click "📊 Reports" in the navigation bar at the top! 🚀
