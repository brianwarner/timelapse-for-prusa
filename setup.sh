#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Brian Warner
#
# Timelapse for Prusa - Interactive Setup Script

set -e

# Parse command line arguments
VERBOSE=0
DEBUG=0
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=1
            shift
            ;;
        -d|--debug)
            DEBUG=1
            VERBOSE=1  # Debug implies verbose
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [-v|--verbose] [-d|--debug]"
            echo "  -v, --verbose  Enable detailed logging output (INFO level)"
            echo "  -d, --debug    Enable debug logging output (DEBUG level, includes all verbose output)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Export VERBOSE and DEBUG so they're available to subprocesses
export VERBOSE
export DEBUG

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
SERVICE_NAME="prusa-timelapse.service"
SERVICE_FILE="$SCRIPT_DIR/$SERVICE_NAME"

# Print colored header
print_header() {
    echo -e "\n${CYAN}${BOLD}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}${BOLD}${NC}   ${WHITE}${BOLD}$1${NC}"
    echo -e "${CYAN}${BOLD}╚════════════════════════════════════════════════════════════╝${NC}\n"
}

# Print colored message
print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
print_info() { echo -e "${BLUE}ℹ${NC} $1"; }

# Prompt for input with default value
prompt_input() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    local value
    
    if [ -n "$default" ]; then
        read -p "$(echo -e "${CYAN}$prompt${NC} [${YELLOW}$default${NC}]: ")" value
        value="${value:-$default}"
    else
        read -p "$(echo -e "${CYAN}$prompt${NC}: ")" value
    fi
    
    eval "$var_name='$value'"
}

# Prompt for yes/no with default
prompt_yn() {
    local prompt="$1"
    local default="${2:-n}"
    local response
    
    if [ "$default" = "y" ]; then
        read -p "$(echo -e "${CYAN}$prompt${NC} [${GREEN}Y${NC}/${WHITE}n${NC}]: ")" response
        response="${response:-y}"
    else
        read -p "$(echo -e "${CYAN}$prompt${NC} [${WHITE}y${NC}/${GREEN}N${NC}]: ")" response
        response="${response:-n}"
    fi
    
    case "$response" in
        [yY]|[yY][eE][sS]) return 0 ;;
        *) return 1 ;;
    esac
}

# Show main menu
show_menu() {
    clear
    echo -e "${CYAN}${BOLD}"
    cat << "EOF"
╔════════════════════════════════════════════════════════════╗
║   ▀▛▘▗        ▜               ▗▀▖        ▛▀▖               ║
║    ▌ ▄ ▛▚▀▖▞▀▖▐ ▝▀▖▛▀▖▞▀▘▞▀▖  ▐  ▞▀▖▙▀▖  ▙▄▘▙▀▖▌ ▌▞▀▘▝▀▖   ║
║    ▌ ▐ ▌▐ ▌▛▀ ▐ ▞▀▌▙▄▘▝▀▖▛▀   ▜▀ ▌ ▌▌    ▌  ▌  ▌ ▌▝▀▖▞▀▌   ║
║    ▘ ▀▘▘▝ ▘▝▀▘ ▘▝▀▘▌  ▀▀ ▝▀▘  ▐  ▝▀ ▘    ▘  ▘  ▝▀▘▀▀ ▝▀▘   ║
║                                                            ║
║     https://github.com/brianwarner/timelapse-for-prusa     ║
║                                                            ║
║             Brian Warner <brian@bdwarner.com>              ║
╚════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
    
    echo -e "${WHITE}${BOLD}Installation & Configuration:${NC}"
    echo -e "  ${GREEN}1${NC}) Install prerequisites"
    echo -e "  ${GREEN}2${NC}) Check dependencies"
    echo -e "  ${GREEN}3${NC}) Create/edit .env configuration file"
    echo -e "  ${GREEN}4${NC}) Configure focus distance"
    echo -e "  ${GREEN}5${NC}) Send test email"
    echo -e "  ${GREEN}6${NC}) Capture and email current camera view"
    echo -e "  ${GREEN}7${NC}) Capture and email test timelapse (10 frames)"
    echo -e "  ${GREEN}8${NC}) Upload current camera view to Prusa Connect"
    echo ""
    echo -e "${WHITE}${BOLD}Service Management:${NC}"
    echo -e "  ${MAGENTA}9${NC}) Configure and install systemd service"
    echo -e "  ${MAGENTA}10${NC}) View service status"
    echo -e "  ${MAGENTA}11${NC}) Restart service"
    echo -e "  ${MAGENTA}12${NC}) Stop service"
    echo -e "  ${MAGENTA}13${NC}) Disable service"
    echo ""
    echo -e "  ${RED}0${NC}) Exit"
    echo ""
}

# Option 1: Install prerequisites
install_prerequisites() {
    print_header "Installing Prerequisites"
    
    print_info "This will install: rpicam-apps-lite, ffmpeg, python3, python3-pip, python3-requests, python3-dotenv, python3-pil"
    echo ""
    
    if ! prompt_yn "Continue with installation?" "y"; then
        print_warning "Installation cancelled"
        return
    fi
    
    echo ""
    print_info "Updating package lists..."
    sudo apt update || { print_error "Failed to update package lists"; return 1; }
    
    print_info "Installing system packages..."
    sudo apt install -y rpicam-apps-lite ffmpeg python3 python3-pip || {
        print_error "Failed to install system packages"
        return 1
    }
    
    print_info "Installing Python packages..."
    sudo apt install -y python3-requests python3-dotenv python3-pil || {
        print_error "Failed to install Python packages"
        return 1
    }
    
    echo ""
    print_success "All prerequisites installed successfully!"
    
    read -p "Press Enter to continue..."
}

# Option 2: Check dependencies
check_dependencies() {
    print_header "Check Dependencies"
    
    print_info "Checking if all required dependencies are installed..."
    echo ""
    
    local all_ok=true
    
    # Check Python 3
    print_info "Checking Python 3..."
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1)
        print_success "Python 3 found: $PYTHON_VERSION"
    else
        print_error "Python 3 not found"
        all_ok=false
    fi
    
    echo ""
    
    # Check ffmpeg (with timeout)
    print_info "Checking ffmpeg..."
    if command -v ffmpeg &> /dev/null; then
        FFMPEG_VERSION=$(timeout 10 ffmpeg -version 2>&1 | head -n1 || echo "timeout")
        if [ "$FFMPEG_VERSION" = "timeout" ]; then
            print_warning "ffmpeg found but version check timed out"
        else
            print_success "ffmpeg found: $FFMPEG_VERSION"
        fi
    else
        print_error "ffmpeg not found"
        all_ok=false
    fi
    
    echo ""
    
    # Check rpicam-still
    print_info "Checking rpicam-still..."
    if command -v rpicam-still &> /dev/null; then
        print_success "rpicam-still found"
    else
        print_error "rpicam-still not found"
        all_ok=false
    fi
    
    echo ""
    
    # Check Python dependencies
    print_info "Checking Python dependencies..."
    
    python3 << PYTHON_CHECK_DEPS_EOF
import sys

modules = [
    ('requests', 'python3-requests'),
    ('dotenv', 'python3-dotenv'),
    ('PIL', 'python3-pil')
]

all_found = True
for module_name, package_name in modules:
    try:
        __import__(module_name)
        print(f"  ✓ {package_name}")
    except ImportError:
        print(f"  ✗ {package_name} (missing)")
        all_found = False

sys.exit(0 if all_found else 1)
PYTHON_CHECK_DEPS_EOF
    
    if [ $? -eq 0 ]; then
        print_success "All Python dependencies found"
    else
        print_error "Some Python dependencies are missing"
        all_ok=false
    fi
    
    echo ""
    echo "════════════════════════════════════════════════════════════"
    
    if [ "$all_ok" = true ]; then
        print_success "All dependencies are installed!"
    else
        print_warning "Some dependencies are missing. Run option 1 to install them."
    fi
    
    echo ""
    read -p "Press Enter to continue..."
}

# Option 3: Create .env file
create_env_file() {
    print_header "Create/Edit Configuration File"
    
    # Check if .env exists
    if [ -f "$ENV_FILE" ]; then
        print_warning ".env file already exists"
        echo ""
        echo "Options:"
        echo "  1) Load existing values (edit mode)"
        echo "  2) Backup existing and create new"
        echo "  3) Overwrite existing"
        echo "  4) Cancel"
        echo ""
        read -p "$(echo -e "${CYAN}Select option${NC} [1-4]: ")" option
        
        case "$option" in
            1)
                print_info "Loading existing .env file..."
                source "$ENV_FILE"
                ;;
            2)
                backup_file="${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
                cp "$ENV_FILE" "$backup_file"
                print_success "Backed up to: $backup_file"
                ;;
            3)
                print_warning "Overwriting existing .env file"
                ;;
            *)
                print_info "Cancelled"
                return
                ;;
        esac
        echo ""
    fi
    
    print_info "Configuration Wizard"
    print_warning "Required fields cannot be left empty. Optional fields can be skipped."
    echo ""
    
    # PrusaLink Configuration
    print_header "PrusaLink API Configuration"
    print_info "Find your printer's IP: LCD Menu → Settings → Network → Show IP"
    prompt_input "Printer IP address or hostname" "${PRUSA_PRINTER_HOST}" PRUSA_PRINTER_HOST
    while [ -z "$PRUSA_PRINTER_HOST" ]; do
        print_error "Printer host is required!"
        prompt_input "Printer IP address or hostname" "" PRUSA_PRINTER_HOST
    done
    
    echo ""
    print_info "Get API key from: http://$PRUSA_PRINTER_HOST → Settings → API"
    prompt_input "PrusaLink API Key" "${PRUSA_API_KEY}" PRUSA_API_KEY
    while [ -z "$PRUSA_API_KEY" ]; do
        print_error "API key is required!"
        prompt_input "PrusaLink API Key" "" PRUSA_API_KEY
    done
    
    # Camera Configuration
    print_header "Camera & Timelapse Configuration"
    prompt_input "Capture interval in seconds" "${CAPTURE_INTERVAL_SECONDS:-15}" CAPTURE_INTERVAL_SECONDS
    prompt_input "Image width" "${IMAGE_WIDTH:-1920}" IMAGE_WIDTH
    prompt_input "Image height" "${IMAGE_HEIGHT:-1080}" IMAGE_HEIGHT
    
    echo ""
    print_info "Camera rotation (if camera is mounted at an angle)"
    print_info "Valid values: 0, 90, 180, or 270 degrees"
    prompt_input "Camera rotation" "${CAMERA_ROTATION:-0}" CAMERA_ROTATION
    while [[ ! "$CAMERA_ROTATION" =~ ^(0|90|180|270)$ ]]; do
        print_warning "Invalid rotation value. Must be 0, 90, 180, or 270"
        prompt_input "Camera rotation" "0" CAMERA_ROTATION
    done
    
    echo ""
    print_info "Focus distance: distance from camera lens to center of field of view"
    print_info "Valid range: 10-100 cm (closer subjects = lower numbers)"
    prompt_input "Focus distance in centimeters" "${FOCUS_DISTANCE:-22}" FOCUS_DISTANCE
    while [[ ! "$FOCUS_DISTANCE" =~ ^[0-9]+$ ]] || [ "$FOCUS_DISTANCE" -lt 10 ] || [ "$FOCUS_DISTANCE" -gt 100 ]; do
        print_warning "Invalid focus distance. Must be between 10 and 100 cm"
        prompt_input "Focus distance in centimeters" "22" FOCUS_DISTANCE
    done
    
    echo ""
    prompt_input "Video FPS" "${VIDEO_FPS:-10}" VIDEO_FPS
    prompt_input "Video quality (CRF 0-51, lower=better)" "${VIDEO_QUALITY:-28}" VIDEO_QUALITY
    
    # Email Configuration
    print_header "Email Configuration"
    prompt_input "SMTP server" "${SMTP_SERVER}" SMTP_SERVER
    while [ -z "$SMTP_SERVER" ]; do
        print_error "SMTP server is required!"
        prompt_input "SMTP server" "" SMTP_SERVER
    done
    
    prompt_input "SMTP port" "${SMTP_PORT:-25}" SMTP_PORT
    
    echo ""
    print_info "Leave username/password empty for no authentication"
    prompt_input "SMTP username (optional)" "${SMTP_USERNAME}" SMTP_USERNAME
    if [ -n "$SMTP_USERNAME" ]; then
        prompt_input "SMTP password" "${SMTP_PASSWORD}" SMTP_PASSWORD
    else
        SMTP_PASSWORD=""
    fi
    
    prompt_input "From email address" "${EMAIL_FROM:-$SMTP_USERNAME}" EMAIL_FROM
    prompt_input "To email address" "${EMAIL_TO}" EMAIL_TO
    while [ -z "$EMAIL_TO" ]; do
        print_error "Destination email is required!"
        prompt_input "To email address" "" EMAIL_TO
    done
    
    # Monitoring Configuration
    print_header "Monitoring Configuration"
    prompt_input "API polling interval in seconds" "${POLL_INTERVAL_SECONDS:-10}" POLL_INTERVAL_SECONDS
    
    # Storage Configuration
    print_header "Storage Configuration"
    prompt_input "Output directory name (in home folder)" "${PRINTS_DIR_NAME:-prints}" PRINTS_DIR_NAME
    while [ -z "$PRINTS_DIR_NAME" ]; do
        print_error "Output directory name is required!"
        prompt_input "Output directory name (in home folder)" "prints" PRINTS_DIR_NAME
    done
    
    echo ""
    print_info "Extra rpicam-still parameters (optional, for advanced users)"
    print_warning "Leave empty for defaults. Do not include --output, --width, or --height"
    prompt_input "Extra parameters" "${RPICAM_EXTRA_PARAMS}" RPICAM_EXTRA_PARAMS
    
    # Prusa Connect (Optional)
    print_header "Prusa Connect Live Monitoring (Optional)"
    print_info "Enable live snapshots on Prusa Connect website"
    print_info "Get token from: https://connect.prusa3d.com → Add Camera"
    echo ""
    
    # Default to "y" if already configured, otherwise "n"
    if [ -n "$PRUSA_CONNECT_CAMERA_TOKEN" ]; then
        PRUSA_CONNECT_DEFAULT="y"
    else
        PRUSA_CONNECT_DEFAULT="n"
    fi
    
    if prompt_yn "Enable Prusa Connect uploads?" "$PRUSA_CONNECT_DEFAULT"; then
        prompt_input "Prusa Connect camera token" "${PRUSA_CONNECT_CAMERA_TOKEN}" PRUSA_CONNECT_CAMERA_TOKEN
        if [ -n "$PRUSA_CONNECT_CAMERA_TOKEN" ]; then
            print_info "Generate fingerprint with: uuidgen"
            prompt_input "Camera fingerprint" "${PRUSA_CONNECT_CAMERA_FINGERPRINT}" PRUSA_CONNECT_CAMERA_FINGERPRINT
        else
            PRUSA_CONNECT_CAMERA_FINGERPRINT=""
        fi
    else
        PRUSA_CONNECT_CAMERA_TOKEN=""
        PRUSA_CONNECT_CAMERA_FINGERPRINT=""
    fi
    
    # Write .env file
    echo ""
    print_info "Review your configuration:"
    echo ""
    echo "  Printer: $PRUSA_PRINTER_HOST"
    echo "  SMTP: $SMTP_SERVER:$SMTP_PORT"
    echo "  Email To: $EMAIL_TO"
    echo "  Prusa Connect: ${PRUSA_CONNECT_CAMERA_TOKEN:+Enabled}"
    echo ""
    
    if ! prompt_yn "Save configuration to $ENV_FILE?" "y"; then
        print_warning "Configuration not saved"
        read -p "Press Enter to continue..."
        return
    fi
    
    print_info "Writing configuration to $ENV_FILE..."
    
    cat > "$ENV_FILE" << EOF
# PrusaLink Local API Configuration
PRUSA_PRINTER_HOST=$PRUSA_PRINTER_HOST
PRUSA_API_KEY=$PRUSA_API_KEY

# Camera & Timelapse Configuration
CAPTURE_INTERVAL_SECONDS=$CAPTURE_INTERVAL_SECONDS
IMAGE_WIDTH=$IMAGE_WIDTH
IMAGE_HEIGHT=$IMAGE_HEIGHT
CAMERA_ROTATION=$CAMERA_ROTATION
FOCUS_DISTANCE=$FOCUS_DISTANCE
VIDEO_FPS=$VIDEO_FPS
VIDEO_QUALITY=$VIDEO_QUALITY

# Email Configuration
SMTP_SERVER=$SMTP_SERVER
SMTP_PORT=$SMTP_PORT
SMTP_USERNAME=$SMTP_USERNAME
SMTP_PASSWORD=$SMTP_PASSWORD
EMAIL_FROM=$EMAIL_FROM
EMAIL_TO=$EMAIL_TO

# Monitoring Configuration
POLL_INTERVAL_SECONDS=$POLL_INTERVAL_SECONDS

# Storage Configuration
PRINTS_DIR_NAME=$PRINTS_DIR_NAME

# Camera Extra Parameters (Optional)
RPICAM_EXTRA_PARAMS=$RPICAM_EXTRA_PARAMS

# Prusa Connect Camera (Optional)
PRUSA_CONNECT_CAMERA_TOKEN=$PRUSA_CONNECT_CAMERA_TOKEN
PRUSA_CONNECT_CAMERA_FINGERPRINT=$PRUSA_CONNECT_CAMERA_FINGERPRINT
EOF
    
    chmod 600 "$ENV_FILE"
    print_success "Configuration saved to $ENV_FILE"
    
    echo ""
    read -p "Press Enter to continue..."
}

# Option 3: Configure focus distance
configure_focus_distance() {
    print_header "Configure Focus Distance"
    
    if [ ! -f "$ENV_FILE" ]; then
        print_error "No .env file found. Please run option 2 first to create configuration."
        read -p "Press Enter to continue..."
        return
    fi
    
    # Load current value
    if [ -f "$ENV_FILE" ]; then
        source "$ENV_FILE"
    fi
    
    CURRENT_FOCUS="${FOCUS_DISTANCE:-22}"
    CURRENT_LENS_POS=$(python3 -c "print(round(100 / $CURRENT_FOCUS, 2))")
    
    echo ""
    print_info "Focus distance is the distance from camera lens to center of field of view"
    print_info "This controls the --lens-position parameter for rpicam-still"
    print_info "Formula: lens_position = 100 / focus_distance"
    echo ""
    print_info "Current setting: ${CURRENT_FOCUS}cm (lens position: $CURRENT_LENS_POS)"
    print_info "Valid range: 10-100 cm"
    print_info "  • Closer subjects (10-30cm) = lower focus distance values"
    print_info "  • Medium distance (30-50cm) = typical for 3D printer monitoring"
    print_info "  • Farther subjects (50-100cm) = higher focus distance values"
    echo ""
    
    prompt_input "Focus distance in centimeters" "$CURRENT_FOCUS" NEW_FOCUS_DISTANCE
    
    # Validate input
    while [[ ! "$NEW_FOCUS_DISTANCE" =~ ^[0-9]+$ ]] || [ "$NEW_FOCUS_DISTANCE" -lt 10 ] || [ "$NEW_FOCUS_DISTANCE" -gt 100 ]; do
        print_warning "Invalid focus distance. Must be between 10 and 100 cm"
        prompt_input "Focus distance in centimeters" "$CURRENT_FOCUS" NEW_FOCUS_DISTANCE
    done
    
    NEW_LENS_POS=$(python3 -c "print(round(100 / $NEW_FOCUS_DISTANCE, 2))")
    
    echo ""
    print_info "New setting: ${NEW_FOCUS_DISTANCE}cm (lens position: $NEW_LENS_POS)"
    
    if ! prompt_yn "Update configuration?" "y"; then
        print_warning "Configuration not updated"
        read -p "Press Enter to continue..."
        return
    fi
    
    # Update .env file
    if grep -q "^FOCUS_DISTANCE=" "$ENV_FILE"; then
        # Update existing value
        sed -i.bak "s/^FOCUS_DISTANCE=.*/FOCUS_DISTANCE=$NEW_FOCUS_DISTANCE/" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
    else
        # Add new value after CAMERA_ROTATION
        sed -i.bak "/^CAMERA_ROTATION=/a\\
FOCUS_DISTANCE=$NEW_FOCUS_DISTANCE" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
    fi
    
    print_success "Focus distance updated to ${NEW_FOCUS_DISTANCE}cm"
    print_info "Lens position will be set to $NEW_LENS_POS"
    
    echo ""
    read -p "Press Enter to continue..."
}

# Option 4: Send test email
send_test_email() {
    print_header "Send Test Email"
    
    if [ ! -f "$ENV_FILE" ]; then
        print_error ".env file not found. Please configure it first (option 2)"
        read -p "Press Enter to continue..."
        return 1
    fi
    
    # Load environment
    source "$ENV_FILE"
    
    if [ -z "$EMAIL_TO" ] || [ -z "$SMTP_SERVER" ]; then
        print_error "Email configuration incomplete. Please configure .env first"
        read -p "Press Enter to continue..."
        return 1
    fi
    
    print_info "This will send a test email to: $EMAIL_TO"
    echo ""
    
    if ! prompt_yn "Send test email?" "y"; then
        print_warning "Cancelled"
        return
    fi
    
    print_info "Sending test email..."
    
    python3 << PYTHON_TEST_EMAIL_EOF
import sys
import logging
import os
sys.path.insert(0, '$SCRIPT_DIR')

# Configure logging if verbose or debug mode is enabled
if os.getenv('DEBUG') == '1':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(levelname)s: %(message)s'
    )
elif os.getenv('VERBOSE') == '1':
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )

import prusa_lib
from datetime import datetime

# Load config
smtp_server = "$SMTP_SERVER"
smtp_port = int("${SMTP_PORT:-25}")
smtp_username = "$SMTP_USERNAME" if "$SMTP_USERNAME" else None
smtp_password = "$SMTP_PASSWORD" if "$SMTP_PASSWORD" else None
email_from = "${EMAIL_FROM:-$SMTP_USERNAME}"
email_to = "$EMAIL_TO"

try:
    # HTML body
    body = f"""<!DOCTYPE html>
<html>
<head><style>
body {{ font-family: 'Segoe UI', sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }}
.container {{ background-color: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow: hidden; }}
.header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
.header h1 {{ margin: 0; font-size: 28px; }}
.content {{ padding: 30px; }}
.footer {{ background-color: #f9f9f9; padding: 20px; text-align: center; color: #666; font-size: 14px; border-top: 1px solid #ddd; }}
</style></head>
<body>
<div class="container">
    <div class="header"><h1>✉️ Test Email</h1></div>
    <div class="content">
        <p>This is a <strong>test email</strong> from Timelapse for Prusa.</p>
        <p><strong>Configuration:</strong></p>
        <ul>
            <li>SMTP Server: {smtp_server}:{smtp_port}</li>
            <li>From: {email_from}</li>
            <li>To: {email_to}</li>
            <li>Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
        </ul>
        <p>If you received this email, your email configuration is working correctly!</p>
    </div>
    <div class="footer"><p>Timelapse for Prusa</p></div>
</div>
</body>
</html>"""
    
    # Send email using prusa_lib
    success = prusa_lib.send_email(
        smtp_server=smtp_server,
        smtp_port=smtp_port,
        email_from=email_from,
        email_to=email_to,
        subject='Timelapse for Prusa - Test Email',
        html_body=body,
        attachment_path=None,
        smtp_username=smtp_username,
        smtp_password=smtp_password
    )
    
    if success:
        print('SUCCESS')
        sys.exit(0)
    else:
        print('ERROR: Failed to send email')
        sys.exit(1)
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
PYTHON_TEST_EMAIL_EOF
    
    if [ $? -eq 0 ]; then
        print_success "Test email sent to $EMAIL_TO"
    else
        print_error "Failed to send email"
    fi
    
    echo ""
    read -p "Press Enter to continue..."
}

# Option 5: Capture and email current camera view
capture_and_email_current_view() {
    print_header "Capture and Email Current Camera View"
    
    if [ ! -f "$ENV_FILE" ]; then
        print_error ".env file not found. Please configure it first (option 2)"
        read -p "Press Enter to continue..."
        return 1
    fi
    
    # Load environment
    source "$ENV_FILE"
    
    if [ -z "$EMAIL_TO" ] || [ -z "$SMTP_SERVER" ]; then
        print_error "Email configuration incomplete. Please configure .env first"
        read -p "Press Enter to continue..."
        return 1
    fi
    
    print_info "This will capture a single image and email it to: $EMAIL_TO"
    echo ""
    
    if ! prompt_yn "Continue?" "y"; then
        print_warning "Cancelled"
        return
    fi
    
    # Create temp directory in /tmp for automatic cleanup
    TEMP_DIR="/tmp/camera_snapshot_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$TEMP_DIR"
    TEMP_IMAGE="$TEMP_DIR/snapshot.jpg"
    
    print_info "Capturing image..."
    echo ""
    
    # Capture image using prusa_lib
    python3 << PYTHON_CAPTURE_SNAPSHOT_EOF
import sys
import os
import logging
sys.path.insert(0, '$SCRIPT_DIR')

# Configure logging if verbose or debug mode is enabled
if os.getenv('DEBUG') == '1':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(levelname)s: %(message)s'
    )
elif os.getenv('VERBOSE') == '1':
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )

import prusa_lib

# Configuration
width = int('${IMAGE_WIDTH:-1920}')
height = int('${IMAGE_HEIGHT:-1080}')
extra_params = '${RPICAM_EXTRA_PARAMS}'
focus_distance = int('${FOCUS_DISTANCE:-22}')
lens_position = round(100 / focus_distance, 2)
temp_image = '$TEMP_IMAGE'

try:
    if prusa_lib.capture_image(temp_image, width, height, extra_params, lens_position):
        print('SUCCESS')
        sys.exit(0)
    else:
        print('ERROR: Failed to capture image')
        sys.exit(1)
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
PYTHON_CAPTURE_SNAPSHOT_EOF

    if [ $? -ne 0 ]; then
        print_error "Failed to capture image"
        rm -rf "$TEMP_DIR"
        read -p "Press Enter to continue..."
        return 1
    fi
    
    print_success "Image captured"
    
    # Email image using prusa_lib
    print_info "Sending email to $EMAIL_TO..."
    
    python3 << PYTHON_EMAIL_SNAPSHOT_EOF
import sys
import logging
import os
sys.path.insert(0, '$SCRIPT_DIR')

# Configure logging if verbose or debug mode is enabled
if os.getenv('DEBUG') == '1':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(levelname)s: %(message)s'
    )
elif os.getenv('VERBOSE') == '1':
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )

import prusa_lib
from datetime import datetime

# Load config
smtp_server = "$SMTP_SERVER"
smtp_port = int("${SMTP_PORT:-25}")
smtp_username = "$SMTP_USERNAME" if "$SMTP_USERNAME" else None
smtp_password = "$SMTP_PASSWORD" if "$SMTP_PASSWORD" else None
email_from = "${EMAIL_FROM:-$SMTP_USERNAME}"
email_to = "$EMAIL_TO"
image_file = '$TEMP_IMAGE'

try:
    # HTML body
    body = f"""<!DOCTYPE html>
<html>
<head><style>
body {{ font-family: 'Segoe UI', sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }}
.container {{ background-color: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow: hidden; }}
.header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
.header h1 {{ margin: 0; font-size: 28px; }}
.content {{ padding: 30px; }}
.footer {{ background-color: #f9f9f9; padding: 20px; text-align: center; color: #666; font-size: 14px; border-top: 1px solid #ddd; }}
</style></head>
<body>
<div class="container">
    <div class="header"><h1>📸 Camera Snapshot</h1></div>
    <div class="content">
        <p>This is a <strong>camera snapshot</strong> from Timelapse for Prusa.</p>
        <p><strong>Details:</strong></p>
        <ul>
            <li>Captured: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
            <li>Resolution: ${IMAGE_WIDTH}x${IMAGE_HEIGHT}</li>
            <li>Focus distance: ${FOCUS_DISTANCE}cm</li>
        </ul>
        <p>The snapshot image is attached to this email.</p>
    </div>
    <div class="footer"><p>Timelapse for Prusa</p></div>
</div>
</body>
</html>"""
    
    # Send email using prusa_lib
    success = prusa_lib.send_email(
        smtp_server=smtp_server,
        smtp_port=smtp_port,
        email_from=email_from,
        email_to=email_to,
        subject='Timelapse for Prusa - Camera Snapshot',
        html_body=body,
        attachment_path=image_file,
        smtp_username=smtp_username,
        smtp_password=smtp_password
    )
    
    if success:
        print('SUCCESS')
        sys.exit(0)
    else:
        print('ERROR: Failed to send email')
        sys.exit(1)
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
PYTHON_EMAIL_SNAPSHOT_EOF
    
    if [ $? -eq 0 ]; then
        print_success "Snapshot emailed to $EMAIL_TO"
    else
        print_error "Failed to send email"
    fi
    
    # Clean up
    rm -rf "$TEMP_DIR"
    
    echo ""
    read -p "Press Enter to continue..."
}

# Option 6: Test timelapse
test_timelapse() {
    print_header "Capture Test Timelapse"
    
    if [ ! -f "$ENV_FILE" ]; then
        print_error ".env file not found. Please configure it first (option 2)"
        read -p "Press Enter to continue..."
        return 1
    fi
    
    # Load environment
    source "$ENV_FILE"
    
    if [ -z "$EMAIL_TO" ] || [ -z "$SMTP_SERVER" ]; then
        print_error "Email configuration incomplete. Please configure .env first"
        read -p "Press Enter to continue..."
        return 1
    fi
    
    print_info "This will capture 10 frames (1 second apart) and email a test video"
    echo ""
    
    if ! prompt_yn "Continue?" "y"; then
        print_warning "Cancelled"
        return
    fi
    
    # Create temp directory in /tmp for automatic cleanup
    TEST_DIR="/tmp/test_timelapse_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$TEST_DIR"
    
    print_info "Capturing 10 frames to $TEST_DIR..."
    echo ""
    
    # Capture 10 frames using prusa_lib
    print_info "Capturing 10 frames..."
    python3 << PYTHON_CAPTURE_EOF
import sys
import os
import logging
sys.path.insert(0, '$SCRIPT_DIR')

# Configure logging if verbose or debug mode is enabled
if os.getenv('DEBUG') == '1':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(levelname)s: %(message)s'
    )
elif os.getenv('VERBOSE') == '1':
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )

import prusa_lib

# Configuration
width = int('${IMAGE_WIDTH:-1920}')
height = int('${IMAGE_HEIGHT:-1080}')
extra_params = '${RPICAM_EXTRA_PARAMS}'
focus_distance = int('${FOCUS_DISTANCE:-22}')
lens_position = round(100 / focus_distance, 2)

success = True
for i in range(10):
    output_path = f"$TEST_DIR/frame_{i:05d}.jpg"
    print(f"\r  Frame {i+1}/10...", end='', flush=True)
    
    if not prusa_lib.capture_image(output_path, width, height, extra_params, lens_position):
        print(f"\nError: Failed to capture frame {i+1}")
        success = False
        break

if success:
    print()  # New line after progress
    sys.exit(0)
else:
    sys.exit(1)
PYTHON_CAPTURE_EOF

    if [ $? -ne 0 ]; then
        print_error "Failed to capture frames"
        rm -rf "$TEST_DIR"
        read -p "Press Enter to continue..."
        return 1
    fi
    
    print_success "All frames captured"
    
    # Create video using prusa_lib
    print_info "Creating video..."
    VIDEO_FILE="$TEST_DIR/test_timelapse.mp4"
    
    python3 << PYTHON_VIDEO_EOF
import sys
import logging
import os
sys.path.insert(0, '$SCRIPT_DIR')

# Configure logging if verbose or debug mode is enabled
if os.getenv('DEBUG') == '1':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(levelname)s: %(message)s'
    )
elif os.getenv('VERBOSE') == '1':
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )

import prusa_lib

fps = int('${VIDEO_FPS:-10}')
quality = int('${VIDEO_QUALITY:-23}')
# Handle empty or unset CAMERA_ROTATION
rotation_str = '${CAMERA_ROTATION}'.strip()
rotation = int(rotation_str) if rotation_str else 0

if prusa_lib.create_video('$TEST_DIR', '$VIDEO_FILE', fps, quality, rotation):
    sys.exit(0)
else:
    sys.exit(1)
PYTHON_VIDEO_EOF

    if [ $? -ne 0 ]; then
        print_error "Failed to create video"
        rm -rf "$TEST_DIR"
        read -p "Press Enter to continue..."
        return 1
    fi
    
    print_success "Video created: $VIDEO_FILE"
    
    # Email video using prusa_lib
    print_info "Sending email to $EMAIL_TO..."
    
    python3 << PYTHON_EOF
import sys
import logging
import os
sys.path.insert(0, '$SCRIPT_DIR')

# Configure logging if verbose or debug mode is enabled
if os.getenv('DEBUG') == '1':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(levelname)s: %(message)s'
    )
elif os.getenv('VERBOSE') == '1':
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )

import prusa_lib
from datetime import datetime

# Load config
smtp_server = "$SMTP_SERVER"
smtp_port = int("${SMTP_PORT:-25}")
smtp_username = "$SMTP_USERNAME" if "$SMTP_USERNAME" else None
smtp_password = "$SMTP_PASSWORD" if "$SMTP_PASSWORD" else None
email_from = "${EMAIL_FROM:-$SMTP_USERNAME}"
email_to = "$EMAIL_TO"
video_file = "$VIDEO_FILE"

try:
    # HTML body
    body = f"""<!DOCTYPE html>
<html>
<head><style>
body {{ font-family: 'Segoe UI', sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }}
.container {{ background-color: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow: hidden; }}
.header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
.header h1 {{ margin: 0; font-size: 28px; }}
.content {{ padding: 30px; }}
.footer {{ background-color: #f9f9f9; padding: 20px; text-align: center; color: #666; font-size: 14px; border-top: 1px solid #ddd; }}
</style></head>
<body>
<div class="container">
    <div class="header"><h1>🎬 Test Timelapse</h1></div>
    <div class="content">
        <p>This is a <strong>test timelapse</strong> from Timelapse for Prusa.</p>
        <p><strong>Details:</strong></p>
        <ul>
            <li>Frames captured: 10</li>
            <li>Interval: 1 second</li>
            <li>Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
        </ul>
        <p>The test video is attached to this email.</p>
    </div>
    <div class="footer"><p>Timelapse for Prusa</p></div>
</div>
</body>
</html>"""
    
    # Send email using prusa_lib
    success = prusa_lib.send_email(
        smtp_server=smtp_server,
        smtp_port=smtp_port,
        email_from=email_from,
        email_to=email_to,
        subject='Timelapse for Prusa - Test Video',
        html_body=body,
        attachment_path=video_file,
        smtp_username=smtp_username,
        smtp_password=smtp_password
    )
    
    if success:
        print('SUCCESS')
        sys.exit(0)
    else:
        print('ERROR: Failed to send email')
        sys.exit(1)
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
PYTHON_EOF
    
    if [ $? -eq 0 ]; then
        print_success "Test timelapse emailed to $EMAIL_TO"
        print_info "Test files saved in: $TEST_DIR"
    else
        print_error "Failed to send email"
    fi
    
    echo ""
    read -p "Press Enter to continue..."
}

# Option 5: Upload snapshot to Prusa Connect
upload_prusa_connect() {
    print_header "Upload Snapshot to Prusa Connect"
    
    if [ ! -f "$ENV_FILE" ]; then
        print_error ".env file not found. Please configure it first (option 2)"
        read -p "Press Enter to continue..."
        return 1
    fi
    
    # Load environment
    source "$ENV_FILE"
    
    if [ -z "$PRUSA_CONNECT_CAMERA_TOKEN" ] || [ -z "$PRUSA_CONNECT_CAMERA_FINGERPRINT" ]; then
        print_error "Prusa Connect not configured in .env"
        print_info "Set PRUSA_CONNECT_CAMERA_TOKEN and PRUSA_CONNECT_CAMERA_FINGERPRINT"
        echo ""
        read -p "Press Enter to continue..."
        return 1
    fi
    
    print_info "This will capture the current camera view and upload to Prusa Connect"
    echo ""
    
    if ! prompt_yn "Continue?" "y"; then
        print_warning "Cancelled"
        return
    fi
    
    # Capture and upload using prusa_lib
    TEMP_IMAGE="/tmp/prusa_connect_snapshot_$$.jpg"
    print_info "Capturing and uploading image..."
    
    python3 << PYTHON_UPLOAD_EOF
import sys
import logging
import os
sys.path.insert(0, '$SCRIPT_DIR')

# Configure logging if verbose or debug mode is enabled
if os.getenv('DEBUG') == '1':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(levelname)s: %(message)s'
    )
elif os.getenv('VERBOSE') == '1':
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )

import prusa_lib

# Configuration
width = int('${IMAGE_WIDTH:-1920}')
height = int('${IMAGE_HEIGHT:-1080}')
extra_params = '${RPICAM_EXTRA_PARAMS}'
focus_distance = int('${FOCUS_DISTANCE:-22}')
lens_position = round(100 / focus_distance, 2)
# Handle empty or unset CAMERA_ROTATION
rotation_str = '${CAMERA_ROTATION}'.strip()
rotation = int(rotation_str) if rotation_str else 0
token = '$PRUSA_CONNECT_CAMERA_TOKEN'
fingerprint = '$PRUSA_CONNECT_CAMERA_FINGERPRINT'
temp_image = '$TEMP_IMAGE'

try:
    # Capture image
    if not prusa_lib.capture_image(temp_image, width, height, extra_params, lens_position):
        print("ERROR: Failed to capture image", file=sys.stderr)
        sys.exit(1)
    
    # Upload to Prusa Connect (with rotation)
    if prusa_lib.upload_to_prusa_connect(temp_image, token, fingerprint, rotation):
        print("SUCCESS")
        sys.exit(0)
    else:
        print("ERROR: Upload failed", file=sys.stderr)
        sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
finally:
    import os
    if os.path.exists(temp_image):
        os.remove(temp_image)
PYTHON_UPLOAD_EOF
    
    if [ $? -eq 0 ]; then
        print_success "Snapshot uploaded successfully!"
        print_info "View at: https://connect.prusa3d.com"
    else
        print_error "Failed to upload snapshot"
    fi
    
    echo ""
    read -p "Press Enter to continue..."
}

# Option 6: Configure systemd service
configure_service() {
    print_header "Configure systemd Service"
    
    # Get current user
    CURRENT_USER="${USER:-$(whoami)}"
    CURRENT_HOME="${HOME:-$(eval echo ~$CURRENT_USER)}"
    
    print_info "Service will run as user: $CURRENT_USER"
    print_info "Working directory: $SCRIPT_DIR"
    echo ""
    
    if ! prompt_yn "Continue with service installation?" "y"; then
        print_warning "Installation cancelled"
        return
    fi
    
    # Create service file
    print_info "Creating service file..."
    cat > "$SERVICE_FILE" << EOF
# SPDX-License-Identifier: Apache-2.0
[Unit]
Description=Timelapse for Prusa
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 $SCRIPT_DIR/prusa_timelapse.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    print_success "Service file created: $SERVICE_FILE"
    echo ""
    
    # Copy to systemd
    print_info "Installing service to /etc/systemd/system/..."
    if sudo cp "$SERVICE_FILE" "/etc/systemd/system/$SERVICE_NAME"; then
        print_success "Service file installed"
    else
        print_error "Failed to install service file"
        return 1
    fi
    
    # Reload systemd
    print_info "Reloading systemd daemon..."
    if sudo systemctl daemon-reload; then
        print_success "Systemd daemon reloaded"
    else
        print_error "Failed to reload systemd daemon"
        return 1
    fi
    
    echo ""
    if prompt_yn "Enable service to start on boot?" "y"; then
        if sudo systemctl enable "$SERVICE_NAME"; then
            print_success "Service enabled"
        else
            print_error "Failed to enable service"
        fi
    fi
    
    echo ""
    if prompt_yn "Start service now?" "y"; then
        if sudo systemctl start "$SERVICE_NAME"; then
            print_success "Service started"
            echo ""
            print_info "View logs with: journalctl -u $SERVICE_NAME -f"
        else
            print_error "Failed to start service"
            echo ""
            print_info "Check status with: systemctl status $SERVICE_NAME"
        fi
    fi
    
    echo ""
    read -p "Press Enter to continue..."
}

# Option 5: Service status
service_status() {
    print_header "Service Status"
    
    sudo systemctl status "$SERVICE_NAME" --no-pager || true
    
    echo ""
    read -p "Press Enter to continue..."
}

# Option 6: Restart service
restart_service() {
    print_header "Restart Service"
    
    if prompt_yn "Restart $SERVICE_NAME?" "y"; then
        if sudo systemctl restart "$SERVICE_NAME"; then
            print_success "Service restarted"
            echo ""
            sudo systemctl status "$SERVICE_NAME" --no-pager || true
        else
            print_error "Failed to restart service"
        fi
    fi
    
    echo ""
    read -p "Press Enter to continue..."
}

# Option 7: Stop service
stop_service() {
    print_header "Stop Service"
    
    if prompt_yn "Stop $SERVICE_NAME?" "y"; then
        if sudo systemctl stop "$SERVICE_NAME"; then
            print_success "Service stopped"
        else
            print_error "Failed to stop service"
        fi
    fi
    
    echo ""
    read -p "Press Enter to continue..."
}

# Option 8: Disable service
disable_service() {
    print_header "Disable Service"
    
    print_warning "This will disable the service from starting on boot"
    print_warning "The service will also be stopped if currently running"
    echo ""
    
    if prompt_yn "Disable $SERVICE_NAME?" "n"; then
        sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        if sudo systemctl disable "$SERVICE_NAME"; then
            print_success "Service disabled"
        else
            print_error "Failed to disable service"
        fi
    fi
    
    echo ""
    read -p "Press Enter to continue..."
}

# Main loop
main() {
    while true; do
        show_menu
        read -p "$(echo -e "${WHITE}Select option${NC} [0-13]: ")" choice
        
        case "$choice" in
            1) install_prerequisites ;;
            2) check_dependencies ;;
            3) create_env_file ;;
            4) configure_focus_distance ;;
            5) send_test_email ;;
            6) capture_and_email_current_view ;;
            7) test_timelapse ;;
            8) upload_prusa_connect ;;
            9) configure_service ;;
            10) service_status ;;
            11) restart_service ;;
            12) stop_service ;;
            13) disable_service ;;
            0)
                echo ""
                print_info "Thank you for using Timelapse for Prusa!"
                echo ""
                exit 0
                ;;
            *)
                print_error "Invalid option: $choice"
                sleep 1
                ;;
        esac
    done
}

# Run main
main
