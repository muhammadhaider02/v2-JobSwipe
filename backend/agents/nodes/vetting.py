"""
Vetting Officer Node: Intelligent job matching with multi-factor scoring.

Scores and filters jobs based on Title Similarity (35%), Skill Match (25%), 
Quiz Score (20%), Experience Alignment (15%), and Location Fit (5%).
"""

import re
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from sentence_transformers import SentenceTransformer
from agents.state import AgentState, VettedJob
from services import get_supabase_service, get_llm_service
from langchain_core.messages import AIMessage


# Scoring weights (must sum to 1.0)
WEIGHTS = {
    "title_similarity": 0.35,
    "skill_match": 0.25,
    "quiz_score": 0.20,
    "experience_alignment": 0.15,
    "location_fit": 0.05
}

# Minimum score threshold for jobs to pass vetting
MIN_SCORE_THRESHOLD = 0.60

# Semantic similarity threshold for skill matching
SKILL_SIMILARITY_THRESHOLD = 0.30

# Experience band definitions (years)
EXPERIENCE_BANDS = {
    "intern": (0, 1),
    "junior": (0, 2),
    "mid": (2, 5),
    "senior": (5, 10),
    "lead": (10, float('inf'))
}

# Seniority keywords for title-based experience detection
SENIORITY_KEYWORDS = {
    "intern": ["intern", "trainee", "apprentice"],
    "junior": ["junior", "jr", "associate", "entry"],
    "mid": ["mid", "intermediate", "engineer", "developer"],
    "senior": ["senior", "sr", "principal", "lead", "staff"],
    "lead": ["lead", "principal", "architect", "director", "head", "manager"]
}

# Cache for embedding model (load once)
_model_cache = None


def get_embedding_model() -> SentenceTransformer:
    """Get or initialize cached SentenceTransformer model."""
    global _model_cache
    if _model_cache is None:
        print("Loading SentenceTransformer model (all-MiniLM-L6-v2)...")
        _model_cache = SentenceTransformer("all-MiniLM-L6-v2")
    return _model_cache


def fetch_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch complete user profile including quiz scores.
    
    Args:
        user_id: UUID of user
        
    Returns:
        User profile dict or None if not found
    """
    supabase = get_supabase_service()
    profile = supabase.get_user_profile(user_id)
    
    if not profile:
        print(f"User profile not found for: {user_id}")
        return None
    
    # Ensure required fields have defaults
    profile.setdefault("skills", [])
    profile.setdefault("previous_roles", [])
    profile.setdefault("experience", [])
    profile.setdefault("years_of_experience", 0)
    profile.setdefault("location", "")
    profile.setdefault("quiz_scores", [])
    
    return profile


def extract_user_titles(profile: Dict[str, Any]) -> List[str]:
    """
    Extract all job titles from user profile.
    
    Combines previous_roles array and job titles from experience array.
    
    Args:
        profile: User profile dictionary
        
    Returns:
        List of job titles
    """
    titles = []
    
    # Add from previous_roles
    previous_roles = profile.get("previous_roles", [])
    if isinstance(previous_roles, list):
        titles.extend([role for role in previous_roles if role])
    
    # Add from experience array
    experience = profile.get("experience", [])
    if isinstance(experience, list):
        for exp in experience:
            if isinstance(exp, dict):
                title = exp.get("job_title") or exp.get("title")
                if title:
                    titles.append(title)
    
    # Remove duplicates and empty strings
    titles = list(set([t.strip() for t in titles if t and t.strip()]))
    
    return titles


def calculate_title_similarity(user_titles: List[str], job_title: str) -> float:
    """
    Calculate semantic similarity between user's previous titles and job title.
    
    Uses SentenceTransformer embeddings and cosine similarity. Returns max 
    similarity across all user titles.
    
    Args:
        user_titles: List of user's previous job titles
        job_title: Job title to match against
        
    Returns:
        Similarity score (0.0 to 1.0)
    """
    if not user_titles or not job_title:
        return 0.0
    
    try:
        model = get_embedding_model()
        
        # Batch encode all titles at once (efficient)
        all_titles = user_titles + [job_title]
        embeddings = model.encode(all_titles, normalize_embeddings=True)
        
        # User embeddings vs job embedding
        user_embeddings = embeddings[:-1]
        job_embedding = embeddings[-1]
        
        # Calculate cosine similarities
        similarities = user_embeddings @ job_embedding
        
        # Return max similarity
        max_similarity = float(np.max(similarities))
        return max_similarity
    
    except Exception as e:
        print(f"Title similarity error: {e}")
        return 0.0


def normalize_skill(skill: str) -> str:
    """Normalize skill name for matching (lowercase, no special chars)."""
    return re.sub(r'[.\-_\s]+', '', skill.lower())


def calculate_skill_match(user_skills: List[str], job_skills: List[str]) -> Tuple[float, List[str], List[str]]:
    """
    Calculate skill match using semantic similarity.
    
    Uses SentenceTransformer with 0.65 similarity threshold for matching.
    Returns both score and lists of matching/missing skills.
    
    Args:
        user_skills: User's skills from profile
        job_skills: Required skills from job
        
    Returns:
        Tuple of (match_score, matching_skills, missing_skills)
    """
    if not job_skills:
        return 1.0, [], []  # No requirements = perfect match
    
    if not user_skills:
        return 0.0, [], job_skills  # No skills = no match
    
    try:
        model = get_embedding_model()
        
        # Encode all skills
        user_embeddings = model.encode(user_skills, normalize_embeddings=True)
        job_embeddings = model.encode(job_skills, normalize_embeddings=True)
        
        # Calculate similarity matrix (user_skills x job_skills)
        similarity_matrix = user_embeddings @ job_embeddings.T
        
        matching_skills = []
        missing_skills = []
        
        # For each job skill, check if any user skill matches
        for job_idx, job_skill in enumerate(job_skills):
            max_similarity = similarity_matrix[:, job_idx].max()
            
            if max_similarity >= SKILL_SIMILARITY_THRESHOLD:
                matching_skills.append(job_skill)
            else:
                missing_skills.append(job_skill)
        
        # Score = percentage of required skills matched
        match_score = len(matching_skills) / len(job_skills)
        
        return match_score, matching_skills, missing_skills
    
    except Exception as e:
        print(f"Skill match error: {e}")
        # Fallback to exact string matching
        user_skills_normalized = {normalize_skill(s): s for s in user_skills}
        matching = []
        missing = []
        
        for job_skill in job_skills:
            normalized = normalize_skill(job_skill)
            if normalized in user_skills_normalized:
                matching.append(job_skill)
            else:
                missing.append(job_skill)
        
        score = len(matching) / len(job_skills) if job_skills else 1.0
        return score, matching, missing


def calculate_quiz_score(quiz_scores: List[Dict], job_skills: List[str]) -> float:
    """
    Calculate weighted quiz score for job-relevant skills.
    
    Filters quiz scores to only those for skills the job requires, then 
    computes weighted average. Returns 0 if no relevant quizzes taken.
    
    Args:
        quiz_scores: List of quiz score objects from user profile
        job_skills: Required skills from job
        
    Returns:
        Quiz score (0.0 to 1.0)
    """
    if not quiz_scores or not job_skills:
        return 0.0
    
    try:
        # Normalize job skills for matching
        job_skills_normalized = {normalize_skill(s): s for s in job_skills}
        
        # Filter to relevant quizzes
        relevant_quizzes = []
        for quiz in quiz_scores:
            skill_name = quiz.get("skill_name", "")
            if normalize_skill(skill_name) in job_skills_normalized:
                # Extract score percentage (0-1 scale)
                score_pct = quiz.get("score_percentage", 0) / 100.0
                relevant_quizzes.append({
                    "skill": skill_name,
                    "score": score_pct
                })
        
        if not relevant_quizzes:
            return 0.0
        
        # Weighted average (all skills weighted equally for now)
        total_score = sum(q["score"] for q in relevant_quizzes)
        avg_score = total_score / len(relevant_quizzes)
        
        return avg_score
    
    except Exception as e:
        print(f"Quiz score error: {e}")
        return 0.0


def parse_experience_band(years: int, title: str = "") -> str:
    """
    Determine experience band from years and validate with title keywords.
    
    Args:
        years: Years of experience
        title: Job title for keyword validation
        
    Returns:
        Experience band: "intern", "junior", "mid", "senior", or "lead"
    """
    title_lower = title.lower() if title else ""
    
    # Check title keywords first (more specific)
    for band, keywords in SENIORITY_KEYWORDS.items():
        if any(kw in title_lower for kw in keywords):
            return band
    
    # Fallback to years-based bands
    if years < 1:
        return "intern"
    elif years < 2:
        return "junior"
    elif years < 5:
        return "mid"
    elif years < 10:
        return "senior"
    else:
        return "lead"


def calculate_experience_alignment(user_years: int, user_latest_title: str, 
                                   job_experience: Optional[str]) -> float:
    """
    Calculate experience alignment between user and job requirements.
    
    Scores based on band matching with partial credit for adjacent bands.
    
    Args:
        user_years: User's years of experience
        user_latest_title: User's most recent job title
        job_experience: Job's experience requirement string
        
    Returns:
        Alignment score (0.0 to 1.0)
    """
    if not job_experience:
        return 1.0  # No requirement = always match
    
    try:
        # Parse user's band
        user_band = parse_experience_band(user_years, user_latest_title)
        
        # Parse job's required band from text
        job_experience_lower = job_experience.lower()
        job_band = None
        
        for band, keywords in SENIORITY_KEYWORDS.items():
            if any(kw in job_experience_lower for kw in keywords):
                job_band = band
                break
        
        # Fallback: extract years from job requirement
        if not job_band:
            years_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)', job_experience_lower)
            if years_match:
                required_years = int(years_match.group(1))
                job_band = parse_experience_band(required_years)
            else:
                return 0.7  # Unknown requirement, give moderate score
        
        # Band hierarchy for distance calculation
        band_order = ["intern", "junior", "mid", "senior", "lead"]
        
        try:
            user_idx = band_order.index(user_band)
            job_idx = band_order.index(job_band)
            distance = abs(user_idx - job_idx)
        except ValueError:
            return 0.7  # Unknown band, moderate score
        
        # Score based on distance
        if distance == 0:
            return 1.0  # Exact match
        elif distance == 1:
            return 0.7  # Adjacent band (e.g., mid vs senior)
        elif distance == 2:
            return 0.4  # 2 bands apart
        else:
            return 0.3  # 3+ bands apart
    
    except Exception as e:
        print(f"Experience alignment error: {e}")
        return 0.5  # Default to moderate score on error


def calculate_location_fit(user_location: str, job_location: str, 
                          job_type: Optional[str] = None) -> float:
    """
    Calculate location compatibility score.
    
    Args:
        user_location: User's location from profile
        job_location: Job's location requirement
        job_type: Employment type (checks for "remote")
        
    Returns:
        Location score (0.0 to 1.0)
    """
    # Remote jobs always match
    if job_type and "remote" in job_type.lower():
        return 1.0
    
    if "remote" in job_location.lower():
        return 1.0
    
    # Exact location match (case-insensitive)
    if user_location and job_location:
        user_loc_clean = user_location.strip().lower()
        job_loc_clean = job_location.strip().lower()
        
        if user_loc_clean == job_loc_clean:
            return 1.0
        
        # Partial match (city within location string)
        if user_loc_clean in job_loc_clean or job_loc_clean in user_loc_clean:
            return 0.8
    
    # Location mismatch
    return 0.4


def calculate_final_score(scores: Dict[str, float]) -> float:
    """
    Calculate weighted final score from individual component scores.
    
    Args:
        scores: Dictionary with keys matching WEIGHTS
        
    Returns:
        Final weighted score (0.0 to 1.0)
    """
    final_score = sum(scores[key] * WEIGHTS[key] for key in WEIGHTS.keys())
    return final_score


def generate_reasoning(job: Dict[str, Any], user_profile: Dict[str, Any], 
                      scores: Dict[str, float], matching_skills: List[str], 
                      skill_gaps: List[str]) -> str:
    """
    Generate LLM-based reasoning for job match.
    
    Args:
        job: Job data dictionary
        user_profile: User profile dictionary
        scores: Score breakdown dictionary
        matching_skills: List of matched skills
        skill_gaps: List of missing skills
        
    Returns:
        2-3 sentence reasoning string
    """
    try:
        llm = get_llm_service()
        
        # Build prompt for LLM
        final_score = calculate_final_score(scores)
        
        prompt = f"""You are a career advisor analyzing job fit. Generate a 2-3 sentence explanation of why this job is a good match for the candidate.

Job Title: {job.get('title', 'Unknown')}
Company: {job.get('company', 'Unknown')}
Required Skills: {', '.join(job.get('skills', [])[:10])}

Candidate Profile:
- Previous Roles: {', '.join(user_profile.get('previous_roles', [])[:3])}
- Skills: {', '.join(user_profile.get('skills', [])[:15])}
- Years of Experience: {user_profile.get('years_of_experience', 0)}
- Location: {user_profile.get('location', 'Unknown')}

Match Analysis:
- Overall Score: {final_score:.1%}
- Title Similarity: {scores['title_similarity']:.1%}
- Skill Match: {scores['skill_match']:.1%}
- Quiz Performance: {scores['quiz_score']:.1%}
- Experience Fit: {scores['experience_alignment']:.1%}
- Location Fit: {scores['location_fit']:.1%}
- Matching Skills: {', '.join(matching_skills[:8])}
- Skill Gaps: {', '.join(skill_gaps[:5])}

Generate a concise 2-3 sentence explanation focusing on the candidate's strengths that make them suitable for this role, and briefly mention any gaps. Be specific and reference actual skills."""

        response = llm.generate_text(
            prompt=prompt,
            temperature=0.7,
            max_tokens=200
        )
        
        reasoning = response.get("content", "").strip()
        
        # Fallback if LLM fails
        if not reasoning:
            raise ValueError("Empty LLM response")
        
        return reasoning
    
    except Exception as e:
        print(f"LLM reasoning generation failed: {e}")
        
        # Fallback to template-based reasoning
        final_score = calculate_final_score(scores)
        
        if final_score >= 0.75:
            strength = "strong match"
        elif final_score >= 0.60:
            strength = "moderate match"
        else:
            strength = "potential opportunity"
        
        gap_text = ""
        if skill_gaps:
            gap_text = f" You'll need to develop {', '.join(skill_gaps[:3])}."
        
        return f"This role is a {strength} based on your {', '.join(matching_skills[:3])} experience.{gap_text} Your background in {', '.join(user_profile.get('previous_roles', ['your field'])[:2])} aligns well with the requirements."


def vetting_officer_node(state: AgentState) -> Dict[str, Any]:
    """
    Vetting Officer: Score and filter jobs using 5-factor analysis.
    
    Responsibilities:
    1. Fetch user profile and quiz scores
    2. Score each enriched job on 5 factors:
       - Title Similarity (35%)
       - Skill Match (25%)
       - Quiz Score (20%)
       - Experience Alignment (15%)
       - Location Fit (5%)
    3. Filter jobs scoring < 0.60 threshold
    4. Generate LLM reasoning for each match
    5. Sort by match score descending
    6. Update state with vetted_jobs
    
    Args:
        state: Current agent state with enriched jobs
        
    Returns:
        Updated state dictionary with vetted_jobs
    """
    print("\n" + "="*60)
    print("VETTING OFFICER ACTIVATED")
    print("="*60 + "\n")
    
    # Extract state data
    user_id = state.get("user_id", "")
    raw_jobs = state.get("raw_job_list", [])
    
    if not user_id:
        error_msg = "No user_id provided for vetting"
        print(f"{error_msg}")
        return {
            "vetted_jobs": [],
            "error": error_msg,
            "messages": [AIMessage(content=f"Error: {error_msg}")]
        }
    
    if not raw_jobs:
        print("No jobs to vet")
        return {
            "vetted_jobs": [],
            "messages": [AIMessage(content="No jobs available for vetting.")]
        }
    
    print(f"Vetting {len(raw_jobs)} jobs for user {user_id}...\n")
    
    # Fetch user profile
    print("Fetching user profile...")
    user_profile = fetch_user_profile(user_id)
    
    if not user_profile:
        error_msg = f"User profile not found: {user_id}"
        print(f"{error_msg}")
        return {
            "vetted_jobs": [],
            "error": error_msg,
            "messages": [AIMessage(content=f"Error: {error_msg}")]
        }
    
    print(f"   Profile loaded")
    print(f"   Skills: {len(user_profile.get('skills', []))}")
    print(f"   Experience: {user_profile.get('years_of_experience', 0)} years")
    print(f"   Quiz scores: {len(user_profile.get('quiz_scores', []))}\n")
    
    # Extract user data for scoring
    user_titles = extract_user_titles(user_profile)
    user_skills = user_profile.get("skills", [])
    user_years = user_profile.get("years_of_experience", 0)
    user_location = user_profile.get("location", "")
    quiz_scores = user_profile.get("quiz_scores", [])
    
    # Get latest title for experience matching
    user_latest_title = ""
    experience = user_profile.get("experience", [])
    if experience and isinstance(experience, list) and len(experience) > 0:
        latest_exp = experience[0]
        if isinstance(latest_exp, dict):
            user_latest_title = latest_exp.get("job_title") or latest_exp.get("title", "")
    
    print(f"Scoring jobs with 5-factor analysis...")
    print(f"   Weights: Title={WEIGHTS['title_similarity']:.0%}, Skill={WEIGHTS['skill_match']:.0%}, "
          f"Quiz={WEIGHTS['quiz_score']:.0%}, Exp={WEIGHTS['experience_alignment']:.0%}, "
          f"Location={WEIGHTS['location_fit']:.0%}\n")
    
    vetted_jobs = []
    filtered_count = 0
    
    try:
        # Process each job
        for idx, job in enumerate(raw_jobs, 1):
            job_title = job.get("title", "")
            job_skills = job.get("skills", [])
            job_experience = job.get("experience_required")
            job_location = job.get("location", "")
            job_type = job.get("employment_type")
            
            # Skip jobs with low enrichment confidence
            enrichment_confidence = job.get("enrichment_confidence", 1.0)
            if enrichment_confidence < 0.5:
                print(f"Job {idx}: Skipped (low enrichment confidence: {enrichment_confidence:.2f})")
                filtered_count += 1
                continue
            
            # Calculate individual scores
            title_score = calculate_title_similarity(user_titles, job_title)
            skill_score, matching_skills, skill_gaps = calculate_skill_match(user_skills, job_skills)
            quiz_score = calculate_quiz_score(quiz_scores, job_skills)
            experience_score = calculate_experience_alignment(user_years, user_latest_title, job_experience)
            location_score = calculate_location_fit(user_location, job_location, job_type)
            
            # Build score breakdown
            scores = {
                "title_similarity": title_score,
                "skill_match": skill_score,
                "quiz_score": quiz_score,
                "experience_alignment": experience_score,
                "location_fit": location_score
            }
            
            # Calculate final weighted score
            final_score = calculate_final_score(scores)
            
            # Filter by threshold
            if final_score < MIN_SCORE_THRESHOLD:
                print(f"Job {idx}: {job_title} - Filtered (score: {final_score:.2f})")
                filtered_count += 1
                continue
            
            # Generate reasoning
            reasoning = generate_reasoning(job, user_profile, scores, matching_skills, skill_gaps)
            
            # Determine confidence level
            if final_score >= 0.75:
                confidence = "high"
                recommendation = "strong_fit"
            elif final_score >= 0.60:
                confidence = "medium"
                recommendation = "moderate_fit"
            else:
                confidence = "low"
                recommendation = "weak_fit"
            
            # Create VettedJob object
            vetted_job: VettedJob = {
                "job_id": job.get("job_id", ""),
                "job_data": job,
                "match_score": final_score,
                "reasoning": reasoning,
                "confidence": confidence,
                "recommendation": recommendation,
                "skill_gaps": skill_gaps,
                "matching_skills": matching_skills
            }
            
            vetted_jobs.append(vetted_job)
            
            print(f"Job {idx}: {job_title} - Score: {final_score:.2f} ({confidence})")
        
        # Sort by match score descending
        vetted_jobs.sort(key=lambda x: x["match_score"], reverse=True)
        
        print(f"\nVetting Complete:")
        print(f"   Total jobs processed: {len(raw_jobs)}")
        print(f"   Jobs passed vetting: {len(vetted_jobs)}")
        print(f"   Jobs filtered out: {filtered_count}")
        
        if vetted_jobs:
            print(f"   Top match: {vetted_jobs[0]['job_data'].get('title')} ({vetted_jobs[0]['match_score']:.2f})")
            print(f"   Average score: {np.mean([j['match_score'] for j in vetted_jobs]):.2f}\n")
        
        # Build summary message
        summary = f"""Vetted {len(raw_jobs)} jobs - {len(vetted_jobs)} qualified matches found:

Scoring Breakdown:
  • Jobs passed threshold (≥{MIN_SCORE_THRESHOLD:.0%}): {len(vetted_jobs)}
  • High confidence matches (≥75%): {sum(1 for j in vetted_jobs if j['match_score'] >= 0.75)}
  • Medium confidence (60-75%): {sum(1 for j in vetted_jobs if 0.60 <= j['match_score'] < 0.75)}
  • Jobs filtered out: {filtered_count}

Top matches sorted by relevance and ready for review."""
        
        return {
            "vetted_jobs": vetted_jobs,
            "user_profile": user_profile,  # Store for downstream nodes
            "messages": [AIMessage(content=summary)]
        }
    
    except Exception as e:
        error_msg = f"Vetting error: {str(e)}"
        print(f"\n{error_msg}\n")
        import traceback
        traceback.print_exc()
        
        return {
            "vetted_jobs": [],
            "error": error_msg,
            "messages": [AIMessage(content=f"Vetting failed: {error_msg}")]
        }


# Export node
__all__ = ["vetting_officer_node"]
