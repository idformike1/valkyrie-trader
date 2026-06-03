import time
import threading
from typing import Dict, Any

class QuoteHealthTracker:
    _lock = threading.Lock()
    _hits = 0
    _misses = 0
    _synthetic_fills = 0

    @classmethod
    def record_hit(cls):
        with cls._lock:
            cls._hits += 1

    @classmethod
    def record_miss(cls):
        with cls._lock:
            cls._misses += 1

    @classmethod
    def record_synthetic_fill(cls):
        with cls._lock:
            cls._synthetic_fills += 1

    @classmethod
    def reset(cls):
        with cls._lock:
            cls._hits = 0
            cls._misses = 0
            cls._synthetic_fills = 0

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        from v2.option_quote_cache import OptionQuoteCache, get_subscribed_keys
        
        subscribed = get_subscribed_keys()
        total_sub = len(subscribed)
        
        now_ms = int(time.time() * 1000)
        stale_threshold_ms = 1500
        
        live_count = 0
        stale_count = 0
        
        for key in subscribed:
            quote = OptionQuoteCache.get(key)
            if quote is not None:
                age_ms = now_ms - quote.last_update_ms
                if age_ms <= stale_threshold_ms:
                    live_count += 1
                else:
                    stale_count += 1
            else:
                stale_count += 1 # Subscribed but no quotes yet
                
        with cls._lock:
            total_requests = cls._hits + cls._misses
            hit_rate = (cls._hits / total_requests * 100.0) if total_requests > 0 else 100.0
            miss_rate = (cls._misses / total_requests * 100.0) if total_requests > 0 else 0.0
            syn_fills = cls._synthetic_fills
            
        return {
            "subscribed_contracts": total_sub,
            "live_quotes": live_count,
            "stale_quotes": stale_count,
            "hit_rate": round(hit_rate, 2),
            "miss_rate": round(miss_rate, 2),
            "synthetic_fills": syn_fills
        }

    @classmethod
    def get_health_metrics(cls) -> Dict[str, Any]:
        """
        Retrieves options quote health metrics for V2 operational certification.
        """
        stats = cls.get_stats()
        with cls._lock:
            stats["quote_hits"] = cls._hits
            stats["quote_misses"] = cls._misses
            stats["synthetic_fill_count"] = cls._synthetic_fills
        return stats
