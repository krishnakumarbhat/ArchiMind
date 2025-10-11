#!/bin/bash
# ArchiMind Setup Script
# Automated setup for development and production environments

set -e  # Exit on error

echo "================================================"
echo "  ArchiMind Setup Script"
echo "================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}! $1${NC}"
}

print_step() {
    echo -e "\n${GREEN}==> $1${NC}"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    print_error "Please do not run this script as root"
    exit 1
fi

# Step 1: Check prerequisites
print_step "Checking prerequisites..."

# Check Python version
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_success "Python $PYTHON_VERSION found"
else
    print_error "Python 3.11+ is required but not found"
    exit 1
fi

# Check PostgreSQL
if command -v psql &> /dev/null; then
    print_success "PostgreSQL found"
else
    print_warning "PostgreSQL not found. You'll need to install it manually."
    echo "  Ubuntu/Debian: sudo apt install postgresql postgresql-contrib"
    echo "  macOS: brew install postgresql"
fi

# Check Ollama
if command -v ollama &> /dev/null; then
    print_success "Ollama found"
else
    print_warning "Ollama not found. Install from: https://ollama.ai"
fi

# Step 2: Create virtual environment
print_step "Setting up Python virtual environment..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_success "Virtual environment created"
else
    print_warning "Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate
print_success "Virtual environment activated"

# Step 3: Install dependencies
print_step "Installing Python dependencies..."

pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt
print_success "Dependencies installed"

# Step 4: Setup environment file
print_step "Configuring environment variables..."

if [ ! -f ".env" ]; then
    cp .env.example .env
    print_success "Created .env file from template"
    
    # Generate SECRET_KEY
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/your_secret_key_here/$SECRET_KEY/" .env
    print_success "Generated SECRET_KEY"
    
    print_warning "Please edit .env file and add:"
    echo "  - GEMINI_API_KEY (get from https://makersuite.google.com/app/apikey)"
    echo "  - DATABASE_URL (your PostgreSQL connection string)"
else
    print_warning ".env file already exists"
fi

# Step 5: Setup PostgreSQL database
print_step "Setting up PostgreSQL database..."

read -p "Do you want to create the PostgreSQL database? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter PostgreSQL superuser password: " -s PG_PASSWORD
    echo
    
    read -p "Enter database name [archimind]: " DB_NAME
    DB_NAME=${DB_NAME:-archimind}
    
    read -p "Enter database user [archimind_user]: " DB_USER
    DB_USER=${DB_USER:-archimind_user}
    
    read -p "Enter database password: " -s DB_PASSWORD
    echo
    
    # Create database
    PGPASSWORD=$PG_PASSWORD psql -U postgres -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || print_warning "Database may already exist"
    PGPASSWORD=$PG_PASSWORD psql -U postgres -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null || print_warning "User may already exist"
    PGPASSWORD=$PG_PASSWORD psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" 2>/dev/null
    
    # Update .env file
    DB_URL="postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"
    sed -i "s|postgresql://.*|$DB_URL|" .env
    
    print_success "Database configured"
fi

# Step 6: Setup Ollama
print_step "Setting up Ollama embedding model..."

if command -v ollama &> /dev/null; then
    read -p "Do you want to download the Ollama embedding model? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ollama pull nomic-embed-text
        print_success "Ollama model downloaded"
    fi
else
    print_warning "Ollama not found. Install it from: https://ollama.ai"
fi

# Step 7: Create data directories
print_step "Creating data directories..."

mkdir -p data/temp_repo
mkdir -p data/chroma_db
print_success "Data directories created"

# Step 8: Initialize database tables
print_step "Initializing database tables..."

python3 -c "
from app import ArchiMindApplication
app = ArchiMindApplication()
with app.app.app_context():
    from app import db
    db.create_all()
print('Database tables initialized')
" 2>/dev/null && print_success "Database initialized" || print_warning "Database initialization failed (may already be initialized)"

# Step 9: Run tests
print_step "Running test suite..."

read -p "Do you want to run the test suite? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    pytest tests/ -v --cov=. --cov-report=term-missing
    print_success "Tests completed"
fi

# Final message
echo ""
echo "================================================"
echo -e "${GREEN}  Setup Complete!${NC}"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Edit .env file and add your GEMINI_API_KEY"
echo "2. Start the application: python app.py"
echo "3. Open http://localhost:5000 in your browser"
echo ""
echo "For more information, see README.md"
echo ""
