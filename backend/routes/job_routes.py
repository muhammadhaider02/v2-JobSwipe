"""
Job routes - API endpoints for job scraping and retrieval.
"""
print("  → job_routes: Starting imports...", flush=True)
from flask import Blueprint, request, jsonify, Response
from flask_cors import cross_origin
import uuid
import json
import threading
from datetime import datetime
from typing import Dict, Any

print("  → job_routes: Importing job_scraper_service...", flush=True)
from services.job_scraper_service import get_scraper_service
print("  → job_routes: Importing database_service...", flush=True)
from services.database_service import DatabaseService
print("  → job_routes: Importing scraper modules...", flush=True)
from scraper.producer import JobProducer
from scraper.worker import JobWorker


# Create blueprint
print("  → job_routes: Creating blueprint...", flush=True)
job_bp = Blueprint('jobs', __name__)

# Services will be initialized lazily when needed
_scraper_service = None
_db_service = None

def get_services():
    """Get or initialize services (lazy initialization)"""
    global _scraper_service, _db_service
    if _scraper_service is None:
        _scraper_service = get_scraper_service()
    if _db_service is None:
        _db_service = DatabaseService()
    return _scraper_service, _db_service

print("  → job_routes: Initialization complete!", flush=True)


@job_bp.route('/jobs/scrape', methods=['POST', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def scrape_jobs():
    """
    Trigger job scraping with filters.
    
    Request body:
    {
        "user_id": "user123",
        "city": "Islamabad",
        "country": "Pakistan",
        "experience_level": "entry",
        "job_type": "remote",
        "limit": 5
    }
    
    Returns:
    {
        "scrape_id": "uuid",
        "status": "running",
        "message": "Scraping started"
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        data = request.get_json()
        
        print(f"\n{'='*60}")
        print(f"POST /jobs/scrape")
        print(f"{'='*60}")
        print(f"Request data: {json.dumps(data, indent=2)}")
        
        # Validation
        if not data or 'user_id' not in data:
            return jsonify({
                "error": "user_id is required",
                "status": "error"
            }), 400
        
        user_id = data['user_id']
        limit = data.get('limit', 5)  # Default to 5 for testing
        
        # Filters are optional now (role-based scraping)
        filters = {
            'city': data.get('city'),
            'country': data.get('country'),
            'experience_level': data.get('experience_level'),
            'job_type': data.get('job_type')
        }
        
        # Generate scrape ID
        scrape_id = str(uuid.uuid4())
        
        # Start scraping metadata
        scraper_service.start_scraping(scrape_id, user_id, filters, limit)
        
        # Run producer and worker in background thread
        def run_scraping():
            try:
                # Step 1: Producer - push URLs to queue
                producer = JobProducer()
                queued = producer.produce_jobs(scrape_id, user_id, filters, limit)
                
                print(f"  ✓ Producer queued {queued} URLs")
                
                # Step 2: Worker - process queue
                worker = JobWorker()
                processed = worker.run(scrape_id, limit=limit, timeout=300)
                
                print(f"  ✓ Worker processed {processed} jobs")
                
            except Exception as e:
                print(f"  ✗ Scraping error: {e}")
                import traceback
                traceback.print_exc()
                
                # Update progress with error
                scraper_service.publish_progress(scrape_id, {
                    "scrape_id": scrape_id,
                    "completed": 0,
                    "total": limit,
                    "status": "failed",
                    "message": f"Error: {str(e)}",
                    "percentage": 0
                })
        
        # Start background thread
        thread = threading.Thread(target=run_scraping, daemon=True)
        thread.start()
        
        response = {
            "scrape_id": scrape_id,
            "status": "running",
            "message": f"Scraping started for {limit} jobs",
            "user_id": user_id,
            "filters": filters
        }
        
        print(f"Response: {json.dumps(response, indent=2)}")
        print(f"{'='*60}\n")
        
        return jsonify(response), 202
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@job_bp.route('/jobs/scrape/status/<scrape_id>', methods=['GET', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def get_scrape_status(scrape_id):
    """
    Get scraping progress/status.
    
    Returns:
    {
        "scrape_id": "uuid",
        "user_id": "user123",
        "completed": 3,
        "total": 5,
        "status": "running|completed|failed",
        "percentage": 60.0,
        "message": "Scraped job 3/5"
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        status = scraper_service.get_scrape_status(scrape_id)
        
        if not status:
            return jsonify({
                "error": "Scrape ID not found",
                "status": "error"
            }), 404
        
        return jsonify(status)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@job_bp.route('/jobs', methods=['GET', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def get_jobs():
    """
    Get scraped jobs, optionally filtered by user_id.
    
    Query params:
        user_id (optional): Filter jobs by user
        limit (optional): Max results (default 50)
    
    Returns:
    {
        "jobs": [...],
        "count": 10
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        user_id = request.args.get('user_id')
        limit = int(request.args.get('limit', 50))
        
        print(f"\n{'='*60}")
        print(f"GET /jobs")
        print(f"user_id: {user_id}, limit: {limit}")
        print(f"{'='*60}\n")
        
        jobs = db_service.get_jobs(user_id=user_id, limit=limit)
        
        response = {
            "jobs": jobs,
            "count": len(jobs),
            "status": "success"
        }
        
        print(f"  ✓ Returning {len(jobs)} jobs")
        
        return jsonify(response)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@job_bp.route('/jobs/<job_id>', methods=['GET', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def get_job_by_id(job_id):
    """
    Get a single job by ID.
    
    Returns:
    {
        "job": {...},
        "raw_html": "path/to/html" (optional)
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        print(f"\n{'='*60}")
        print(f"GET /jobs/{job_id}")
        print(f"{'='*60}\n")
        
        job = db_service.get_job_by_id(job_id)
        
        if not job:
            return jsonify({
                "error": "Job not found",
                "status": "error"
            }), 404
        
        # Optionally read raw HTML if requested
        include_html = request.args.get('include_html', 'false').lower() == 'true'
        
        if include_html and job.get('raw_html_path'):
            from pathlib import Path
            html_path = Path(__file__).parent.parent / job['raw_html_path']
            
            if html_path.exists():
                with open(html_path, 'r', encoding='utf-8') as f:
                    job['raw_html_content'] = f.read()
        
        response = {
            "job": job,
            "status": "success"
        }
        
        print(f"  ✓ Returning job: {job['url']}")
        
        return jsonify(response)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@job_bp.route('/jobs/filters/<user_id>', methods=['GET', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def get_user_filters(user_id):
    """
    Get default filters for a user (from profile or defaults).
    
    For now, returns defaults. In future, fetch from user profile.
    
    Returns:
    {
        "city": "Islamabad",
        "country": "Pakistan",
        "experience_level": "entry",
        "job_type": "remote"
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        print(f"\n{'='*60}")
        print(f"GET /jobs/filters/{user_id}")
        print(f"{'='*60}\n")
        
        # TODO: In future, fetch from user profile in database
        # For now, return sensible defaults
        
        default_filters = {
            "city": "Islamabad",
            "country": "Pakistan",
            "experience_level": "entry",
            "job_type": "remote"
        }
        
        response = {
            "filters": default_filters,
            "status": "success"
        }
        
        print(f"  ✓ Returning default filters")
        
        return jsonify(response)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@job_bp.route('/jobs/stats', methods=['GET', 'OPTIONS'])
@cross_origin(
    origins="http://localhost:3000",
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)
def get_scraper_stats():
    """
    Get scraping system statistics (admin endpoint).
    
    Returns:
    {
        "queue_length": 5,
        "scraped_urls_count": 150,
        "redis_connected": true
    }
    """
    if request.method == "OPTIONS":
        return ("", 204)
    
    try:
        stats = scraper_service.get_stats()
        
        response = {
            "stats": stats,
            "status": "success"
        }
        
        return jsonify(response)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500
