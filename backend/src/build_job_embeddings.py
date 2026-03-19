"""
Standalone script to build job embeddings from Supabase.
Fetches jobs, creates embeddings for job titles, and saves to models folder.

Usage:
    python src/build_job_embeddings.py --force    # Rebuild from scratch
    python src/build_job_embeddings.py --check    # Check current status
"""
import argparse
import json
import sys
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

# Add backend directory to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from services.supabase_service import SupabaseService


def main():
    parser = argparse.ArgumentParser(
        description="Build job embeddings from Supabase",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Rebuild embeddings from scratch'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Check current embedding status'
    )
    
    args = parser.parse_args()
    
    # Paths
    models_dir = BASE_DIR / "models"
    models_dir.mkdir(exist_ok=True)
    
    embeddings_path = models_dir / "job_embeddings.npy"
    metadata_path = models_dir / "job_metadata.json"
    
    if args.check:
        print("\n" + "="*60)
        print("JOB EMBEDDINGS STATUS")
        print("="*60)
        
        if embeddings_path.exists() and metadata_path.exists():
            embeddings = np.load(str(embeddings_path))
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            print(f"✓ Embeddings file exists: {embeddings_path}")
            print(f"✓ Metadata file exists: {metadata_path}")
            print(f"✓ Number of jobs: {len(metadata)}")
            print(f"✓ Embedding dimension: {embeddings.shape[1] if len(embeddings.shape) > 1 else 'N/A'}")
            print(f"✓ Embeddings shape: {embeddings.shape}")
        else:
            print("✗ No embeddings found. Run with --force to build.")
        
        print("="*60 + "\n")
        return
    
    if not args.force:
        print("Please specify --force to build embeddings or --check to view status")
        return
    
    print("\n" + "="*60)
    print("BUILDING JOB EMBEDDINGS FROM SUPABASE")
    print("="*60)
    
    try:
        # Initialize services
        print("Initializing Supabase service...")
        supabase_service = SupabaseService()
        
        # Fetch all jobs
        print("Fetching jobs from Supabase...")
        jobs = supabase_service.fetch_all_jobs()
        
        if not jobs:
            print("✗ No jobs found in Supabase")
            return
        
        print(f"✓ Fetched {len(jobs)} jobs")
        
        # Filter valid jobs
        valid_jobs = []
        skipped = 0
        
        for job in jobs:
            job_id = job.get("job_id")
            job_title = job.get("job_title")
            
            if not job_id or not job_title:
                skipped += 1
                continue
            
            valid_jobs.append(job)
        
        if not valid_jobs:
            print("✗ No valid jobs to process")
            return
        
        print(f"✓ Valid jobs: {len(valid_jobs)}, Skipped: {skipped}")
        
        # Initialize embedding model
        print("Loading embedding model (all-MiniLM-L6-v2)...")
        model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Create embeddings for job titles
        print("Generating embeddings for job titles...")
        job_titles = [job["job_title"] for job in valid_jobs]
        embeddings = model.encode(job_titles, normalize_embeddings=True, show_progress_bar=True)
        
        print(f"✓ Generated {len(embeddings)} embeddings")
        
        # Create metadata
        print("Creating metadata...")
        metadata = []
        for idx, job in enumerate(valid_jobs):
            # Parse skills_required if it's a string
            skills_required = job.get("skills_required", [])
            if isinstance(skills_required, str):
                try:
                    skills_required = json.loads(skills_required)
                except:
                    skills_required = []
            
            metadata.append({
                "job_id": job["job_id"],
                "job_title": job["job_title"],
                "job_description": job.get("job_description", ""),
                "skills_required": skills_required,
                "experience_required": job.get("experience_required"),
                "education_required": job.get("education_required"),
                "job_type": job.get("job_type"),
                "location": job.get("location"),
                "industry": job.get("industry"),
                "embedding_index": idx
            })
        
        # Save embeddings
        print(f"Saving embeddings to {embeddings_path}...")
        np.save(str(embeddings_path), embeddings)
        
        # Save metadata
        print(f"Saving metadata to {metadata_path}...")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print("\n" + "="*60)
        print("BUILD COMPLETE")
        print("="*60)
        print(f"✓ Jobs processed: {len(valid_jobs)}")
        print(f"✓ Embeddings saved: {embeddings_path}")
        print(f"✓ Metadata saved: {metadata_path}")
        print(f"✓ Embedding shape: {embeddings.shape}")
        print("="*60 + "\n")
    
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
