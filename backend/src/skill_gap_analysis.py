import os

# --- FORCE DISABLE META TENSOR MODE ---
os.environ["PYTORCH_DISABLE_META_LOADER"] = "1"
os.environ["TORCH_LOAD_DIRECT"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Dict, Any
from threading import Lock
from src.logging_config import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
load_dotenv(BASE_DIR / ".env.local")

# Set custom cache directory for sentence-transformers models
SENTENCE_TRANSFORMERS_HOME = os.getenv("SENTENCE_TRANSFORMERS_HOME")
if SENTENCE_TRANSFORMERS_HOME:
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(BASE_DIR / SENTENCE_TRANSFORMERS_HOME)

SRC_DIR = Path(__file__).resolve().parent  # src/
EXCEL_SKILL_GAP = str(SRC_DIR / os.getenv("EXCEL_SKILL_GAP"))
SHEET_SKILL_GAP = os.getenv("SHEET_SKILL_GAP")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")

# Similarity threshold for matching skills
SIMILARITY_THRESHOLD = 0.65

# Cache the model to avoid concurrent loading issues
# Cache the model to avoid concurrent loading issues
_model_cache = None
_model_lock = Lock()

# Cache the Excel data to avoid repeated reads
_excel_cache = None
_excel_lock = Lock()


def load_skill_gap_data(role_name: str) -> List[str]:
    """
    Load the skill gap Excel file and extract required skills for the given role.
    
    Args:
        role_name: The name of the role to analyze
        
    Returns:
        List of required skills for that role
        
    Raises:
        FileNotFoundError: If Excel file doesn't exist
        ValueError: If role is not found in the Excel file
    """
    global _excel_cache
    
    # Load Excel data if not cached
    if _excel_cache is None:
        with _excel_lock:
            if _excel_cache is None:
                logger.info("Loading skill gap data from %s, sheet=%s", EXCEL_SKILL_GAP, SHEET_SKILL_GAP)
                
                if not os.path.exists(EXCEL_SKILL_GAP):
                    raise FileNotFoundError(f"Skill gap Excel file not found at: {EXCEL_SKILL_GAP}")
                
                # Read the Excel file
                df = pd.read_excel(EXCEL_SKILL_GAP, sheet_name=SHEET_SKILL_GAP)
                df.columns = [c.strip() for c in df.columns]
                
                logger.debug("Total roles in Excel: %d, columns: %s", len(df), list(df.columns))
                _excel_cache = df
    
    df = _excel_cache
    logger.debug("Target role: %s", role_name)
    
    # Find the row matching the role (case-insensitive)
    role_row = df[df['Role'].str.strip().str.lower() == role_name.strip().lower()]
    
    if role_row.empty:
        available_roles = df['Role'].tolist()
        logger.warning("Role '%s' not found in Excel file. Available roles: %s", role_name, available_roles)
        raise ValueError(f"Role '{role_name}' not found in skill gap data. Available roles: {available_roles}")
    
    # Extract all skills from the row (all columns except 'Role')
    role_row = role_row.iloc[0]
    skill_columns = [col for col in df.columns if col.lower() != 'role']
    
    required_skills = []
    for col in skill_columns:
        skill_value = role_row[col]
        if pd.notna(skill_value) and str(skill_value).strip():
            required_skills.append(str(skill_value).strip())
    
    logger.debug("Required skills found: %d", len(required_skills))
    
    return required_skills


def get_embedding_model():
    """
    Safely load the embedding model with thread lock to prevent concurrent loading issues.
    
    Returns:
        SentenceTransformer: The cached or newly loaded embedding model
    """
    global _model_cache
    if _model_cache is not None:
        logger.debug("Using cached embedding model: %s", EMBEDDING_MODEL_NAME)
        return _model_cache

    # Prevent concurrent model loads
    with _model_lock:
        if _model_cache is None:
            logger.info("Loading embedding model: %s", EMBEDDING_MODEL_NAME)
            _model_cache = SentenceTransformer(EMBEDDING_MODEL_NAME)

        return _model_cache


def compare_skills_semantic(user_skills: List[str], required_skills: List[str]) -> Dict[str, Any]:
    """
    Compare user skills with required skills using semantic similarity.
    
    Args:
        user_skills: List of skills the user has
        required_skills: List of skills required for the role
        
    Returns:
        Dictionary containing:
        - existing_skills: Skills user has that match requirements
        - required_skills: Skills user needs to acquire
        - skill_matches: Detailed matching information with similarity scores
    """
    logger.info(
        "Comparing skills semantically: user_skills=%d, required_skills=%d, threshold=%.2f",
        len(user_skills), len(required_skills), SIMILARITY_THRESHOLD,
    )
    
    if not user_skills:
        logger.debug("No user skills provided - all required skills are missing")
        return {
            "existing_skills": [],
            "required_skills": required_skills,
            "skill_matches": []
        }
    
    if not required_skills:
        logger.debug("No required skills found for this role")
        return {
            "existing_skills": user_skills,
            "required_skills": [],
            "skill_matches": []
        }
    
    # Load the embedding model safely
    model = get_embedding_model()
    
    # Compute embeddings
    logger.debug("Computing embeddings for user skills")
    user_embeddings = model.encode(user_skills, convert_to_numpy=True, show_progress_bar=False)
    
    logger.debug("Computing embeddings for required skills")
    required_embeddings = model.encode(required_skills, convert_to_numpy=True, show_progress_bar=False)
    
    # Calculate cosine similarity matrix
    logger.debug("Calculating similarity matrix")
    similarity_matrix = cosine_similarity(user_embeddings, required_embeddings)
    
    # Track which required skills have been matched
    matched_required_indices = set()
    existing_skills = []
    skill_matches = []
    
    logger.debug("Similarity analysis starting")
    
    # For each user skill, find the best matching required skill
    for i, user_skill in enumerate(user_skills):
        similarities = similarity_matrix[i]
        best_match_idx = np.argmax(similarities)
        best_similarity = similarities[best_match_idx]
        best_required_skill = required_skills[best_match_idx]
        
        logger.debug("User skill '%s' -> best match '%s' (similarity: %.3f)", user_skill, best_required_skill, best_similarity)
        
        if best_similarity >= SIMILARITY_THRESHOLD:
            existing_skills.append(user_skill)
            matched_required_indices.add(best_match_idx)
            skill_matches.append({
                "user_skill": user_skill,
                "matched_required_skill": best_required_skill,
                "similarity": round(float(best_similarity), 3),
                "status": "matched"
            })
        else:
            skill_matches.append({
                "user_skill": user_skill,
                "matched_required_skill": best_required_skill,
                "similarity": round(float(best_similarity), 3),
                "status": "no_match"
            })
    
    # Find required skills that weren't matched
    missing_skills = [
        required_skills[i] 
        for i in range(len(required_skills)) 
        if i not in matched_required_indices
    ]
    
    logger.info("Skill comparison results: existing=%d, missing=%d", len(existing_skills), len(missing_skills))
    
    return {
        "existing_skills": existing_skills,
        "required_skills": missing_skills,
        "skill_matches": skill_matches
    }


def analyze_skill_gap(role_name: str, user_skills: List[str]) -> Dict[str, Any]:
    """
    Main entry point for skill gap analysis.
    
    Args:
        role_name: The role to analyze
        user_skills: List of skills the user currently has
        
    Returns:
        Dictionary with skill gap analysis results
    """
    logger.info("Starting skill gap analysis for role=%s", role_name)
    
    # Load required skills for the role
    required_skills = load_skill_gap_data(role_name)
    
    # Compare user skills with required skills
    comparison_result = compare_skills_semantic(user_skills, required_skills)
    
    # Add role name to the result
    comparison_result["role"] = role_name
    comparison_result["total_required_skills"] = len(required_skills)
    comparison_result["total_existing_skills"] = len(comparison_result["existing_skills"])
    comparison_result["total_missing_skills"] = len(comparison_result["required_skills"])
    
    # Calculate completion percentage
    # Formula: (Matched Skills / (Matched Skills + Missing Skills)) * 100
    # This ensures it never exceeds 100% and accurately reflects coverage of requirements
    total_relevant_skills = comparison_result["total_existing_skills"] + comparison_result["total_missing_skills"]
    
    if total_relevant_skills > 0:
        completion_percentage = (comparison_result["total_existing_skills"] / total_relevant_skills) * 100
        comparison_result["completion_percentage"] = round(completion_percentage, 1)
    else:
        comparison_result["completion_percentage"] = 0.0
    
    logger.info("Skill gap analysis complete: completion=%.1f%%", comparison_result['completion_percentage'])
    
    return comparison_result
