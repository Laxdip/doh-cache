"""
Utility functions for Prasad's Advanced DOH Cache
Cross-platform compatible (Windows, Linux, macOS)
"""

import os
import sys
import socket
import platform
from datetime import datetime
from typing import Optional, Tuple

# Color codes for terminal output (Windows compatible)
class Colors:
    """ANSI color codes with Windows fallback"""
    if platform.system() == "Windows":
        # Disable colors on Windows by default (can be enabled with colorama)
        HEADER = ''
        OKBLUE = ''
        OKCYAN = ''
        OKGREEN = ''
        WARNING = ''
        FAIL = ''
        ENDC = ''
        BOLD = ''
        UNDERLINE = ''
    else:
        HEADER = '\033[95m'
        OKBLUE = '\033[94m'
        OKCYAN = '\033[96m'
        OKGREEN = '\033[92m'
        WARNING = '\033[93m'
        FAIL = '\033[91m'
        ENDC = '\033[0m'
        BOLD = '\033[1m'
        UNDERLINE = '\033[4m'

def print_banner():
    """Display Prasad's DOH Cache banner"""
    banner = f"""
{Colors.HEADER}{Colors.BOLD}
╔═════════════════════════════════════════════════════════════════════════╗
║                                                                         ║
║  ██████╗  ██████╗ ██╗  ██╗      ██████╗ █████╗  ██████╗██╗  ██╗███████╗ ║
║  ██╔══██╗██╔═══██╗██║  ██║     ██╔════╝██╔══██╗██╔════╝██║  ██║██╔════╝ ║
║  ██║  ██║██║   ██║███████║     ██║     ███████║██║     ███████║█████╗   ║
║  ██║  ██║██║   ██║██╔══██║     ██║     ██╔══██║██║     ██╔══██║██╔══╝   ║
║  ██████╔╝╚██████╔╝██║  ██║     ╚██████╗██║  ██║╚██████╗██║  ██║███████╗ ║
║  ╚═════╝  ╚═════╝ ╚═╝  ╚═╝      ╚═════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝ ║
║                                                                         ║
║           Advanced DNS-over-HTTPS Cache v1.0.0                          ║
║                    Created by Prasad                                    ║
║                                                                         ║
╚═════════════════════════════════════════════════════════════════════════╝
{Colors.ENDC}
"""
    print(banner)

def check_port_available(host: str, port: int) -> bool:
    """Check if port is available for binding"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            return True
    except OSError:
        return False

def get_local_ip() -> str:
    """Get local machine's IP address"""
    try:
        # Create a socket to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def validate_domain(domain: str) -> bool:
    """Basic domain name validation"""
    if not domain or len(domain) > 253:
        return False
    
    # Check for valid characters
    allowed = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_')
    if not all(c in allowed for c in domain):
        return False
    
    # Check label length
    labels = domain.split('.')
    for label in labels:
        if not label or len(label) > 63:
            return False
    
    return True

def format_bytes(size: int) -> str:
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

def get_system_info() -> dict:
    """Get system information for diagnostics"""
    return {
        'os': platform.system(),
        'os_version': platform.release(),
        'python_version': sys.version.split()[0],
        'architecture': platform.machine(),
        'hostname': socket.gethostname()
    }

def timestamp() -> str:
    """Get formatted timestamp"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

class RateLimiter:
    """Simple rate limiter for query control"""
    def __init__(self, max_requests: int, time_window: int = 1):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    def allow_request(self) -> bool:
        """Check if request is allowed under rate limit"""
        import time
        now = time.time()
        
        # Clean old requests
        self.requests = [t for t in self.requests if t > now - self.time_window]
        
        # Check limit
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        return False
    
    def get_remaining(self) -> int:
        """Get remaining allowed requests in current window"""
        import time
        now = time.time()
        self.requests = [t for t in self.requests if t > now - self.time_window]
        return max(0, self.max_requests - len(self.requests))
