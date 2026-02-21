import os
import pandas as pd
import numpy as np
import re
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Set

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
    print(f"\n==== LOADING ALL UNIQUE SKILLS ====")
    print(f"Excel Path: {EXCEL_SKILL_GAP}")
    print(f"Sheet Name: {SHEET_SKILL_GAP}")
    
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
    
    print(f"Total unique skills found: {len(unique_skills)}")
    print(f"Sample skills: {unique_skills[:10]}")
    
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
    
    print(f"\n==== SKILL ENRICHMENT ====")
    print(f"Existing skills count: {len(existing_skills)}")
    print(f"Existing skills: {existing_skills}")
    
    # Load all unique skills from master list
    try:
        master_skills = load_all_unique_skills()
    except Exception as e:
        print(f"Error loading master skills: {e}")
        print("Returning existing skills without enrichment")
        return existing_skills
    
    # Normalize existing skills for case-insensitive comparison
    existing_skills_lower = {skill.lower().strip() for skill in existing_skills}
    
    # Filter out skills that are already in the existing list
    skills_to_check = [
        skill for skill in master_skills 
        if skill.lower().strip() not in existing_skills_lower
    ]
    
    print(f"Skills to check against resume: {len(skills_to_check)}")
    
    if not skills_to_check:
        print("All master skills already present in existing skills")
        return existing_skills
    
    discovered_skills = []
    
    # PASS 1: Normalized string matching (fast)
    print(f"\n==== PASS 1: NORMALIZED STRING MATCHING ====")
    resume_normalized = normalize_skill(resume_text)
    
    unmatched_skills = []
    for skill in skills_to_check:
        skill_normalized = normalize_skill(skill)
        if skill_normalized in resume_normalized:
            discovered_skills.append(skill)
            print(f"  ✓ String match: '{skill}' (normalized: '{skill_normalized}')")
        else:
            unmatched_skills.append(skill)
    
    print(f"Pass 1 results: {len(discovered_skills)} skills found via string matching")
    
    # PASS 2: Sentence-based semantic matching (fallback for unmatched skills)
    if unmatched_skills:
        print(f"\n==== PASS 2: SEMANTIC MATCHING (FALLBACK) ====")
        print(f"Checking {len(unmatched_skills)} unmatched skills using semantic similarity...")
        
        # Load or use cached embedding model
        if _model_cache is None:
            print(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
            _model_cache = SentenceTransformer(EMBEDDING_MODEL_NAME, device="cpu")
            print("Model loaded successfully")
        else:
            print(f"Using cached embedding model: {EMBEDDING_MODEL_NAME}")
        
        model = _model_cache
        
        # Split resume into sentences for better semantic matching
        sentences = [s.strip() for s in resume_text.split('.') if s.strip()]
        print(f"Split resume into {len(sentences)} sentences")
        
        # Encode sentences
        print("Computing embeddings for resume sentences...")
        sentence_embeddings = model.encode(sentences)
        
        # Check each unmatched skill
        for skill in unmatched_skills:
            skill_embedding = model.encode([skill])
            similarities = cosine_similarity(skill_embedding, sentence_embeddings)
            max_similarity = similarities.max()
            
            if max_similarity >= SIMILARITY_THRESHOLD:
                discovered_skills.append(skill)
                print(f"  ✓ Semantic match: '{skill}' (similarity: {max_similarity:.3f})")
        
        pass2_count = len([s for s in discovered_skills if s not in discovered_skills[:len(discovered_skills) - len(unmatched_skills)]])
        print(f"Pass 2 results: {pass2_count} additional skills found via semantic matching")
    
    print(f"\n==== ENRICHMENT RESULTS ====")
    print(f"Total auto-detected skills: {len(discovered_skills)}")
    print(f"Skills found: {discovered_skills}")
    
    # Merge with existing skills
    enriched_skills = existing_skills + discovered_skills
    
    print(f"Total skills after enrichment: {len(enriched_skills)}")
    print("=" * 60)
    
    return enriched_skills
