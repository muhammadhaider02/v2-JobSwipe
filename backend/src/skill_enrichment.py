import os
import pandas as pd
import numpy as np
import re
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Set
from src.logging_config import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
load_dotenv(BASE_DIR / ".env.local")

SRC_DIR = Path(__file__).resolve().parent  # src/
EXCEL_SKILL_GAP = str(SRC_DIR / os.getenv("EXCEL_SKILL_GAP"))
SHEET_SKILL_GAP = os.getenv("SHEET_SKILL_GAP")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")

# Similarity threshold for matching skills
SIMILARITY_THRESHOLD = 0.65

# Cache the model to avoid concurrent loading issues
_model_cache = None


def load_all_unique_skills() -> List[str]:
    """
    Load all unique skills from the skill_gap.xlsx file.
    Extracts skills from all columns except 'Role'.
    
    Returns:
        List of unique skill names
        
    Raises:
        FileNotFoundError: If Excel file doesn't exist
    """
    logger.info("Loading all unique skills")
    logger.debug("Excel path: %s, sheet: %s", EXCEL_SKILL_GAP, SHEET_SKILL_GAP)
    
    if not os.path.exists(EXCEL_SKILL_GAP):
        raise FileNotFoundError(f"Skill gap Excel file not found at: {EXCEL_SKILL_GAP}")
    
    # Read the Excel file
    df = pd.read_excel(EXCEL_SKILL_GAP, sheet_name=SHEET_SKILL_GAP)
    df.columns = [c.strip() for c in df.columns]
    
    # Get all columns except 'Role'
    skill_columns = [col for col in df.columns if col.lower() != 'role']
    
    # Collect all unique skills
    all_skills = set()
    for col in skill_columns:
        for value in df[col]:
            if pd.notna(value) and str(value).strip():
                all_skills.add(str(value).strip())
    
    unique_skills = sorted(list(all_skills))
    
    logger.info("Total unique skills found: %d", len(unique_skills))
    logger.debug("Sample skills: %s", unique_skills[:10])
    
    return unique_skills


def normalize_skill(text: str) -> str:
    """
    Normalize skill name for fuzzy matching.
    Removes dots, hyphens, underscores, spaces and converts to lowercase.
    
    Examples:
        'React.js' -> 'reactjs'
        'Node.js' -> 'nodejs'
        'Scikit-learn' -> 'scikitlearn'
    """
    return re.sub(r'[.\-_\s]+', '', text.lower())


def enrich_skills(resume_text: str, existing_skills: List[str]) -> List[str]:
    """
    Enrich the skills list by detecting technical skills mentioned in the resume.
    
    Uses hybrid approach:
    1. Normalized string matching (fast, handles React.js vs ReactJS)
    2. Sentence-based semantic matching (fallback for edge cases)
    
    Args:
        resume_text: Full text of the resume
        existing_skills: List of skills already parsed from Skills section
        
    Returns:
        Enriched list of skills (existing + auto-detected)
    """
    global _model_cache
    
    logger.info("Skill enrichment started")
    logger.debug("Existing skills count: %d", len(existing_skills))
    
    # Load all unique skills from master list
    try:
        master_skills = load_all_unique_skills()
    except Exception as e:
        logger.error("Error loading master skills: %s", e)
        logger.warning("Returning existing skills without enrichment")
        return existing_skills
    
    # Normalize existing skills for case-insensitive comparison
    existing_skills_lower = {skill.lower().strip() for skill in existing_skills}
    
    # Filter out skills that are already in the existing list
    skills_to_check = [
        skill for skill in master_skills 
        if skill.lower().strip() not in existing_skills_lower
    ]
    
    logger.debug("Skills to check against resume: %d", len(skills_to_check))
    
    if not skills_to_check:
        logger.debug("All master skills already present in existing skills")
        return existing_skills
    
    discovered_skills = []
    
    # PASS 1: Normalized string matching (fast)
    logger.debug("Pass 1: normalized string matching")
    resume_normalized = normalize_skill(resume_text)
    
    unmatched_skills = []
    for skill in skills_to_check:
        skill_normalized = normalize_skill(skill)
        if skill_normalized in resume_normalized:
            discovered_skills.append(skill)
            logger.debug("String match: %s", skill)
        else:
            unmatched_skills.append(skill)
    
    logger.debug("Pass 1 results: %d skills found via string matching", len(discovered_skills))
    
    # PASS 2: Sentence-based semantic matching (fallback for unmatched skills)
    if unmatched_skills:
        logger.debug("Pass 2: semantic matching fallback (%d unmatched skills)", len(unmatched_skills))
        
        # Load or use cached embedding model
        if _model_cache is None:
            logger.info("Loading embedding model: %s", EMBEDDING_MODEL_NAME)
            _model_cache = SentenceTransformer(EMBEDDING_MODEL_NAME, device="cpu")
            logger.info("Model loaded successfully")
        else:
            logger.debug("Using cached embedding model: %s", EMBEDDING_MODEL_NAME)
        
        model = _model_cache
        
        # Split resume into sentences for better semantic matching
        sentences = [s.strip() for s in resume_text.split('.') if s.strip()]
        logger.debug("Split resume into %d sentences", len(sentences))
        
        # Encode sentences
        logger.debug("Computing embeddings for resume sentences")
        sentence_embeddings = model.encode(sentences, show_progress_bar=False)
        
        # Encode ALL unmatched skills in one batch call (much faster than one at a time)
        logger.debug("Computing embeddings for unmatched skills (batch)")
        skill_embeddings = model.encode(unmatched_skills, batch_size=64, show_progress_bar=False)
        similarities_matrix = cosine_similarity(skill_embeddings, sentence_embeddings)

        for i, skill in enumerate(unmatched_skills):
            max_similarity = similarities_matrix[i].max()
            if max_similarity >= SIMILARITY_THRESHOLD:
                discovered_skills.append(skill)
                logger.debug("Semantic match: %s (similarity: %.3f)", skill, max_similarity)

        pass2_count = len(discovered_skills) - len([s for s in discovered_skills if s in skills_to_check[:len(skills_to_check) - len(unmatched_skills)]])
        logger.debug("Pass 2 results: %d additional skills found via semantic matching", pass2_count)
    
    logger.info("Enrichment complete: %d auto-detected skills", len(discovered_skills))
    
    # Merge with existing skills
    enriched_skills = existing_skills + discovered_skills
    
    logger.info("Total skills after enrichment: %d", len(enriched_skills))
    
    return enriched_skills
