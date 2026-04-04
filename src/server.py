"""
Main DNS Server for Prasad's DOH Cache
Handles UDP DNS queries, caching, and DOH resolution
"""

import socket
import threading
import time
import signal
import sys
from typing import Tuple, Optional
import dns.message
import dns.query
import dns.rdatatype
from concurrent.futures import ThreadPoolExecutor

from .cache import AdvancedCache
from .resolver import DOHResolver
from .logger import get_logger, get_request_logger
from .utils import check_port_available, RateLimiter, get_local_ip, print_banner

logger = get_logger()
request_logger = None

class DohCacheServer:
    """Main DNS-over-HTTPS Cache Server"""
    
    def __init__(self, host: str = '127.0.0.1', port: int = 5353,
                 primary_doh: str = "https://cloudflare-dns.com/dns-query",
                 secondary_doh: Optional[str] = "https://dns.google/dns-query",
                 cache_size: int = 1000, default_ttl: int = 300,
                 rate_limit: int = 100, enable_prefetch: bool = True,
                 timeout: int = 5, workers: int = 10):
        """
        Initialize DOH Cache Server
        
        Args:
            host: Server bind address
            port: Server port
            primary_doh: Primary DOH server URL
            secondary_doh: Secondary DOH server URL
            cache_size: Maximum cache entries
            default_ttl: Default TTL in seconds
            rate_limit: Max queries per second per IP
            enable_prefetch: Enable prefetching
            timeout: Resolution timeout
            workers: Number of worker threads
        """
        self.host = host
        self.port = port
        self.workers = workers
        self.running = False
        self.socket = None
        
        # Initialize components
        self.cache = AdvancedCache(
            max_size=cache_size,
            default_ttl=default_ttl,
            enable_prefetch=enable_prefetch,
            cleanup_interval=60
        )
        
        self.resolver = DOHResolver(
            primary_url=primary_doh,
            secondary_url=secondary_doh,
            timeout=timeout,
            max_retries=2
        )
        
        self.rate_limiter = RateLimiter(rate_limit, time_window=1)
        
        # Thread pool for handling requests
        self.executor = ThreadPoolExecutor(max_workers=workers)
        
        # Statistics
        self.stats = {
            'start_time': time.time(),
            'total_queries': 0,
            'successful_responses': 0,
            'failed_responses': 0,
            'rate_limited': 0,
            'invalid_queries': 0
        }
        
        logger.info(f"Server initialized: {host}:{port}")
        logger.info(f"Cache size: {cache_size}, Rate limit: {rate_limit}/s, Workers: {workers}")
    
    def start(self):
        """Start the DNS server"""
        global request_logger
        request_logger = get_request_logger(logger)
        
        # Check if port is available
        if not check_port_available(self.host, self.port):
            logger.error(f"Port {self.port} is already in use!")
            return False
        
        try:
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.settimeout(1)  # Timeout for graceful shutdown
            
            self.running = True
            
            # Setup signal handlers
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            # Display banner
            print_banner()
            
            local_ip = get_local_ip()
            logger.info(f"\n{'='*60}")
            logger.info(f"✅ DOH Cache Server Started Successfully!")
            logger.info(f"📍 Listening on: {self.host}:{self.port}")
            logger.info(f"🌐 Local network: {local_ip}:{self.port}")
            logger.info(f"💾 Cache: {self.cache.max_size} entries (LRU + TTL)")
            logger.info(f"🚀 Upstream: {self.resolver.primary_url}")
            if self.resolver.secondary_url:
                logger.info(f"🔄 Fallback: {self.resolver.secondary_url}")
            logger.info(f"{'='*60}\n")
            
            # Main loop
            while self.running:
                try:
                    data, addr = self.socket.recvfrom(512)  # Max DNS size
                    # Handle request in thread pool
                    self.executor.submit(self._handle_request, data, addr)
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        logger.error(f"Socket error: {e}")
            
            return True
            
        except PermissionError:
            logger.error(f"Permission denied to bind to port {self.port}. "
                        f"On Linux/Mac try: sudo python run.py, or use port > 1024")
            return False
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            return False
    
    def _handle_request(self, data: bytes, addr: Tuple[str, int]):
        """
        Handle incoming DNS request
        
        Args:
            data: DNS query data
            addr: Client address (ip, port)
        """
        client_ip = addr[0]
        
        # Rate limiting
        if not self.rate_limiter.allow_request():
            self.stats['rate_limited'] += 1
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return
        
        self.stats['total_queries'] += 1
        
        try:
            # Parse DNS query
            try:
                query = dns.message.from_wire(data)
            except Exception as e:
                logger.warning(f"Invalid DNS query from {client_ip}: {e}")
                self.stats['invalid_queries'] += 1
                return
            
            # Extract query info
            if len(query.question) == 0:
                logger.warning(f"No question in DNS query from {client_ip}")
                return
            
            question = query.question[0]
            domain = str(question.name).rstrip('.')
            record_type = dns.rdatatype.to_text(question.rdtype)
            
            # Log request
            request_logger.log_request(domain, record_type, client_ip)
            
            # Check cache first
            cached_ips = self.cache.get(domain, record_type)
            
            if cached_ips:
                # Cache hit
                entry = None
                for e in self.cache.get_all_entries():
                    if e['domain'] == domain and e['type'] == record_type:
                        entry = e
                        break
                
                remaining_ttl = entry['remaining_ttl'] if entry else 0
                request_logger.log_cache_hit(domain, record_type, cached_ips, remaining_ttl)
                
                # Build response from cache
                response = self._build_dns_response(query, domain, cached_ips, record_type, remaining_ttl)
                self.socket.sendto(response, addr)
                self.stats['successful_responses'] += 1
                return
            
            # Cache miss - resolve via DOH
            request_logger.log_cache_miss(domain, record_type)
            
            ips, ttl = self.resolver.resolve(domain, record_type)
            
            if ips:
                # Successfully resolved
                request_logger.log_resolution(domain, record_type, ips, ttl or 300, 'DOH')
                
                # Store in cache
                self.cache.set(domain, ips, record_type, ttl)
                
                # Build response
                response = self._build_dns_response(query, domain, ips, record_type, ttl or 300)
                self.socket.sendto(response, addr)
                self.stats['successful_responses'] += 1
            else:
                # Resolution failed
                request_logger.log_error(domain, record_type, "No response from upstream")
                self.stats['failed_responses'] += 1
                
                # Send empty response (SERVFAIL)
                response = self._build_error_response(query)
                self.socket.sendto(response, addr)
                
        except Exception as e:
            logger.error(f"Error handling request from {client_ip}: {e}")
            self.stats['failed_responses'] += 1
    
    def _build_dns_response(self, query: dns.message.Message, domain: str,
                           ips: list, record_type: str, ttl: int) -> bytes:
        """
        Build DNS response from resolved IPs
        
        Args:
            query: Original DNS query
            domain: Domain name
            ips: List of IP addresses
            record_type: DNS record type
            ttl: Time to live in seconds
        
        Returns:
            DNS response as bytes
        """
        response = dns.message.make_response(query)
        response.flags |= dns.flags.AA  # Authoritative Answer
        
        # Get record type as integer
        rdtype = getattr(dns.rdatatype, record_type, dns.rdatatype.A)
        
        # Add answer records
        for ip in ips:
            try:
                if record_type == 'A':
                    import ipaddress
                    ip_obj = ipaddress.ip_address(ip)
                    if ip_obj.version == 4:
                        rd = dns.rdtypes.IN.A.A(rdtype, dns.rdataclass.IN, ttl, ip)
                        response.answer.append(dns.rrset.from_rdata(domain, ttl, rd))
                elif record_type == 'AAAA':
                    import ipaddress
                    ip_obj = ipaddress.ip_address(ip)
                    if ip_obj.version == 6:
                        rd = dns.rdtypes.IN.AAAA.AAAA(rdtype, dns.rdataclass.IN, ttl, ip)
                        response.answer.append(dns.rrset.from_rdata(domain, ttl, rd))
                else:
                    # Generic record (should not happen for A/AAAA)
                    pass
            except Exception as e:
                logger.warning(f"Failed to add IP {ip} to response: {e}")
        
        return response.to_wire()
    
    def _build_error_response(self, query: dns.message.Message) -> bytes:
        """Build error response (SERVFAIL)"""
        response = dns.message.make_response(query)
        response.flags |= dns.flags.AA
        response.set_rcode(dns.rcode.SERVFAIL)
        return response.to_wire()
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"\nReceived signal {signum}, shutting down...")
        self.stop()
    
    def stop(self):
        """Stop the server gracefully"""
        logger.info("Stopping DOH Cache Server...")
        self.running = False
        
        if self.socket:
            self.socket.close()
        
        self.executor.shutdown(wait=True)
        self.cache.shutdown()
        self.resolver.close()
        
        # Print final statistics
        uptime = time.time() - self.stats['start_time']
        logger.info(f"\n{'='*50}")
        logger.info("FINAL STATISTICS:")
        logger.info(f"Uptime: {uptime:.1f} seconds")
        logger.info(f"Total queries: {self.stats['total_queries']}")
        logger.info(f"Successful: {self.stats['successful_responses']}")
        logger.info(f"Failed: {self.stats['failed_responses']}")
        logger.info(f"Rate limited: {self.stats['rate_limited']}")
        logger.info(f"Invalid queries: {self.stats['invalid_queries']}")
        
        cache_stats = self.cache.get_stats()
        logger.info(f"Cache hits: {cache_stats['hits']}")
        logger.info(f"Cache misses: {cache_stats['misses']}")
        logger.info(f"Cache hit rate: {cache_stats['hit_rate_percent']}%")
        logger.info(f"Cache size: {cache_stats['current_size']}/{cache_stats['max_size']}")
        
        resolver_stats = self.resolver.get_stats()
        logger.info(f"Resolver success rate: {resolver_stats['success_rate_percent']}%")
        logger.info(f"Avg response time: {resolver_stats['avg_response_time_ms']}ms")
        
        if request_logger:
            req_stats = request_logger.get_stats()
            logger.info(f"Request cache hit rate: {req_stats['hit_rate']}%")
        
        logger.info(f"{'='*50}")
        logger.info("Server stopped. Goodbye!")
    
    def get_stats(self) -> dict:
        """Get server statistics"""
        return {
            'server': self.stats,
            'cache': self.cache.get_stats(),
            'resolver': self.resolver.get_stats(),
            'requests': request_logger.get_stats() if request_logger else {}
        }