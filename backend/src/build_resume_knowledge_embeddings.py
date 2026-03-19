"""
Standalone script to build resume optimization knowledge base embeddings.
Loads rules from JSON, creates embeddings, and saves FAISS index.

Usage:
    python src/build_resume_knowledge_embeddings.py --force    # Build from scratch
    python src/build_resume_knowledge_embeddings.py --check    # Check current status
"""
import argparse
import json
import sys
import pickle
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
import faiss


# Add backend directory to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def main():
    parser = argparse.ArgumentParser(
        description="Build resume knowledge base embeddings",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Rebuild embeddings and FAISS index from scratch'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Check current knowledge base status'
    )
    
    args = parser.parse_args()
    
    # Paths
    data_dir = BASE_DIR / "data"
    models_dir = BASE_DIR / "models"
    models_dir.mkdir(exist_ok=True)
    
    knowledge_base_path = data_dir / "resume_optimization_rules.json"
    faiss_index_path = models_dir / "resume_rules_faiss.index"
    metadata_path = models_dir / "resume_rules_metadata.pkl"
    
    if args.check:
        print("\n" + "="*60)
        print("RESUME KNOWLEDGE BASE STATUS")
        print("="*60)
        
        if knowledge_base_path.exists():
            with open(knowledge_base_path, 'r', encoding='utf-8') as f:
                kb_data = json.load(f)
            print(f"✓ Knowledge base file exists: {knowledge_base_path}")
            print(f"✓ Total chunks: {len(kb_data['chunks'])}")
        else:
            print(f"✗ Knowledge base file not found: {knowledge_base_path}")
        
        if faiss_index_path.exists() and metadata_path.exists():
            index = faiss.read_index(str(faiss_index_path))
            with open(metadata_path, 'rb') as f:
                metadata = pickle.load(f)
            
            print(f"✓ FAISS index exists: {faiss_index_path}")
            print(f"✓ Metadata file exists: {metadata_path}")
            print(f"✓ Indexed chunks: {index.ntotal}")
            print(f"✓ Embedding dimension: {index.d}")
            print(f"✓ Metadata entries: {len(metadata)}")
            
            # Show chunk type distribution
            chunk_types = {}
            role_tags = {}
            for chunk in metadata:
                ct = chunk.get('chunk_type', 'unknown')
                chunk_types[ct] = chunk_types.get(ct, 0) + 1
                
                for tag in chunk.get('role_tags', []):
                    role_tags[tag] = role_tags.get(tag, 0) + 1
            
            print("\n  Chunk Types:")
            for ct, count in sorted(chunk_types.items()):
                print(f"    - {ct}: {count}")
            
            print("\n  Role Tags (top 10):")
            for tag, count in sorted(role_tags.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"    - {tag}: {count}")
        else:
            print("✗ FAISS index or metadata not found. Run with --force to build.")
        
        print("="*60 + "\n")
        return
    
    if not args.force:
        print("Please specify --force to build embeddings or --check to view status")
        return
    
    print("\n" + "="*60)
    print("BUILDING RESUME KNOWLEDGE BASE EMBEDDINGS")
    print("="*60)
    
    try:
        # Load knowledge base
        print(f"\nLoading knowledge base from {knowledge_base_path}...")
        if not knowledge_base_path.exists():
            print(f"✗ Knowledge base file not found: {knowledge_base_path}")
            print("  Please create the file first with resume optimization rules.")
            return
        
        with open(knowledge_base_path, 'r', encoding='utf-8') as f:
            kb_data = json.load(f)
        
        chunks = kb_data.get('chunks', [])
        if not chunks:
            print("✗ No chunks found in knowledge base")
            return
        
        print(f"✓ Loaded {len(chunks)} optimization rules")
        
        # Initialize sentence transformer (same model as job embeddings)
        print("\nLoading sentence transformer model...")
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        model = SentenceTransformer(model_name)
        print(f"✓ Loaded model: {model_name}")
        
        # Extract texts and metadata
        texts = []
        metadata = []
        
        for chunk in chunks:
            chunk_text = chunk.get('chunk_text', '').strip()
            if not chunk_text:
                continue
            
            texts.append(chunk_text)
            metadata.append({
                'id': chunk.get('id'),
                'chunk_text': chunk_text,
                'role_tags': chunk.get('role_tags', []),
                'chunk_type': chunk.get('chunk_type', 'unknown'),
                'metadata': chunk.get('metadata', {})
            })
        
        print(f"\n✓ Prepared {len(texts)} chunks for embedding")
        
        # Generate embeddings
        print("\nGenerating embeddings (this may take a minute)...")
        embeddings = model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=True,
            batch_size=32
        )
        
        print(f"✓ Generated embeddings with shape: {embeddings.shape}")
        
        # Normalize embeddings for cosine similarity (Inner Product = Cosine for normalized vectors)
        print("\nNormalizing embeddings for cosine similarity...")
        faiss.normalize_L2(embeddings)
        print("✓ Embeddings normalized")
        
        # Build FAISS index (using Inner Product for cosine similarity with normalized vectors)
        print("\nBuilding FAISS index...")
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatIP(dimension)  # Inner Product (cosine similarity for normalized vectors)
        index.add(embeddings)
        
        print(f"✓ Built FAISS index with {index.ntotal} vectors")
        
        # Save FAISS index
        print(f"\nSaving FAISS index to {faiss_index_path}...")
        faiss.write_index(index, str(faiss_index_path))
        print("✓ FAISS index saved")
        
        # Save metadata
        print(f"Saving metadata to {metadata_path}...")
        with open(metadata_path, 'wb') as f:
            pickle.dump(metadata, f)
        print("✓ Metadata saved")
        
        # Summary
        print("\n" + "="*60)
        print("BUILD COMPLETE")
        print("="*60)
        print(f"✓ Total chunks indexed: {len(metadata)}")
        print(f"✓ Embedding dimension: {dimension}")
        print(f"✓ FAISS index: {faiss_index_path}")
        print(f"✓ Metadata: {metadata_path}")
        
        # Show statistics
        chunk_types = {}
        role_tags = {}
        for chunk in metadata:
            ct = chunk.get('chunk_type', 'unknown')
            chunk_types[ct] = chunk_types.get(ct, 0) + 1
            
            for tag in chunk.get('role_tags', []):
                role_tags[tag] = role_tags.get(tag, 0) + 1
        
        print("\nChunk Types:")
        for ct, count in sorted(chunk_types.items()):
            print(f"  - {ct}: {count}")
        
        print("\nRole Tags (top 15):")
        for tag, count in sorted(role_tags.items(), key=lambda x: x[1], reverse=True)[:15]:
            print(f"  - {tag}: {count}")
        
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n✗ Error building knowledge base: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
