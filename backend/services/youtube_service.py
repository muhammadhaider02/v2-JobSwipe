"""
YouTube Data API service.
Handles fetching and parsing YouTube playlists and videos.
"""
import os
import requests
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env.local")


class YouTubeService:
    """Service for fetching YouTube playlists and videos"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize YouTube service.
        
        Args:
            api_key: YouTube Data API key (or from environment)
        """
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        self.base_url = "https://www.googleapis.com/youtube/v3"
        
        if not self.api_key:
            print("WARNING: YouTube API key not configured. Please set YOUTUBE_API_KEY in .env.local")
        else:
            print(f"YouTube API initialized successfully")
        
    def search_playlists(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for playlists on YouTube.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            List of playlist data
        """
        if not self.api_key:
            print("WARNING: YouTube API key not configured. Using mock data.")
            return self._mock_playlist_results(query, max_results)
        
        try:
            print(f"Searching YouTube playlists for: {query}")
            params = {
                "key": self.api_key,
                "part": "snippet",
                "q": query,
                "type": "playlist",
                "maxResults": min(max_results, 25),  # API supports up to 50
                "order": "relevance",
                "videoDuration": "any"
            }
            
            response = requests.get(f"{self.base_url}/search", params=params, timeout=15)
            
            if response.status_code == 403:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', 'Unknown error')
                print(f"YouTube API quota exceeded or invalid key: {error_message}")
                print("Falling back to mock data...")
                return self._mock_playlist_results(query, max_results)
            
            response.raise_for_status()
            
            data = response.json()
            items = data.get("items", [])
            
            print(f"Found {len(items)} playlists")
            
            # Enrich with playlist details
            enriched_items = []
            for item in items:
                try:
                    playlist_id = item["id"]["playlistId"]
                    details = self._get_playlist_details(playlist_id)
                    if details:
                        item["details"] = details
                    enriched_items.append(item)
                except Exception as e:
                    print(f"  ⚠️  Error enriching playlist: {e}")
                    enriched_items.append(item)
            
            return enriched_items
            
        except requests.exceptions.RequestException as e:
            print(f"YouTube API error: {e}")
            print("Falling back to mock data...")
            return self._mock_playlist_results(query, max_results)
    
    def search_videos(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for videos on YouTube (fallback if no playlists).
        
        Args:
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            List of video data
        """
        if not self.api_key:
            return self._mock_video_results(query, max_results)
        
        try:
            print(f"Searching YouTube videos for: {query}")
            params = {
                "key": self.api_key,
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": min(max_results, 25),
                "order": "relevance",
                "videoDuration": "medium",  # Filter out very short videos
                "videoDefinition": "any",
                "videoEmbeddable": "true"
            }
            
            response = requests.get(f"{self.base_url}/search", params=params, timeout=15)
            
            if response.status_code == 403:
                print(f"YouTube API quota exceeded")
                return self._mock_video_results(query, max_results)
            
            response.raise_for_status()
            
            data = response.json()
            items = data.get("items", [])
            
            print(f"Found {len(items)} videos")
            
            # Enrich with video statistics
            enriched_items = []
            video_ids = [item["id"]["videoId"] for item in items if "videoId" in item.get("id", {})]
            
            if video_ids:
                stats_map = self._get_bulk_video_statistics(video_ids)
                for item in items:
                    video_id = item["id"].get("videoId")
                    if video_id and video_id in stats_map:
                        item["statistics"] = stats_map[video_id]
                    enriched_items.append(item)
            else:
                enriched_items = items
            
            return enriched_items
            
        except requests.exceptions.RequestException as e:
            print(f"YouTube API error: {e}")
            return self._mock_video_results(query, max_results)
    
    def _get_playlist_details(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a playlist"""
        if not self.api_key:
            return None
        
        try:
            params = {
                "key": self.api_key,
                "part": "contentDetails,snippet",
                "id": playlist_id
            }
            
            response = requests.get(f"{self.base_url}/playlists", params=params, timeout=10)
            
            if not response.ok:
                return None
            
            data = response.json()
            items = data.get("items", [])
            if items:
                return {
                    "itemCount": items[0].get("contentDetails", {}).get("itemCount", 0),
                    "channelTitle": items[0].get("snippet", {}).get("channelTitle", "")
                }
            return None
            
        except Exception as e:
            print(f"Error fetching playlist details: {e}")
            return None
    
    def _get_bulk_video_statistics(self, video_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get statistics for multiple videos in one API call"""
        if not self.api_key or not video_ids:
            return {}
        
        try:
            # YouTube API allows up to 50 IDs per request
            video_ids_str = ",".join(video_ids[:50])
            
            params = {
                "key": self.api_key,
                "part": "statistics",
                "id": video_ids_str
            }
            
            response = requests.get(f"{self.base_url}/videos", params=params, timeout=10)
            
            if not response.ok:
                return {}
            
            data = response.json()
            stats_map = {}
            
            for item in data.get("items", []):
                video_id = item.get("id")
                stats = item.get("statistics", {})
                stats_map[video_id] = stats
            
            return stats_map
            
        except Exception as e:
            print(f"Error fetching bulk video statistics: {e}")
            return {}
    
    def _get_video_statistics(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a single video (legacy method)"""
        stats_map = self._get_bulk_video_statistics([video_id])
        return stats_map.get(video_id)
    
    def extract_playlist_data(self, raw_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant data from raw YouTube playlist result"""
        snippet = raw_result.get("snippet", {})
        details = raw_result.get("details", {})
        
        playlist_id = raw_result["id"].get("playlistId", "")
        
        return {
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", "") or details.get("channelTitle", ""),
            "description": snippet.get("description", ""),
            "url": f"https://www.youtube.com/playlist?list={playlist_id}",
            "video_count": details.get("itemCount", 0),
            "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", "") or 
                           snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
            "channel_id": snippet.get("channelId", ""),
            "published_at": snippet.get("publishedAt", "")
        }
    
    def extract_video_data(self, raw_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant data from raw YouTube video result"""
        snippet = raw_result.get("snippet", {})
        statistics = raw_result.get("statistics", {})
        
        video_id = raw_result["id"].get("videoId", "")
        
        return {
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "description": snippet.get("description", ""),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "view_count": int(statistics.get("viewCount", 0)),
            "like_count": int(statistics.get("likeCount", 0)),
            "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", "") or
                           snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
            "channel_id": snippet.get("channelId", ""),
            "published_at": snippet.get("publishedAt", "")
        }
    
    @staticmethod
    def _mock_playlist_results(query: str, max_results: int) -> List[Dict[str, Any]]:
        """Generate mock playlist results for testing"""
        skill = query.replace(" tutorial playlist", "").replace(" full course", "").strip()
        
        mock_playlists = [
            {
                "id": {"playlistId": "PLmock1"},
                "snippet": {
                    "title": f"{skill.title()} Full Course - FreeCodeCamp",
                    "channelTitle": "freeCodeCamp.org",
                    "description": f"Complete {skill} course for beginners. Learn all the fundamentals.",
                    "thumbnails": {"high": {"url": "https://i.ytimg.com/vi/mock1/hqdefault.jpg"}},
                    "channelId": "UC8mock1"
                },
                "details": {"itemCount": 25}
            },
            {
                "id": {"playlistId": "PLmock2"},
                "snippet": {
                    "title": f"{skill.title()} Tutorial for Beginners",
                    "channelTitle": "Programming with Mosh",
                    "description": f"Learn {skill} from scratch with hands-on projects.",
                    "thumbnails": {"high": {"url": "https://i.ytimg.com/vi/mock2/hqdefault.jpg"}},
                    "channelId": "UC8mock2"
                },
                "details": {"itemCount": 18}
            },
            {
                "id": {"playlistId": "PLmock3"},
                "snippet": {
                    "title": f"Complete {skill.title()} Course 2024",
                    "channelTitle": "Corey Schafer",
                    "description": f"Comprehensive {skill} tutorials covering basics to advanced topics.",
                    "thumbnails": {"high": {"url": "https://i.ytimg.com/vi/mock3/hqdefault.jpg"}},
                    "channelId": "UC8mock3"
                },
                "details": {"itemCount": 32}
            }
        ]
        
        return mock_playlists[:max_results]
    
    @staticmethod
    def _mock_video_results(query: str, max_results: int) -> List[Dict[str, Any]]:
        """Generate mock video results for testing"""
        skill = query.replace(" tutorial", "").strip()
        
        mock_videos = [
            {
                "id": {"videoId": "vidmock1"},
                "snippet": {
                    "title": f"{skill.title()} Crash Course",
                    "channelTitle": "Traversy Media",
                    "description": f"Learn {skill} in one video - crash course for beginners",
                    "thumbnails": {"high": {"url": "https://i.ytimg.com/vi/vidmock1/hqdefault.jpg"}},
                    "channelId": "UCvid1"
                },
                "statistics": {
                    "viewCount": "500000",
                    "likeCount": "25000"
                }
            }
        ]
        
        return mock_videos[:max_results]
