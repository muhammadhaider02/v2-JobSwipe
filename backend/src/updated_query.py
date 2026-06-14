import os
import pickle
import numpy as np
from sklearn.preprocessing import normalize
import faiss
from dotenv import load_dotenv
from pathlib import Path
from src.logging_config import get_logger
from services.embedding_service import get_embedding_service

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
load_dotenv(BASE_DIR / ".env.local")

SRC_DIR = Path(__file__).resolve().parent  # src/
FAISS_INDEX_PATH = str(SRC_DIR / os.getenv("FAISS_INDEX_PATH"))
METADATA_PATH = str(SRC_DIR / os.getenv("METADATA_PATH"))

ROLES = [
    "Software Engineer", "Full Stack Developer", "Frontend Developer", "Backend Developer",
    "Mobile App Developer", "Game Developer", "UI/UX Designer", "AI Engineer", "ML Engineer",
    "Data Scientist", "Data Analyst", "Computer Vision Engineer", "NLP Engineer",
    "DevOps Engineer", "Cloud Engineer", "Cybersecurity Engineer", "Blockchain Developer",
    "Embedded Systems Engineer", "AR/VR Developer", "Research Scientist (AI)"
]


def load_index_and_metadata(idx_path, meta_path):
    if not os.path.exists(idx_path) or not os.path.exists(meta_path):
        raise FileNotFoundError("Index or metadata not found. Please build embeddings first.")
    index = faiss.read_index(idx_path)
    with open(meta_path, "rb") as f:
        metadata = pickle.load(f)
    return index, metadata


def query_index(index, metadata, query, top_k=10):
    model = get_embedding_service()
    q_emb = model.encode([query], convert_to_numpy=True, show_progress_bar=False)
    q_emb = normalize(q_emb, norm="l2", axis=1).astype(np.float32)
    D, I = index.search(q_emb, top_k)
    results = []
    for score, idx in zip(D[0], I[0]):
        if idx >= 0:
            meta = metadata[idx].copy()
            meta["score"] = float(score)
            results.append(meta)
    return results


def suggest_roles(input_skills, top_k=20, top_n_choices=20):
    index, metadata = load_index_and_metadata(FAISS_INDEX_PATH, METADATA_PATH)

    query_text = " | ".join([s.strip() for s in input_skills if s]) + " || QuerySkills"
    hits = query_index(index, metadata, query_text, top_k=top_k)

    role_scores, role_example_hits = {}, {}
    for hit in hits:
        role = hit["role"]
        score = hit["score"]
        role_scores[role] = role_scores.get(role, 0) + score
        role_example_hits.setdefault(role, []).append(hit)

    candidates = sorted(
        [{"role": r, "aggregated_score": s, "example_hits": role_example_hits[r][:3]} for r, s in role_scores.items()],
        key=lambda x: x["aggregated_score"], reverse=True
    )

    choices = [c["role"] for c in candidates[:top_n_choices]]
    for r in ROLES:
        if len(choices) >= top_n_choices:
            break
        if r not in choices:
            choices.append(r)

    result = {
        "query_text": query_text,
        "candidates": candidates,
        "choices": choices[:top_n_choices]
    }

    # --- If fewer than 4 skills, suggest more ---
    if len(input_skills) < 4 and candidates:
        top_role = candidates[0]["role"]
        example_skills = []
        for hit in role_example_hits[top_role]:
            example_skills.extend(hit["skills"])
        unique_suggestions = list(dict.fromkeys(example_skills))[:5]
        result["suggest_more_skills"] = {
            "message": f"You provided only {len(input_skills)} skills. "
                       f"Consider adding more relevant skills for better accuracy.",
            "suggested_role": top_role,
            "example_skills": unique_suggestions
        }

    return result


if __name__ == "__main__":
    input_skills = ["Python", "SQL"]

    logger.info("Query skills: %s", input_skills)
    result = suggest_roles(input_skills, top_k=20, top_n_choices=4)

    logger.info("Multiple-choice suggestions: %s", result["choices"])

    for cand in result["candidates"][:6]:
        logger.info("Role: %s, score=%.4f", cand['role'], cand['aggregated_score'])

    if "suggest_more_skills" in result:
        msg = result["suggest_more_skills"]
        logger.info("%s Suggested skills for '%s': %s", msg['message'], msg['suggested_role'], ", ".join(msg["example_skills"]))
