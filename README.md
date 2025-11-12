# CppUTest Generator with RAG

Automatic CppUTest case generation for C projects using CodeLlama and RAG (Retrieval Augmented Generation).

## Features

- 🔍 **Automatic C Code Analysis** - Parses C projects and extracts function signatures
- 🧪 **Smart Test Generation** - Uses CodeLlama to generate CppUTest cases
- 📚 **Example-Based Learning** - Learns from your existing test patterns via RAG
- 🚀 **Batch Processing** - Handles large projects with hundreds of functions
- ⚡ **GPU Acceleration** - Auto-detects and uses NVIDIA GPU when available
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
│  (Regex-based)  │      │  (Your patterns) │
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

### For GPU Acceleration (Recommended)
- Docker and Docker Compose
- NVIDIA GPU (GTX 1060 or better recommended)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- At least 8GB GPU RAM for CodeLlama
- 20GB disk space for models

### For CPU-Only (Slower but Works)
- Docker and Docker Compose
- At least 16GB RAM (32GB recommended)
- 20GB disk space for models
- **Note:** CPU inference is 10-30x slower than GPU

### Test Your GPU Setup (Optional)
```bash
# Check if GPU is available
nvidia-smi

# Test NVIDIA Container Toolkit
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

## Quick Start

### One-Command Setup (Recommended)

```bash
# Clone the repository
git clone <your-repo>
cd cpputest-generator

# Run setup (auto-detects GPU, creates example project, starts services)
chmod +x setup.sh
./setup.sh
```

The `setup.sh` script will:
- ✅ Auto-detect if GPU is available
- ✅ Configure .env with optimal settings
- ✅ Create example C project
- ✅ Pull required models automatically
- ✅ Start all services
- ✅ Verify everything works

### Manual Setup (If Preferred)

```bash
# 1. Create environment file
cp .env.example .env

# 2. Edit .env if needed (GPU settings auto-detected)
nano .env

# 3. Create directories
mkdir -p c_projects test_examples generated_tests logs

# 4. Start services
docker-compose up -d

# 5. Pull models
docker exec ollama ollama pull codellama:latest
docker exec ollama ollama pull all-minilm:latest
```

## Usage

### Via Web Interface (Easiest)

1. **Open Browser**: http://localhost:8000

2. **Analyze Your Project**:
   - Enter project path: `/app/c_projects/example_math`
   - Click "Analyze Project"
   - Review detected functions

3. **Generate Tests**:
   - Path auto-fills after analysis
   - Leave function name empty for all functions, or specify one
   - Click "Generate CppUTest Cases"
   - Wait for generation (time depends on GPU/CPU)

4. **Review Generated Tests**:
   - Tests saved in `generated_tests/tests_TIMESTAMP/`
   - Each function gets: `Test_<function_name>.cpp`
   - Makefile included for building

### Via API

#### Health Check
```bash
curl http://localhost:8000/health
```

#### Analyze Project
```bash
curl "http://localhost:8000/analyze-project?project_path=/app/c_projects/example_math" | jq
```

#### Generate Tests for All Functions
```bash
curl -X POST http://localhost:8000/generate-tests \
  -H "Content-Type: application/json" \
  -d '{
    "project_path": "/app/c_projects/example_math",
    "generate_all": true
  }' | jq
```

#### Generate Test for Specific Function
```bash
curl -X POST http://localhost:8000/generate-tests \
  -H "Content-Type: application/json" \
  -d '{
    "project_path": "/app/c_projects/example_math",
    "function_name": "add",
    "generate_all": false
  }' | jq
```

## Adding Your C Project

```bash
# Copy your project to c_projects directory
cp -r /path/to/your/project ./c_projects/my_project

# Project structure example:
c_projects/my_project/
├── src/
│   ├── main.c
│   ├── utils.c
│   └── utils.h
└── include/
    └── config.h

# Then analyze via web UI or API
```

## Building and Running Generated Tests

```bash
# Navigate to generated tests directory
cd generated_tests/tests_20251028_153000/

# Install CppUTest (if not already installed)
# Ubuntu/Debian:
sudo apt-get install cpputest

# macOS:
brew install cpputest

# Build tests
make

# Run tests
./run_tests

# Or run with verbose output
./run_tests -v
```

## Example Generated Test

For this C function:
```c
int add(int a, int b) {
    return a + b;
}
```

The system generates:
```cpp
// Auto-generated CppUTest for function: add
// Source: /app/c_projects/example_math/math_utils.c:4
// Generated: 2025-10-28T15:30:00

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
    int result = add(5, 3);
    CHECK_EQUAL(8, result);
}

TEST(AddFunctionTests, AddNegativeNumbers)
{
    int result = add(-5, -3);
    CHECK_EQUAL(-8, result);
}

TEST(AddFunctionTests, AddZero)
{
    int result = add(0, 5);
    CHECK_EQUAL(5, result);
}

TEST(AddFunctionTests, AddMixedSignNumbers)
{
    int result = add(10, -5);
    CHECK_EQUAL(5, result);
}
```

## Performance

### With GPU (NVIDIA GTX 1060 or better)
- **Per function**: ~30-60 seconds
- **10 functions**: ~5-15 minutes
- **50 functions**: ~30-60 minutes
- **100 functions**: ~1-2 hours

### CPU-Only Mode
- **Per function**: ~5-10 minutes
- **10 functions**: ~1-2 hours
- **50 functions**: ~4-8 hours
- **100 functions**: ~12-24 hours

**Recommendation:** For projects with 50+ functions, GPU acceleration is highly recommended.

## Configuration

### Environment Variables (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://ollama:11434/api` | Ollama API endpoint |
| `EMBED_MODEL` | `all-minilm:latest` | Embedding model for RAG |
| `GEN_MODEL` | `codellama:latest` | Code generation model |
| `C_PROJECT_DIR` | `/app/c_projects` | C projects directory |
| `TEST_EXAMPLES_DIR` | `/app/test_examples` | Test examples directory |
| `OUTPUT_DIR` | `/app/generated_tests` | Output directory |
| `TOP_K` | `3` | Number of example tests to retrieve |
| `REQUEST_TIMEOUT` | `180` | Timeout for LLM requests (seconds) |
| `OLLAMA_GPU_LAYERS` | `35` (GPU) / `0` (CPU) | GPU layers (auto-detected) |

### Speed Optimization

**For CPU mode (slower):**
```env
GEN_MODEL=codellama:7b        # Use smaller/faster model
BATCH_SIZE=1                   # Process one at a time
REQUEST_TIMEOUT=600            # Increase timeout
```

**For GPU mode (better quality):**
```env
GEN_MODEL=codellama:13b        # Larger model, better tests
BATCH_SIZE=5                   # Process multiple functions
OLLAMA_GPU_LAYERS=35           # More GPU layers
```

## Improving Test Quality

### Add Example Tests

The more example tests you provide, the better the generated tests:

```bash
# Add your existing CppUTest files to test_examples/
cp my_existing_tests/*.cpp test_examples/

# Rebuild the RAG index
curl -X POST http://localhost:8000/rebuild-examples-index
```

### Example Test Structure

```
test_examples/
├── example_simple_function.cpp    # Auto-created
├── example_string_function.cpp     # Auto-created
├── my_embedded_tests.cpp           # Your examples
├── my_algorithm_tests.cpp          # Your examples
└── my_error_handling_tests.cpp     # Your examples
```

## Common Commands

```bash
# Start services
./start.sh
# or
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f cpputest-generator
docker-compose logs -f ollama

# Restart services
docker-compose restart

# Check status
curl http://localhost:8000/health

# Monitor GPU usage (if available)
watch -n 1 nvidia-smi

# Rebuild with new code
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Project Structure

```
.
├── docker-compose.yml      # Docker orchestration (CPU + GPU auto-detect)
├── docker-compose.gpu.yml  # Explicit GPU version (optional)
├── Dockerfile             # Application container
├── requirements.txt       # Python dependencies
├── main.py               # FastAPI application
├── .env                  # Configuration (auto-generated)
├── setup.sh              # Initial setup script
├── start.sh              # Quick start script
├── wait_for_service.sh   # Health check helper
├── c_projects/           # Your C projects
│   ├── example_math/     # Auto-created example
│   └── my_project/       # Your projects
├── test_examples/        # Reference test patterns
│   ├── example_simple_function.cpp
│   └── example_string_function.cpp
├── generated_tests/      # Output directory
│   └── tests_20251028_153000/
│       ├── Test_add.cpp
│       ├── Test_multiply.cpp
│       └── Makefile
└── logs/                 # Application logs
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs cpputest-generator --tail=50

# Check if ports are in use
lsof -i :8000
lsof -i :11434

# Restart everything
docker-compose down
docker-compose up -d
```

### Models Not Downloaded

```bash
# Check models
docker exec ollama ollama list

# Pull manually
docker exec ollama ollama pull codellama:latest
docker exec ollama ollama pull all-minilm:latest
```

### GPU Not Being Used

```bash
# Check GPU detection
nvidia-smi

# Check if GPU accessible in container
docker exec ollama nvidia-smi

# Verify .env settings
cat .env | grep OLLAMA_GPU
```

### Generation Takes Too Long

- Increase `REQUEST_TIMEOUT` in .env
- Use smaller model: `GEN_MODEL=codellama:7b`
- Generate one function at a time instead of all
- Consider GPU if using CPU

### Poor Test Quality

1. Add more example tests in `test_examples/`
2. Rebuild the index: `POST /rebuild-examples-index`
3. Use larger model: `GEN_MODEL=codellama:13b`
4. Increase `TOP_K` to retrieve more examples

### "No functions found in project"

- Verify C files have function definitions with `{` braces
- Check file paths are correct (use absolute: `/app/c_projects/...`)
- Test parsing: `curl "http://localhost:8000/debug/test-parse?file_path=/app/c_projects/my_project/file.c"`
- Ensure functions aren't just prototypes (need full implementation)

## Advanced Usage

### Custom Test Templates

Create specialized test templates for your domain:

```cpp
// test_examples/embedded_system_test.cpp
#include "CppUTest/TestHarness.h"
#include "CppUTestExt/MockSupport.h"

TEST_GROUP(HardwareTests)
{
    void setup() {
        mock().clear();
        // Initialize hardware mocks
    }
    
    void teardown() {
        mock().checkExpectations();
        mock().clear();
    }
};

// Your test patterns...
```

### Batch Processing Script

```bash
#!/bin/bash
# generate_all.sh

PROJECTS=(
    "/app/c_projects/project1"
    "/app/c_projects/project2"
    "/app/c_projects/project3"
)

for project in "${PROJECTS[@]}"; do
    echo "Processing $project..."
    curl -X POST http://localhost:8000/generate-tests \
      -H "Content-Type: application/json" \
      -d "{\"project_path\": \"$project\", \"generate_all\": true}"
done
```

## Contributing

Contributions welcome! Areas to improve:
- Better C/C++ parsing (integration with clang)
- Support for C++ projects
- More test example templates
- Better error handling in generated tests
- Integration with CI/CD pipelines

## License

MIT License

## Support

- **Documentation**: This README
- **Logs**: `docker-compose logs -f`
- **Health Check**: http://localhost:8000/health
- **Example Project**: `/app/c_projects/example_math`

For issues:
1. Check logs: `docker-compose logs`
2. Verify GPU: `nvidia-smi` (if applicable)
3. Test with example project first
4. Check `.env` configuration

---

**Made with ❤️ for automated testing**

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

### For GPU Acceleration (Recommended)
- Docker and Docker Compose
- NVIDIA GPU (GTX 1060 or better recommended)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- At least 8GB GPU RAM for CodeLlama
- 20GB disk space for models

### For CPU-Only (Slower but Works)
- Docker and Docker Compose
- At least 16GB RAM (32GB recommended)
- 20GB disk space for models
- **Note:** CPU inference is 10-30x slower than GPU

### Test Your GPU Setup
```bash
# Check if GPU is available
nvidia-smi

# Test NVIDIA Container Toolkit
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

## Quick Start

### Option 1: Auto-detect GPU (Recommended)

```bash
# Make scripts executable
chmod +x setup.sh start.sh wait_for_service.sh

# Run auto-setup
./start.sh
```

The `start.sh` script will:
- Auto-detect if GPU is available
- Use GPU acceleration if available, otherwise CPU
- Pull required models automatically
- Wait for services to be ready

### Option 2: Manual Start

#### With GPU:
```bash
# Use GPU compose file
docker-compose -f docker-compose.gpu.yml up -d

# Pull models
docker exec ollama ollama pull codellama:latest
docker exec ollama ollama pull all-minilm:latest
```

#### Without GPU (CPU only):
```bash
# Use default compose file (CPU mode)
docker-compose up -d

# Pull models
docker exec ollama ollama pull codellama:latest
docker exec ollama ollama pull all-minilm:latest
```

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

### With GPU (NVIDIA GTX 1060 or better)
- **Small Projects** (10-50 functions): ~5-15 minutes
- **Medium Projects** (50-200 functions): ~30-60 minutes
- **Large Projects** (200+ functions): ~2-4 hours
- **Per function**: ~30-60 seconds

### CPU-Only Mode
- **Small Projects** (10-50 functions): ~1-3 hours
- **Medium Projects** (50-200 functions): ~4-8 hours
- **Large Projects** (200+ functions): ~12-24 hours
- **Per function**: ~5-10 minutes

**Recommendation:** For projects with 50+ functions, GPU acceleration is highly recommended.

### Speed Optimization Tips

**For CPU mode:**
```env
# In .env file
GEN_MODEL=codellama:7b        # Use smaller model
BATCH_SIZE=1                   # Process one at a time
REQUEST_TIMEOUT=600            # Increase timeout
```

**For GPU mode:**
```env
GEN_MODEL=codellama:13b        # Use larger model for better quality
BATCH_SIZE=5
OLLAMA_GPU_LAYERS=35           # Load more layers on GPU
```

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