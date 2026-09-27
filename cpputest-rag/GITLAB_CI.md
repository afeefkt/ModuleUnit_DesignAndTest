# GitLab CI/CD Setup Guide

## 📋 Overview

This project includes GitLab CI/CD pipelines for automated testing and validation.

## 🚀 Quick Start

### 1. Choose Your Pipeline

We provide two pipeline configurations:

#### **Option A: Full Pipeline** (`.gitlab-ci.yml`)
- **Duration**: ~15-20 minutes
- **Tests**: Build, lint, integration, security
- **When to use**: For main branch and important merge requests

#### **Option B: Quick Pipeline** (`.gitlab-ci-quick.yml`)
- **Duration**: ~5 minutes
- **Tests**: Build validation, smoke tests
- **When to use**: For rapid feedback on every commit

### 2. Setup in GitLab

```bash
# For full pipeline
cp .gitlab-ci.yml .gitlab-ci.yml

# For quick pipeline (rename to use it)
mv .gitlab-ci-quick.yml .gitlab-ci.yml
```

### 3. GitLab Runner Configuration

Your GitLab runner needs:
- Docker executor
- At least 4GB RAM
- 10GB disk space

**No GPU required** - CI runs in CPU mode automatically.

## 🧪 Pipeline Stages

### Full Pipeline (`.gitlab-ci.yml`)

```
┌─────────────┐
│   Build     │  Build Docker images
└──────┬──────┘
       │
┌──────▼──────┐
│   Test      │  Lint, compose validation, smoke tests
└──────┬──────┘
       │
┌──────▼──────┐
│ Integration │  Start services, test analysis
└─────────────┘
```

#### Stage 1: Build
- `build:docker` - Build Docker image with current code

#### Stage 2: Test
- `test:lint` - Code quality checks (flake8, black)
- `test:compose` - Validate docker-compose.yml
- `test:smoke` - Quick import and build test
- `security:trivy` - Security vulnerability scan

#### Stage 3: Integration
- `test:integration` - Full service test with analysis
- `test:example` - Generate test for example project (manual)

### Quick Pipeline (`.gitlab-ci-quick.yml`)

```
┌─────────────┐
│  Validate   │  Fast validation tests
└──────┬──────┘
       │
┌──────▼──────┐
│ Quick Test  │  Smoke test with minimal setup
└─────────────┘
```

## 💻 Testing Locally

### Run CI Tests Before Pushing

```bash
# Make executable
chmod +x test-ci-local.sh

# Run all CI tests locally
./test-ci-local.sh
```

This runs all tests that will run in GitLab CI.

### Manual Testing

```bash
# Test 1: Validate compose
docker compose config

# Test 2: Build
docker build -t cpputest-generator:test .

# Test 3: Start services
docker compose up -d

# Test 4: Health check
curl http://localhost:8000/health

# Test 5: Analysis
curl "http://localhost:8000/analyze-project?project_path=/app/c_projects/example_math"

# Cleanup
docker compose down
```

## 📊 Pipeline Configuration

### Environment Variables

The CI pipeline uses these variables (set in `.gitlab-ci.yml`):

```yaml
variables:
  DOCKER_DRIVER: overlay2
  OLLAMA_GPU_LAYERS: "0"           # CPU mode for CI
  OLLAMA_FLASH_ATTENTION: "false"
```

### GitLab CI/CD Variables (Optional)

Set these in GitLab: **Settings → CI/CD → Variables**

| Variable | Description | Required |
|----------|-------------|----------|
| `CI_REGISTRY` | Docker registry URL | No |
| `CI_REGISTRY_USER` | Registry username | No |
| `CI_REGISTRY_PASSWORD` | Registry password | No |

## 🔧 Customization

### Run Tests on Specific Branches

Edit `.gitlab-ci.yml`:

```yaml
only:
  - main
  - develop
  - /^feature\/.*$/  # All feature branches
```

### Adjust Timeouts

```yaml
test:integration:
  timeout: 20m  # Increase if tests are slow
```

### Skip Tests for Specific Commits

```bash
git commit -m "docs: update README [skip ci]"
```

## 📈 Expected Results

### Successful Pipeline

```
✓ build:docker        (2m 30s)
✓ test:lint          (45s)
✓ test:compose       (20s)
✓ test:smoke         (1m 15s)
✓ test:integration   (8m 30s)
```

### Common Failures

| Job | Issue | Solution |
|-----|-------|----------|
| `build:docker` | Out of memory | Increase runner RAM |
| `test:integration` | Timeout | Increase timeout value |
| `test:lint` | Code style | Run `black main.py` |
| `test:integration` | Can't connect | Check Docker networking |

## 🐛 Troubleshooting

### Pipeline Fails on Build

```bash
# Check locally
docker build -t test .

# View build logs in GitLab
# Go to: CI/CD → Pipelines → Click job → View logs
```

### Integration Test Timeout

```bash
# Test locally with same timeout
timeout 10m docker compose up -d
sleep 30
curl http://localhost:8000/health
```

### Service Not Starting

```bash
# Check logs in CI artifacts
# Or run locally
docker compose up -d
docker compose logs cpputest-generator
```

## 📋 CI Artifacts

Artifacts saved by pipeline:

- **Build logs**: `/tmp/build.log`
- **Test results**: JSON format
- **Docker logs**: Service logs on failure

Access artifacts:
1. Go to pipeline page
2. Click on failed job
3. Click "Browse" in right sidebar

## 🔐 Security Scanning

The pipeline includes Trivy security scanning:

```yaml
security:trivy:
  script:
    - trivy image --severity HIGH,CRITICAL cpputest-generator:scan
```

View results in: **Security → Vulnerability Report**

## 🚀 Advanced: Deploy Pipeline

Add deployment stage (optional):

```yaml
stages:
  - build
  - test
  - integration
  - deploy

deploy:production:
  stage: deploy
  script:
    - echo "Deploy to production server"
    - ssh user@server 'cd /app && docker compose pull && docker compose up -d'
  only:
    - main
  when: manual
```

## 📊 Pipeline Badges

Add to your README.md:

```markdown
[![pipeline status](https://gitlab.com/YOUR_USERNAME/YOUR_REPO/badges/main/pipeline.svg)](https://gitlab.com/YOUR_USERNAME/YOUR_REPO/-/commits/main)
```

## ⚡ Performance Tips

### Speed Up Pipeline

1. **Use Quick Pipeline** for feature branches
2. **Cache dependencies**:
   ```yaml
   cache:
     paths:
       - .pip-cache/
   ```
3. **Parallel tests**:
   ```yaml
   test:smoke:
     parallel: 3
   ```

### Reduce Resource Usage

```yaml
# Limit Docker memory
docker run --memory="2g" ...

# Use smaller base images
FROM python:3.11-slim-alpine
```

## 📚 Best Practices

1. ✅ **Run `test-ci-local.sh` before pushing**
2. ✅ **Keep pipeline under 10 minutes** for quick feedback
3. ✅ **Use `only:` to limit pipeline runs**
4. ✅ **Set `allow_failure: true` for non-critical jobs**
5. ✅ **Add meaningful job names**
6. ✅ **Use `when: manual` for expensive tests**

## 🔄 CI/CD Workflow

```
Developer → Commit → Push → GitLab CI
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
                  Build     Test    Integration
                    │         │         │
                    └─────────┴─────────┘
                              │
                         ✓ All Pass
                              │
                    Ready for Merge/Deploy
```

## 📞 Support

If CI pipeline fails:

1. Check job logs in GitLab
2. Run `test-ci-local.sh` to reproduce locally
3. Check Docker and compose versions
4. Verify GitLab runner has enough resources

## 🔗 References

- [GitLab CI/CD Documentation](https://docs.gitlab.com/ee/ci/)
- [Docker-in-Docker](https://docs.gitlab.com/ee/ci/docker/using_docker_build.html)
- [GitLab Runner Configuration](https://docs.gitlab.com/runner/)

---

**Last Updated**: 2025-10-28