"""
Test Digital Scout end-to-end: Scraping → Deduplication → Storage

Run this to validate Phase 2 infrastructure.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.state import AgentState
from agents.nodes import digital_scout_node
from langchain_core.messages import HumanMessage


def test_scout():
    """Test Digital Scout with real job search."""
    
    print("\n" + "="*70)
    print("🧪 TESTING DIGITAL SCOUT NODE")
    print("="*70 + "\n")
    
    # Create initial state
    state: AgentState = {
        "messages": [HumanMessage(content="Find data engineer jobs in Lahore")],
        "user_id": "test_user_123",
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
    
    # Run Digital Scout
    try:
        result = digital_scout_node(state)
        
        print("\n" + "="*70)
        print("📊 RESULTS")
        print("="*70 + "\n")
        
        print(f"Status: {result.get('scraping_status')}")
        print(f"Jobs Found: {len(result.get('raw_job_list', []))}")
        
        if result.get('error'):
            print(f"\n❌ Error: {result['error']}")
        else:
            print("\n✅ Test completed successfully!")
            
            # Show sample jobs
            jobs = result.get('raw_job_list', [])
            if jobs:
                print(f"\n📋 Sample Jobs (showing first 5):\n")
                for i, job in enumerate(jobs[:5], 1):
                    print(f"{i}. {job['title']}")
                    print(f"   Company: {job['company']}")
                    print(f"   Location: {job['location']}")
                    print(f"   Board: {job['board'].upper()}")
                    print(f"   Skills: {', '.join(job['skills'][:5])}")
                    print()
        
        return result
    
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    test_scout()
