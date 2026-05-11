"""
Campaign Manager Routes
API endpoints for application material preparation and submission automation.
"""

import os
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
import json
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from agents.tools.material_prep import MaterialPreparationTool
from services.supabase_service import get_supabase_service

CORS_ORIGIN = os.environ.get("CORS_ALLOWED_ORIGIN", "http://localhost:3000")

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
@cross_origin(origins=CORS_ORIGIN)
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




@campaign_bp.route('/application-materials/<job_id>', methods=['GET', 'OPTIONS'])
@cross_origin(origins=CORS_ORIGIN)
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
@cross_origin(origins=CORS_ORIGIN)
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


@campaign_bp.route('/mark-applied', methods=['POST', 'OPTIONS'])
@cross_origin(origins=CORS_ORIGIN)
def mark_applied():
    """Mark a job application as applied and record applied_at timestamp."""
    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        user_id = data.get("user_id")
        job_id = data.get("job_id")
        application_id = data.get("application_id")

        if not user_id or not job_id:
            return jsonify({"error": "user_id and job_id are required"}), 400

        if not _is_valid_uuid(user_id):
            return jsonify({"error": "Invalid user_id format"}), 400

        supabase = get_supabase_service()

        if application_id:
            app_id = int(application_id)
        else:
            existing = _get_latest_application_for_job(supabase, user_id, job_id)
            if existing:
                app_id = existing["id"]
            else:
                app_id = supabase.create_application(
                    user_id=user_id,
                    job_id=job_id,
                    reasoning_note="Manually applied via apply button",
                )

        if not app_id:
            return jsonify({"error": "Failed to resolve application record"}), 500

        supabase.update_application_status(app_id, "applied", applied_at=datetime.utcnow())

        return jsonify({"success": True, "application_id": app_id, "status": "applied"}), 200

    except Exception as e:
        logger.error(f"Error in mark_applied: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@campaign_bp.route('/user-applications', methods=['GET', 'OPTIONS'])
@cross_origin(origins=CORS_ORIGIN)
def get_user_applications():
    """Return jobs the user has applied to (status='applied'), with job details."""
    if request.method == 'OPTIONS':
        return '', 204

    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id query parameter is required"}), 400

        if not _is_valid_uuid(user_id):
            return jsonify({"error": "Invalid user_id format"}), 400

        supabase = get_supabase_service()

        apps_resp = (
            supabase.client.table("job_applications")
            .select("id, job_id, applied_at, created_at")
            .eq("user_id", user_id)
            .eq("status", "applied")
            .order("applied_at", desc=True)
            .execute()
        )
        applications = apps_resp.data or []

        if not applications:
            return jsonify({"success": True, "applications": []}), 200

        job_ids = list({a["job_id"] for a in applications})
        jobs_resp = (
            supabase.client.table("jobs")
            .select("job_id, job_title, company, location, job_type, url")
            .in_("job_id", job_ids)
            .execute()
        )
        jobs_map = {j["job_id"]: j for j in (jobs_resp.data or [])}

        result = []
        for app in applications:
            job = jobs_map.get(app["job_id"], {})
            result.append({
                "job_id": app["job_id"],
                "title": job.get("job_title") or "Unknown Role",
                "company": job.get("company") or "Unknown Company",
                "location": job.get("location") or "",
                "type": job.get("job_type") or "",
                "url": job.get("url") or "",
                "applied_at": app.get("applied_at") or app.get("created_at"),
            })

        return jsonify({"success": True, "applications": result}), 200

    except Exception as e:
        logger.error(f"Error in get_user_applications: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@campaign_bp.route('/application-materials/save-draft', methods=['POST', 'OPTIONS'])
@cross_origin(origins=CORS_ORIGIN)
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
