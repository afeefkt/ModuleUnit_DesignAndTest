# 🛠️ CppUTest RAG Generator - Scripts Reference

This document lists all available utility scripts and their usage.

---

## 📋 Quick Reference

**Only 2 scripts needed!**

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `setup.sh` | Initial project setup | **Once** - First time only |
| `manage.sh` | All operations (start/stop/test/cleanup/logs) | **Daily** - Everything else |

---

## 🎯 The Two Scripts Explained

### `manage.sh` - **Your Main Tool** 🔧

One unified script that does **everything**:

```bash
./manage.sh start      # Start all services
./manage.sh stop       # Stop all services
./manage.sh restart    # Restart everything
./manage.sh status     # Check health of all services
./manage.sh test       # Test API endpoints
./manage.sh cleanup    # Remove old files
./manage.sh logs       # View all logs
./manage.sh logs backend   # View specific service logs
./manage.sh help       # Show help
```

**Available commands:**
- `start` - Start Docker services and wait for health checks
- `stop` - Stop all services gracefully
- `restart` - Stop and start (useful after code changes)
- `status` - Show running containers and health status
- `test` - Run API endpoint tests
- `cleanup` - Clean old test directories, Python cache, backups
- `logs [service]` - View logs (optionally for specific service)
- `help` - Show detailed help

---

## 🚀 Getting Started Scripts

### `setup.sh` - Initial Setup (Run Once)
**Purpose:** Complete one-time setup for the project

**What it does:**
- Detects GPU (NVIDIA) and configures Ollama accordingly
- Pulls required LLM models (CodeLlama, all-minilm)
- Creates necessary directories
- Starts all Docker services
- Runs initial health checks

**Usage:**
```bash
./setup.sh
```

**Run this:** Once when you first clone the project

---

## 🎯 Common Workflows

### First Time Setup
```bash
# 1. Clone the repository
git clone <repo-url>
cd cpputest_rag

# 2. Run initial setup (ONCE)
./setup.sh

# 3. Open browser to http://localhost:3000
```

### Daily Development
```bash
# Morning - Start services
./manage.sh start

# Check everything is running
./manage.sh status

# Work on code...

# Test changes
./manage.sh test

# View logs if needed
./manage.sh logs backend

# Evening - Stop services
./manage.sh stop
```

### After Code Changes
```bash
# Restart to apply changes
./manage.sh restart

# Or rebuild specific service
docker-compose up -d --build backend
```

### Weekly Maintenance
```bash
# Clean old files
./manage.sh cleanup

# Verify everything still works
./manage.sh start
./manage.sh test
```

---

## 📦 Docker Commands

If you prefer using Docker Compose directly:

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild after code changes
docker-compose up -d --build

# View running containers
docker-compose ps
```

---

## 🆘 Troubleshooting

### Services won't start
```bash
# Check if ports are in use
netstat -ano | findstr :3000
netstat -ano | findstr :8000
netstat -ano | findstr :11434

# Force restart
docker-compose down
docker-compose up -d --build
```

### Tests failing
```bash
# Check backend logs
docker-compose logs backend

# Restart services
./Stop.sh
./start.sh
```

### Disk space issues
```bash
# Run cleanup
./cleanup.sh

# Clean Docker (removes unused images/containers)
docker system prune -a
```

---

## 📝 Notes

- All scripts are designed to be run from the project root directory
- Scripts will create necessary directories if they don't exist
- Most scripts show colored output for better readability
- Check script exit codes: `0` = success, non-zero = error

---

## 🔗 Related Documentation

- [README.md](README.md) - Project overview and architecture
- [GITLAB_CI.md](GITLAB_CI.md) - CI/CD pipeline documentation
- [backend/README.md](backend/README.md) - Backend API documentation (if exists)
- [frontend/README.md](frontend/README.md) - Frontend documentation (if exists)
