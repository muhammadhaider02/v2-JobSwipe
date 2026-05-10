"""
Campaign Manager Node: Application preparation and tailored material generation.

Prepares job-specific resumes and cover letters using RAG-enhanced optimization,
then automates form filling for Indeed (with HITL approval before submission).
"""

import os
from typing import Dict, Any, Optional
from datetime import datetime
from agents.state import AgentState
from langchain_core.messages import AIMessage
from config.settings import get_settings


def campaign_manager_node(state: AgentState) -> Dict[str, Any]:
    """
    Campaign Manager agent: Prepares application materials for target job.
    
    Workflow:
    1. Extract target job from state (set by user swipe/selection)
    2. Analyze job description for context (company, critical skills, culture)
    3. Generate tailored resume using enhanced RAG pipeline
    4. Generate tailored cover letter using template service
    5. Validate materials (keyword presence, length checks)
    6. Store materials and return updated state
    
    Args:
        state: Current agent state with target_job and user_profile
        
    Returns:
        Updated state with optimized_materials and messages
    """
    
    print("\n" + "="*70)
    print("CAMPAIGN MANAGER: Preparing Application Materials")
    print("="*70)
    
    # Validate required state fields
    if not state.get("target_job"):
        error_msg = "No target job specified. User must select a job first."
        print(f"{error_msg}")
        return {
            "error": error_msg,
            "messages": [AIMessage(content=error_msg)]
        }
    
    if not state.get("user_id"):
        error_msg = "Missing user_id in state."
        print(f"{error_msg}")
        return {
            "error": error_msg,
            "messages": [AIMessage(content=error_msg)]
        }
    
    target_job = state["target_job"]
    user_id = state["user_id"]
    
    print(f"Target Job: {target_job.get('title', 'Unknown')} at {target_job.get('company', 'Unknown')}")
    print(f"User ID: {user_id}")
    print(f"Job Board: {target_job.get('board', 'Unknown')}")

    auth_status = str(state.get("auth_status") or "").lower()
    auth_required = bool(state.get("auth_required"))
    if auth_required and auth_status != "authenticated":
        msg = "Session expired. Please log in manually in the opened browser window."
        print(f"{msg}")
        return {
            "error": msg,
            "application_status": "paused_auth",
            "messages": [AIMessage(content=msg)]
        }

    settings = get_settings()
    threshold = state.get("campaign_ats_score_threshold", settings.campaign_ats_score_threshold)
    max_retries = state.get("campaign_max_tailoring_retries", settings.campaign_max_tailoring_retries)
    try:
        threshold = float(threshold)
    except (TypeError, ValueError):
        threshold = settings.campaign_ats_score_threshold
    try:
        max_retries = int(max_retries)
    except (TypeError, ValueError):
        max_retries = settings.campaign_max_tailoring_retries
    max_retries = max(0, min(max_retries, 3))
    
    try:
        # Import tools here to avoid circular dependencies
        from agents.tools.material_prep import MaterialPreparationTool
        
        # Initialize material preparation tool
        prep_tool = MaterialPreparationTool()
        
        # Prepare application materials with local scorer loop.
        print("\nGenerating tailored application materials...")
        attempt = 0
        materials = None
        score_feedback = None
        score_history = []

        while attempt <= max_retries:
            attempt += 1
            print(f"\nCampaign tailoring attempt {attempt}/{max_retries + 1}")
            materials = prep_tool.prepare_materials(
                user_id=user_id,
                job_data=target_job,
                user_profile=state.get("user_profile"),
                optimization_feedback=score_feedback
            )

            if not materials or materials.get("error"):
                break

            metadata = materials.get("metadata", {})
            ats = metadata.get("ats_simulation", {})
            current_score = float(ats.get("score", 0.0) or 0.0)
            score_history.append({
                "attempt": attempt,
                "score": round(current_score, 4),
                "score_percent": ats.get("score_percent", round(current_score * 100, 2)),
                "missing_keywords": ats.get("missing_keywords", []),
                "weak_sections": ats.get("weak_sections", []),
                "unsupported_numeric_facts_detected": ats.get("unsupported_numeric_facts_detected", False)
            })

            print(
                f"ATS score: {current_score:.2%} "
                f"(threshold: {threshold:.2%})"
            )

            if current_score >= threshold:
                print("Score threshold reached, stopping retries")
                break

            if attempt > max_retries:
                print("Max retries reached, proceeding with best available output")
                break

            score_feedback = {
                "missing_keywords": ats.get("missing_keywords", []),
                "weak_sections": ats.get("weak_sections", []),
            }
            print("Retrying with scorer feedback")
        
        if not materials or materials.get("error"):
            error_msg = materials.get("error", "Failed to generate materials")
            print(f"Material preparation failed: {error_msg}")
            return {
                "error": error_msg,
                "messages": [AIMessage(content=f"Failed to prepare materials: {error_msg}")]
            }
        
        # Extract results
        optimized_resume = materials.get("optimized_resume")
        cover_letter = materials.get("cover_letter")
        metadata = materials.get("metadata", {})
        metadata["campaign_loop"] = {
            "attempts_used": len(score_history),
            "max_retries": max_retries,
            "threshold": threshold,
            "score_history": score_history,
            "passed_threshold": bool(score_history and score_history[-1].get("score", 0.0) >= threshold)
        }
        
        print("\nMaterials generated successfully!")
        print(f"Resume sections optimized: {metadata.get('sections_optimized', [])}")
        print(f"Cover letter length: {len(cover_letter)} chars")
        print(f"Job keywords matched: {metadata.get('keywords_matched', 0)}/{metadata.get('keywords_total', 0)}")
        print(f"Optimization confidence: {metadata.get('overall_confidence', 0):.1%}")
        ats_score = metadata.get("ats_simulation", {}).get("score_percent")
        if ats_score is not None:
            print(f"ATS simulated score: {ats_score}%")
        
        # Store materials in state
        optimized_materials = {
            "resume": optimized_resume,
            "cover_letter": cover_letter,
            "metadata": metadata,
            "generated_at": datetime.utcnow().isoformat(),
            "job_id": target_job.get("job_id"),
            "job_title": target_job.get("title"),
            "company": target_job.get("company")
        }
        
        # Success message
        success_msg = (
            f"Application materials ready for {target_job.get('title')} at {target_job.get('company')}. "
            f"Resume optimized with {metadata.get('keywords_matched', 0)} relevant keywords. "
            f"Ready for review and submission."
        )
        
        print(f"\n{success_msg}")
        
        return {
            "optimized_materials": optimized_materials,
            "human_approval": "pending",  # Requires HITL approval before submission
            "messages": [AIMessage(content=success_msg)]
        }
        
    except Exception as e:
        error_msg = f"Campaign Manager error: {str(e)}"
        print(f"\n{error_msg}")
        import traceback
        traceback.print_exc()
        
        return {
            "error": error_msg,
            "messages": [AIMessage(content=error_msg)]
        }
