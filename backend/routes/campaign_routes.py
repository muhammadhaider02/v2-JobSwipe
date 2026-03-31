"""
Campaign Manager Routes
API endpoints for application material preparation and submission automation.
"""

from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
import json
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from agents.tools.material_prep import MaterialPreparationTool
from services.supabase_service import get_supabase_service

campaign_bp = Blueprint('campaign', __name__)
logger = logging.getLogger(__name__)
ALLOWED_RESUME_SECTIONS = {"summary", "experience", "skills", "projects", "education"}


def _is_valid_uuid(val):
    """Check if string is a valid UUID format"""
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError):
        return False


def _get_latest_application_for_job(supabase, user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    """Fetch the latest application record for a user and job pair via direct query."""
    try:
        response = (
            supabase.client.table("job_applications")
            .select("*")
            .eq("user_id", user_id)
            .eq("job_id", job_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None
    except Exception as e:
        logger.warning(f"Could not fetch application for user={user_id} job={job_id}: {e}")
        return None


def _resolve_application_id(
    supabase,
    user_id: str,
    job_id: str,
    cover_letter: Optional[str],
    requested_id: Optional[int],
) -> Optional[int]:
    """Resolve or create an application row so workflow updates are durable."""
    if requested_id:
        return requested_id

    existing = _get_latest_application_for_job(supabase, user_id, job_id)
    if existing and existing.get("id"):
        return existing.get("id")

    return supabase.create_application(
        user_id=user_id,
        job_id=job_id,
        reasoning_note="Campaign workflow initialized",
        optimized_cover_letter=cover_letter,
    )


@campaign_bp.route('/prepare-application-materials', methods=['POST', 'OPTIONS'])
@cross_origin(origins="http://localhost:3000")
def prepare_application_materials():
    """
    Prepare tailored resume and cover letter for a specific job.
    
    Request JSON:
    {
        "user_id": "uuid",  # Required: User UUID from Supabase
        "job_id": "j123abc",  # Required: Job ID (SHA256 hash)
        "sections_to_optimize": ["experience", "skills", "summary"]  # Optional
    }
    
    Response:
    {
        "success": true,
        "materials": {
            "optimized_resume": {...},  # Full resume JSON with optimized sections
            "cover_letter": "...",  # Generated cover letter text
            "metadata": {
                "job_context": {...},  # Job analysis results
                "keywords_matched": 10,
                "keywords_total": 15,
                "overall_confidence": 0.85,
                "sections_optimized": ["experience", "skills"],
                "template_used": "template1.txt"
            }
        },
        "job_info": {
            "title": "...",
            "company": "...",
            "board": "indeed"
        }
    }
    """
    
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        user_id = data.get('user_id')
        job_id = data.get('job_id')
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        if not job_id:
            return jsonify({"error": "job_id is required"}), 400
        
        if not _is_valid_uuid(user_id):
            return jsonify({"error": "Invalid user_id format"}), 400
        
        # Optional parameters
        requested_sections = data.get('sections_to_optimize', ["experience", "skills", "summary"])
        if not isinstance(requested_sections, list):
            return jsonify({"error": "sections_to_optimize must be a list"}), 400

        sections_to_optimize = [
            str(section).strip().lower()
            for section in requested_sections
            if str(section).strip().lower() in ALLOWED_RESUME_SECTIONS
        ]

        if not sections_to_optimize:
            return jsonify({"error": "At least one valid section must be selected"}), 400
        
        logger.info(f"Preparing materials for user {user_id}, job {job_id}")
        
        # Fetch job data from Supabase
        supabase = get_supabase_service()
        job_data = supabase.get_job_by_id(job_id)
        
        if not job_data:
            return jsonify({"error": f"Job not found: {job_id}"}), 404
        
        logger.info(f"Found job: {job_data.get('title')} at {job_data.get('company')}")
        
        # Initialize material preparation tool
        prep_tool = MaterialPreparationTool()
        
        # Prepare materials
        result = prep_tool.prepare_materials(
            user_id=user_id,
            job_data=job_data,
            sections_to_optimize=sections_to_optimize
        )
        
        # Reconnect to Supabase after the long LLM operation to avoid stale HTTP/2 connection
        supabase.reconnect()

        # Check for errors
        if result.get("error"):
            logger.error(f"Material preparation failed: {result['error']}")
            return jsonify({
                "success": False,
                "error": result["error"]
            }), 500

        # Persist optimized resume version for tracking/history.
        resume_version = supabase.save_resume_version(
            user_id=user_id,
            original_json=result.get("original_resume") or {},
            optimized_json=result.get("optimized_resume") or {},
            job_id=job_id,
            job_title=(job_data.get("title") or job_data.get("job_title")),
            optimization_metadata=result.get("metadata") or {},
            is_base_version=False,
            sections_optimized=sections_to_optimize,
        )
        
        application_id = _resolve_application_id(
            supabase=supabase, 
            user_id=user_id,
            job_id=job_id,
            cover_letter=result.get("cover_letter"),
            requested_id=None,
        )

        # Success response
        return jsonify({
            "success": True,
            "materials": {
                "optimized_resume": result["optimized_resume"],
                "cover_letter": result["cover_letter"],
                "metadata": result["metadata"]
            },
            "application_id": application_id,
            "resume_version": resume_version,
            "job_info": {
                "title": job_data.get("title") or job_data.get("job_title"),
                "company": job_data.get("company"),
                "board": job_data.get("board"),
                "job_id": job_id
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error in prepare_application_materials: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@campaign_bp.route('/fill-application', methods=['POST', 'OPTIONS'])
@cross_origin(origins="http://localhost:3000")
def fill_application():
    """
    Automate form filling for job application (HITL approval required before submit).
    
    Request JSON:
    {
        "user_id": "uuid",
        "job_id": "j123abc",
        "materials": {  # From prepare-application-materials response
            "optimized_resume": {...},
            "cover_letter": "..."
        }
    }
    
    Response:
    {
        "success": true,
        "status": "filled",  # "filled" | "error" | "captcha_required"
        "screenshot_path": "/screenshots/app_123.png",
        "fields_filled": {
            "name": true,
            "email": true,
            "phone": true,
            "resume": true,
            "cover_letter": false
        },
        "message": "Form filled successfully. Review and confirm submission."
    }
    """
    
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        user_id = data.get('user_id')
        job_id = data.get('job_id')
        materials = data.get('materials')
        requested_application_id = data.get('application_id')
        
        if not user_id or not job_id or not materials:
            return jsonify({"error": "user_id, job_id, and materials are required"}), 400
        
        logger.info(f"Filling application for user {user_id}, job {job_id}")
        
        # Fetch job data
        supabase = get_supabase_service()
        job_data = supabase.get_job_by_id(job_id)
        
        if not job_data:
            return jsonify({"error": f"Job not found: {job_id}"}), 404

        application_id = _resolve_application_id(
            supabase=supabase,
            user_id=user_id,
            job_id=job_id,
            cover_letter=(materials or {}).get("cover_letter"),
            requested_id=requested_application_id,
        )
        
        job_board = job_data.get("board", "").lower()
        job_url = job_data.get("job_url")
        
        # Check if board is supported
        if job_board not in ["indeed", "mustakbil"]:
            return jsonify({
                "success": False,
                "error": f"Job board '{job_board}' not yet supported. Supported boards: indeed, mustakbil.",
                "fallback_url": job_url
            }), 400
        
        # Import browser tool
        from agents.tools.browser_tool import BrowserTool
        
        # Fetch user profile for contact info
        user_profile = supabase.get_user_profile(user_id)
        if not user_profile:
            return jsonify({"error": f"User profile not found: {user_id}"}), 404
        
        # Initialize browser automation
        browser = BrowserTool()
        
        # Fill application form
        result = browser.fill_application(
            job_url=job_url,
            job_board=job_board,
            materials=materials,
            user_profile=user_profile
        )
        
        # Handle result
        if result.get("error"):
            error_msg = result["error"]
            if application_id:
                supabase.update_application_status(application_id, "error")

            if bool(result.get("preauth_required")):
                return jsonify({
                    "success": False,
                    "status": "preauth_required",
                    "error": error_msg,
                    "application_id": application_id,
                    "instance_id": result.get("instance_id"),
                    "tab_id": result.get("tab_id"),
                    "fallback_url": job_url,
                    "message": "Please sign in within the PinchTab browser session, then retry."
                }), 200
            
            # Check for CAPTCHA or login wall (fallback to manual)
            if "captcha" in error_msg.lower() or "login" in error_msg.lower():
                return jsonify({
                    "success": False,
                    "status": "captcha_required",
                    "error": error_msg,
                    "application_id": application_id,
                    "fallback_url": job_url,
                    "message": "Automated application blocked. Please apply manually."
                }), 200  # Not a server error, just requires fallback
            
            # Other errors
            return jsonify({
                "success": False,
                "status": "error",
                "application_id": application_id,
                "error": error_msg
            }), 500

        if application_id:
            # Keep application pending until explicit user approval endpoint is called.
            supabase.update_application_status(application_id, "pending")
        
        # Success
        return jsonify({
            "success": True,
            "status": "filled",
            "application_id": application_id,
            "screenshot_path": result.get("screenshot_path"),
            "fields_filled": result.get("fields_filled", {}),
            "instance_id": result.get("instance_id"),
            "tab_id": result.get("tab_id"),
            "warnings": result.get("warnings", []),
            "review_required": True,
            "message": "Form filled successfully. Review and confirm submission."
        }), 200
        
    except Exception as e:
        logger.error(f"Error in fill_application: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "status": "error",
            "error": str(e)
        }), 500


@campaign_bp.route('/submit-application/<job_id>', methods=['POST', 'OPTIONS'])
@cross_origin(origins="http://localhost:3000")
def submit_application(job_id: str):
    """
    Confirm human approval/rejection for a filled application.

    v1 intentionally does not auto-submit. This endpoint records approval state
    and returns manual handoff instructions.
    
    Request JSON:
    {
        "user_id": "uuid",
        "approval_confirmed": true,
        "application_id": 123
    }
    
    Response:
    {
        "success": true,
        "status": "approved",
        "manual_submission_required": true,
        "message": "Approval recorded. Please submit manually in v1."
    }
    """
    
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        user_id = data.get('user_id')
        approval_confirmed = data.get('approval_confirmed')
        
        if user_id is None or approval_confirmed is None:
            return jsonify({"error": "user_id and approval_confirmed are required"}), 400
        
        if not _is_valid_uuid(user_id):
            return jsonify({"error": "Invalid user_id format"}), 400
        
        logger.info(f"Recording approval for user {user_id}, job {job_id}")
        
        # Fetch job data
        supabase = get_supabase_service()
        job_data = supabase.get_job_by_id(job_id)
        
        if not job_data:
            return jsonify({"error": f"Job not found: {job_id}"}), 404

        requested_application_id = data.get("application_id")
        application_id = _resolve_application_id(
            supabase=supabase,
            user_id=user_id,
            job_id=job_id,
            cover_letter=None,
            requested_id=requested_application_id,
        )

        if not application_id:
            return jsonify({
                "success": False,
                "status": "error",
                "error": "Failed to create application record"
            }), 500

        if bool(approval_confirmed):
            supabase.update_application_status(application_id, "approved")
            return jsonify({
                "success": True,
                "status": "approved",
                "application_id": application_id,
                "manual_submission_required": True,
                "manual_url": job_data.get("job_url"),
                "message": "Approval recorded. Auto-submit is disabled in v1; submit manually on the job site."
            }), 200

        supabase.update_application_status(application_id, "rejected")
        return jsonify({
            "success": True,
            "status": "rejected",
            "application_id": application_id,
            "message": "Application was rejected by reviewer and will not be submitted."
        }), 200
        
    except Exception as e:
        logger.error(f"Error in submit_application: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "status": "error",
            "error": str(e)
        }), 500


@campaign_bp.route('/application-materials/<job_id>', methods=['GET', 'OPTIONS'])
@cross_origin(origins="http://localhost:3000")
def get_application_materials(job_id: str):
    """
    Fetch existing saved application materials (resume + cover letter) for a job.

    Returns immediately from the database — no LLM call is made.
    The frontend uses this to skip re-generation on refresh/revisits.

    Query params:
        user_id (str): Required. The user's UUID.

    Response:
    {
        "has_materials": true,
        "application_id": 42,
        "optimized_resume": {...},   # parsed JSON or null
        "cover_letter": "...",       # text or null
    }
    """
    if request.method == 'OPTIONS':
        return '', 204

    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id query parameter is required"}), 400

        if not _is_valid_uuid(user_id):
            return jsonify({"error": "Invalid user_id format"}), 400

        supabase = get_supabase_service()
        latest = _get_latest_application_for_job(supabase, user_id=user_id, job_id=job_id)

        if not latest:
            return jsonify({"has_materials": False}), 200

        # optimized_resume_url stores the resume as a JSON string (set by save-draft)
        raw_resume = latest.get("optimized_resume_url")
        optimized_resume = None
        if raw_resume:
            try:
                optimized_resume = json.loads(raw_resume)
            except (ValueError, TypeError):
                # Stored as a plain URL string rather than JSON — treat as no resume
                optimized_resume = None

        cover_letter = latest.get("optimized_cover_letter") or None
        has_materials = optimized_resume is not None or cover_letter is not None

        return jsonify({
            "has_materials": has_materials,
            "application_id": latest.get("id"),
            "optimized_resume": optimized_resume,
            "cover_letter": cover_letter,
        }), 200

    except Exception as e:
        logger.error(f"Error in get_application_materials: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@campaign_bp.route('/application-status/<job_id>', methods=['GET', 'OPTIONS'])
@cross_origin(origins="http://localhost:3000")
def get_application_status(job_id: str):
    """
    Get application status for a specific job.
    
    Response:
    {
        "success": true,
        "status": "submitted" | "filled" | "pending" | "error",
        "submitted_at": "2026-03-12T10:30:00Z",
        "job_info": {...}
    }
    """
    
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id query parameter is required"}), 400

        supabase = get_supabase_service()
        latest = _get_latest_application_for_job(supabase, user_id=user_id, job_id=job_id)
        if not latest:
            return jsonify({
                "success": True,
                "status": "not_found",
                "application": None
            }), 200

        return jsonify({
            "success": True,
            "status": latest.get("status"),
            "application": {
                "id": latest.get("id"),
                "job_id": latest.get("job_id"),
                "status": latest.get("status"),
                "created_at": latest.get("created_at"),
                "updated_at": latest.get("updated_at"),
                "applied_at": latest.get("applied_at"),
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error in get_application_status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@campaign_bp.route('/application-materials/save-draft', methods=['POST', 'OPTIONS'])
@cross_origin(origins="http://localhost:3000")
def save_application_materials_draft():
    """Save user-edited resume and cover letter draft for an application."""

    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        application_id = data.get("application_id")
        user_id = data.get("user_id")
        optimized_resume = data.get("optimized_resume")
        cover_letter = data.get("cover_letter")
        template_name = data.get("template_name")

        if not application_id:
            return jsonify({"error": "application_id is required"}), 400

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        supabase = get_supabase_service()
        application = supabase.get_application_by_id(int(application_id))

        if not application:
            return jsonify({"error": f"Application not found: {application_id}"}), 404

        if application.get("user_id") != user_id:
            return jsonify({"error": "Application does not belong to provided user_id"}), 403

        success = supabase.save_application_materials_draft(
            application_id=int(application_id),
            optimized_resume=optimized_resume,
            optimized_cover_letter=cover_letter,
            template_name=template_name,
        )

        if not success:
            return jsonify({"success": False, "error": "Failed to save draft materials"}), 500

        return jsonify({
            "success": True,
            "application_id": int(application_id),
            "status": "draft",
        }), 200

    except ValueError:
        return jsonify({"error": "application_id must be an integer"}), 400
    except Exception as e:
        logger.error(f"Error in save_application_materials_draft: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
