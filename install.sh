#!/bin/sh

# Exit immediately if any command exits with a non-zero status
set -e

# Text formatting helper variables (POSIX compliant)
BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Define configuration variables
TARGET_DIR="/opt/joule"
SYS_USER="joule"
SERVICE_NAME="joule.service"

echo "${BOLD}====================================================${NC}"
echo "${BOLD}${GREEN}          Joule Environment Installer${NC}"
echo "${BOLD}====================================================${NC}"
echo "This script will perform the following actions:"
echo "  1. Install system prerequisites via apt"
echo "     (${YELLOW}gcc, python3-pip, python3-dev, python3-venv, libhdf5-dev, python3-h5py${NC})"
echo "  2. Create a dedicated system user (${YELLOW}${SYS_USER}${NC})"
echo "  3. Create an isolated directory at ${YELLOW}${TARGET_DIR}${NC}"
echo "  4. Set up a Python virtual environment and install ${BOLD}Joule${NC}"
echo "  5. Prompt for your TimescaleDB/PostgreSQL DSN"
echo "  6. Run ${BOLD}joule admin initialize${NC} to configure the system"
echo "${BOLD}====================================================${NC}"
echo

# Prompt the user for confirmation (Pulling strictly from /dev/tty)
printf "Do you want to proceed with the installation? (y/N): "
read choice </dev/tty

case "$choice" in 
  [yY][eE][sS]|[yY]) 
    echo "\n${BOLD}Starting installation...${NC}"
    echo "Note: You may be prompted for your local 'sudo' password to install system dependencies.\n"
    ;;
  *)
    echo "\n${YELLOW}Installation cancelled by user.${NC}"
    exit 0
    ;;
esac

# Prompt for the Database DSN (Pulling strictly from /dev/tty)
echo "${BOLD}Database Configuration:${NC}"
echo "Format: ${YELLOW}username:password@hostname:port/database${NC}"
printf "Enter your TimescaleDB DSN: "
read DB_DSN </dev/tty

if [ -z "$DB_DSN" ]; then
    echo "${RED}Error: DSN cannot be empty.${NC}" >&2
    exit 1
fi

# --- 1. Install APT Dependencies ---
echo "Updating apt package listings and installing prerequisites..."
if sudo apt-get update && sudo apt-get install -y gcc python3-pip python3-dev python3-venv libhdf5-dev python3-h5py; then
    echo "${GREEN}Apt dependencies installed successfully.${NC}"
else
    echo "${RED}Error: Failed to install one or more apt packages.${NC}" >&2
    exit 1
fi

# --- 2. Create System User ---
printf "Creating system user '$SYS_USER'... "
if id "$SYS_USER" >/dev/null 2>&1; then
    echo "${YELLOW}User already exists.${NC}"
else
    if sudo useradd -r -s /bin/false "$SYS_USER"; then
        echo "${GREEN}Done.${NC}"
    else
        echo "${RED}Failed to create user.${NC}" >&2
        exit 1
    fi
fi

# --- 3. Create Directory & Set Permissions ---
printf "Preparing directory '$TARGET_DIR'... "
if sudo mkdir -p "$TARGET_DIR" && sudo chown -R "$SYS_USER":"$SYS_USER" "$TARGET_DIR"; then
    echo "${GREEN}Done.${NC}"
else
    echo "${RED}Failed to set up directory.${NC}" >&2
    exit 1
fi

# --- 4. Build Virtual Environment & Install Joule ---
echo "Creating virtual environment and installing Joule (this may take a moment)..."
if ! sudo -u "$SYS_USER" python3 -m venv "$TARGET_DIR"; then
    echo "${RED}Error: Failed to create Python virtual environment.${NC}" >&2
    exit 1
fi

if ! sudo -u "$SYS_USER" "$TARGET_DIR/bin/pip" install --upgrade pip >/dev/null 2>&1; then
    echo "${YELLOW}Warning: Failed to upgrade pip inside venv. Continuing anyway...${NC}"
fi

if sudo -u "$SYS_USER" "$TARGET_DIR/bin/pip" install joule; then
    echo "${GREEN}Joule package installed successfully.${NC}"
else
    echo "${RED}Error: Failed to install Joule via pip.${NC}" >&2
    exit 1
fi

# --- 5. Initialize Joule Environment via Admin Command ---
echo "Initializing Joule with the provided database DSN..."
if sudo "$TARGET_DIR/bin/joule" admin initialize --dsn "$DB_DSN"; then
    echo "${GREEN}Joule initialized successfully.${NC}"
else
    echo "${RED}Error: 'joule admin initialize' failed. Verify your DSN and database availability.${NC}" >&2
    exit 1
fi

# --- Final Instructions ---
printf "\n"
printf "${BOLD}${GREEN}✓ Installation complete!${NC}\n"
printf "To make the Joule CLI commands accessible in your terminal right away, run:\n"
printf "${BOLD}  echo 'export PATH=\"\$PATH:${TARGET_DIR}/bin\"' >> ~/.bashrc && source ~/.bashrc${NC}\n"
printf "\n"
printf "Check service status using: ${BOLD}sudo systemctl status %s${NC}\n" "$SERVICE_NAME"