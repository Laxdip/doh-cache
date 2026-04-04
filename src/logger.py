"""
Advanced Logging System for Prasad's DOH Cache
Features: Colored output, log rotation, file & console handlers, cross-platform
"""

import os
import sys
import logging
import logging.handlers
from datetime import datetime
from typing import Optional
import platform

# Try to import colorama for Windows support
try:
    if platform.system() == "Windows":
        import colorama
        colorama.init()
        COLORS_SUPPORTED = True
    else:
        COLORS_SUPPORTED = True
except ImportError:
    COLORS_SUPPORTED = False

# ANSI color codes
class LogColors:
    """Log level colors"""
    RESET = '\033[0m'
    DEBUG = '\033[36m'      # Cyan
    INFO = '\033[32m'       # Green
    WARNING = '\033[33m'    # Yellow
    ERROR = '\033[31m'      # Red
    CRITICAL = '\033[35m'   # Magenta
    BOLD = '\033[1m'
    
    # Time stamp color
    TIME = '\033[90m'       # Bright Black (Gray)

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output"""
    
    def __init__(self, fmt: str, datefmt: str = None, use_colors: bool = True):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and COLORS_SUPPORTED
        
        # Color mapping for log levels
        self.level_colors = {
            logging.DEBUG: LogColors.DEBUG,
            logging.INFO: LogColors.INFO,
            logging.WARNING: LogColors.WARNING,
            logging.ERROR: LogColors.ERROR,
            logging.CRITICAL: LogColors.CRITICAL
        }
    
    def format(self, record: logging.LogRecord) -> str:
        # Save original values
        original_levelname = record.levelname
        original_msg = record.msg
        
        if self.use_colors:
            # Add colors to level name
            color = self.level_colors.get(record.levelno, LogColors.RESET)
            record.levelname = f"{color}{original_levelname}{LogColors.RESET}"
            
            # Add colors to message based on level
            if record.levelno >= logging.ERROR:
                record.msg = f"{LogColors.ERROR}{original_msg}{LogColors.RESET}"
            elif record.levelno == logging.WARNING:
                record.msg = f"{LogColors.WARNING}{original_msg}{LogColors.RESET}"
        
        # Format the log message
        result = super().format(record)
        
        # Restore original values
        record.levelname = original_levelname
        record.msg = original_msg
        
        return result

class PlainFormatter(logging.Formatter):
    """Plain formatter for file output (no colors)"""
    
    def __init__(self, fmt: str, datefmt: str = None):
        super().__init__(fmt, datefmt)
    
    def format(self, record: logging.LogRecord) -> str:
        # Ensure no color codes in file
        result = super().format(record)
        # Strip ANSI codes for file output
        import re
        result = re.sub(r'\x1b\[[0-9;]*m', '', result)
        return result

class CustomLogger:
    """Custom logger with advanced features"""
    
    _instances = {}  # Singleton instances
    
    def __new__(cls, name: str = "DOHCache", *args, **kwargs):
        """Singleton pattern to avoid duplicate loggers"""
        if name not in cls._instances:
            cls._instances[name] = super().__new__(cls)
        return cls._instances[name]
    
    def __init__(self, name: str = "DOHCache", log_level: str = "INFO", 
                 log_file: Optional[str] = None, max_bytes: int = 10485760, 
                 backup_count: int = 5, console_output: bool = True):
        """
        Initialize custom logger
        
        Args:
            name: Logger name
            log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Path to log file (optional)
            max_bytes: Maximum log file size before rotation
            backup_count: Number of backup files to keep
            console_output: Whether to output to console
        """
        # Avoid re-initialization
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Remove existing handlers
        self.logger.handlers.clear()
        
        # Create formatters
        console_format = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
        file_format = '%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'
        
        # Console handler with colors
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, log_level.upper()))
            console_formatter = ColoredFormatter(console_format, date_format)
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
        
        # File handler with rotation
        if log_file:
            # Create log directory if it doesn't exist
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            
            # Rotating file handler
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)  # Always log DEBUG to file
            file_formatter = PlainFormatter(file_format, date_format)
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        
        # Add error file handler for errors only
        if log_file:
            error_log_file = log_file.replace('.log', '_error.log')
            error_handler = logging.handlers.RotatingFileHandler(
                error_log_file, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_formatter = PlainFormatter(file_format, date_format)
            error_handler.setFormatter(error_formatter)
            self.logger.addHandler(error_handler)
        
        self.logger.info(f"Logger initialized - Level: {log_level}, File: {log_file}")
    
    def debug(self, message: str, *args, **kwargs):
        self.logger.debug(message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        self.logger.info(message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        self.logger.warning(message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        self.logger.error(message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        self.logger.critical(message, *args, **kwargs)
    
    def exception(self, message: str, *args, **kwargs):
        self.logger.exception(message, *args, **kwargs)
    
    def log_with_context(self, level: str, message: str, context: dict = None):
        """Log with additional context dictionary"""
        if context:
            context_str = " | ".join([f"{k}={v}" for k, v in context.items()])
            message = f"{message} | {context_str}"
        
        getattr(self, level.lower())(message)
    
    def get_stats(self) -> dict:
        """Get logger statistics"""
        return {
            'name': self.logger.name,
            'level': logging.getLevelName(self.logger.level),
            'handlers': len(self.logger.handlers),
            'enabled': not self.logger.disabled
        }

class RequestLogger:
    """Specialized logger for DNS request/response logging"""
    
    def __init__(self, parent_logger: CustomLogger):
        self.logger = parent_logger
        self.request_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
    
    def log_request(self, domain: str, record_type: str, client_ip: str):
        """Log incoming DNS request"""
        self.request_count += 1
        self.logger.debug(
            f"DNS Request #{self.request_count}",
            extra={
                'domain': domain,
                'type': record_type,
                'client': client_ip
            }
        )
        self.logger.log_with_context(
            'debug',
            f"DNS request received",
            {'domain': domain, 'type': record_type, 'client': client_ip, 'req_id': self.request_count}
        )
    
    def log_cache_hit(self, domain: str, record_type: str, ips: list, remaining_ttl: int):
        """Log cache hit"""
        self.cache_hits += 1
        self.logger.log_with_context(
            'debug',
            f"CACHE HIT: {domain}",
            {
                'type': record_type,
                'ips': ','.join(ips),
                'remaining_ttl': remaining_ttl,
                'hit_rate': self.get_hit_rate()
            }
        )
    
    def log_cache_miss(self, domain: str, record_type: str):
        """Log cache miss"""
        self.cache_misses += 1
        self.logger.log_with_context(
            'debug',
            f"CACHE MISS: {domain}",
            {'type': record_type, 'miss_rate': self.get_miss_rate()}
        )
    
    def log_resolution(self, domain: str, record_type: str, ips: list, ttl: int, source: str):
        """Log successful resolution"""
        self.logger.log_with_context(
            'info',
            f"Resolved {domain} -> {', '.join(ips)}",
            {'type': record_type, 'ttl': ttl, 'source': source, 'ips_count': len(ips)}
        )
    
    def log_error(self, domain: str, record_type: str, error: str):
        """Log resolution error"""
        self.logger.log_with_context(
            'warning',
            f"Failed to resolve {domain}",
            {'type': record_type, 'error': error}
        )
    
    def get_hit_rate(self) -> float:
        """Get cache hit rate"""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return round((self.cache_hits / total) * 100, 2)
    
    def get_miss_rate(self) -> float:
        """Get cache miss rate"""
        return round(100 - self.get_hit_rate(), 2)
    
    def get_stats(self) -> dict:
        """Get request statistics"""
        return {
            'total_requests': self.request_count,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': self.get_hit_rate(),
            'miss_rate': self.get_miss_rate()
        }

# Global logger instance
_default_logger = None

def get_logger(name: str = "DOHCache", log_level: str = "INFO", 
               log_file: Optional[str] = "logs/doh-cache.log") -> CustomLogger:
    """Get or create default logger instance"""
    global _default_logger
    if _default_logger is None or _default_logger.logger.name != name:
        _default_logger = CustomLogger(name, log_level, log_file)
    return _default_logger

def get_request_logger(parent_logger: CustomLogger = None) -> RequestLogger:
    """Get request logger instance"""
    if parent_logger is None:
        parent_logger = get_logger()
    return RequestLogger(parent_logger)