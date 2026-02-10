# 📊 Test Coverage Reports Guide

## Overview

Your CppUTest Generator now includes **comprehensive code coverage** reporting with:

✅ **LCOV Coverage Data** - Industry-standard coverage format
✅ **Branch Coverage** - Track which code paths are tested
✅ **HTML Coverage Reports** - Visual coverage reports
✅ **JUnit XML** - Test results in standard XML format

---

## What's Included

### 1. LCOV Coverage (`.info` file)
- **Format**: LCOV tracefile format
- **Contains**: Line coverage and branch coverage data
- **Use For**: CI/CD pipelines, SonarQube, Codecov, Coveralls
- **Branch Coverage**: Enabled by default

### 2. HTML Coverage Report
- **Format**: Interactive HTML pages
- **Contains**: Line-by-line coverage visualization
- **Highlights**: Covered/uncovered lines with colors
- **Branch Info**: Shows which branches were taken

### 3. JUnit XML Report
- **Format**: JUnit XML format
- **Contains**: Test results (pass/fail, assertions)
- **Use For**: Jenkins, GitLab CI, GitHub Actions, Azure DevOps

---

## How It Works

### Automatic Coverage Generation

When you run tests, the system automatically:

1. ✅ Compiles code with coverage flags (`--coverage`)
2. ✅ Runs tests and collects coverage data
3. ✅ Generates LCOV coverage file (`coverage.info`)
4. ✅ Creates HTML coverage report (`coverage_html/`)
5. ✅ Exports JUnit XML (`test-results.xml`)

### Coverage Flags Used

```makefile
CXXFLAGS += --coverage -fprofile-arcs -ftest-coverage
CFLAGS += --coverage -fprofile-arcs -ftest-coverage
LDFLAGS += --coverage
```

---

## Accessing Coverage Reports

### From the Generate Page

After running tests, you'll see these buttons:

```
┌────────────────────────────────────────────────┐
│ [View Report] [View Coverage] [LCOV] [JUnit XML] [Test Report]
└────────────────────────────────────────────────┘
```

**Button Actions:**

1. **View Report** - Opens test results HTML
2. **View Coverage** - Opens HTML coverage report in new tab
3. **LCOV** - Downloads `coverage-{dir}.info` file
4. **JUnit XML** - Downloads `junit-{dir}.xml` file
5. **Test Report** - Downloads test results HTML

---

## Report Locations

### On Disk

All reports are saved in your test directory:

```
generated_tests/tests_YYYYMMDD_HHMMSS/
├── Test_*.cpp                  # Generated test files
├── AllTests.cpp                # Test runner
├── Makefile                    # Build file with coverage
├── run_tests                   # Compiled test binary
├── test-report.html            # Test results (visual)
├── coverage.info               # LCOV coverage data
├── test-results.xml            # JUnit XML results
└── coverage_html/              # HTML coverage report
    ├── index.html              # Main coverage page
    ├── *.gcov.html             # Per-file coverage
    └── *.css, *.js             # Styling files
```

### Via API Endpoints

**View HTML Coverage:**
```
GET /api/coverage-html/{test_directory}/index.html
```

**Download LCOV:**
```
GET /api/coverage-lcov/{test_directory}
```

**Download JUnit XML:**
```
GET /api/junit-xml/{test_directory}
```

---

## Understanding Coverage Reports

### HTML Coverage Report

The HTML report shows:

- **Line Coverage**: Percentage of lines executed
- **Function Coverage**: Percentage of functions called
- **Branch Coverage**: Percentage of branches taken
- **Color Coding**:
  - 🟩 Green = Covered
  - 🟥 Red = Not covered
  - 🟨 Yellow = Partially covered

**Example:**
```
File: calculator.c
Lines: 85.7% (12/14)
Functions: 100% (3/3)
Branches: 75.0% (6/8)
```

### LCOV File Format

```
SF:calculator.c
FN:5,add
FN:10,multiply
FNDA:2,add
FNDA:1,multiply
FNH:2
DA:6,2
DA:11,1
LH:2
LF:2
BRDA:6,0,0,1
BRDA:6,0,1,1
BRH:2
BRF:2
end_of_record
```

### JUnit XML Format

```xml
<?xml version="1.0" encoding="UTF-8"?>
<testsuites tests="4" failures="0" time="0.002">
  <testsuite name="AllTests" tests="4" failures="0">
    <testcase name="test_add_positive" time="0.001"/>
    <testcase name="test_multiply_positive" time="0.001"/>
  </testsuite>
</testsuites>
```

---

## Using Coverage Reports

### CI/CD Integration

#### GitLab CI Example

```yaml
test:
  script:
    - make coverage
  artifacts:
    reports:
      junit: test-results.xml
      coverage_report:
        coverage_format: cobertura
        path: coverage.info
```

#### GitHub Actions Example

```yaml
- name: Run Tests with Coverage
  run: make coverage

- name: Upload Coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    files: ./coverage.info
    flags: unittests

- name: Publish Test Results
  uses: EnricoMi/publish-unit-test-result-action@v2
  with:
    junit_files: test-results.xml
```

### SonarQube Integration

```properties
sonar.cfamily.gcov.reportsPath=.
sonar.junit.reportPaths=test-results.xml
```

---

## Manual Coverage Generation

If you want to generate coverage manually:

```bash
# Navigate to test directory
cd generated_tests/tests_YYYYMMDD_HHMMSS/

# Build and run tests with coverage
make coverage

# Coverage files are created:
# - coverage.info
# - coverage_html/index.html
# - test-results.xml
```

---

## Makefile Targets

The generated Makefile includes these targets:

```makefile
make all        # Build test binary
make test       # Run tests with JUnit XML output
make coverage   # Run tests + generate all coverage reports
make clean      # Remove all build artifacts and coverage files
```

---

## Coverage Metrics

### Line Coverage
- **What**: Percentage of source code lines executed
- **Formula**: (Executed Lines / Total Lines) × 100
- **Good Target**: > 80%

### Function Coverage
- **What**: Percentage of functions called
- **Formula**: (Called Functions / Total Functions) × 100
- **Good Target**: > 90%

### Branch Coverage
- **What**: Percentage of decision branches taken
- **Formula**: (Taken Branches / Total Branches) × 100
- **Good Target**: > 75%
- **Includes**: if/else, switch, loops, ternary operators

---

## Troubleshooting

### "Coverage buttons not showing"

**Cause**: Coverage reports weren't generated

**Solutions**:
1. Check Docker is running
2. Verify lcov is installed in test-runner container
3. Check test execution logs for errors

### "LCOV file empty or missing"

**Cause**: Tests didn't run successfully

**Solutions**:
1. Check build output for compilation errors
2. Ensure tests actually ran (check test output)
3. Verify gcov generated `.gcda` and `.gcno` files

### "HTML coverage report 404"

**Cause**: `genhtml` failed to generate HTML

**Solutions**:
1. Check coverage.info exists and is not empty
2. Verify genhtml is installed: `genhtml --version`
3. Check test directory permissions

### "JUnit XML not generated"

**Cause**: CppUTest JUnit output failed

**Solutions**:
1. Check CppUTest version supports `-ojunit`
2. Verify write permissions in test directory
3. Check test execution logs

---

## Best Practices

### 1. Review Coverage After Each Test Run
- Check HTML report for uncovered lines
- Focus on critical code paths first
- Aim for high branch coverage

### 2. Use Coverage in Code Reviews
- Download LCOV and JUnit XML
- Share coverage trends with team
- Track coverage over time

### 3. Set Coverage Thresholds
- Block merges if coverage drops
- Set minimum coverage % in CI
- Monitor coverage trends

### 4. Focus on Quality, Not Just %
- 100% coverage ≠ bug-free code
- Cover edge cases and error paths
- Test meaningful scenarios

---

## Example Workflow

### Step 1: Generate and Run Tests

```
1. Go to Generate page
2. Select project
3. Click "Generate CppUTest Cases"
4. Click "Build & Run Tests"
```

### Step 2: View Coverage

```
1. Click "View Coverage" button
2. See coverage summary
3. Click file names to see line-by-line coverage
4. Identify uncovered code
```

### Step 3: Download for CI/CD

```
1. Click "LCOV" to download coverage.info
2. Click "JUnit XML" to download test results
3. Upload to your CI/CD pipeline
4. Configure coverage thresholds
```

---

## Quick Reference

### File Extensions
- `.info` - LCOV coverage data
- `.xml` - JUnit test results
- `.gcda` - GCC coverage runtime data
- `.gcno` - GCC coverage compile-time data
- `.gcov` - GCC coverage text format

### Important Flags
- `--coverage` - Enable coverage (equivalent to `-fprofile-arcs -ftest-coverage`)
- `-fprofile-arcs` - Generate arc profiling data
- `-ftest-coverage` - Generate coverage notes files
- `--rc lcov_branch_coverage=1` - Enable branch coverage in LCOV

### LCOV Commands
```bash
# Capture coverage
lcov --capture --directory . --output-file coverage.info

# Remove system headers
lcov --remove coverage.info '/usr/*' --output-file coverage.info

# Generate HTML
genhtml coverage.info --output-directory coverage_html --branch-coverage
```

---

## Summary

✅ **Automatic**: Coverage generated on every test run
✅ **Complete**: LCOV, HTML, and JUnit XML formats
✅ **Branch Coverage**: Tracks all code paths
✅ **CI/CD Ready**: Standard formats for all tools
✅ **Visual**: HTML reports with color-coded coverage
✅ **Accessible**: View in browser or download files

**Your tests now include enterprise-grade coverage reporting!** 🎉
