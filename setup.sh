#!/bin/bash
# setup.sh - Complete setup and start for CppUTest Generator
# Run this ONCE for initial setup, then use docker-compose commands

echo "🚀 CppUTest Generator - Initial Setup"
echo "======================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ========== GPU Detection ==========
echo -e "\n${BLUE}1. Detecting GPU...${NC}"

GPU_DETECTED=false
if command -v nvidia-smi &> /dev/null; then
    if nvidia-smi &> /dev/null 2>&1; then
        echo -e "${GREEN}✓ GPU detected — enabling GPU acceleration${NC}"
        nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader | head -1
        
        export OLLAMA_GPU_LAYERS=35
        export OLLAMA_FLASH_ATTENTION=true
        export OLLAMA_GPU_OVERHEAD=1000
        GPU_DETECTED=true
    else
        echo -e "${YELLOW}⚠ nvidia-smi found but GPU not accessible${NC}"
    fi
else
    echo -e "${YELLOW}⚠ No GPU detected — running in CPU mode${NC}"
fi

if [ "$GPU_DETECTED" = false ]; then
    export OLLAMA_GPU_LAYERS=0
    export OLLAMA_FLASH_ATTENTION=false
    export OLLAMA_GPU_OVERHEAD=0
fi

# ========== Create Directories ==========
echo -e "\n${BLUE}2. Creating directories...${NC}"
mkdir -p c_projects test_examples generated_tests logs
echo -e "${GREEN}✓ Directories created${NC}"

# ========== Create .env File ==========
echo -e "\n${BLUE}3. Creating configuration...${NC}"

if [ -f .env ]; then
    echo -e "${YELLOW}⚠ .env already exists - updating GPU settings only${NC}"
    # Update GPU settings in existing .env
    if grep -q "OLLAMA_GPU_LAYERS" .env; then
        sed -i.bak "s/^OLLAMA_GPU_LAYERS=.*/OLLAMA_GPU_LAYERS=${OLLAMA_GPU_LAYERS}/" .env
    else
        echo "OLLAMA_GPU_LAYERS=${OLLAMA_GPU_LAYERS}" >> .env
    fi
    if grep -q "OLLAMA_FLASH_ATTENTION" .env; then
        sed -i.bak "s/^OLLAMA_FLASH_ATTENTION=.*/OLLAMA_FLASH_ATTENTION=${OLLAMA_FLASH_ATTENTION}/" .env
    else
        echo "OLLAMA_FLASH_ATTENTION=${OLLAMA_FLASH_ATTENTION}" >> .env
    fi
    rm -f .env.bak
else
    cat > .env << EOF
# Ollama Configuration
OLLAMA_URL=http://ollama:11434/api
EMBED_MODEL=all-minilm:latest
GEN_MODEL=codellama:latest

# GPU Configuration (auto-detected)
OLLAMA_GPU_LAYERS=${OLLAMA_GPU_LAYERS}
OLLAMA_FLASH_ATTENTION=${OLLAMA_FLASH_ATTENTION}
OLLAMA_GPU_OVERHEAD=${OLLAMA_GPU_OVERHEAD:-0}

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
fi

echo -e "${GREEN}   GPU Settings: OLLAMA_GPU_LAYERS=${OLLAMA_GPU_LAYERS}${NC}"

# ========== Create Example Project ==========
echo -e "\n${BLUE}4. Creating example C project...${NC}"

if [ ! -d "c_projects/example_math" ]; then
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

    echo -e "${GREEN}✓ Example project created: c_projects/example_math/${NC}"
else
    echo -e "${YELLOW}⚠ Example project already exists${NC}"
fi

# ========== Start Services ==========
echo -e "\n${BLUE}5. Starting Docker services...${NC}"
docker-compose up -d

echo -e "\n${YELLOW}Waiting for services to initialize...${NC}"
sleep 8

# ========== Check Ollama ==========
echo -e "\n${BLUE}6. Checking Ollama...${NC}"
if docker exec ollama ollama list 2>/dev/null; then
    echo -e "${GREEN}✓ Ollama is running${NC}"
    
    # Verify GPU inside container
    if [ "$GPU_DETECTED" = true ]; then
        if docker exec ollama nvidia-smi &> /dev/null; then
            echo -e "${GREEN}✓ GPU accessible in container${NC}"
        else
            echo -e "${YELLOW}⚠ GPU not accessible in container${NC}"
            echo -e "${YELLOW}  Install NVIDIA Container Toolkit: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html${NC}"
            GPU_DETECTED=false
        fi
    fi
    
    # Check/pull models
    echo -e "\n${YELLOW}Checking models...${NC}"
    if docker exec ollama ollama list | grep -q "codellama"; then
        echo -e "${GREEN}✓ codellama model ready${NC}"
    else
        echo -e "${YELLOW}⚠ Pulling codellama model (this takes 5-10 minutes)...${NC}"
        docker exec ollama ollama pull codellama:latest
    fi
    
    if docker exec ollama ollama list | grep -q "all-minilm"; then
        echo -e "${GREEN}✓ all-minilm model ready${NC}"
    else
        echo -e "${YELLOW}⚠ Pulling all-minilm model...${NC}"
        docker exec ollama ollama pull all-minilm:latest
    fi
else
    echo -e "${RED}✗ Ollama not responding${NC}"
    echo -e "${YELLOW}Check logs: docker-compose logs ollama${NC}"
    exit 1
fi

# ========== Check CppUTest Generator ==========
echo -e "\n${BLUE}7. Checking CppUTest Generator...${NC}"
MAX_ATTEMPTS=30
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ CppUTest Generator is running${NC}"
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    echo -n "."
    sleep 2
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo -e "\n${RED}✗ CppUTest Generator failed to start${NC}"
    echo -e "${YELLOW}Check logs: docker-compose logs cpputest-generator${NC}"
    exit 1
fi

# ========== Summary ==========
echo -e "\n${GREEN}========================================"
echo "✅ Setup Complete!"
echo -e "========================================${NC}"

echo -e "\n${BLUE}Hardware Configuration:${NC}"
if [ "$GPU_DETECTED" = true ]; then
    echo -e "${GREEN}Running with GPU acceleration ⚡${NC}"
    echo "  • Per function: ~30-60 seconds"
    echo "  • 10 functions: ~5-10 minutes"
    echo "  • 100 functions: ~1-2 hours"
else
    echo -e "${YELLOW}Running in CPU mode 🐌${NC}"
    echo "  • Per function: ~5-10 minutes"
    echo "  • 10 functions: ~1-2 hours"
    echo "  • 100 functions: ~8-16 hours"
fi

echo -e "\n${BLUE}Next Steps:${NC}"
echo "1. Open web UI:     ${GREEN}http://localhost:8000${NC}"
echo "2. Try example:     ${GREEN}/app/c_projects/example_math${NC}"
echo "3. Add your project to: ${GREEN}./c_projects/your_project${NC}"

echo -e "\n${BLUE}Useful Commands:${NC}"
echo "  Start:       ${GREEN}docker-compose up -d${NC}"
echo "  Stop:        ${GREEN}docker-compose down${NC}"
echo "  Logs:        ${GREEN}docker-compose logs -f${NC}"
echo "  Restart:     ${GREEN}docker-compose restart${NC}"
if [ "$GPU_DETECTED" = true ]; then
echo "  GPU Monitor: ${GREEN}watch -n 1 nvidia-smi${NC}"
fi

echo ""#!/bin/bash

echo "🚀 CppUTest Generator Setup Script"
echo "===================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ========== GPU Detection ==========
echo -e "\n${BLUE}Detecting GPU...${NC}"

GPU_DETECTED=false
if command -v nvidia-smi &> /dev/null; then
    if nvidia-smi &> /dev/null 2>&1; then
        echo -e "${GREEN}✓ GPU detected — enabling GPU acceleration${NC}"
        nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader | head -1
        
        export OLLAMA_GPU_LAYERS=35
        export OLLAMA_FLASH_ATTENTION=true
        export OLLAMA_GPU_OVERHEAD=1000
        GPU_DETECTED=true
        
        # Update .env file with GPU settings
        if [ -f .env ]; then
            sed -i.bak 's/^OLLAMA_GPU_LAYERS=.*/OLLAMA_GPU_LAYERS=35/' .env 2>/dev/null || true
            sed -i.bak 's/^OLLAMA_FLASH_ATTENTION=.*/OLLAMA_FLASH_ATTENTION=true/' .env 2>/dev/null || true
        fi
    else
        echo -e "${YELLOW}⚠ nvidia-smi found but GPU not accessible${NC}"
    fi
else
    echo -e "${YELLOW}⚠ No GPU detected — running in CPU mode${NC}"
fi

if [ "$GPU_DETECTED" = false ]; then
    export OLLAMA_GPU_LAYERS=0
    export OLLAMA_FLASH_ATTENTION=false
    export OLLAMA_GPU_OVERHEAD=0
    
    # Update .env file with CPU settings
    if [ -f .env ]; then
        sed -i.bak 's/^OLLAMA_GPU_LAYERS=.*/OLLAMA_GPU_LAYERS=0/' .env 2>/dev/null || true
        sed -i.bak 's/^OLLAMA_FLASH_ATTENTION=.*/OLLAMA_FLASH_ATTENTION=false/' .env 2>/dev/null || true
    fi
fi

# Create directories
echo -e "\n${YELLOW}Creating directories...${NC}"
mkdir -p c_projects test_examples generated_tests logs

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    cat > .env << EOF
# Ollama Configuration
OLLAMA_URL=http://ollama:11434/api
EMBED_MODEL=all-minilm:latest
GEN_MODEL=codellama:latest

# GPU Configuration (auto-detected)
OLLAMA_GPU_LAYERS=${OLLAMA_GPU_LAYERS}
OLLAMA_FLASH_ATTENTION=${OLLAMA_FLASH_ATTENTION}
OLLAMA_GPU_OVERHEAD=${OLLAMA_GPU_OVERHEAD:-0}

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
    echo -e "${GREEN}✓ .env created with GPU settings: OLLAMA_GPU_LAYERS=${OLLAMA_GPU_LAYERS}${NC}"
else
    echo -e "${GREEN}✓ .env already exists (GPU settings updated)${NC}"
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
    
    # Verify GPU inside container (if GPU detected on host)
    if [ "$GPU_DETECTED" = true ]; then
        echo -e "\n${BLUE}Verifying GPU access in Ollama container...${NC}"
        if docker exec ollama nvidia-smi &> /dev/null; then
            echo -e "${GREEN}✓ GPU is accessible inside Ollama container${NC}"
        else
            echo -e "${YELLOW}⚠ GPU not accessible in container - may need NVIDIA Container Toolkit${NC}"
            echo -e "${YELLOW}  Install: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html${NC}"
        fi
    fi
    
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
    echo -e "${YELLOW}⚠ Debug endpoint not available (using older version)${NC}"
fi

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"

# Performance info
echo -e "\n${BLUE}Performance Expectations:${NC}"
if [ "$GPU_DETECTED" = true ]; then
    echo -e "${GREEN}Running with GPU acceleration ⚡${NC}"
    echo "  • Per function: ~30-60 seconds"
    echo "  • 10 functions: ~5-10 minutes"
    echo "  • 100 functions: ~1-2 hours"
else
    echo -e "${YELLOW}Running in CPU mode 🐌${NC}"
    echo "  • Per function: ~5-10 minutes"
    echo "  • 10 functions: ~1-2 hours"
    echo "  • 100 functions: ~8-16 hours"
    echo -e "\n${YELLOW}Tip: For better performance, consider using a GPU${NC}"
fi

echo -e "\n${YELLOW}Next Steps:${NC}"
echo "1. Open browser: http://localhost:8000"
echo "2. Analyze project: /app/c_projects/example_math"
echo "3. Generate tests"
echo ""
echo -e "${YELLOW}Useful Commands:${NC}"
echo "  View logs:           docker-compose logs -f"
echo "  Check status:        curl http://localhost:8000/health"
if [ "$GPU_DETECTED" = true ]; then
echo "  Monitor GPU:         watch -n 1 nvidia-smi"
fi
echo "  Restart services:    docker-compose restart"
echo "  Stop services:       docker-compose down"
echo ""

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