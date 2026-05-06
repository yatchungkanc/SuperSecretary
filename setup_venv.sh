#!/bin/bash

# setup_venv.sh
# Interactive script to create a virtual environment for the Meeting Transcript Processor
# Detects available tools and guides user through setup

set -e  # Exit on error

echo "=========================================="
echo "Virtual Environment Setup"
echo "Meeting Transcript Processor"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Project configuration
PROJECT_NAME="transcript-processor"
PYTHON_VERSION="3.10.0"

# Detect available tools
echo "Detecting available Python environment tools..."
echo ""

# Check for pyenv
PYENV_AVAILABLE=false
if command -v pyenv &> /dev/null; then
    PYENV_AVAILABLE=true
    PYENV_VERSION=$(pyenv --version 2>/dev/null || echo "unknown")
    echo -e "${GREEN}✓${NC} pyenv detected: $PYENV_VERSION"
fi

# Check for Python and venv
VENV_AVAILABLE=false
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PYTHON_VERSION_STR=$(python3 --version 2>/dev/null || echo "unknown")
    # Check if venv module is available
    if python3 -m venv --help &> /dev/null; then
        VENV_AVAILABLE=true
        echo -e "${GREEN}✓${NC} Python venv detected: $PYTHON_VERSION_STR"
    fi
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    PYTHON_VERSION_STR=$(python --version 2>/dev/null || echo "unknown")
    # Check if venv module is available
    if python -m venv --help &> /dev/null; then
        VENV_AVAILABLE=true
        echo -e "${GREEN}✓${NC} Python venv detected: $PYTHON_VERSION_STR"
    fi
fi

echo ""

# Check if any tools are available
if [ "$PYENV_AVAILABLE" = false ] && [ "$VENV_AVAILABLE" = false ]; then
    echo -e "${RED}✗ No suitable Python environment tools found!${NC}"
    echo ""
    echo "Please install one of the following:"
    echo "  1. pyenv: https://github.com/pyenv/pyenv#installation"
    echo "  2. Python 3 with venv module (usually included with Python)"
    echo ""
    exit 1
fi

# Present options to user
echo "Available options:"
echo ""

OPTION_NUM=1
declare -a OPTIONS
declare -a OPTION_DESCRIPTIONS

if [ "$PYENV_AVAILABLE" = true ]; then
    OPTIONS[$OPTION_NUM]="pyenv"
    OPTION_DESCRIPTIONS[$OPTION_NUM]="Use pyenv (recommended for managing multiple Python versions)"
    echo "  ${OPTION_NUM}. pyenv - Recommended for managing multiple Python versions"
    ((OPTION_NUM++))
fi

if [ "$VENV_AVAILABLE" = true ]; then
    OPTIONS[$OPTION_NUM]="venv"
    OPTION_DESCRIPTIONS[$OPTION_NUM]="Use Python's built-in venv module"
    echo "  ${OPTION_NUM}. venv - Python's built-in virtual environment ($PYTHON_VERSION_STR)"
    ((OPTION_NUM++))
fi

echo ""
echo -n "Select an option [1-$((OPTION_NUM-1))]: "
read -r CHOICE

# Validate choice
if ! [[ "$CHOICE" =~ ^[0-9]+$ ]] || [ "$CHOICE" -lt 1 ] || [ "$CHOICE" -ge "$OPTION_NUM" ]; then
    echo -e "${RED}Invalid choice. Exiting.${NC}"
    exit 1
fi

SELECTED_TOOL="${OPTIONS[$CHOICE]}"
echo ""
echo -e "${BLUE}Selected: $SELECTED_TOOL${NC}"
echo ""

# Create virtual environment based on selection
case $SELECTED_TOOL in
    "pyenv")
        echo "Setting up with pyenv..."
        echo ""
        
        # Check if Python version is installed
        if ! pyenv versions | grep -q "$PYTHON_VERSION"; then
            echo -e "${YELLOW}Python $PYTHON_VERSION is not installed.${NC}"
            echo -n "Would you like to install it now? [y/N]: "
            read -r INSTALL_PYTHON
            
            if [[ "$INSTALL_PYTHON" =~ ^[Yy]$ ]]; then
                echo "Installing Python $PYTHON_VERSION..."
                pyenv install "$PYTHON_VERSION"
            else
                # Let user specify a version
                echo ""
                echo "Available Python versions:"
                pyenv versions
                echo ""
                echo -n "Enter the Python version to use (e.g., 3.10.0): "
                read -r PYTHON_VERSION
                
                if ! pyenv versions | grep -q "$PYTHON_VERSION"; then
                    echo -e "${RED}Version $PYTHON_VERSION not found. Exiting.${NC}"
                    exit 1
                fi
            fi
        fi
        
        # Check if virtualenv already exists
        if pyenv virtualenvs | grep -q "$PROJECT_NAME"; then
            echo -e "${YELLOW}Virtual environment '$PROJECT_NAME' already exists.${NC}"
            echo -n "Would you like to delete and recreate it? [y/N]: "
            read -r RECREATE
            
            if [[ "$RECREATE" =~ ^[Yy]$ ]]; then
                echo "Deleting existing virtual environment..."
                pyenv virtualenv-delete -f "$PROJECT_NAME"
            else
                echo "Using existing virtual environment."
                SKIP_CREATION=true
            fi
        fi
        
        # Create virtual environment
        if [ "$SKIP_CREATION" != true ]; then
            echo "Creating virtual environment '$PROJECT_NAME' with Python $PYTHON_VERSION..."
            pyenv virtualenv "$PYTHON_VERSION" "$PROJECT_NAME"
        fi
        
        # Set local Python version
        echo "Setting local Python version..."
        pyenv local "$PROJECT_NAME"
        
        echo ""
        echo -e "${GREEN}✓ Virtual environment created successfully!${NC}"
        echo ""
        echo "The virtual environment will automatically activate when you navigate to this directory."
        echo ""
        echo "To manually activate it elsewhere:"
        echo -e "  ${BLUE}pyenv activate $PROJECT_NAME${NC}"
        echo ""
        echo "To deactivate:"
        echo -e "  ${BLUE}pyenv deactivate${NC}"
        ;;
        
    "venv")
        echo "Setting up with Python venv..."
        echo ""
        
        VENV_DIR="venv"
        
        # Check if venv directory already exists
        if [ -d "$VENV_DIR" ]; then
            echo -e "${YELLOW}Virtual environment directory '$VENV_DIR' already exists.${NC}"
            echo -n "Would you like to delete and recreate it? [y/N]: "
            read -r RECREATE
            
            if [[ "$RECREATE" =~ ^[Yy]$ ]]; then
                echo "Deleting existing virtual environment..."
                rm -rf "$VENV_DIR"
            else
                echo "Using existing virtual environment."
                SKIP_CREATION=true
            fi
        fi
        
        # Create virtual environment
        if [ "$SKIP_CREATION" != true ]; then
            echo "Creating virtual environment in '$VENV_DIR'..."
            $PYTHON_CMD -m venv "$VENV_DIR"
        fi
        
        echo ""
        echo -e "${GREEN}✓ Virtual environment created successfully!${NC}"
        echo ""
        echo "To activate the virtual environment:"
        if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
            echo -e "  ${BLUE}$VENV_DIR\\Scripts\\activate${NC}"
        else
            echo -e "  ${BLUE}source $VENV_DIR/bin/activate${NC}"
        fi
        echo ""
        echo "To deactivate:"
        echo -e "  ${BLUE}deactivate${NC}"
        ;;
esac

echo ""
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo ""
echo "1. Activate the virtual environment (see instructions above)"
echo ""
echo "2. Install dependencies:"
echo -e "   ${BLUE}pip install -r requirements.txt${NC}"
echo "   Or:"
echo -e "   ${BLUE}pip install boto3 python-docx python-dotenv PyYAML${NC}"
echo ""
echo "3. Configure AWS credentials in .env file"
echo ""
echo "4. Run the application:"
echo -e "   ${BLUE}python process_transcript.py transcripts/${NC}"
echo ""
echo "=========================================="
