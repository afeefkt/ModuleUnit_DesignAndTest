# CppUTest Generator with RAG — v2.0

Automatic CppUTest case generation for C projects using CodeLlama and RAG (Retrieval Augmented Generation).

**NEW in v2.0:** Separated frontend, backend API, SQLite persistence, project upload, and generation history!

## Features

- 🔍 **Automatic C Code Analysis** - Parses C projects and extracts function signatures
- 🧪 **Smart Test Generation** - Uses CodeLlama to generate CppUTest cases
- 📚 **Example-Based Learning** - Learns from your existing test patterns via RAG
- 🚀 **Batch Processing** - Handles large projects with hundreds of functions
- ⚡ **GPU Acceleration** - Auto-detects and uses NVIDIA GPU when available
- 🐳 **Docker Ready** - Full Docker setup with Ollama integration
- 💾 **RAG System** - FAISS-based retrieval of similar test examples
- 📤 **Project Upload** - Upload C projects as ZIP files via web UI
- 📊 **Generation History** - SQLite database tracks all test generations
- 🎨 **Modern UI** - Clean HTML + Tailwind CSS interface

## Architecture v2.0

```
┌─────────────────────────────────────────────────┐
│               Frontend (Nginx)                  │
│         http://localhost:3000                   │
│  - Dashboard  - Analyze  - Generate  - History  │
└──────────────────┬──────────────────────────────┘
                   │ (Nginx reverse proxy)
                   ▼
┌─────────────────────────────────────────────────┐
│            Backend (FastAPI)                    │
│         http://localhost:8000/docs              │
│  - REST API  - SQLite  - RAG Engine             │
└──────────────────┬──────────────────────────────┘
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
┌─────────────────┐  ┌─────────────────┐
│  Ollama         │  │  SQLite DB      │
│  (LLM Runtime)  │  │  (History)      │
│  - CodeLlama    │  │  - Projects     │
│  - Embeddings   │  │  - Analyses     │
└─────────────────┘  │  - Generations  │
                     └─────────────────┘
```

### Project Structure

```
cpputest_rag/
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── main.py       # App entry
│   │   ├── config.py     # Configuration
│   │   ├── database.py   # SQLite layer
│   │   ├── models.py     # Pydantic schemas
│   │   ├── api/          # API routes
│   │   │   ├── health.py
│   │   │   ├── analysis.py
│   │   │   ├── generation.py
│   │   │   └── projects.py
│   │   └── services/     # Core logic
│   │       ├── c_parser.py
│   │       ├── rag_engine.py
│   │       └── test_generator.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/             # HTML + Tailwind + Nginx
│   ├── index.html        # Dashboard
│   ├── analyze.html      # Project analysis
│   ├── generate.html     # Test generation
│   ├── history.html      # Generation history
│   ├── js/
│   │   ├── api.js        # API client
│   │   └── *.js          # Page logic
│   ├── nginx.conf
│   └── Dockerfile
│
├── docker-compose.yml    # 3 services
├── .gitlab-ci.yml        # CI/CD pipeline
├── c_projects/           # Input: C projects
├── test_examples/        # RAG training data
├── generated_tests/      # Output: test files
└── data/                 # SQLite database
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
cd cpputest_rag

# Run setup (auto-detects GPU, creates example project, starts services)
chmod +x setup.sh
./setup.sh
```

The `setup.sh` script will:
- ✅ Auto-detect if GPU is available
- ✅ Configure .env with optimal settings
- ✅ Create example C project
- ✅ Pull required models automatically
- ✅ Start all 3 services (backend, frontend, ollama)
- ✅ Verify everything works

### Manual Setup (If Preferred)

```bash
# 1. Create environment file
cp .env.example .env

# 2. Edit .env if needed (GPU settings auto-detected)
nano .env

# 3. Create directories
mkdir -p c_projects test_examples generated_tests data logs

# 4. Start services (backend, frontend, ollama)
docker-compose up -d

# 5. Pull models
docker exec ollama ollama pull codellama:latest
docker exec ollama ollama pull all-minilm:latest

# 6. Wait for services to be ready (check health)
curl http://localhost:8000/health
```

## Usage

### Via Web Interface (Easiest)

1. **Open Dashboard**: http://localhost:3000

2. **Upload a Project** (Option 1):
   - Click "Upload Project"
   - Select a ZIP file containing your C code
   - Project automatically registered

3. **Or Use Existing Projects** (Option 2):
   - Projects in `c_projects/` are auto-detected
   - Example: `c_projects/example_math` is included

4. **Analyze Project**:
   - Go to "Analyze" page
   - Enter project path or select from dropdown
   - Click "Analyze Project"
   - View detected functions with signatures

5. **Generate Tests**:
   - Go to "Generate" page
   - Enter project path (auto-filled from analysis)
   - Optionally specify a single function name
   - Click "Generate CppUTest Cases"
   - Wait for generation (progress shown)

6. **View History**:
   - Go to "History" page
   - See all past test generation runs
   - Timestamps, stats, output directories

7. **Review Generated Tests**:
   - Tests saved in `generated_tests/tests_TIMESTAMP/`
   - Each function gets: `Test_<function_name>.cpp`
   - Makefile included for building

### Via API

The backend API is available at `http://localhost:8000` with interactive docs at `http://localhost:8000/docs`.

#### Health Check
```bash
curl http://localhost:8000/health
```

#### List Projects
```bash
curl http://localhost:8000/projects | jq
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

#### View Generation History
```bash
curl http://localhost:8000/generation-history | jq
```

## Adding Your C Project

### Option 1: Upload via Web UI (Easiest)
1. Create a ZIP file of your C project
2. Go to Dashboard (http://localhost:3000)
3. Click "Upload Project" and select the ZIP
4. Project is extracted to `c_projects/` and registered

### Option 2: Manual Copy
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
cd generated_tests/tests_20260208_153000/

# Install CppUTest (if not already installed)
# Ubuntu/Debian:
sudo apt-get install cpputest

# macOS:
brew install cpputest

# Build tests
make

# Run tests
./run_tests
```

## Improving Test Quality

The RAG system learns from example test files in `test_examples/`. To improve generation:

1. Add your own high-quality test examples:
```bash
cp my_excellent_test.cpp test_examples/
```

2. Rebuild the RAG index:
   - Via Web UI: Go to Generate page → "Rebuild RAG Index"
   - Via API: `curl -X POST http://localhost:8000/rebuild-examples-index`

3. The system will now use your examples as reference patterns

## Services

| Service | Port | Purpose |
|---------|------|---------|
| **Frontend** | 3000 | Web UI (dashboard, analysis, generation, history) |
| **Backend** | 8000 | REST API + RAG engine + SQLite database |
| **Ollama** | 11434 | LLM runtime (CodeLlama + embeddings) |

## Configuration

Edit `.env` to customize:

```bash
# Models
GEN_MODEL=codellama:latest        # Code generation model
EMBED_MODEL=all-minilm:latest     # Embedding model for RAG

# Ports
PORT=8000                          # Backend API port
FRONTEND_PORT=3000                 # Frontend port

# Database
DATABASE_PATH=/app/data/cpputest.db

# Generation
TOP_K=3                            # Number of similar examples to retrieve
REQUEST_TIMEOUT=180                # LLM timeout (seconds)

# Performance
OLLAMA_GPU_LAYERS=20               # GPU layers (0 for CPU-only)
```

## Performance

| Configuration | Functions/Hour | Per Function |
|---------------|----------------|--------------|
| **GPU (RTX 3060+)** | 60-120 | 30-60 sec |
| **GPU (GTX 1060)** | 30-60 | 1-2 min |
| **CPU (16 cores)** | 6-12 | 5-10 min |
| **CPU (8 cores)** | 3-6 | 10-20 min |

## Troubleshooting

### Services Won't Start
```bash
# Check logs
docker-compose logs backend
docker-compose logs frontend
docker-compose logs ollama

# Restart services
docker-compose restart
```

### Frontend Can't Connect to Backend
- Check that backend is healthy: `curl http://localhost:8000/health`
- Check nginx logs: `docker logs cpputest-frontend`
- Verify ports aren't already in use

### No Functions Found
- Ensure C files have valid function definitions
- Check debug endpoint: `curl http://localhost:8000/debug/list-projects`
- Review regex pattern in `backend/app/services/c_parser.py`

### Generation Timeout
- Increase `REQUEST_TIMEOUT` in `.env`
- Use GPU if available (10-30x faster)
- Generate one function at a time for testing

### Out of Memory
- Reduce model size: Use `codellama:7b` instead of `codellama:13b`
- Lower `OLLAMA_GPU_LAYERS` in `.env`
- Close other GPU applications

## CI/CD

The project includes a GitLab CI pipeline (`.gitlab-ci.yml`) with:

**Validation Stage:**
- Backend build test
- Frontend build test
- Python imports test

**Test Stage:**
- Backend health check
- API integration test

All tests run in ~5 minutes without requiring Ollama models.

## Development

### Running Locally Without Docker

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
python -m http.server 3000
# Or use any static file server
```

### Database Schema

The SQLite database (`data/cpputest.db`) has 4 tables:
- `projects` — Registered C projects
- `analyses` — Analysis runs with extracted functions
- `generations` — Test generation runs with stats
- `test_examples` — RAG training examples

View schema: `sqlite3 data/cpputest.db .schema`

## Contributing

Contributions welcome! Areas for improvement:
- Support for additional test frameworks (Google Test, Unity, etc.)
- More sophisticated C parsing (handle macros, complex types)
- Multi-language support (C++, Rust, etc.)
- Test execution + coverage analysis
- LLM fine-tuning on domain-specific test patterns

## License

[Your License Here]

## Credits

- **FastAPI** — Web framework
- **Ollama** — Local LLM runtime
- **CodeLlama** — Meta's code generation model
- **FAISS** — Facebook AI similarity search
- **CppUTest** — C/C++ unit testing framework
- **Tailwind CSS** — UI styling

## Version History

- **v2.0** (2026-02) — Full-stack restructure: separate frontend, backend API, SQLite database, project upload, generation history
- **v1.0** (2025-11) — Initial release: monolithic FastAPI app with embedded HTML, basic RAG

---

**Built with ❤️ for C developers who hate writing tests manually**
