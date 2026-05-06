"""

"""

import time
import threading
from typing import Dict, Optional, Any, List, Tuple
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Individual cache entry with metadata"""
    domain: str
    ip_addresses: List[str]
    record_type: str  # A, AAAA, CNAME, etc.
    ttl: int  # Original TTL from DNS response
    expires_at: float  # Unix timestamp when entry expires
    created_at: float  # Unix timestamp when created
    hits: int = 0  # Number of times accessed
    last_accessed: float = field(default_factory=time.time)
    is_prefetched: bool = False  # Whether this was prefetched
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        return time.time() >= self.expires_at
    
    def remaining_ttl(self) -> int:
        """Get remaining TTL in seconds"""
        remaining = int(self.expires_at - time.time())
        return max(0, remaining)
    
    def hit(self):
        """Record a cache hit"""
        self.hits += 1
        self.last_accessed = time.time()

class AdvancedCache:
    """LRU cache with TTL management and statistics"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300, 
                 cleanup_interval: int = 60, enable_prefetch: bool = True):
        """
        Initialize advanced cache
        
        Args:
            max_size: Maximum number of entries in cache
            default_ttl: Default TTL in seconds (if DNS doesn't provide)
            cleanup_interval: How often to clean expired entries (seconds)
            enable_prefetch: Enable automatic prefetching of popular entries
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.enable_prefetch = enable_prefetch
        self.cleanup_interval = cleanup_interval
        
        # Main cache storage (OrderedDict for LRU)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        
        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'total_queries': 0,
            'evictions': 0,
            'prefetches': 0,
            'cache_size': 0
        }
        
        # Prefetch tracking (domains that should be prefetched)
        self._prefetch_tracking: Dict[str, int] = {}  # domain -> hit count
        
        # Lock for thread safety
        self._lock = threading.RLock()
        
        # Start cleanup thread
        self._running = True
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        
        logger.info(f"Cache initialized: max_size={max_size}, default_ttl={default_ttl}s, "
                   f"prefetch={enable_prefetch}")
    
    def get(self, domain: str, record_type: str = 'A') -> Optional[List[str]]:
        """
        Get IP addresses for domain from cache
        
        Args:
            domain: Domain name to lookup
            record_type: DNS record type (A, AAAA, etc.)
        
        Returns:
            List of IP addresses or None if not found/expired
        """
        key = f"{domain}:{record_type}"
        
        with self._lock:
            self.stats['total_queries'] += 1
            
            if key not in self._cache:
                self.stats['misses'] += 1
                # Track for prefetch (if enabled)
                if self.enable_prefetch:
                    self._track_for_prefetch(domain)
                return None
            
            entry = self._cache[key]
            
            # Check if expired
            if entry.is_expired():
                self._delete_entry(key)
                self.stats['misses'] += 1
                return None
            
            # Cache hit
            entry.hit()
            self.stats['hits'] += 1
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            
            # Track for prefetch (frequently accessed)
            if self.enable_prefetch and entry.hits >= 5:
                self._track_for_prefetch(domain, entry.hits)
            
            logger.debug(f"Cache HIT: {domain} ({record_type}) - remaining TTL: {entry.remaining_ttl()}s")
            
            return entry.ip_addresses
    
    def set(self, domain: str, ip_addresses: List[str], record_type: str = 'A', 
            ttl: Optional[int] = None):
        """
        Store DNS resolution result in cache
        
        Args:
            domain: Domain name
            ip_addresses: List of resolved IP addresses
            record_type: DNS record type
            ttl: Time to live in seconds (optional)
        """
        key = f"{domain}:{record_type}"
        
        with self._lock:
            # Apply TTL (use provided, or DNS TTL, or default)
            actual_ttl = ttl or self.default_ttl
            actual_ttl = min(actual_ttl, 86400)  # Cap at 24 hours
            
            expires_at = time.time() + actual_ttl
            
            entry = CacheEntry(
                domain=domain,
                ip_addresses=ip_addresses,
                record_type=record_type,
                ttl=actual_ttl,
                expires_at=expires_at,
                created_at=time.time()
            )
            
            # Check if we need to evict
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()
            
            # Add/Update entry
            self._cache[key] = entry
            self._cache.move_to_end(key)
            
            # Update stats
            self.stats['cache_size'] = len(self._cache)
            
            logger.debug(f"Cached: {domain} ({record_type}) -> {ip_addresses} (TTL: {actual_ttl}s)")
    
    def _delete_entry(self, key: str):
        """Delete entry from cache"""
        if key in self._cache:
            del self._cache[key]
            self.stats['cache_size'] = len(self._cache)
            logger.debug(f"Deleted from cache: {key}")
    
    def _evict_lru(self):
        """Evict least recently used entry"""
        if self._cache:
            key, entry = self._cache.popitem(last=False)
            self.stats['evictions'] += 1
            logger.debug(f"Evicted LRU entry: {key} (hits={entry.hits})")
    
    def _track_for_prefetch(self, domain: str, hits: int = 1):
        """Track frequently accessed domains for prefetching"""
        if domain in self._prefetch_tracking:
            self._prefetch_tracking[domain] += hits
        else:
            self._prefetch_tracking[domain] = hits
        
        # Clean up tracking dict if too large
        if len(self._prefetch_tracking) > self.max_size * 2:
            # Remove least frequent entries
            sorted_items = sorted(self._prefetch_tracking.items(), key=lambda x: x[1])
            for old_domain, _ in sorted_items[:self.max_size]:
                del self._prefetch_tracking[old_domain]
    
    def get_prefetch_candidates(self) -> List[str]:
        """
        Get domains that should be prefetched based on access patterns
        
        Returns:
            List of domain names that are frequently accessed
        """
        if not self.enable_prefetch:
            return []
        
        # Get domains with high hit counts
        candidates = [
            domain for domain, hits in self._prefetch_tracking.items() 
            if hits >= 10  # Threshold for prefetch
        ]
        
        # Limit number of candidates
        return candidates[:20]
    
    def invalidate(self, domain: Optional[str] = None, record_type: Optional[str] = None):
        """
        Invalidate cache entries
        
        Args:
            domain: Specific domain to invalidate (None = all)
            record_type: Specific record type (None = all types)
        """
        with self._lock:
            if domain is None:
                # Clear entire cache
                self._cache.clear()
                self._prefetch_tracking.clear()
                self.stats['cache_size'] = 0
                logger.info("Cache completely cleared")
                return
            
            # Invalidate specific domain
            keys_to_delete = []
            for key in self._cache.keys():
                key_domain, key_type = key.split(':', 1)
                if key_domain == domain:
                    if record_type is None or key_type == record_type:
                        keys_to_delete.append(key)
            
            for key in keys_to_delete:
                self._delete_entry(key)
            
            logger.info(f"Invalidated {len(keys_to_delete)} entries for {domain}")
    
    def _cleanup_worker(self):
        """Background thread to periodically clean expired entries"""
        while self._running:
            time.sleep(self.cleanup_interval)
            self._cleanup_expired()
    
    def _cleanup_expired(self):
        """Remove all expired entries"""
        with self._lock:
            expired_keys = []
            for key, entry in self._cache.items():
                if entry.is_expired():
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._delete_entry(key)
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            hit_rate = 0
            if self.stats['total_queries'] > 0:
                hit_rate = (self.stats['hits'] / self.stats['total_queries']) * 100
            
            return {
                **self.stats,
                'hit_rate_percent': round(hit_rate, 2),
                'current_size': len(self._cache),
                'max_size': self.max_size,
                'utilization_percent': round((len(self._cache) / self.max_size) * 100, 2),
                'prefetch_tracked': len(self._prefetch_tracking)
            }
    
    def get_all_entries(self) -> List[Dict[str, Any]]:
        """Get all cache entries for debugging/display"""
        with self._lock:
            entries = []
            for key, entry in self._cache.items():
                entries.append({
                    'key': key,
                    'domain': entry.domain,
                    'ips': entry.ip_addresses,
                    'type': entry.record_type,
                    'remaining_ttl': entry.remaining_ttl(),
                    'hits': entry.hits,
                    'created': datetime.fromtimestamp(entry.created_at).isoformat(),
                    'expires': datetime.fromtimestamp(entry.expires_at).isoformat()
                })
            return entries
    
    def shutdown(self):
        """Gracefully shutdown cache"""
        self._running = False
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        logger.info("Cache shutdown complete")
