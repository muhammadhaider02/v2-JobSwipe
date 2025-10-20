import os
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import normalize
import chromadb
from dotenv import load_dotenv

# ---- Load environment variables ----
load_dotenv()

CHROMA_API_KEY = os.getenv("CHROMA_API_KEY")
CHROMA_TENANT = os.getenv("CHROMA_TENANT")
CHROMA_DATABASE = os.getenv("CHROMA_DATABASE")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")

# ---- Connect to Chroma Cloud ----
client = chromadb.CloudClient(
    api_key=CHROMA_API_KEY,
    tenant=CHROMA_TENANT,
    database=CHROMA_DATABASE
)
collection = client.get_collection(COLLECTION_NAME)

# ---- Query Function ----
def query_roles(skills, top_k=5):
    """
    Query roles based on user skills
    Args:
        skills: List of skill strings
        top_k: Number of top recommendations to return
    Returns: List of dicts with role, score, and skills
    """
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    query_text = " | ".join(skills)
    q_emb = normalize(model.encode([query_text], convert_to_numpy=True), norm="l2", axis=1)

    print(f"\n🔍 Searching for roles similar to: {skills}")
    results = collection.query(query_embeddings=q_emb.tolist(), n_results=top_k)

    seen_roles = set()
    recommendations = []
    
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        role = meta["role"]
        skills_for_role = meta.get("skills", "")
        score = results['distances'][0][i]
        
        if role not in seen_roles:
            seen_roles.add(role)
            recommendations.append({
                "role": role,
                "score": float(score),
                "skills": skills_for_role
            })
            print(f"• {role} (score={score:.4f})")
    
    return recommendations

# ---- Demo ----
def main():
    examples = [
        ['nestjs', 'python', 'numpy', "Node.js", "MongoDB", 'powerbi', 'sql']
    ]
    for ex in examples:
        results = query_roles(ex)
        print(f"\nReturned {len(results)} recommendations")

if __name__ == "__main__":
    main()
