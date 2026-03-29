"""
Test Scout + Enricher + Vetting Officer workflow: Scraping → Enrichment → Matching → Storage

Run this to validate the complete data pipeline.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.state import AgentState
from agents.nodes import digital_scout_node, job_enricher_node, vetting_officer_node
from langchain_core.messages import HumanMessage


def test_scout_and_enricher():
    """Test Digital Scout + Enricher with real job search."""
    
    print("\n" + "="*70)
    print("🧪 TESTING SCOUT + ENRICHER + VETTING PIPELINE")
    print("="*70 + "\n")
    
    # Clear Redis cache to test fresh scraping
    from services import get_redis_service
    redis_service = get_redis_service()
    print("🗑️  Clearing Redis cache for fresh test...\n")
    redis_service.client.flushdb()
    
    # Create initial state
    state: AgentState = {
        "messages": [HumanMessage(content="Find data engineer jobs in Lahore")],
        "user_id": "d28190b3-e0b4-4af9-97a6-dc2a686d26e2",  
        "user_profile": None,
        "search_query": "data engineer in lahore",
        "raw_job_list": [],
        "scraping_status": "pending",
        "current_page": 1,
        "vetted_jobs": [],
        "target_job": None,
        "optimized_materials": None,
        "human_approval": None,
        "error": None,
        "retry_count": 0
    }
    
    print("📝 Initial State:")
    print(f"   User ID: {state['user_id']}")
    print(f"   Query: {state['search_query']}")
    print(f"   Status: {state['scraping_status']}\n")
    
    print("⚠️  NOTE: Make sure you have a test user profile in Supabase with this user_id!")
    print("   Or the vetting step will fail.\n")
    
    # Step 1: Run Digital Scout
    try:
        print("\n" + "="*70)
        print("STEP 1: DIGITAL SCOUT")
        print("="*70)
        
        scout_result = digital_scout_node(state)
        
        # Update state
        state.update(scout_result)
        
        raw_jobs = state.get('raw_job_list', [])
        print(f"\n✅ Scout completed: {len(raw_jobs)} raw jobs scraped\n")
        
        if not raw_jobs:
            print("❌ No jobs found. Exiting.")
            return
        
        # Show sample raw job
        if raw_jobs:
            sample = raw_jobs[0]
            print(f"📋 Sample Raw Job:")
            print(f"   Title: {sample['title']}")
            print(f"   Company: {sample['company']}")
            print(f"   Board: {sample['board']}")
            print(f"   Skills (raw): {', '.join(sample['skills'][:5])}")
            print(f"   Description length: {len(sample['description'])} chars")
            print()
        
        # Step 2: Run Enricher
        print("\n" + "="*70)
        print("STEP 2: JOB ENRICHER")
        print("="*70)
        
        enricher_result = job_enricher_node(state)
        
        # Update state
        state.update(enricher_result)
        
        enriched_jobs = state.get('raw_job_list', [])
        print(f"\n✅ Enricher completed: {len(enriched_jobs)} jobs enriched\n")
        
        if not enriched_jobs:
            print("❌ No enriched jobs. Exiting.")
            return
        
        # Step 3: Run Vetting Officer
        print("\n" + "="*70)
        print("STEP 3: VETTING OFFICER")
        print("="*70)
        
        vetting_result = vetting_officer_node(state)
        
        # Update state
        state.update(vetting_result)
        
        vetted_jobs = state.get('vetted_jobs', [])
        
        print("\n" + "="*70)
        print("📊 FINAL RESULTS")
        print("="*70 + "\n")
        
        print(f"Jobs Scraped: {len(raw_jobs)}")
        print(f"Jobs Enriched: {len(enriched_jobs)}")
        print(f"Jobs Passed Vetting: {len(vetted_jobs)}\n")
        
        # Show vetted jobs
        if vetted_jobs:
            print(f"🎯 Top {min(3, len(vetted_jobs))} Matches:\n")
            for idx, vetted_job in enumerate(vetted_jobs[:3], 1):
                job_data = vetted_job['job_data']
                print(f"{idx}. {job_data['title']} @ {job_data['company']}")
                print(f"   Match Score: {vetted_job['match_score']:.2%} ({vetted_job['confidence'].upper()} confidence)")
                print(f"   Matching Skills: {', '.join(vetted_job['matching_skills'][:5])}")
                if vetted_job['skill_gaps']:
                    print(f"   Skill Gaps: {', '.join(vetted_job['skill_gaps'][:3])}")
                print()
        
        # Show enriched sample (for reference)
        if enriched_jobs:
            sample = enriched_jobs[0]
            print(f"\n📋 Sample Enriched Job (for reference):\n")
            print(f"Title: {sample['title']}")
            print(f"Company: {sample['company']}")
            print(f"Location: {sample['location']}")
            print(f"Board: {sample['board'].upper()}")
            print(f"Confidence: {sample.get('enrichment_confidence', 0):.2f}")
            print()
            
            # Skills
            skills_cat = sample.get('skills_categorized', {})
            if skills_cat:
                print("Skills (Categorized):")
                for category, skills in skills_cat.items():
                    if skills:
                        print(f"  {category.title()}: {', '.join(skills[:5])}")
            print()
        
        # Statistics
        high_conf = sum(1 for j in enriched_jobs if j.get('enrichment_confidence', 0) >= 0.7)
        avg_skills = sum(len(j.get('skills', [])) for j in enriched_jobs) / len(enriched_jobs) if enriched_jobs else 0
        
        print(f"\n📊 Pipeline Statistics:")
        print(f"  • Jobs scraped: {len(raw_jobs)}")
        print(f"  • Jobs enriched: {len(enriched_jobs)}")
        print(f"  • High confidence enrichment (≥0.7): {high_conf}/{len(enriched_jobs)}")
        print(f"  • Average skills per job: {avg_skills:.1f}")
        print(f"  • Jobs passed vetting (≥60%): {len(vetted_jobs)}")
        if vetted_jobs:
            high_match = sum(1 for j in vetted_jobs if j['match_score'] >= 0.75)
            avg_match = sum(j['match_score'] for j in vetted_jobs) / len(vetted_jobs)
            print(f"  • High match score (≥75%): {high_match}/{len(vetted_jobs)}")
            print(f"  • Average match score: {avg_match:.2%}")
        print()
        
        print("✅ Pipeline test completed successfully!")
        
        return vetted_jobs
    
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    test_scout_and_enricher()
