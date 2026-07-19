#!/bin/bash
# manage.sh - Unified management script for CppUTest RAG Generator
# Usage: ./manage.sh [command]
# Commands: start, stop, restart, status, test, cleanup, logs, help

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="CppUTest RAG Generator"
BACKEND_URL="http://localhost:8000"
FRONTEND_URL="http://localhost:3000"
OLLAMA_URL="http://localhost:11434"

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=0

    echo -n "Waiting for $service_name to be ready..."

    while [ $attempt -lt $max_attempts ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            echo ""
            print_success "$service_name is ready"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done

    echo ""
    print_error "$service_name failed to start after ${max_attempts} attempts"
    return 1
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi

    if ! docker ps &> /dev/null; then
        print_error "Docker is not running"
        exit 1
    fi
}

# ============================================================================
# Command Functions
# ============================================================================

cmd_start() {
    print_header "Starting $PROJECT_NAME"

    check_docker

    echo "Starting Docker services..."
    docker-compose up -d

    echo ""
    print_info "Waiting for services to become healthy..."

    # Wait for backend
    if wait_for_service "$BACKEND_URL/health" "Backend API"; then
        :
    else
        print_warning "Backend might not be fully ready, check logs with: ./manage.sh logs backend"
    fi

    # Wait for frontend
    if wait_for_service "$FRONTEND_URL" "Frontend"; then
        :
    else
        print_warning "Frontend might not be fully ready, check logs with: ./manage.sh logs frontend"
    fi

    echo ""
    print_header "Services Status"
    docker-compose ps

    echo ""
    print_success "All services started!"
    echo ""
    echo "Access the application:"
    echo "  • Frontend:  ${CYAN}$FRONTEND_URL${NC}"
    echo "  • Backend:   ${CYAN}$BACKEND_URL${NC}"
    echo "  • API Docs:  ${CYAN}$BACKEND_URL/docs${NC}"
    echo ""
    echo "Useful commands:"
    echo "  • View logs:    ${CYAN}./manage.sh logs${NC}"
    echo "  • Stop:         ${CYAN}./manage.sh stop${NC}"
    echo "  • Check status: ${CYAN}./manage.sh status${NC}"
}

cmd_stop() {
    print_header "Stopping $PROJECT_NAME"

    check_docker

    docker-compose down

    print_success "All services stopped"
}

cmd_restart() {
    print_header "Restarting $PROJECT_NAME"

    cmd_stop
    echo ""
    cmd_start
}

cmd_status() {
    print_header "Service Status"

    check_docker

    echo "Docker Containers:"
    docker-compose ps

    echo ""
    echo "Health Checks:"

    # Check backend
    echo -n "  Backend API:   "
    if curl -sf "$BACKEND_URL/health" > /dev/null 2>&1; then
        response=$(curl -s "$BACKEND_URL/health" | python -m json.tool 2>/dev/null || echo "{}")
        print_success "Running - $BACKEND_URL"
        if command -v python &> /dev/null; then
            echo "     $(curl -s "$BACKEND_URL/health" | python -m json.tool | grep -E 'status|model|examples_count' | head -3)"
        fi
    else
        print_error "Not responding"
    fi

    # Check frontend
    echo -n "  Frontend:      "
    if curl -sf "$FRONTEND_URL" > /dev/null 2>&1; then
        print_success "Running - $FRONTEND_URL"
    else
        print_error "Not responding"
    fi

    # Check Ollama
    echo -n "  Ollama:        "
    if curl -sf "$OLLAMA_URL" > /dev/null 2>&1; then
        print_success "Running - $OLLAMA_URL"
    else
        print_error "Not responding"
    fi
}

cmd_test() {
    print_header "Testing API Endpoints"

    # Check if backend is running
    if ! curl -sf "$BACKEND_URL/health" > /dev/null 2>&1; then
        print_error "Backend is not running. Start it with: ./manage.sh start"
        exit 1
    fi

    echo ""
    echo "1. Health Check"
    echo "   GET $BACKEND_URL/health"
    response=$(curl -s "$BACKEND_URL/health")
    echo "   Response: $response"
    if echo "$response" | grep -q "healthy"; then
        print_success "Health check passed"
    else
        print_error "Health check failed"
    fi

    echo ""
    echo "2. List Projects"
    echo "   GET $BACKEND_URL/list-projects"
    response=$(curl -s "$BACKEND_URL/list-projects")
    project_count=$(echo "$response" | python -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    echo "   Found: $project_count projects"
    print_success "List projects passed"

    echo ""
    echo "3. Test calculator project analysis"
    if [ -d "c_projects/calculator" ]; then
        echo "   GET $BACKEND_URL/analyze-project?project_path=c_projects/calculator"
        response=$(curl -s "$BACKEND_URL/analyze-project?project_path=c_projects/calculator")
        func_count=$(echo "$response" | python -c "import sys, json; print(json.load(sys.stdin)['total_functions'])" 2>/dev/null || echo "0")
        echo "   Found: $func_count functions"
        print_success "Analysis passed"
    else
        print_warning "Calculator project not found, skipping"
    fi

    echo ""
    print_success "All API tests passed!"
}

cmd_cleanup() {
    print_header "Project Cleanup"

    echo "This will:"
    echo "  • Remove old test directories (keep 3 most recent)"
    echo "  • Clean Python cache files"
    echo "  • Remove backup files"
    echo ""
    read -p "Continue? (y/N): " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Cleanup cancelled"
        return
    fi

    removed=0

    # Clean old test directories
    echo ""
    echo "Cleaning old test directories..."
    cd generated_tests || exit 1
    dirs_to_keep=3
    total_dirs=$(find . -maxdepth 1 -type d -name "tests_*" | wc -l)

    if [ "$total_dirs" -gt "$dirs_to_keep" ]; then
        find . -maxdepth 1 -type d -name "tests_*" -printf '%T+ %p\n' | sort | head -n -$dirs_to_keep | while read -r line; do
            dir=$(echo "$line" | awk '{print $2}')
            echo "  Removing: $dir"
            rm -rf "$dir"
            ((removed++))
        done
        print_success "Cleaned old test directories"
    else
        print_info "Only $total_dirs test directories found, no cleanup needed"
    fi
    cd ..

    # Clean Python cache
    echo ""
    echo "Cleaning Python cache..."
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
    find . -type f -name "*.pyc" -delete 2>/dev/null
    find . -type f -name "*.pyo" -delete 2>/dev/null
    print_success "Cleaned Python cache"

    # Clean backup files
    echo ""
    echo "Cleaning backup files..."
    find . -maxdepth 1 -name "*.backup" -o -name "*.bak" 2>/dev/null | while read -r file; do
        if [ -f "$file" ]; then
            echo "  Removing: $file"
            rm -f "$file"
            ((removed++))
        fi
    done
    print_success "Cleaned backup files"

    # Docker cleanup (optional)
    echo ""
    read -p "Clean Docker images and cache? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker system prune -f
        print_success "Docker cache cleaned"
    fi

    echo ""
    print_success "Cleanup complete!"
}

cmd_logs() {
    check_docker

    local service=$1

    if [ -z "$service" ]; then
        print_header "Logs for All Services"
        docker-compose logs --tail=50 -f
    else
        print_header "Logs for $service"
        docker-compose logs --tail=50 -f "$service"
    fi
}

cmd_help() {
    cat << EOF
${BLUE}$PROJECT_NAME - Management Script${NC}

${YELLOW}USAGE:${NC}
    ./manage.sh [command] [options]

${YELLOW}COMMANDS:${NC}
    ${CYAN}start${NC}           Start all services
    ${CYAN}stop${NC}            Stop all services
    ${CYAN}restart${NC}         Restart all services
    ${CYAN}status${NC}          Check service status and health
    ${CYAN}test${NC}            Test API endpoints
    ${CYAN}cleanup${NC}         Clean old files and directories
    ${CYAN}logs [service]${NC}  View logs (backend, frontend, ollama, or all)
    ${CYAN}help${NC}            Show this help message

${YELLOW}EXAMPLES:${NC}
    ./manage.sh start              # Start all services
    ./manage.sh status             # Check if services are running
    ./manage.sh logs backend       # View backend logs
    ./manage.sh test               # Test the API
    ./manage.sh cleanup            # Clean old files
    ./manage.sh stop               # Stop everything

${YELLOW}URLS:${NC}
    Frontend:   ${CYAN}$FRONTEND_URL${NC}
    Backend:    ${CYAN}$BACKEND_URL${NC}
    API Docs:   ${CYAN}$BACKEND_URL/docs${NC}

${YELLOW}FIRST TIME SETUP:${NC}
    Run './setup.sh' for initial installation and configuration
    Then use './manage.sh start' for daily usage

${YELLOW}TROUBLESHOOTING:${NC}
    • Services won't start:     ./manage.sh logs
    • API not responding:       ./manage.sh status
    • Need fresh start:         ./manage.sh restart
    • Disk space issues:        ./manage.sh cleanup

EOF
}

# ============================================================================
# Main Script
# ============================================================================

main() {
    local command=${1:-help}

    case $command in
        start)
            cmd_start
            ;;
        stop)
            cmd_stop
            ;;
        restart)
            cmd_restart
            ;;
        status)
            cmd_status
            ;;
        test)
            cmd_test
            ;;
        cleanup)
            cmd_cleanup
            ;;
        logs)
            cmd_logs "$2"
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            print_error "Unknown command: $command"
            echo ""
            cmd_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
