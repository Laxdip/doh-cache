#!/usr/bin/env python3
"""
Prasad's Advanced DOH Cache - Main Entry Point
DNS-over-HTTPS Cache Server with Advanced Features
"""

import os
import sys
import argparse
import yaml
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.server import DohCacheServer
from src.logger import get_logger
from src.utils import get_system_info, print_banner

def load_config(config_file: str = "config.yaml") -> dict:
    """
    Load configuration from YAML file
    
    Args:
        config_file: Path to configuration file
    
    Returns:
        Dictionary with configuration
    """
    default_config = {
        'server': {
            'host': '127.0.0.1',
            'port': 5353
        },
        'upstream': {
            'primary': 'https://cloudflare-dns.com/dns-query',
            'secondary': 'https://dns.google/dns-query',
            'timeout': 5
        },
        'cache': {
            'max_size': 1000,
            'default_ttl': 300,
            'max_ttl': 86400,
            'cleanup_interval': 60
        },
        'logging': {
            'level': 'INFO',
            'file': 'logs/doh-cache.log',
            'max_bytes': 10485760,
            'backup_count': 5
        },
        'features': {
            'prefetch': True,
            'ratelimit': 100,
            'blocklist': []
        }
    }
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                user_config = yaml.safe_load(f)
                # Merge configurations
                for key, value in user_config.items():
                    if key in default_config:
                        if isinstance(value, dict) and isinstance(default_config[key], dict):
                            default_config[key].update(value)
                        else:
                            default_config[key] = value
                    else:
                        default_config[key] = value
            print(f"✅ Loaded configuration from {config_file}")
        except Exception as e:
            print(f"⚠️  Warning: Failed to load config file: {e}")
    else:
        print(f"ℹ️  Config file {config_file} not found, using defaults")
    
    return default_config

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Prasad's Advanced DNS-over-HTTPS Cache Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings (localhost:5353)
  python run.py
  
  # Run on specific port with custom cache size
  python run.py --port 53 --cache-size 5000
  
  # Run with system DNS (requires admin/root)
  sudo python run.py --port 53 --host 0.0.0.0
  
  # Use custom config file
  python run.py --config my-config.yaml
  
  # Run with debug logging
  python run.py --debug
        """
    )
    
    parser.add_argument(
        '--host',
        type=str,
        help='Server host address (default: 127.0.0.1)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        help='Server port (default: 5353)'
    )
    
    parser.add_argument(
        '--cache-size',
        type=int,
        help='Maximum cache entries (default: 1000)'
    )
    
    parser.add_argument(
        '--ttl',
        type=int,
        help='Default TTL in seconds (default: 300)'
    )
    
    parser.add_argument(
        '--rate-limit',
        type=int,
        help='Max queries per second (default: 100)'
    )
    
    parser.add_argument(
        '--primary-doh',
        type=str,
        help='Primary DOH server URL'
    )
    
    parser.add_argument(
        '--secondary-doh',
        type=str,
        help='Secondary DOH server URL'
    )
    
    parser.add_argument(
        '--no-prefetch',
        action='store_true',
        help='Disable cache prefetching'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Configuration file path (default: config.yaml)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='Prasad\'s DOH Cache v1.0.0'
    )
    
    return parser.parse_args()

def main():
    """Main entry point"""
    # Parse arguments
    args = parse_arguments()
    
    # Load configuration
    config = load_config(args.config)
    
    # Override config with command line arguments
    host = args.host or config['server']['host']
    port = args.port or config['server']['port']
    cache_size = args.cache_size or config['cache']['max_size']
    default_ttl = args.ttl or config['cache']['default_ttl']
    rate_limit = args.rate_limit or config['features']['ratelimit']
    primary_doh = args.primary_doh or config['upstream']['primary']
    secondary_doh = args.secondary_doh or config['upstream']['secondary']
    enable_prefetch = not args.no_prefetch and config['features']['prefetch']
    timeout = config['upstream']['timeout']
    
    # Logging configuration
    log_level = 'DEBUG' if args.debug else config['logging']['level']
    log_file = config['logging']['file']
    max_bytes = config['logging']['max_bytes']
    backup_count = config['logging']['backup_count']
    
    # Initialize logger
    logger = get_logger(
        name="DOHCache",
        log_level=log_level,
        log_file=log_file
    )
    
    # Display system info
    sys_info = get_system_info()
    logger.info(f"System: {sys_info['os']} {sys_info['os_version']} ({sys_info['architecture']})")
    logger.info(f"Python: {sys_info['python_version']}")
    logger.info(f"Hostname: {sys_info['hostname']}")
    
    # Check for admin/root when using privileged port
    if port < 1024:
        if os.name == 'nt':  # Windows
            import ctypes
            if not ctypes.windll.shell32.IsUserAnAdmin():
                logger.warning(f"Port {port} requires administrator privileges!")
                logger.warning("Please run as Administrator")
                response = input("Continue anyway? (y/N): ")
                if response.lower() != 'y':
                    sys.exit(1)
        else:  # Linux/Mac
            if os.geteuid() != 0:
                logger.error(f"Port {port} requires root privileges!")
                logger.error(f"Please run: sudo python {sys.argv[0]}")
                sys.exit(1)
    
    # Create server instance
    server = DohCacheServer(
        host=host,
        port=port,
        primary_doh=primary_doh,
        secondary_doh=secondary_doh,
        cache_size=cache_size,
        default_ttl=default_ttl,
        rate_limit=rate_limit,
        enable_prefetch=enable_prefetch,
        timeout=timeout,
        workers=10
    )
    
    # Start server
    try:
        if server.start():
            # Keep main thread alive
            while server.running:
                import time
                time.sleep(1)
        else:
            logger.error("Failed to start server")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user")
        server.stop()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        server.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()
