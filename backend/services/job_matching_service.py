"""
Job Matching Service: Implements 4-component weighted scoring algorithm.

Scoring Components:
1. Title Similarity (35%): Semantic match between previous roles and job title
2. Skill Match (20%): Overlap between user skills and required skills
3. Green Skills Count (30%): Number of matching skills user possesses
4. Experience Alignment (15%): Band matching (intern/junior/mid/senior)

Final Score = 0.35×title + 0.20×skill + 0.30×green_skills + 0.15×experience
Note: Quiz scores are ignored. Jobs are filtered by recommended roles only.
"""

import os
import json
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env.local")

logger = logging.getLogger(__name__)


class JobMatchingService:
    """Service for matching user profiles to jobs using multi-component scoring"""
    
    def __init__(self):
        """Initialize the job matching service"""
        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        
        # File paths
        self.embeddings_path = BASE_DIR / "models" / "job_embeddings.npy"
        self.metadata_path = BASE_DIR / "models" / "job_metadata.json"
        
        # Load scoring weights from environment
        self.semantic_weight = float(os.getenv('JOB_MATCHING_SEMANTIC_WEIGHT', 0.35))
        self.skill_weight = float(os.getenv('JOB_MATCHING_SKILL_WEIGHT', 0.20))
        self.green_skills_weight = float(os.getenv('JOB_MATCHING_GREEN_SKILLS_WEIGHT', 0.30))
        self.experience_weight = 0.15
        # Quiz and location are no longer used in scoring
        self.quiz_weight = 0.0
        self.location_weight = 0.0
        
        logger.info(
            f"JobMatchingService initialized with weights: "
            f"semantic={self.semantic_weight}, skill={self.skill_weight}, "
            f"green_skills={self.green_skills_weight}, experience={self.experience_weight}"
        )
        
        # Initialize storage
        self.embeddings: Optional[np.ndarray] = None
        self.metadata: Optional[List[Dict[str, Any]]] = None
        
        # Preload embeddings if available
        self._load_embeddings()
    
    def _load_embeddings(self) -> bool:
        """
        Load job embeddings and metadata from disk.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            if not self.embeddings_path.exists():
                logger.warning(f"Embeddings file not found: {self.embeddings_path}")
                return False
            
            if not self.metadata_path.exists():
                logger.warning(f"Metadata file not found: {self.metadata_path}")
                return False
            
            # Load embeddings
            self.embeddings = np.load(self.embeddings_path)
            
            # Load metadata
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
            
            logger.info(
                f"Loaded {len(self.embeddings)} job embeddings and "
                f"{len(self.metadata)} metadata entries"
            )
            
            # Validate consistency
            if len(self.embeddings) != len(self.metadata):
                logger.error(
                    f"Mismatch: {len(self.embeddings)} embeddings but "
                    f"{len(self.metadata)} metadata entries"
                )
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading embeddings: {e}")
            self.embeddings = None
            self.metadata = None
            return False
    
    def check_index_status(self) -> Dict[str, Any]:
        """
        Check if embeddings are loaded and provide status info.
        
        Returns:
            Status dictionary with loaded state and counts
        """
        is_loaded = self.embeddings is not None and self.metadata is not None
        
        return {
            "index_loaded": is_loaded,
            "embeddings_count": len(self.embeddings) if self.embeddings is not None else 0,
            "metadata_count": len(self.metadata) if self.metadata is not None else 0,
            "embeddings_path": str(self.embeddings_path),
            "metadata_path": str(self.metadata_path),
            "embeddings_exist": self.embeddings_path.exists(),
            "metadata_exist": self.metadata_path.exists()
        }
    
    def _compute_title_similarity(
        self, 
        previous_roles: List[str], 
        job_titles: List[str],
        job_embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Compute semantic similarity between previous roles and job titles.
        
        Args:
            previous_roles: List of user's previous job titles
            job_titles: List of job titles from metadata
            job_embeddings: Pre-computed embeddings for job titles
        
        Returns:
            Array of similarity scores (0-1) for each job
        """
        if not previous_roles:
            # No previous roles - return zeros
            return np.zeros(len(job_titles))
        
        # Encode previous roles
        role_text = " | ".join(previous_roles)
        role_embedding = self.model.encode([role_text])
        
        # Compute similarity with pre-computed job embeddings
        similarities = cosine_similarity(role_embedding, job_embeddings)[0]
        
        # Ensure range [0, 1]
        similarities = np.clip(similarities, 0, 1)
        
        return similarities
    
    def _normalize_skill(self, skill: str) -> str:
        """Normalize skill name for matching (lowercase, strip whitespace)"""
        return skill.strip().lower()
    
    def _compute_skill_match(
        self, 
        user_skills: List[str], 
        jobs_metadata: List[Dict[str, Any]]
    ) -> np.ndarray:
        """
        Compute skill match percentage for each job.
        
        Args:
            user_skills: List of user's skills
            jobs_metadata: List of job metadata dictionaries
        
        Returns:
            Array of skill match scores (0-1) for each job
        """
        if not user_skills:
            return np.zeros(len(jobs_metadata))
        
        # Normalize user skills
        normalized_user_skills = set(self._normalize_skill(s) for s in user_skills)
        
        skill_scores = []
        
        for job in jobs_metadata:
            skills_required = job.get('skills_required', [])
            
            if not skills_required or not isinstance(skills_required, list):
                skill_scores.append(0.0)
                continue
            
            # Normalize required skills
            normalized_required = set(
                self._normalize_skill(s) for s in skills_required
            )
            
            if len(normalized_required) == 0:
                skill_scores.append(0.0)
                continue
            
            # Calculate overlap
            matched = normalized_user_skills.intersection(normalized_required)
            match_percentage = len(matched) / len(normalized_required)
            
            skill_scores.append(match_percentage)
        
        return np.array(skill_scores)
    
    def _compute_green_skills_score(
        self, 
        user_skills: List[str], 
        jobs_metadata: List[Dict[str, Any]]
    ) -> np.ndarray:
        """
        Compute normalized score based on number of matching skills (green skills).
        Higher score for jobs where user has more matching skills.
        
        Args:
            user_skills: List of user's skills
            jobs_metadata: List of job metadata dictionaries
        
        Returns:
            Array of green skills scores (0-1) for each job
        """
        if not user_skills:
            return np.zeros(len(jobs_metadata))
        
        # Normalize user skills
        normalized_user_skills = set(self._normalize_skill(s) for s in user_skills)
        
        green_skills_scores = []
        max_matched_count = 0
        matched_counts = []
        
        # First pass: count matches for each job
        for job in jobs_metadata:
            skills_required = job.get('skills_required', [])
            
            if not skills_required or not isinstance(skills_required, list):
                matched_counts.append(0)
                continue
            
            # Normalize required skills
            normalized_required = set(
                self._normalize_skill(s) for s in skills_required
            )
            
            # Count matching skills (green skills)
            matched = normalized_user_skills.intersection(normalized_required)
            matched_count = len(matched)
            matched_counts.append(matched_count)
            
            if matched_count > max_matched_count:
                max_matched_count = matched_count
        
        # Second pass: normalize by max to get 0-1 scale
        if max_matched_count == 0:
            # No matches at all
            return np.zeros(len(jobs_metadata))
        
        for count in matched_counts:
            normalized_score = count / max_matched_count
            green_skills_scores.append(normalized_score)
        
        return np.array(green_skills_scores)
    
    def _compute_quiz_score(
        self, 
        quiz_scores: Optional[Dict[str, float]], 
        jobs_metadata: List[Dict[str, Any]]
    ) -> np.ndarray:
        """
        Compute average quiz score for skills required by each job.
        
        Args:
            quiz_scores: Dictionary mapping skill -> score (0-100)
            jobs_metadata: List of job metadata dictionaries
        
        Returns:
            Array of quiz scores (0-1) for each job
        """
        if not quiz_scores:
            # No quiz scores - return zeros
            return np.zeros(len(jobs_metadata))
        
        # Normalize quiz score keys
        normalized_quiz_scores = {
            self._normalize_skill(skill): score / 100.0  # Convert to 0-1
            for skill, score in quiz_scores.items()
        }
        
        quiz_score_array = []
        
        for job in jobs_metadata:
            skills_required = job.get('skills_required', [])
            
            if not skills_required or not isinstance(skills_required, list):
                quiz_score_array.append(0.0)
                continue
            
            # Find quiz scores for required skills
            relevant_scores = []
            for skill in skills_required:
                normalized_skill = self._normalize_skill(skill)
                if normalized_skill in normalized_quiz_scores:
                    relevant_scores.append(normalized_quiz_scores[normalized_skill])
            
            if relevant_scores:
                # Average of relevant quiz scores
                avg_score = sum(relevant_scores) / len(relevant_scores)
                quiz_score_array.append(avg_score)
            else:
                # No quiz scores for any required skills
                quiz_score_array.append(0.0)
        
        return np.array(quiz_score_array)
    
    def _get_experience_band(self, years: int) -> str:
        """
        Map years of experience to experience band.
        
        Args:
            years: Years of experience
        
        Returns:
            Experience band: 'intern', 'junior', 'mid', 'senior'
        """
        if years == 0:
            return 'intern'
        elif years <= 2:
            return 'junior'
        elif years <= 5:
            return 'mid'
        else:
            return 'senior'
    
    def _compute_experience_alignment(
        self, 
        user_years: int, 
        jobs_metadata: List[Dict[str, Any]]
    ) -> np.ndarray:
        """
        Compute experience band alignment for each job.
        
        Args:
            user_years: User's years of experience
            jobs_metadata: List of job metadata dictionaries
        
        Returns:
            Array of experience alignment scores (0-1) for each job
        """
        user_band = self._get_experience_band(user_years)
        
        experience_scores = []
        
        for job in jobs_metadata:
            job_experience = job.get('experience_required', 0)
            
            # Handle different formats
            if isinstance(job_experience, str):
                try:
                    job_experience = int(job_experience)
                except (ValueError, TypeError):
                    job_experience = 0
            elif job_experience is None:
                job_experience = 0
            
            job_band = self._get_experience_band(job_experience)
            
            # Perfect match
            if user_band == job_band:
                experience_scores.append(1.0)
            # Adjacent bands (e.g., junior -> mid)
            elif (
                (user_band == 'intern' and job_band == 'junior') or
                (user_band == 'junior' and job_band in ['intern', 'mid']) or
                (user_band == 'mid' and job_band in ['junior', 'senior']) or
                (user_band == 'senior' and job_band == 'mid')
            ):
                experience_scores.append(0.7)
            # Two bands apart
            else:
                experience_scores.append(0.4)
        
        return np.array(experience_scores)
    
    def _compute_location_fit(
        self, 
        preferred_location: Optional[str], 
        jobs_metadata: List[Dict[str, Any]]
    ) -> np.ndarray:
        """
        Compute location compatibility for each job.
        
        Args:
            preferred_location: User's preferred location (can be None, "Remote", or city name)
            jobs_metadata: List of job metadata dictionaries
        
        Returns:
            Array of location fit scores (0-1) for each job
        """
        location_scores = []
        
        for job in jobs_metadata:
            job_location = job.get('location', '').strip()
            is_remote = job.get('is_remote', False)
            
            # Remote job always scores high
            if is_remote or job_location.lower() in ['remote', 'anywhere']:
                location_scores.append(1.0)
                continue
            
            # No preferred location - neutral score
            if not preferred_location:
                location_scores.append(0.7)
                continue
            
            # Normalize for comparison
            preferred_normalized = preferred_location.strip().lower()
            job_location_normalized = job_location.lower()
            
            # User wants remote, job is remote
            if preferred_normalized == 'remote':
                location_scores.append(1.0 if is_remote else 0.4)
            # Exact location match
            elif preferred_normalized in job_location_normalized or job_location_normalized in preferred_normalized:
                location_scores.append(1.0)
            # Different location
            else:
                location_scores.append(0.4)
        
        return np.array(location_scores)
    
    def match_jobs(
        self,
        user_profile: Dict[str, Any],
        quiz_scores: Optional[Dict[str, float]] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Match user profile to jobs using 4-component weighted scoring.
        Quiz scores are ignored. Jobs are filtered by recommended roles.
        
        Args:
            user_profile: Dictionary containing:
                - skills: List of user's skills
                - previous_roles: List of previous job titles
                - years_of_experience: Years of work experience
                - preferred_location: Preferred job location (not used in scoring)
                - recommended_roles: List of recommended role titles to filter by (required)
            quiz_scores: Dictionary of skill -> score (0-100) (optional)
            top_k: Number of top matches to return
        
        Returns:
            List of matched jobs with scores and details
        """
        # Extract profile fields
        skills = user_profile.get("skills", [])
        previous_roles = user_profile.get("previous_roles", [])
        years_of_experience = user_profile.get("years_of_experience", 0)
        preferred_location = user_profile.get("preferred_location")
        recommended_roles = user_profile.get("recommended_roles", [])
        
        # Check if embeddings are loaded
        if self.embeddings is None or self.metadata is None:
            success = self._load_embeddings()
            if not success:
                raise ValueError(
                    "Job embeddings not loaded. Run: python src/build_job_embeddings.py --force"
                )
        
        if len(self.metadata) == 0:
            return []
        
        logger.info(
            f"Matching jobs for user: {len(skills)} skills, {len(previous_roles)} roles, "
            f"{years_of_experience} years exp, location={preferred_location}, "
            f"quiz_scores={'yes' if quiz_scores else 'no'}, "
            f"recommended_roles={len(recommended_roles) if recommended_roles else 0}"
        )
        
        # Filter jobs by recommended roles if provided
        filtered_metadata = self.metadata
        filtered_embeddings = self.embeddings
        
        if recommended_roles and len(recommended_roles) > 0:
            # Normalize recommended roles for case-insensitive matching
            normalized_recommended = [role.strip().lower() for role in recommended_roles]
            
            # Filter metadata and embeddings to only include jobs matching recommended roles
            filtered_indices = []
            for idx, job in enumerate(self.metadata):
                job_title = job.get('job_title', '').strip().lower()
                # Check if job title contains any of the recommended roles
                if any(rec_role in job_title or job_title in rec_role for rec_role in normalized_recommended):
                    filtered_indices.append(idx)
            
            if len(filtered_indices) == 0:
                logger.info(f"No jobs found matching recommended roles: {recommended_roles}")
                return []
            
            logger.info(f"Filtered to {len(filtered_indices)} jobs based on recommended roles")
            
            # Create filtered lists
            filtered_metadata = [self.metadata[i] for i in filtered_indices]
            filtered_embeddings = self.embeddings[filtered_indices]
        
        # Extract job titles for semantic similarity
        job_titles = [job.get('job_title', '') for job in filtered_metadata]
        
        # Compute component scores
        title_scores = self._compute_title_similarity(previous_roles, job_titles, filtered_embeddings)
        skill_scores = self._compute_skill_match(skills, filtered_metadata)
        green_skills_scores = self._compute_green_skills_score(skills, filtered_metadata)
        experience_scores = self._compute_experience_alignment(years_of_experience, filtered_metadata)
        
        # Note: quiz_scores and location are ignored as per new requirements
        # Weighted final score (no quiz or location components)
        final_scores = (
            self.semantic_weight * title_scores +
            self.skill_weight * skill_scores +
            self.green_skills_weight * green_skills_scores +
            self.experience_weight * experience_scores
        )
        
        # Get top K indices
        top_indices = np.argsort(final_scores)[::-1][:top_k]
        
        # Build result list
        matches = []
        
        # Normalize user skills for matched/missing calculation
        normalized_user_skills = set(self._normalize_skill(s) for s in skills)
        
        for idx in top_indices:
            job = filtered_metadata[idx]
            final_score = float(final_scores[idx])
            
            # Get skills required
            skills_required = job.get('skills_required', [])
            if not isinstance(skills_required, list):
                skills_required = []
            
            normalized_required = set(self._normalize_skill(s) for s in skills_required)
            
            # Calculate matched and missing skills
            matched_skills = list(normalized_user_skills.intersection(normalized_required))
            missing_skills = list(normalized_required - normalized_user_skills)
            
            match_data = {
                "job_id": job.get('job_id'),
                "job_title": job.get('job_title'),
                "job_description": job.get('job_description', ''),
                "company_name": job.get('company_name', ''),
                "location": job.get('location', ''),
                "is_remote": job.get('is_remote', False),
                "job_type": job.get('job_type', ''),
                "experience_required": job.get('experience_required', 0),
                "skills_required": skills_required,
                "final_score": round(final_score, 3),
                "fit_percentage": f"{int(final_score * 100)}%",
                "component_scores": {
                    "title_similarity": round(float(title_scores[idx]), 3),
                    "skill_match": round(float(skill_scores[idx]), 3),
                    "green_skills_count": round(float(green_skills_scores[idx]), 3),
                    "experience_alignment": round(float(experience_scores[idx]), 3)
                },
                "matched_skills": matched_skills,
                "missing_skills": missing_skills,
                "url": job.get('url', ''),
                "source": job.get('source', ''),
                "date_posted": job.get('date_posted', ''),
                "compensation_min": job.get('compensation_min'),
                "compensation_max": job.get('compensation_max'),
                "compensation_currency": job.get('compensation_currency', '')
            }
            
            matches.append(match_data)
        
        logger.info(f"Matched {len(matches)} jobs for user")
        
        return matches
    
    def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific job by its ID.
        
        Args:
            job_id: Job ID to fetch
        
        Returns:
            Job dictionary or None if not found
        """
        if self.metadata is None:
            self._load_embeddings()
        
        if self.metadata is None:
            return None
        
        for job in self.metadata:
            if job.get('job_id') == job_id:
                return job
        
        return None
