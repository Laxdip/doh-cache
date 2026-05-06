"""
DNS-over-HTTPS Resolver for Prasad's DOH Cache
Supports multiple upstream providers with failover and timeout handling
"""

import json
import time
import logging
import httpx
import dns.message
import dns.rdatatype
import dns.rdataclass
import dns.resolver
from typing import List, Optional, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import socket

logger = logging.getLogger(__name__)

class DOHResolver:
    """DNS-over-HTTPS resolver with multiple upstream support"""
    
    def __init__(self, primary_url: str, secondary_url: Optional[str] = None, 
                 timeout: int = 5, max_retries: int = 2):
        """
        Initialize DOH resolver
        
        Args:
            primary_url: Primary DOH server URL (e.g., https://cloudflare-dns.com/dns-query)
            secondary_url: Secondary DOH server for failover
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.primary_url = primary_url
        self.secondary_url = secondary_url
        self.timeout = timeout
        self.max_retries = max_retries
        
        # HTTP client with connection pooling
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
            http2=True,  # Enable HTTP/2 for better performance
            follow_redirects=True
        )
        
        # Statistics
        self.stats = {
            'primary_queries': 0,
            'secondary_queries': 0,
            'primary_success': 0,
            'secondary_success': 0,
            'failures': 0,
            'total_response_time': 0
        }
        
        logger.info(f"DOH Resolver initialized: primary={primary_url}, secondary={secondary_url}")
    
    def resolve(self, domain: str, record_type: str = 'A') -> Tuple[Optional[List[str]], Optional[int]]:
        """
        Resolve domain using DOH
        
        Args:
            domain: Domain name to resolve
            record_type: DNS record type (A, AAAA, etc.)
        
        Returns:
            Tuple of (list of IP addresses, TTL in seconds) or (None, None) on failure
        """
        start_time = time.time()
        
        # Convert record type to DNS format
        rdtype = self._get_rdtype(record_type)
        
        # Build DNS query
        try:
            query = dns.message.make_query(domain, rdtype, want_dnssec=False)
            query_data = query.to_wire()
        except Exception as e:
            logger.error(f"Failed to build DNS query for {domain}: {e}")
            self.stats['failures'] += 1
            return None, None
        
        # Try primary first
        result, ttl = self._query_doh(self.primary_url, query_data, domain)
        self.stats['primary_queries'] += 1
        
        if result:
            self.stats['primary_success'] += 1
            response_time = time.time() - start_time
            self.stats['total_response_time'] += response_time
            logger.debug(f"Resolved {domain} ({record_type}) via primary in {response_time:.3f}s: {result}")
            return result, ttl
        
        # Try secondary if available and primary failed
        if self.secondary_url:
            self.stats['secondary_queries'] += 1
            result, ttl = self._query_doh(self.secondary_url, query_data, domain, retry=False)
            
            if result:
                self.stats['secondary_success'] += 1
                response_time = time.time() - start_time
                self.stats['total_response_time'] += response_time
                logger.info(f"Resolved {domain} via secondary (primary failed) in {response_time:.3f}s")
                return result, ttl
        
        # Both failed
        self.stats['failures'] += 1
        logger.warning(f"Failed to resolve {domain} ({record_type}) from all upstreams")
        return None, None
    
    def _query_doh(self, url: str, query_data: bytes, domain: str, 
                   retry: bool = True) -> Tuple[Optional[List[str]], Optional[int]]:
        """
        Perform DOH query to specific server
        
        Args:
            url: DOH server URL
            query_data: DNS query in wire format
            domain: Original domain name (for logging)
            retry: Whether to retry on failure
        
        Returns:
            Tuple of (IP addresses list, TTL) or (None, None)
        """
        headers = {
            'Content-Type': 'application/dns-message',
            'Accept': 'application/dns-message'
        }
        
        for attempt in range(self.max_retries if retry else 1):
            try:
                response = self.client.post(
                    url,
                    content=query_data,
                    headers=headers
                )
                
                if response.status_code != 200:
                    logger.warning(f"DOH query to {url} returned {response.status_code} for {domain}")
                    continue
                
                # Parse DNS response
                try:
                    dns_response = dns.message.from_wire(response.content)
                    ips, ttl = self._extract_answers(dns_response, domain)
                    
                    if ips:
                        return ips, ttl
                    else:
                        logger.debug(f"No answers for {domain} from {url}")
                        return None, None
                        
                except Exception as e:
                    logger.error(f"Failed to parse DNS response for {domain}: {e}")
                    continue
                    
            except httpx.TimeoutException:
                logger.warning(f"Timeout querying {url} for {domain} (attempt {attempt + 1})")
            except httpx.RequestError as e:
                logger.warning(f"Request error to {url} for {domain}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error querying {url}: {e}")
            
            # Small delay before retry
            if attempt < self.max_retries - 1:
                time.sleep(0.1 * (attempt + 1))
        
        return None, None
    
    def _extract_answers(self, dns_response, domain: str) -> Tuple[List[str], int]:
        """
        Extract IP addresses and TTL from DNS response
        
        Args:
            dns_response: DNS message object
            domain: Original domain name
        
        Returns:
            Tuple of (list of IP addresses, minimum TTL)
        """
        ips = []
        ttl_values = []
        
        for answer in dns_response.answer:
            for rr in answer:
                # Check if it's an A or AAAA record
                if rr.rdtype == dns.rdatatype.A:
                    ips.append(str(rr.address))
                    ttl_values.append(rr.ttl)
                elif rr.rdtype == dns.rdatatype.AAAA:
                    ips.append(str(rr.address))
                    ttl_values.append(rr.ttl)
                elif rr.rdtype == dns.rdatatype.CNAME:
                    # Handle CNAME (can add follow-up resolution if needed)
                    logger.debug(f"Got CNAME for {domain}: {rr.target}")
        
        # Use minimum TTL for safety
        min_ttl = min(ttl_values) if ttl_values else 300
        
        return ips, min_ttl
    
    def _get_rdtype(self, record_type: str):
        """Convert string record type to DNS rdatatype"""
        record_map = {
            'A': dns.rdatatype.A,
            'AAAA': dns.rdatatype.AAAA,
            'CNAME': dns.rdatatype.CNAME,
            'MX': dns.rdatatype.MX,
            'TXT': dns.rdatatype.TXT,
            'NS': dns.rdatatype.NS,
            'PTR': dns.rdatatype.PTR,
            'SOA': dns.rdatatype.SOA
        }
        return record_map.get(record_type.upper(), dns.rdatatype.A)
    
    def resolve_with_fallback(self, domain: str, record_type: str = 'A') -> Optional[List[str]]:
        """
        Resolve with local DNS as ultimate fallback
        
        Args:
            domain: Domain name
            record_type: Record type
        
        Returns:
            List of IP addresses or None
        """
        # Try DOH first
        ips, _ = self.resolve(domain, record_type)
        if ips:
            return ips
        
        # Fallback to system DNS
        logger.info(f"Using system DNS fallback for {domain}")
        try:
            resolver = dns.resolver.Resolver()
            answers = resolver.resolve(domain, record_type)
            ips = [str(answer) for answer in answers]
            logger.info(f"System DNS resolved {domain}: {ips}")
            return ips
        except Exception as e:
            logger.error(f"System DNS fallback failed for {domain}: {e}")
            return None
    
    def batch_resolve(self, domains: List[Tuple[str, str]]) -> Dict[str, List[str]]:
        """
        Resolve multiple domains in parallel
        
        Args:
            domains: List of (domain, record_type) tuples
        
        Returns:
            Dictionary mapping domain:type to IP list
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {}
            for domain, record_type in domains:
                future = executor.submit(self.resolve, domain, record_type)
                futures[future] = (domain, record_type)
            
            for future in futures:
                domain, record_type = futures[future]
                try:
                    ips, _ = future.result(timeout=self.timeout)
                    if ips:
                        results[f"{domain}:{record_type}"] = ips
                except TimeoutError:
                    logger.warning(f"Batch resolve timeout for {domain}")
                except Exception as e:
                    logger.error(f"Batch resolve error for {domain}: {e}")
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get resolver statistics"""
        avg_response_time = 0
        total_queries = self.stats['primary_queries'] + self.stats['secondary_queries']
        
        if total_queries > 0:
            avg_response_time = self.stats['total_response_time'] / total_queries
        
        success_rate = 0
        if total_queries > 0:
            success_rate = ((self.stats['primary_success'] + self.stats['secondary_success']) / total_queries) * 100
        
        return {
            **self.stats,
            'total_queries': total_queries,
            'avg_response_time_ms': round(avg_response_time * 1000, 2),
            'success_rate_percent': round(success_rate, 2)
        }
    
    def health_check(self) -> bool:
        """Check if resolver is working"""
        test_domain = "google.com"
        ips, _ = self.resolve(test_domain, 'A')
        return ips is not None
    
    def close(self):
        """Close HTTP client"""
        self.client.close()
        logger.info("DOH Resolver closed")
