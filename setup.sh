#!/bin/bash

echo "🚀 CppUTest Generator Setup Script"
echo "===================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create directories
echo -e "\n${YELLOW}Creating directories...${NC}"
mkdir -p c_projects test_examples generated_tests logs

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    cat > .env << 'EOF'
# Ollama Configuration
OLLAMA_URL=http://ollama:11434/api
EMBED_MODEL=all-minilm:latest
GEN_MODEL=codellama:latest

# Directory Configuration
C_PROJECT_DIR=/app/c_projects
TEST_EXAMPLES_DIR=/app/test_examples
OUTPUT_DIR=/app/generated_tests

# Processing Configuration
MAX_FUNCTIONS_PER_CHUNK=10
TOP_K=3
BATCH_SIZE=5
REQUEST_TIMEOUT=180

# Server Configuration
PORT=8000
HOST=0.0.0.0
LOG_LEVEL=INFO
EOF
    echo -e "${GREEN}✓ .env created${NC}"
else
    echo -e "${GREEN}✓ .env already exists${NC}"
fi

# Create example C project
echo -e "\n${YELLOW}Creating example C project...${NC}"
mkdir -p c_projects/example_math

cat > c_projects/example_math/math_utils.c << 'EOF'
#include "math_utils.h"

// Simple addition function
int add(int a, int b) {
    return a + b;
}

// Simple subtraction function
int subtract(int a, int b) {
    return a - b;
}

// Multiplication function
int multiply(int x, int y) {
    return x * y;
}

// Division function with error checking
int divide(int numerator, int denominator) {
    if (denominator == 0) {
        return -1; // Error: division by zero
    }
    return numerator / denominator;
}

// Factorial function (recursive)
int factorial(int n) {
    if (n < 0) {
        return -1; // Error: negative input
    }
    if (n == 0 || n == 1) {
        return 1;
    }
    return n * factorial(n - 1);
}

// Check if number is even
int is_even(int num) {
    return (num % 2) == 0;
}

// Find maximum of two numbers
int max(int a, int b) {
    return (a > b) ? a : b;
}

// Find minimum of two numbers
int min(int a, int b) {
    return (a < b) ? a : b;
}

// Calculate absolute value
int abs_value(int num) {
    return (num < 0) ? -num : num;
}

// Power function
int power(int base, int exponent) {
    if (exponent == 0) {
        return 1;
    }
    int result = 1;
    for (int i = 0; i < exponent; i++) {
        result *= base;
    }
    return result;
}
EOF

cat > c_projects/example_math/math_utils.h << 'EOF'
#ifndef MATH_UTILS_H
#define MATH_UTILS_H

// Basic arithmetic operations
int add(int a, int b);
int subtract(int a, int b);
int multiply(int x, int y);
int divide(int numerator, int denominator);

// Advanced functions
int factorial(int n);
int is_even(int num);
int max(int a, int b);
int min(int a, int b);
int abs_value(int num);
int power(int base, int exponent);

#endif // MATH_UTILS_H
EOF

echo -e "${GREEN}✓ Example project created in c_projects/example_math/${NC}"

# Start services
echo -e "\n${YELLOW}Starting Docker services...${NC}"
docker-compose up -d

echo -e "\n${YELLOW}Waiting for services to start...${NC}"
sleep 5

# Check if Ollama is running
echo -e "\n${YELLOW}Checking Ollama status...${NC}"
if docker exec ollama ollama list 2>/dev/null; then
    echo -e "${GREEN}✓ Ollama is running${NC}"
    
    # Check if models exist
    if docker exec ollama ollama list | grep -q "codellama"; then
        echo -e "${GREEN}✓ codellama model found${NC}"
    else
        echo -e "${YELLOW}⚠ codellama model not found. Pulling...${NC}"
        echo -e "${YELLOW}This will take several minutes...${NC}"
        docker exec ollama ollama pull codellama:latest
    fi
    
    if docker exec ollama ollama list | grep -q "all-minilm"; then
        echo -e "${GREEN}✓ all-minilm model found${NC}"
    else
        echo -e "${YELLOW}⚠ all-minilm model not found. Pulling...${NC}"
        docker exec ollama ollama pull all-minilm:latest
    fi
else
    echo -e "${RED}✗ Ollama is not responding${NC}"
    echo -e "${YELLOW}Run: docker-compose logs ollama${NC}"
fi

# Check main service
echo -e "\n${YELLOW}Checking CppUTest Generator status...${NC}"
sleep 3
if curl -s http://localhost:8000/health > /dev/null; then
    echo -e "${GREEN}✓ CppUTest Generator is running${NC}"
else
    echo -e "${RED}✗ CppUTest Generator is not responding${NC}"
    echo -e "${YELLOW}Run: docker-compose logs cpputest-generator${NC}"
fi

# Test the debug endpoint
echo -e "\n${YELLOW}Testing debug endpoint...${NC}"
RESULT=$(curl -s http://localhost:8000/debug/list-projects)
if echo "$RESULT" | grep -q "c_project_dir"; then
    echo -e "${GREEN}✓ Debug endpoint working${NC}"
    echo "$RESULT" | python3 -m json.tool 2>/dev/null || echo "$RESULT"
else
    echo -e "${RED}✗ Debug endpoint failed${NC}"
    echo "$RESULT"
fi

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\n${YELLOW}Next Steps:${NC}"
echo "1. Open browser: http://localhost:8000"
echo "2. Analyze project: /app/c_projects/example_math"
echo "3. Generate tests"
echo ""
echo -e "${YELLOW}Useful Commands:${NC}"
echo "  View logs:           docker-compose logs -f"
echo "  Check status:        curl http://localhost:8000/health"
echo "  List projects:       curl http://localhost:8000/debug/list-projects"
echo "  Restart services:    docker-compose restart"
echo "  Stop services:       docker-compose down"
echo ""