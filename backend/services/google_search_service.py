"""
Google Search API service.
Handles searching and result extraction using Google Custom Search API.
"""
import os
import requests
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env.local")


class GoogleSearchService:
    """Service for fetching Google search results with async support"""
    
    def __init__(self, api_key: Optional[str] = None, search_engine_id: Optional[str] = None):
        """
        Initialize Google Search service.
        
        Args:
            api_key: Google API key (or from environment)
            search_engine_id: Custom Search Engine ID (or from environment)
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.search_engine_id = search_engine_id or os.getenv("GOOGLE_SEARCH_ENGINE_ID")
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        self.max_retries = 3
        self.timeout = 10
        
        if not self.api_key or not self.search_engine_id:
            print("WARNING: Google API credentials not configured. Using mock data.")
        else:
            print(f"✓ Google Custom Search API initialized successfully")
        
    def search(self, query: str, num_results: int = 10) -> List[Dict[str, Any]]:
        """
        Execute a Google search query (synchronous).
        
        Args:
            query: Search query string
            num_results: Number of results to fetch (max 10 per request)
            
        Returns:
            List of raw search results
        """
        if not self.api_key or not self.search_engine_id:
            print("WARNING: Google API credentials not configured. Using mock data.")
            return self._mock_search_results(query, num_results)
        
        for attempt in range(self.max_retries):
            try:
                print(f"  🔍 Searching Google for: {query} (attempt {attempt + 1}/{self.max_retries})")
                params = {
                    "key": self.api_key,
                    "cx": self.search_engine_id,
                    "q": query,
                    "num": min(num_results, 10)  # API limit is 10 per request
                }
                
                response = requests.get(self.base_url, params=params, timeout=self.timeout)
                
                if response.status_code == 403:
                    error_data = response.json()
                    error_message = error_data.get('error', {}).get('message', 'Unknown error')
                    print(f"Google API quota exceeded or invalid key: {error_message}")
                    if attempt == self.max_retries - 1:
                        print("Falling back to mock data...")
                        return self._mock_search_results(query, num_results)
                    continue
                
                response.raise_for_status()
                
                data = response.json()
                items = data.get("items", [])
                print(f"Found {len(items)} results from Google")
                return items
                
            except requests.exceptions.Timeout:
                print(f" Request timeout (attempt {attempt + 1}/{self.max_retries})")
                if attempt == self.max_retries - 1:
                    print("  📝 Falling back to mock data...")
                    return self._mock_search_results(query, num_results)
                continue
                
            except requests.exceptions.RequestException as e:
                print(f"Google Search API error: {e}")
                if attempt == self.max_retries - 1:
                    print("  📝 Falling back to mock data...")
                    return self._mock_search_results(query, num_results)
                continue
        
        return []
    
    async def search_async(self, query: str, num_results: int = 10) -> List[Dict[str, Any]]:
        """
        Execute a Google search query (asynchronous).
        
        Args:
            query: Search query string
            num_results: Number of results to fetch
            
        Returns:
            List of raw search results
        """
        if not self.api_key or not self.search_engine_id:
            return self._mock_search_results(query, num_results)
        
        for attempt in range(self.max_retries):
            try:
                params = {
                    "key": self.api_key,
                    "cx": self.search_engine_id,
                    "q": query,
                    "num": min(num_results, 10)
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        self.base_url, 
                        params=params, 
                        timeout=aiohttp.ClientTimeout(total=self.timeout)
                    ) as response:
                        if response.status == 403:
                            if attempt == self.max_retries - 1:
                                return self._mock_search_results(query, num_results)
                            await asyncio.sleep(1)
                            continue
                        
                        response.raise_for_status()
                        data = await response.json()
                        return data.get("items", [])
                        
            except asyncio.TimeoutError:
                if attempt == self.max_retries - 1:
                    return self._mock_search_results(query, num_results)
                await asyncio.sleep(1)
                continue
                
            except Exception as e:
                print(f"  ❌ Async search error: {e}")
                if attempt == self.max_retries - 1:
                    return self._mock_search_results(query, num_results)
                await asyncio.sleep(1)
                continue
        
        return []
    
    def extract_result_data(self, raw_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant data from raw Google search result.
        
        Args:
            raw_result: Raw result from Google API
            
        Returns:
            Normalized result dictionary
        """
        url = raw_result.get("link", "")
        domain = self._extract_domain(url)
        
        return {
            "title": raw_result.get("title", ""),
            "url": url,
            "snippet": raw_result.get("snippet", ""),
            "domain": domain,
            "displayLink": raw_result.get("displayLink", domain),
            "metadata": {
                "htmlTitle": raw_result.get("htmlTitle", ""),
                "htmlSnippet": raw_result.get("htmlSnippet", ""),
                "pagemap": raw_result.get("pagemap", {})
            }
        }
    
    @staticmethod
    def _extract_domain(url: str) -> str:
        """Extract domain from URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except:
            return ""
    
    @staticmethod
    def _mock_search_results(query: str, num_results: int) -> List[Dict[str, Any]]:
        """
        Generate mock search results for testing without API.
        
        Args:
            query: Search query
            num_results: Number of mock results to generate
            
        Returns:
            List of mock results
        """
        skill = query.replace("learn ", "").replace(" tutorial", "").replace("best ", "").strip()
        
        mock_results = [
            {
                "title": f"Learn {skill.title()} - W3Schools",
                "link": f"https://www.w3schools.com/{skill.lower()}/",
                "snippet": f"Well organized and easy to understand {skill} tutorial with lots of examples. Start learning {skill} now!",
                "displayLink": "w3schools.com"
            },
            {
                "title": f"{skill.title()} Tutorial - Official Documentation",
                "link": f"https://docs.{skill.lower()}.org/tutorial/",
                "snippet": f"The official {skill} tutorial. Learn the fundamentals step by step.",
                "displayLink": f"docs.{skill.lower()}.org"
            },
            {
                "title": f"FreeCodeCamp - {skill.title()} Course",
                "link": f"https://www.freecodecamp.org/learn/{skill.lower()}/",
                "snippet": f"Free interactive {skill} course with certifications. Build real projects.",
                "displayLink": "freecodecamp.org"
            },
            {
                "title": f"Real{skill.title()} - Complete Guide",
                "link": f"https://real{skill.lower()}.com/",
                "snippet": f"Comprehensive {skill} tutorials, courses, and learning paths for beginners to advanced.",
                "displayLink": f"real{skill.lower()}.com"
            },
            {
                "title": f"{skill.title()} on GeeksforGeeks",
                "link": f"https://www.geeksforgeeks.org/{skill.lower()}/",
                "snippet": f"Complete {skill} guide with examples, exercises, and interview questions.",
                "displayLink": "geeksforgeeks.org"
            },
            {
                "title": f"{skill.title()} Roadmap - Complete Learning Path",
                "link": f"https://roadmap.sh/{skill.lower()}",
                "snippet": f"Step by step guide to learning {skill}. Community-driven roadmap with resources.",
                "displayLink": "roadmap.sh"
            },
            {
                "title": f"Master {skill.title()} - Coursera",
                "link": f"https://www.coursera.org/learn/{skill.lower()}",
                "snippet": f"Learn {skill} from top universities. Get certified with hands-on projects.",
                "displayLink": "coursera.org"
            },
        ]
        
        return mock_results[:num_results]
