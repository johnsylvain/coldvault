#!/bin/bash
# ColdVault Development Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
PYTHON="${VENV_DIR}/bin/python"
PIP="${VENV_DIR}/bin/pip"

# Detect OS
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    PYTHON="${VENV_DIR}/Scripts/python.exe"
    PIP="${VENV_DIR}/Scripts/pip.exe"
    ACTIVATE="${VENV_DIR}/Scripts/activate"
else
    ACTIVATE="${VENV_DIR}/bin/activate"
fi

function print_info() {
    echo -e "${GREEN}ℹ${NC} $1"
}

function print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

function print_error() {
    echo -e "${RED}✗${NC} $1"
}

function check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install Python 3.11 or higher."
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    REQUIRED_VERSION="3.11"
    
    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
        print_error "Python 3.11 or higher is required. Found: $PYTHON_VERSION"
        exit 1
    fi
    
    # Warn about Python 3.14+ which may have compatibility issues
    if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 14 ]; then
        print_warning "Python 3.14+ detected. Some packages may not have pre-built wheels."
        print_warning "Consider using Python 3.11-3.13 for better compatibility."
        print_warning "If you encounter build errors, install Rust: brew install rust"
    fi
    
    print_info "Python version: $(python3 --version)"
}

function setup_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        print_info "Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
        print_info "Virtual environment created"
    else
        print_info "Virtual environment already exists"
    fi
}

function install_dependencies() {
    print_info "Installing dependencies..."
    "$PIP" install --upgrade pip
    
    # Check if Rust is needed (for Python 3.14+)
    PYTHON_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
    if [ "$PYTHON_MINOR" -ge 14 ]; then
        if ! command -v rustc &> /dev/null && ! command -v cargo &> /dev/null; then
            print_warning "Python 3.14+ detected. Some packages may need Rust to build."
            print_warning "If installation fails, install Rust:"
            if [[ "$OSTYPE" == "darwin"* ]]; then
                print_warning "  brew install rust"
            else
                print_warning "  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
            fi
        fi
    fi
    
    # Try to install dependencies
    if ! "$PIP" install -r requirements.txt; then
        print_error "Failed to install some dependencies."
        print_info "This might be due to missing build tools."
        print_info "For Python 3.14+, you may need Rust: brew install rust"
        print_info "Or consider using Python 3.11-3.13 for better compatibility."
        exit 1
    fi
    
    # Try to install PostgreSQL driver (optional, for PostgreSQL support)
    print_info "Checking for PostgreSQL support..."
    if command -v pg_config &> /dev/null || brew list postgresql@15 &> /dev/null 2>&1 || brew list postgresql &> /dev/null 2>&1; then
        print_info "PostgreSQL found, installing psycopg2-binary..."
        "$PIP" install psycopg2-binary || print_warning "Failed to install psycopg2-binary (PostgreSQL support will be limited)"
    else
        print_warning "PostgreSQL not found. SQLite will be used by default."
        print_info "To use PostgreSQL, install it via: brew install postgresql"
        print_info "Or install psycopg2-binary manually: pip install psycopg2-binary"
    fi
    
    print_info "Dependencies installed"
}

function create_directories() {
    print_info "Creating necessary directories..."
    mkdir -p config cache data/db
    chmod 755 config cache data/db 2>/dev/null || true
    print_info "Directories created"
}

function check_env() {
    if [ ! -f .env ]; then
        print_warning ".env file not found"
        if [ -f .env.example ]; then
            print_info "Creating .env from .env.example..."
            cp .env.example .env
            print_warning "Please edit .env with your configuration"
        else
            print_error ".env.example not found. Please create a .env file manually."
            exit 1
        fi
    fi
}

function setup() {
    echo "🔒 ColdVault Development Setup"
    echo "=============================="
    echo ""
    
    check_python
    setup_venv
    install_dependencies
    create_directories
    check_env
    
    echo ""
    print_info "Setup complete!"
    echo ""
    echo "Next steps:"
    echo "1. Edit .env file with your configuration"
    echo "2. Run: ./dev.sh run"
    echo ""
}

function run() {
    if [ ! -d "$VENV_DIR" ]; then
        print_warning "Virtual environment not found. Running setup..."
        setup
    fi
    
    print_info "Starting ColdVault development server..."
    echo ""
    
    # Activate virtual environment and run
    source "$ACTIVATE"
    export PYTHONPATH="$PROJECT_DIR"
    
    # Check if .env exists
    if [ -f .env ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi
    
    # Set default database URL if not set
    if [ -z "$DATABASE_URL" ]; then
        export DATABASE_URL="sqlite:///./config/coldvault.db"
    fi
    
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8088
}

function test() {
    if [ ! -d "$VENV_DIR" ]; then
        print_error "Virtual environment not found. Run './dev.sh setup' first."
        exit 1
    fi
    
    print_info "Running tests..."
    source "$ACTIVATE"
    # Add test command here when tests are added
    print_warning "Tests not yet implemented"
}

function lint() {
    if [ ! -d "$VENV_DIR" ]; then
        print_error "Virtual environment not found. Run './dev.sh setup' first."
        exit 1
    fi
    
    print_info "Running linters..."
    source "$ACTIVATE"
    
    # Install linting tools if not present
    "$PIP" install --quiet flake8 black isort mypy 2>/dev/null || true
    
    echo "Running flake8..."
    "$VENV_DIR/bin/flake8" app/ --max-line-length=120 --exclude=venv,__pycache__ || true
    
    echo "Checking code formatting with black..."
    "$VENV_DIR/bin/black" --check app/ || print_warning "Code formatting issues found. Run './dev.sh format' to fix."
}

function format() {
    if [ ! -d "$VENV_DIR" ]; then
        print_error "Virtual environment not found. Run './dev.sh setup' first."
        exit 1
    fi
    
    print_info "Formatting code..."
    source "$ACTIVATE"
    
    # Install formatting tools if not present
    "$PIP" install --quiet black isort 2>/dev/null || true
    
    "$VENV_DIR/bin/black" app/
    "$VENV_DIR/bin/isort" app/
    
    print_info "Code formatted"
}

function clean() {
    print_info "Cleaning up..."
    
    # Remove Python cache
    find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type f -name "*.pyo" -delete 2>/dev/null || true
    
    # Remove test artifacts
    rm -rf .pytest_cache .coverage htmlcov 2>/dev/null || true
    
    print_info "Cleanup complete"
}

function shell() {
    if [ ! -d "$VENV_DIR" ]; then
        print_error "Virtual environment not found. Run './dev.sh setup' first."
        exit 1
    fi
    
    print_info "Starting Python shell with app context..."
    source "$ACTIVATE"
    export PYTHONPATH="$PROJECT_DIR"
    
    if [ -f .env ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi
    
    python3 -i -c "
from app.database import *
from app.config import settings
print('ColdVault development shell')
print('Available: db session, models, settings')
"
}

function help() {
    echo "ColdVault Development Script"
    echo ""
    echo "Usage: ./dev.sh [command]"
    echo ""
    echo "Commands:"
    echo "  setup     - Set up development environment (venv, dependencies, directories)"
    echo "  run       - Run development server"
    echo "  test      - Run tests"
    echo "  lint      - Run linters"
    echo "  format    - Format code with black and isort"
    echo "  clean     - Clean Python cache and test artifacts"
    echo "  shell     - Start Python shell with app context"
    echo "  help      - Show this help message"
    echo ""
}

# Main command dispatcher
case "${1:-help}" in
    setup)
        setup
        ;;
    run)
        run
        ;;
    test)
        test
        ;;
    lint)
        lint
        ;;
    format)
        format
        ;;
    clean)
        clean
        ;;
    shell)
        shell
        ;;
    help|--help|-h)
        help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        help
        exit 1
        ;;
esac
