import os
import pandas as pd
import numpy as np
from typing import List
from sklearn.preprocessing import normalize
from sentence_transformers import SentenceTransformer
import chromadb
from dotenv import load_dotenv

# ---- Load environment variables ----
load_dotenv()

CHROMA_API_KEY = os.getenv("CHROMA_API_KEY")
CHROMA_TENANT = os.getenv("CHROMA_TENANT")
CHROMA_DATABASE = os.getenv("CHROMA_DATABASE")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
EXCEL_PATH = os.getenv("EXCEL_PATH")
SHEET_NAME = os.getenv("SHEET_NAME")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")

# ---- Initialize Cloud Client ----
client = chromadb.CloudClient(
    api_key=CHROMA_API_KEY,
    tenant=CHROMA_TENANT,
    database=CHROMA_DATABASE
)
collection = client.get_or_create_collection(name=COLLECTION_NAME)

# ---- Helper Functions ----
def read_excel(excel_path: str, sheet_name: str):
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Excel file not found: {excel_path}")
    df = pd.read_excel(excel_path, sheet_name=sheet_name)
    df.columns = [c.strip() for c in df.columns]
    return df

def row_to_text(skills: List[str], role: str) -> str:
    skills_clean = [s.strip() for s in skills if s and str(s).strip() != ""]
    return " | ".join(skills_clean) + f" || Role: {role}"

def build_embeddings(texts: List[str]) -> np.ndarray:
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    return normalize(embeddings, norm="l2", axis=1)

def upload_to_chroma(df: pd.DataFrame):
    before = len(df)
    df = df.drop_duplicates(subset=["Role"], keep="first")
    after = len(df)
    print(f"✅ Removed {before - after} duplicate roles. Remaining: {after}")

    skill_cols = [c for c in df.columns if c.lower().startswith("skill_")]
    texts, ids, metadatas = [], [], []

    for i, row in df.iterrows():
        skills = [str(row[c]) for c in skill_cols if pd.notna(row.get(c))]
        role = str(row["Role"]).strip()
        text = row_to_text(skills, role)
        texts.append(text)
        ids.append(f"id_{i}")
        metadatas.append({"skills": ", ".join(skills), "role": role})

    print("🔄 Generating embeddings...")
    embeddings = build_embeddings(texts)

    print("☁️ Uploading to Chroma Cloud...")
    collection.upsert(
        ids=ids,
        embeddings=embeddings.tolist(),
        documents=texts,
        metadatas=metadatas
    )
    print(f"✅ Uploaded {len(ids)} unique roles to collection '{COLLECTION_NAME}'.")

def main():
    df = read_excel(EXCEL_PATH, SHEET_NAME)
    upload_to_chroma(df)

if __name__ == "__main__":
    main()
