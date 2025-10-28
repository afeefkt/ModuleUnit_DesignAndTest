# CppUTest Generator with RAG

Automatic CppUTest case generation for C projects using CodeLlama and RAG (Retrieval Augmented Generation).

## Features

- 🔍 **Automatic C Code Analysis** - Parses C projects and extracts function signatures
- 🧪 **Smart Test Generation** - Uses CodeLlama to generate CppUTest cases
- 📚 **Example-Based Learning** - Learns from your existing test patterns
- 🚀 **Batch Processing** - Handles large projects with hundreds of functions
- 🐳 **Docker Ready** - Full Docker setup with Ollama integration
- 💾 **RAG System** - Retrieves similar test examples for better generation

## Architecture

```
┌─────────────────┐
│  C Project      │
│  (Source Code)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│  Code Parser    │      │  Test Examples   │
│  (pycparser)    │      │  (Your patterns) │
└────────┬────────┘      └────────┬─────────┘
         │                        │
         │                        ▼
         │               ┌─────────────────┐
         │               │  FAISS Index    │
         │               │  (Embeddings)   │
         │               └────────┬────────┘
         │                        │
         ▼                        ▼
┌──────────────────────────────────────┐
│         CodeLlama (Ollama)           │
│     Test Generation with Context      │
└────────────────┬─────────────────────┘
                 │
                 ▼
         ┌───────────────┐
         │  CppUTest     │
         │  Test Cases   │
         └───────────────┘
```

## Prerequisites

- Docker and Docker Compose
- NVIDIA GPU with Docker runtime (for GPU acceleration)
- At least 8GB RAM
- 20GB disk space for models

## Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo>
cd cpputest-generator

# Copy environment template
cp .env.example .env

# Create directory structure
mkdir -p c_projects test_examples generated_tests logs
```

### 2. Add Your C Project

```bash
# Copy your C project to the c_projects directory
cp -r /path/to/your/c/project ./c_projects/my_project
```

### 3. Add Test Examples (Optional but Recommended)

Place your existing CppUTest files in `test_examples/` directory. The system will use these as reference patterns.

Example structure:
```
test_examples/
├── example_math_tests.cpp
├── example_string_tests.cpp
└── example_pointer_tests.cpp
```

### 4. Start the System

```bash
# Pull Ollama models first (this takes time!)
docker-compose up ollama -d

# Wait for Ollama to start, then pull models
docker exec -it ollama ollama pull codellama:latest
docker exec -it ollama ollama pull all-minilm:latest

# Start the full system
docker-compose up -d

# Check logs
docker-compose logs -f cpputest-generator
```

### 5. Access the Web Interface

Open your browser to: **http://localhost:8000**

## Usage

### Via Web Interface

1. **Analyze Project**
   - Enter project path: `/app/c_projects/my_project`
   - Click "Analyze Project"
   - Review detected functions

2. **Generate Tests**
   - Enter project path
   - Optionally specify a single function name
   - Click "Generate CppUTest Cases"
   - Wait for generation (can take several minutes for large projects)

3. **Review Generated Tests**
   - Tests are saved in `generated_tests/tests_TIMESTAMP/`
   - Each function gets its own test file: `Test_<function_name>.cpp`
   - A Makefile is automatically generated

### Via API

#### Analyze Project
```bash
curl "http://localhost:8000/analyze-project?project_path=/app/c_projects/my_project"
```

#### Generate Tests for All Functions
```bash
curl -X POST http://localhost:8000/generate-tests \
  -H "Content-Type: application/json" \
  -d '{
    "project_path": "/app/c_projects/my_project",
    "generate_all": true
  }'
```

#### Generate Test for Specific Function
```bash
curl -X POST http://localhost:8000/generate-tests \
  -H "Content-Type: application/json" \
  -d '{
    "project_path": "/app/c_projects/my_project",
    "function_name": "calculate_sum"
  }'
```

## Building and Running Tests

After generation, navigate to the output directory:

```bash
cd generated_tests/tests_YYYYMMDD_HHMMSS/

# Build tests
make

# Run tests
./run_tests
```

## Example C Project Structure

Create a simple example project:

```bash
mkdir -p c_projects/example_project
```

**c_projects/example_project/math_utils.c:**
```c
#include "math_utils.h"

int add(int a, int b) {
    return a + b;
}

int multiply(int a, int b) {
    return a * b;
}

int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}
```

**c_projects/example_project/math_utils.h:**
```c
#ifndef MATH_UTILS_H
#define MATH_UTILS_H

int add(int a, int b);
int multiply(int a, int b);
int factorial(int n);

#endif
```

## Generated Test Example

The system will generate something like:

```cpp
// Auto-generated CppUTest for function: add
// Source: /app/c_projects/example_project/math_utils.c:3
// Generated: 2025-10-28T10:30:00

#include "CppUTest/TestHarness.h"

TEST_GROUP(AddFunctionTests)
{
    void setup() {
        // Setup before each test
    }
    
    void teardown() {
        // Cleanup after each test
    }
};

TEST(AddFunctionTests, AddPositiveNumbers)
{
    // Test adding two positive numbers
    int result = add(5, 3);
    CHECK_EQUAL(8, result);
}

TEST(AddFunctionTests, AddNegativeNumbers)
{
    // Test adding negative numbers
    int result = add(-5, -3);
    CHECK_EQUAL(-8, result);
}

TEST(AddFunctionTests, AddZero)
{
    // Test adding with zero
    int result = add(0, 5);
    CHECK_EQUAL(5, result);
}

TEST(AddFunctionTests, AddLargeNumbers)
{
    // Test with large numbers
    int result = add(1000000, 2000000);
    CHECK_EQUAL(3000000, result);
}
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://ollama:11434/api` | Ollama API endpoint |
| `EMBED_MODEL` | `all-minilm:latest` | Embedding model for RAG |
| `GEN_MODEL` | `codellama:latest` | Code generation model |
| `C_PROJECT_DIR` | `/app/c_projects` | C projects directory |
| `TEST_EXAMPLES_DIR` | `/app/test_examples` | Test examples directory |
| `OUTPUT_DIR` | `/app/generated_tests` | Output directory for generated tests |
| `TOP_K` | `3` | Number of example tests to retrieve |
| `REQUEST_TIMEOUT` | `180` | Timeout for LLM requests (seconds) |

### Tuning for Large Projects

For projects with 100+ functions:

```env
BATCH_SIZE=3
REQUEST_TIMEOUT=300
MAX_FUNCTIONS_PER_CHUNK=5
```

## Troubleshooting

### Ollama Connection Failed

```bash
# Check if Ollama is running
docker-compose ps

# Check Ollama logs
docker-compose logs ollama

# Test Ollama directly
docker exec -it ollama ollama list
```

### Models Not Downloaded

```bash
# Pull models manually
docker exec -it ollama ollama pull codellama:latest
docker exec -it ollama ollama pull all-minilm:latest

# Verify models
docker exec -it ollama ollama list
```

### Out of Memory

- Reduce `BATCH_SIZE` in .env
- Use smaller model: `GEN_MODEL=codellama:7b`
- Reduce `OLLAMA_GPU_LAYERS`

### Generation Takes Too Long

- Increase `REQUEST_TIMEOUT`
- Generate tests for one function at a time
- Use faster model (7b vs 13b/34b)

### Poor Test Quality

1. Add more example tests in `test_examples/`
2. Rebuild the examples index
3. Use larger CodeLlama model (13b or 34b)
4. Increase `TOP_K` to retrieve more examples

## Project Structure

```
.
├── docker-compose.yml      # Docker orchestration
├── Dockerfile             # Application container
├── requirements.txt       # Python dependencies
├── main.py               # FastAPI application
├── .env                  # Configuration
├── c_projects/           # Your C projects
│   └── my_project/
├── test_examples/        # Reference test patterns
│   ├── example_simple_function.cpp
│   └── example_string_function.cpp
├── generated_tests/      # Output directory
│   └── tests_20251028_103000/
│       ├── Test_add.cpp
│       ├── Test_multiply.cpp
│       └── Makefile
└── logs/                 # Application logs
```

## Advanced Usage

### Custom Test Templates

Create specialized test templates in `test_examples/`:

**test_examples/embedded_system_test.cpp:**
```cpp
// Template for embedded system tests with hardware mocking
#include "CppUTest/TestHarness.h"
#include "CppUTestExt/MockSupport.h"

TEST_GROUP(HardwareTests)
{
    void setup() {
        mock().clear();
        // Initialize mock hardware
    }
    
    void teardown() {
        mock().checkExpectations();
        mock().clear();
    }
};

// Tests with hardware mocking...
```

### API Integration

Build automated workflows:

```bash
#!/bin/bash
# auto_test_gen.sh

PROJECT_PATH="/app/c_projects/my_project"

# Analyze
curl -s "http://localhost:8000/analyze-project?project_path=$PROJECT_PATH" | jq .

# Generate all tests
curl -s -X POST http://localhost:8000/generate-tests \
  -H "Content-Type: application/json" \
  -d "{\"project_path\": \"$PROJECT_PATH\", \"generate_all\": true}" | jq .
```

## Performance

- **Small Projects** (10-50 functions): ~2-5 minutes
- **Medium Projects** (50-200 functions): ~10-30 minutes
- **Large Projects** (200+ functions): ~1-2 hours

*Times vary based on hardware, model size, and complexity*

## Contributing

Contributions welcome! Please:
1. Add more example test templates
2. Improve C parsing logic
3. Add support for C++ projects
4. Enhance test quality heuristics

## License

MIT License

## Support

For issues and questions:
- Check logs: `docker-compose logs -f cpputest-generator`
- Review generated tests manually
- Adjust configuration in .env
- Add more example tests for better results