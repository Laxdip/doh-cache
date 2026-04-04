#!/bin/bash
# ============================================================================
# Prasad's Advanced DOH Cache - Installer for Linux & macOS
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored message
print_message() {
    echo -e "${2}${1}${NC}"
}

# Print banner
print_banner() {
    print_message "╔═════════════════════════════════════════════════════════════════════════╗" "$BLUE"
    print_message "║                                                                         ║" "$BLUE"
    print_message "║  ██████╗  ██████╗ ██╗  ██╗      ██████╗ █████╗  ██████╗██╗  ██╗███████╗ ║" "$BLUE"
    print_message "║  ██╔══██╗██╔═══██╗██║  ██║     ██╔════╝██╔══██╗██╔════╝██║  ██║██╔════╝ ║" "$BLUE"
    print_message "║  ██║  ██║██║   ██║███████║     ██║     ███████║██║     ███████║█████╗   ║" "$BLUE"
    print_message "║  ██║  ██║██║   ██║██╔══██║     ██║     ██╔══██║██║     ██╔══██║██╔══╝   ║" "$BLUE"
    print_message "║  ██████╔╝╚██████╔╝██║  ██║     ╚██████╗██║  ██║╚██████╗██║  ██║███████╗ ║" "$BLUE"
    print_message "║  ╚═════╝  ╚═════╝ ╚═╝  ╚═╝      ╚═════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝ ║" "$BLUE"
    print_message "║                                                                         ║" "$BLUE"
    print_message "║           Advanced DNS-over-HTTPS Cache Installer                       ║" "$BLUE"
    print_message "║                    Created by Prasad                                    ║" "$BLUE"
    print_message "╚═════════════════════════════════════════════════════════════════════════╝" "$BLUE"
    echo ""
}

# Check Python version
check_python() {
    print_message "🔍 Checking Python installation..." "$YELLOW"
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        MAJOR_VERSION=$(echo $PYTHON_VERSION | cut -d'.' -f1)
        MINOR_VERSION=$(echo $PYTHON_VERSION | cut -d'.' -f2)
        
        if [ "$MAJOR_VERSION" -ge 3 ] && [ "$MINOR_VERSION" -ge 7 ]; then
            print_message "✅ Python $PYTHON_VERSION found" "$GREEN"
        else
            print_message "❌ Python 3.7+ required (found $PYTHON_VERSION)" "$RED"
            exit 1
        fi
    else
        print_message "❌ Python 3 not found. Please install Python 3.7 or higher" "$RED"
        exit 1
    fi
}

# Check pip
check_pip() {
    print_message "🔍 Checking pip..." "$YELLOW"
    
    if command -v pip3 &> /dev/null; then
        print_message "✅ pip3 found" "$GREEN"
    else
        print_message "⚠️  pip3 not found, installing..." "$YELLOW"
        python3 -m ensurepip --upgrade
    fi
}

# Create virtual environment (optional)
setup_venv() {
    print_message "🔧 Setting up virtual environment..." "$YELLOW"
    
    read -p "Do you want to use a virtual environment? (y/n): " use_venv
    if [[ $use_venv == "y" || $use_venv == "Y" ]]; then
        if command -v python3 -m venv &> /dev/null; then
            python3 -m venv venv
            print_message "✅ Virtual environment created" "$GREEN"
            
            # Activate based on OS
            if [[ "$OSTYPE" == "darwin"* ]] || [[ "$OSTYPE" == "linux-gnu"* ]]; then
                source venv/bin/activate
                print_message "✅ Virtual environment activated" "$GREEN"
            fi
        else
            print_message "⚠️  venv module not available, installing globally" "$YELLOW"
        fi
    else
        print_message "ℹ️  Installing globally" "$YELLOW"
    fi
}

# Install dependencies
install_dependencies() {
    print_message "📦 Installing Python dependencies..." "$YELLOW"
    
    if [ -f "requirements.txt" ]; then
        pip3 install --upgrade pip
        pip3 install -r requirements.txt
        print_message "✅ Dependencies installed successfully" "$GREEN"
    else
        print_message "❌ requirements.txt not found!" "$RED"
        exit 1
    fi
}

# Create directories
create_directories() {
    print_message "📁 Creating directories..." "$YELLOW"
    
    mkdir -p logs
    mkdir -p data
    
    print_message "✅ Directories created" "$GREEN"
}

# Create systemd service (Linux only)
create_systemd_service() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        print_message "🔧 Setting up systemd service..." "$YELLOW"
        
        read -p "Do you want to install as a systemd service? (y/n): " install_service
        if [[ $install_service == "y" || $install_service == "Y" ]]; then
            CURRENT_DIR=$(pwd)
            CURRENT_USER=$(whoami)
            
            sudo tee /etc/systemd/system/doh-cache.service > /dev/null <<EOF
[Unit]
Description=Prasad's Advanced DOH Cache
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
ExecStart=/usr/bin/python3 $CURRENT_DIR/run.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
            
            sudo systemctl daemon-reload
            print_message "✅ Systemd service created" "$GREEN"
            print_message "   Commands:" "$YELLOW"
            print_message "   - Start: sudo systemctl start doh-cache" "$NC"
            print_message "   - Stop: sudo systemctl stop doh-cache" "$NC"
            print_message "   - Status: sudo systemctl status doh-cache" "$NC"
            print_message "   - Enable at boot: sudo systemctl enable doh-cache" "$NC"
        fi
    fi
}

# Create launchd service (macOS only)
create_launchd_service() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        print_message "🔧 Setting up launchd service..." "$YELLOW"
        
        read -p "Do you want to install as a launchd service? (y/n): " install_service
        if [[ $install_service == "y" || $install_service == "Y" ]]; then
            CURRENT_DIR=$(pwd)
            CURRENT_USER=$(whoami)
            PLIST_FILE="$HOME/Library/LaunchAgents/com.prasad.doh-cache.plist"
            
            mkdir -p "$HOME/Library/LaunchAgents"
            
            cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.prasad.doh-cache</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$CURRENT_DIR/run.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$CURRENT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$CURRENT_DIR/logs/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$CURRENT_DIR/logs/stderr.log</string>
</dict>
</plist>
EOF
            
            launchctl load "$PLIST_FILE"
            print_message "✅ Launchd service created" "$GREEN"
            print_message "   Commands:" "$YELLOW"
            print_message "   - Start: launchctl start com.prasad.doh-cache" "$NC"
            print_message "   - Stop: launchctl stop com.prasad.doh-cache" "$NC"
            print_message "   - Unload: launchctl unload $PLIST_FILE" "$NC"
        fi
    fi
}

# Test installation
test_installation() {
    print_message "🧪 Testing installation..." "$YELLOW"
    
    # Quick test to see if imports work
    python3 -c "import dns, httpx, yaml, cachetools" 2>/dev/null
    if [ $? -eq 0 ]; then
        print_message "✅ All modules imported successfully" "$GREEN"
    else
        print_message "⚠️  Some modules may be missing" "$YELLOW"
    fi
}

# Show next steps
show_next_steps() {
    echo ""
    print_message "╔══════════════════════════════════════════════════════════════╗" "$GREEN"
    print_message "║                    INSTALLATION COMPLETE!                    ║" "$GREEN"
    print_message "╚══════════════════════════════════════════════════════════════╝" "$GREEN"
    echo ""
    print_message "Next steps:" "$YELLOW"
    echo ""
    print_message "1. Configure your DNS settings:" "$NC"
    print_message "   - Edit config.yaml to customize settings" "$NC"
    print_message "   - Set your system DNS to 127.0.0.1:$DNS_PORT" "$NC"
    echo ""
    print_message "2. Run the server:" "$NC"
    print_message "   python3 run.py" "$NC"
    echo ""
    print_message "3. Or run with options:" "$NC"
    print_message "   python3 run.py --port 53 --cache-size 5000" "$NC"
    echo ""
    print_message "4. For systemd (Linux):" "$NC"
    print_message "   sudo systemctl start doh-cache" "$NC"
    echo ""
    print_message "5. Check logs:" "$NC"
    print_message "   tail -f logs/doh-cache.log" "$NC"
    echo ""
    print_message "6. Test with dig:" "$NC"
    print_message "   dig @127.0.0.1 -p $DNS_PORT google.com" "$NC"
    echo ""
}

# Main installation flow
main() {
    clear
    print_banner
    
    DNS_PORT=${1:-5353}
    
    check_python
    check_pip
    setup_venv
    install_dependencies
    create_directories
    test_installation
    create_systemd_service
    create_launchd_service
    show_next_steps
}

# Run main function with port argument
main $1