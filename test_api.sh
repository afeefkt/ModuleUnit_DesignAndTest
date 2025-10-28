#!/bin/bash

echo "🧪 Testing CppUTest Generator API"
echo "=================================="

BASE_URL="http://localhost:8000"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test 1: Health Check
echo -e "\n${YELLOW}1. Health Check${NC}"
HEALTH=$(curl -s "$BASE_URL/health")
if echo "$HEALTH" | grep -q "healthy"; then
    echo -e "${GREEN}✓ Service is healthy${NC}"
    echo "$HEALTH" | python3 -m json.tool 2>/dev/null
else
    echo -e "${RED}✗ Service unhealthy${NC}"
    echo "$HEALTH"
fi

# Test 2: List Projects
echo -e "\n${YELLOW}2. List Available Projects${NC}"
PROJECTS=$(curl -s "$BASE_URL/debug/list-projects")
if echo "$PROJECTS" | grep -q "c_project_dir"; then
    echo -e "${GREEN}✓ Projects listed${NC}"
    echo "$PROJECTS" | python3 -m json.tool 2>/dev/null
else
    echo -e "${RED}✗ Failed to list projects${NC}"
    echo "$PROJECTS"
fi

# Test 3: Analyze example_math project
echo -e "\n${YELLOW}3. Analyze example_math Project${NC}"
PROJECT_PATH="/app/c_projects/example_math"
echo "Path: $PROJECT_PATH"
ANALYSIS=$(curl -s "$BASE_URL/analyze-project?project_path=$(echo $PROJECT_PATH | sed 's/ /%20/g')")
if echo "$ANALYSIS" | grep -q "total_functions"; then
    echo -e "${GREEN}✓ Analysis successful${NC}"
    echo "$ANALYSIS" | python3 -m json.tool 2>/dev/null | head -30
    
    # Extract function count
    FUNC_COUNT=$(echo "$ANALYSIS" | grep -o '"total_functions":[0-9]*' | cut -d: -f2)
    echo -e "\n${GREEN}Found $FUNC_COUNT functions${NC}"
else
    echo -e "${RED}✗ Analysis failed${NC}"
    echo "$ANALYSIS"
fi

# Test 4: Generate tests for one function
echo -e "\n${YELLOW}4. Generate Test for 'add' Function${NC}"
echo "This will take 30-60 seconds..."
GENERATE=$(curl -s -X POST "$BASE_URL/generate-tests" \
    -H "Content-Type: application/json" \
    -d "{
        \"project_path\": \"$PROJECT_PATH\",
        \"function_name\": \"add\",
        \"generate_all\": false
    }")

if echo "$GENERATE" | grep -q "tests_generated"; then
    echo -e "${GREEN}✓ Test generation successful${NC}"
    echo "$GENERATE" | python3 -m json.tool 2>/dev/null
    
    # Extract output directory
    OUTPUT_DIR=$(echo "$GENERATE" | grep -o '"output_directory":"[^"]*"' | cut -d'"' -f4)
    echo -e "\n${GREEN}Output: $OUTPUT_DIR${NC}"
    
    # List generated files
    if [ -n "$OUTPUT_DIR" ]; then
        echo -e "\n${YELLOW}Generated files:${NC}"
        docker exec cpputest-generator ls -la "$OUTPUT_DIR" 2>/dev/null || ls -la "$OUTPUT_DIR" 2>/dev/null
    fi
else
    echo -e "${RED}✗ Test generation failed${NC}"
    echo "$GENERATE"
fi

echo -e "\n${GREEN}=================================="
echo "Testing Complete!"
echo -e "==================================${NC}"