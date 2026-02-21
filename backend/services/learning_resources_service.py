"""
Main learning resources service.
Orchestrates the entire resource discovery pipeline.
"""
from typing import List, Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor
from services.google_search_service import GoogleSearchService
from services.youtube_service import YouTubeService
from services.resource_ranker import ResourceRanker
from services.result_normalizer import ResultNormalizer
from utils.query_builder import QueryBuilder
from models.learning_resources import SkillResources


class LearningResourcesService:
    """Main service for generating learning resources"""
    
    def __init__(self):
        """Initialize all sub-services"""
        self.google_service = GoogleSearchService()
        self.youtube_service = YouTubeService()
        self.ranker = ResourceRanker()
        self.normalizer = ResultNormalizer()
        self.query_builder = QueryBuilder()
        
    def generate_resources_for_skill(
        self,
        skill: str,
        num_google_results: int = 7,
        num_youtube_results: int = 3
    ) -> SkillResources:
        """
        Generate complete learning resources for a single skill.
        
        Args:
            skill: Skill name
            num_google_results: Target number of Google results
            num_youtube_results: Target number of YouTube results
            
        Returns:
            SkillResources object with all resources
        """
        print(f"\n{'='*60}")
        print(f"Generating resources for: {skill}")
        print(f"{'='*60}")
        
        # Step 1: Generate Google results
        google_results = self._fetch_and_rank_google_results(skill, num_google_results)
        
        # Step 2: Generate YouTube results
        youtube_results = self._fetch_and_rank_youtube_results(skill, num_youtube_results)
        
        # Step 3: Create normalized output
        skill_resources = self.normalizer.create_skill_resources(
            skill=skill,
            google_results=google_results,
            youtube_results=youtube_results
        )
        
        print(f"\n✓ Generated {len(google_results)} Google results")
        print(f"✓ Generated {len(youtube_results)} YouTube results")
        print(f"✓ Total confidence: {skill_resources.total_confidence:.2f}")
        
        return skill_resources
    
    def generate_resources_for_skills(
        self,
        skills: List[str],
        num_google_results: int = 7,
        num_youtube_results: int = 3,
        parallel: bool = True
    ) -> List[SkillResources]:
        """
        Generate resources for multiple skills.
        
        Args:
            skills: List of skill names
            num_google_results: Target number of Google results per skill
            num_youtube_results: Target number of YouTube results per skill
            parallel: Whether to process skills in parallel
            
        Returns:
            List of SkillResources objects
        """
        print(f"\n{'='*60}")
        print(f"Generating resources for {len(skills)} skills")
        print(f"Parallel processing: {parallel}")
        print(f"{'='*60}")
        
        if parallel:
            # Process skills in parallel using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(len(skills), 5)) as executor:
                results = list(executor.map(
                    lambda skill: self.generate_resources_for_skill(
                        skill, num_google_results, num_youtube_results
                    ),
                    skills
                ))
            return results
        else:
            # Process skills sequentially
            return [
                self.generate_resources_for_skill(skill, num_google_results, num_youtube_results)
                for skill in skills
            ]
    
    def _fetch_and_rank_google_results(self, skill: str, target_count: int) -> List[Any]:
        """Fetch, score, filter, and rank Google results"""
        # Build multiple query variants for comprehensive coverage
        queries = self.query_builder.build_google_queries(skill, num_variants=5)
        
        all_results = []
        seen_urls = set()
        
        for query in queries:
            print(f"  Google query: {query}")
            raw_results = self.google_service.search(query, num_results=10)
            
            for raw_result in raw_results:
                # Extract and normalize
                extracted = self.google_service.extract_result_data(raw_result)
                
                # Skip duplicates
                url = extracted.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                
                # Calculate confidence score
                confidence = self.ranker.score_google_result(extracted, skill)
                
                # Normalize to standard format
                normalized = self.normalizer.normalize_google_result(extracted, confidence)
                all_results.append(normalized)
            
            # Stop early if we have enough high-quality results
            high_quality = [r for r in all_results if r.confidence >= 0.7]
            if len(high_quality) >= target_count * 1.5:
                break
        
        # Filter by threshold
        filtered = [r for r in all_results if r.confidence >= self.ranker.MIN_CONFIDENCE_THRESHOLD]
        
        # Sort by confidence
        sorted_results = sorted(filtered, key=lambda x: x.confidence, reverse=True)
        
        print(f"  ✓ Filtered {len(all_results)} → {len(filtered)} results (threshold: {self.ranker.MIN_CONFIDENCE_THRESHOLD})")
        
        # Return top N
        return sorted_results[:target_count]
    
    def _fetch_and_rank_youtube_results(self, skill: str, target_count: int) -> List[Any]:
        """Fetch, score, filter, and rank YouTube results"""
        # Build YouTube queries
        queries = self.query_builder.build_youtube_queries(skill, num_variants=2)
        
        all_results = []
        seen_urls = set()
        
        for query in queries:
            print(f"  YouTube query: {query}")
            
            # Try playlists first
            raw_playlists = self.youtube_service.search_playlists(query, max_results=5)
            
            for raw_playlist in raw_playlists:
                # Extract and normalize
                extracted = self.youtube_service.extract_playlist_data(raw_playlist)
                
                # Skip duplicates
                url = extracted.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                
                # Calculate confidence score
                confidence = self.ranker.score_youtube_result(extracted, skill, is_playlist=True)
                
                # Normalize to standard format
                normalized = self.normalizer.normalize_youtube_result(extracted, confidence)
                all_results.append(normalized)
        
        # If we don't have enough playlists, fetch videos as fallback
        if len(all_results) < target_count:
            print(f"  Fetching YouTube videos as fallback...")
            for query in queries[:1]:  # Only first query for videos
                raw_videos = self.youtube_service.search_videos(query, max_results=5)
                
                for raw_video in raw_videos:
                    extracted = self.youtube_service.extract_video_data(raw_video)
                    
                    url = extracted.get("url", "")
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    
                    confidence = self.ranker.score_youtube_result(extracted, skill, is_playlist=False)
                    normalized = self.normalizer.normalize_youtube_result(extracted, confidence)
                    all_results.append(normalized)
        
        # Filter by threshold
        filtered = [r for r in all_results if r.confidence >= self.ranker.MIN_CONFIDENCE_THRESHOLD]
        
        # Sort by confidence
        sorted_results = sorted(filtered, key=lambda x: x.confidence, reverse=True)
        
        # Return top N
        return sorted_results[:target_count]
