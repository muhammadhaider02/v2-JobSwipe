import os
import pickle
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import normalize
import faiss
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # this is backend/
load_dotenv(BASE_DIR / ".env.local")  # load backend/.env

EXCEL_ROLE_RECOMMEND = os.getenv("EXCEL_ROLE_RECOMMEND")
SHEET_ROLE_RECOMMEND = os.getenv("SHEET_ROLE_RECOMMEND")
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH")
METADATA_PATH = os.getenv("METADATA_PATH")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")

def read_excel_rows(EXCEL_ROLE_RECOMMEND: str, SHEET_ROLE_RECOMMEND: str = None) -> pd.DataFrame:
    if not os.path.exists(EXCEL_ROLE_RECOMMEND):
        raise FileNotFoundError(f"Excel file not found at: {EXCEL_ROLE_RECOMMEND}")
    df = pd.read_excel(EXCEL_ROLE_RECOMMEND, sheet_name=SHEET_ROLE_RECOMMEND)
    df.columns = [c.strip() for c in df.columns]
    return df

def row_to_text(skills, role):
    skills_clean = [s for s in (skill.strip() for skill in skills) if s]
    return " | ".join(skills_clean) + " || Role: " + role

def build_embeddings(texts, model_name):
    model = SentenceTransformer(model_name)
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    return normalize(embeddings, norm="l2", axis=1)

def build_faiss_index(embeddings):
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype(np.float32))
    return index

def save_index_and_metadata(index, metadata, idx_path, meta_path):
    parent_dir = os.path.dirname(idx_path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir)
    faiss.write_index(index, idx_path)
    with open(meta_path, "wb") as f:
        pickle.dump(metadata, f)

def prepare_and_store_vector_db():
    df = read_excel_rows(EXCEL_ROLE_RECOMMEND, SHEET_ROLE_RECOMMEND)
    skill_cols = [c for c in df.columns if c.lower().startswith("skill_")]
    if "Role" not in df.columns:
        raise ValueError("Excel must have a 'Role' column.")

    texts, metadata = [], []
    for _, row in df.iterrows():
        skills = [str(row[c]) for c in skill_cols if pd.notna(row.get(c)) and str(row.get(c)).strip()]
        role = str(row["Role"]).strip()
        text = row_to_text(skills, role)
        texts.append(text)
        metadata.append({"skills": skills, "role": role, "text": text})

    print(f"Building embeddings using model {EMBEDDING_MODEL_NAME} ...")
    embeddings = build_embeddings(texts, EMBEDDING_MODEL_NAME)
    print("Creating FAISS index ...")
    index = build_faiss_index(embeddings)

    print(f"Saving index to {FAISS_INDEX_PATH} and metadata to {METADATA_PATH} ...")
    save_index_and_metadata(index, metadata, FAISS_INDEX_PATH, METADATA_PATH)
    print("Embeddings and FAISS index built successfully!")

if __name__ == "__main__":
    prepare_and_store_vector_db()
