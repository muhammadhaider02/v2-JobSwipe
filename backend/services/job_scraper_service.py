"""
Job scraper service - orchestrates the producer-consumer scraping system.
Manages Redis connections, progress tracking, and scraping coordination.
"""
import redis
import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import threading
import time


class JobScraperService:
    """Service for orchestrating job scraping operations"""
    
    def __init__(self, redis_host: str = 'localhost', redis_port: int = 6379, redis_db: int = 0):
        """Initialize Redis connection"""
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.redis_client = None
        self.redis_connected = False
        self.job_queue = "job_queue"
        self.scraped_urls_set = "scraped_urls"
        self.progress_channel_prefix = "scrape_progress:"
        
        print("  → Initializing JobScraperService...", flush=True)
        # Try to connect to Redis (but don't fail if not available)
        try:
            self._connect_redis()
        except Exception as e:
            print(f"Redis not available: {e}", flush=True)
            print("  Job scraping will not work until Redis is started.", flush=True)
            print("  To start Redis: docker run -d -p 6379:6379 redis", flush=True)
    
    def _connect_redis(self):
        """Connect to Redis and test connection"""
        self.redis_client = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            db=self.redis_db,
            decode_responses=True,
            socket_connect_timeout=5,  # 5 second connection timeout
            socket_timeout=5  # 5 second operation timeout
        )
        self.redis_client.ping()
        self.redis_connected = True
        print("✓ Redis connection established")
    
    def _ensure_redis_connected(self):
        """Ensure Redis is connected, raise error if not"""
        if not self.redis_connected or self.redis_client is None:
            try:
                self._connect_redis()
            except Exception as e:
                raise ConnectionError(
                    f"Redis is not available. Job scraping requires Redis to be running. "
                    f"Please start Redis with: docker run -d -p 6379:6379 redis\nError: {e}"
                )
    
    def start_scraping(
        self,
        scrape_id: str,
        user_id: str,
        filters: Dict[str, Any],
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Start a scraping job with given filters.
        Returns scrape metadata.
        """
        self._ensure_redis_connected()
        
        print(f"\n{'='*60}")
        print(f"STARTING SCRAPE JOB")
        print(f"Scrape ID: {scrape_id}")
        print(f"User ID: {user_id}")
        print(f"Filters: {json.dumps(filters, indent=2)}")
        print(f"Limit: {limit}")
        print(f"{'='*60}\n")
        
        # Store scrape metadata in Redis
        scrape_data = {
            "scrape_id": scrape_id,
            "user_id": user_id,
            "filters": filters,
            "limit": limit,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "completed": 0,
            "total": limit
        }
        
        self.redis_client.setex(
            f"scrape_metadata:{scrape_id}",
            3600,  # Expire after 1 hour
            json.dumps(scrape_data)
        )
        
        return scrape_data
    
    def check_url_scraped(self, url: str) -> bool:
        """
        Check if URL has already been scraped (Redis Set deduplication).
        Returns True if URL exists in the set.
        """
        self._ensure_redis_connected()
        return self.redis_client.sismember(self.scraped_urls_set, url)
    
    def mark_url_scraped(self, url: str, ttl: int = 86400):
        """
        Mark URL as scraped (add to Redis Set).
        TTL defaults to 24 hours (86400 seconds).
        """
        self._ensure_redis_connected()
        self.redis_client.sadd(self.scraped_urls_set, url)
        # Set expiration on the entire set (not individual members)
        self.redis_client.expire(self.scraped_urls_set, ttl)
    
    def push_job_to_queue(self, job_data: Dict[str, Any]) -> bool:
        """
        Push a job to the Redis queue.
        Returns True if pushed, False if URL already scraped.
        """
        self._ensure_redis_connected()
        url = job_data.get('url')
        
        # Check deduplication
        if self.check_url_scraped(url):
            print(f"  ⊗ Skipping duplicate URL: {url}")
            return False
        
        # Push to queue
        self.redis_client.lpush(self.job_queue, json.dumps(job_data))
        print(f"  ✓ Queued: {url}")
        return True
    
    def pop_job_from_queue(self, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """
        Pop a job from the queue (blocking operation).
        Returns None if timeout reached.
        """
        self._ensure_redis_connected()
        result = self.redis_client.blpop(self.job_queue, timeout=timeout)
        if result:
            _, job_json = result
            return json.loads(job_json)
        return None
    
    def publish_progress(self, scrape_id: str, progress_data: Dict[str, Any]):
        """
        Publish progress update to Redis Pub/Sub channel.
        """
        self._ensure_redis_connected()
        channel = f"{self.progress_channel_prefix}{scrape_id}"
        self.redis_client.publish(channel, json.dumps(progress_data))
        
        # Also update metadata in Redis
        metadata_key = f"scrape_metadata:{scrape_id}"
        metadata_json = self.redis_client.get(metadata_key)
        
        if metadata_json:
            metadata = json.loads(metadata_json)
            metadata.update({
                "completed": progress_data.get("completed", 0),
                "status": progress_data.get("status", "running"),
                "message": progress_data.get("message", ""),
                "updated_at": datetime.now().isoformat()
            })
            self.redis_client.setex(metadata_key, 3600, json.dumps(metadata))
    
    def get_scrape_status(self, scrape_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current scrape status from Redis metadata.
        """
        self._ensure_redis_connected()
        metadata_key = f"scrape_metadata:{scrape_id}"
        metadata_json = self.redis_client.get(metadata_key)
        
        if metadata_json:
            return json.loads(metadata_json)
        return None
    
    def subscribe_to_progress(self, scrape_id: str):
        """
        Subscribe to progress updates (generator for SSE).
        """
        self._ensure_redis_connected()
        channel = f"{self.progress_channel_prefix}{scrape_id}"
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe(channel)
        
        try:
            for message in pubsub.listen():
                if message['type'] == 'message':
                    yield json.loads(message['data'])
        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()
    
    def get_queue_length(self) -> int:
        """Get current queue length"""
        self._ensure_redis_connected()
        return self.redis_client.llen(self.job_queue)
    
    def clear_queue(self):
        """Clear the job queue (admin operation)"""
        self._ensure_redis_connected()
        self.redis_client.delete(self.job_queue)
        print("✓ Job queue cleared")
    
    def clear_scraped_urls(self):
        """Clear the scraped URLs set (admin operation)"""
        self._ensure_redis_connected()
        self.redis_client.delete(self.scraped_urls_set)
        print("✓ Scraped URLs set cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scraping system statistics"""
        try:
            self._ensure_redis_connected()
            return {
                "queue_length": self.get_queue_length(),
                "scraped_urls_count": self.redis_client.scard(self.scraped_urls_set),
                "redis_connected": True
            }
        except Exception:
            return {
                "queue_length": 0,
                "scraped_urls_count": 0,
                "redis_connected": False
            }


# Singleton instance
_scraper_service = None

def get_scraper_service() -> JobScraperService:
    """Get or create singleton scraper service instance"""
    global _scraper_service
    if _scraper_service is None:
        _scraper_service = JobScraperService()
    return _scraper_service
