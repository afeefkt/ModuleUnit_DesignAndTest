#!/bin/bash
# test-ci-local.sh - Run CI tests locally before pushing
# Simulates GitLab CI pipeline

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  CppUTest Generator - CI Test Suite   ║${NC}"
echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo ""

FAILED_TESTS=()
PASSED_TESTS=()

# Helper function to run test
run_test() {
    local test_name=$1
    local test_command=$2
    
    echo -e "\n${YELLOW}▶ Running: $test_name${NC}"
    echo "────────────────────────────────────────"
    
    if eval "$test_command"; then
        echo -e "${GREEN}✓ PASSED: $test_name${NC}"
        PASSED_TESTS+=("$test_name")
        return 0
    else
        echo -e "${RED}✗ FAILED: $test_name${NC}"
        FAILED_TESTS+=("$test_name")
        return 1
    fi
}

# TEST 1: Validate Docker Compose
run_test "Validate Docker Compose" "docker compose config > /dev/null 2>&1"

# TEST 2: Build Docker Image
run_test "Build Docker Image" "docker build -t cpputest-generator:test . > /tmp/build.log 2>&1"

# TEST 3: Python Import Test
run_test "Python Import Test" "docker run --rm cpputest-generator:test python -c 'import main; from fastapi import FastAPI; import faiss; import numpy'"

# TEST 4: Check Required Files
run_test "Check Required Files" "test -f main.py && test -f requirements.txt && test -f Dockerfile && test -f docker-compose.yml"

# TEST 5: Code Syntax Check
run_test "Python Syntax Check" "python3 -m py_compile main.py"

# TEST 6: Start Services
echo -e "\n${YELLOW}▶ Starting services for integration test...${NC}"
echo "────────────────────────────────────────"
docker compose down -v > /dev/null 2>&1 || true
docker compose up -d

# Wait for services
echo "Waiting for services to start..."
sleep 15

# TEST 7: Health Check
run_test "Health Check" "curl -sf http://localhost:8000/health > /dev/null"

# TEST 8: Create test project
echo -e "\n${YELLOW}▶ Creating test project...${NC}"
mkdir -p c_projects/ci_test
cat > c_projects/ci_test/test.c << 'EOF'
int add(int a, int b) {
    return a + b;
}

int multiply(int x, int y) {
    return x * y;
}

int subtract(int a, int b) {
    return a - b;
}
EOF

# TEST 9: Analysis Test
run_test "Project Analysis" "curl -sf 'http://localhost:8000/analyze-project?project_path=/app/c_projects/ci_test' | jq -e '.total_functions == 3'"

# TEST 10: API Response Format
run_test "API Response Format" "curl -sf http://localhost:8000/health | jq -e '.status == \"healthy\"'"

# Cleanup
echo -e "\n${YELLOW}▶ Cleaning up...${NC}"
docker compose down -v > /dev/null 2>&1
rm -rf c_projects/ci_test

# Summary
echo ""
echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           Test Results Summary          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

echo -e "${GREEN}Passed Tests: ${#PASSED_TESTS[@]}${NC}"
for test in "${PASSED_TESTS[@]}"; do
    echo -e "  ${GREEN}✓${NC} $test"
done

if [ ${#FAILED_TESTS[@]} -gt 0 ]; then
    echo ""
    echo -e "${RED}Failed Tests: ${#FAILED_TESTS[@]}${NC}"
    for test in "${FAILED_TESTS[@]}"; do
        echo -e "  ${RED}✗${NC} $test"
    done
    echo ""
    echo -e "${RED}╔════════════════════════════════════════╗${NC}"
    echo -e "${RED}║      CI Tests FAILED - Fix Issues      ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════╝${NC}"
    exit 1
else
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║     All CI Tests PASSED! 🎉            ║${NC}"
    echo -e "${GREEN}║     Safe to commit and push            ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    exit 0
fi