"""
Database service for storing and retrieving learning resources and quizzes.
Uses SQLite for local storage.
"""
import sqlite3
import json
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path
from models.learning_resources import LearningResource, Quiz, QuizQuestion, QuizSubmission


class DatabaseService:
    """Service for managing learning resources and quizzes in SQLite"""
    
    def __init__(self, db_path: str = "learning_resources.db"):
        """Initialize database connection"""
        self.db_path = Path(__file__).parent.parent / db_path
        self.init_database()
    
    def init_database(self):
        """Create tables if they don't exist and migrate existing schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Learning resources table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_resources (
                id TEXT PRIMARY KEY,
                skill TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                snippet TEXT,
                source TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # Quizzes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quizzes (
                id TEXT PRIMARY KEY,
                skill TEXT NOT NULL,
                questions TEXT NOT NULL,
                created_at TEXT NOT NULL,
                total_points INTEGER
            )
        """)
        
        # Quiz submissions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quiz_submissions (
                id TEXT PRIMARY KEY,
                quiz_id TEXT NOT NULL,
                user_answers TEXT NOT NULL,
                score REAL,
                total_points INTEGER,
                passed INTEGER,
                feedback TEXT,
                submitted_at TEXT NOT NULL,
                FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
            )
        """)
        
        # Jobs table - Enhanced with JobSpy-inspired fields
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL,
                raw_html_path TEXT,
                scraped_at TEXT NOT NULL,
                city TEXT,
                country TEXT,
                experience_level TEXT,
                job_type TEXT,
                user_id TEXT,
                status TEXT DEFAULT 'completed',
                -- JobSpy-inspired rich fields
                title TEXT,
                company_name TEXT,
                description TEXT,
                job_url_direct TEXT,
                state TEXT,
                company_url TEXT,
                company_url_direct TEXT,
                compensation_min REAL,
                compensation_max REAL,
                compensation_currency TEXT DEFAULT 'USD',
                compensation_interval TEXT,
                date_posted TEXT,
                emails TEXT,
                is_remote INTEGER DEFAULT 0,
                listing_type TEXT,
                job_level TEXT,
                company_industry TEXT,
                company_logo TEXT,
                banner_photo_url TEXT,
                skills TEXT,
                company_addresses TEXT,
                experience_range TEXT,
                company_rating REAL,
                company_reviews_count INTEGER,
                vacancy_count INTEGER,
                work_from_home_type TEXT,
                job_hash TEXT
            )
        """)
        
        # Scrape log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scrape_log (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                source TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                status_code INTEGER,
                file_path TEXT,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0
            )
        """)
        
        # Migrate existing jobs table to add new columns
        self._migrate_jobs_table(cursor)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_resources_skill ON learning_resources(skill)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_quizzes_skill ON quizzes(skill)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_url ON jobs(url)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_title ON jobs(title)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_date_posted ON jobs(date_posted)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_is_remote ON jobs(is_remote)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_hash ON jobs(job_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scrape_log_url ON scrape_log(url)")
        
        conn.commit()
        conn.close()
        print("✓ Database initialized successfully")
    
    def _migrate_jobs_table(self, cursor):
        """Add new columns to existing jobs table if they don't exist"""
        # Get existing columns
        cursor.execute("PRAGMA table_info(jobs)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        # Define new columns to add
        new_columns = {
            'title': 'TEXT',
            'company_name': 'TEXT',
            'description': 'TEXT',
            'job_url_direct': 'TEXT',
            'state': 'TEXT',
            'company_url': 'TEXT',
            'company_url_direct': 'TEXT',
            'compensation_min': 'REAL',
            'compensation_max': 'REAL',
            'compensation_currency': "TEXT DEFAULT 'USD'",
            'compensation_interval': 'TEXT',
            'date_posted': 'TEXT',
            'emails': 'TEXT',
            'is_remote': 'INTEGER DEFAULT 0',
            'listing_type': 'TEXT',
            'job_level': 'TEXT',
            'company_industry': 'TEXT',
            'company_logo': 'TEXT',
            'banner_photo_url': 'TEXT',
            'skills': 'TEXT',
            'company_addresses': 'TEXT',
            'experience_range': 'TEXT',
            'company_rating': 'REAL',
            'company_reviews_count': 'INTEGER',
            'vacancy_count': 'INTEGER',
            'work_from_home_type': 'TEXT',
            'job_hash': 'TEXT'
        }
        
        # Add missing columns
        for column_name, column_type in new_columns.items():
            if column_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE jobs ADD COLUMN {column_name} {column_type}")
                    print(f"  ✓ Added column: {column_name}")
                except Exception as e:
                    print(f"  ⚠ Could not add column {column_name}: {e}")
        
        print("✓ Jobs table migration complete")
    
    # ==================== Learning Resources ====================
    
    def save_learning_resources(self, skill: str, resources: List[Dict[str, Any]]) -> List[str]:
        """Save multiple learning resources for a skill"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        resource_ids = []
        for resource in resources:
            resource_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO learning_resources (id, skill, title, url, snippet, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                resource_id,
                skill,
                resource.get('title', ''),
                resource.get('url', ''),
                resource.get('snippet', ''),
                resource.get('source', '')
            ))
            resource_ids.append(resource_id)
        
        conn.commit()
        conn.close()
        return resource_ids
    
    def get_learning_resources(self, skill: str) -> List[Dict[str, Any]]:
        """Get all learning resources for a skill"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, skill, title, url, snippet, source, created_at
            FROM learning_resources
            WHERE skill = ?
            ORDER BY created_at DESC
        """, (skill,))
        
        rows = cursor.fetchall()
        conn.close()
        
        resources = []
        for row in rows:
            resources.append({
                'id': row[0],
                'skill': row[1],
                'title': row[2],
                'url': row[3],
                'snippet': row[4],
                'source': row[5],
                'created_at': row[6]
            })
        
        return resources
    
    def delete_old_resources(self, skill: str, keep_latest: int = 10):
        """Delete old resources, keeping only the latest N"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM learning_resources
            WHERE id NOT IN (
                SELECT id FROM learning_resources
                WHERE skill = ?
                ORDER BY created_at DESC
                LIMIT ?
            ) AND skill = ?
        """, (skill, keep_latest, skill))
        
        conn.commit()
        conn.close()
    
    # ==================== Quizzes ====================
    
    def save_quiz(self, quiz: Quiz) -> str:
        """Save a quiz to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        questions_json = json.dumps([q.to_dict() for q in quiz.questions])
        
        cursor.execute("""
            INSERT INTO quizzes (id, skill, questions, created_at, total_points)
            VALUES (?, ?, ?, ?, ?)
        """, (quiz.id, quiz.skill, questions_json, quiz.created_at, quiz.total_points))
        
        conn.commit()
        conn.close()
        return quiz.id
    
    def get_quiz_by_id(self, quiz_id: str) -> Optional[Dict[str, Any]]:
        """Get a quiz by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, skill, questions, created_at, total_points
            FROM quizzes
            WHERE id = ?
        """, (quiz_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'id': row[0],
            'skill': row[1],
            'questions': json.loads(row[2]),
            'created_at': row[3],
            'total_points': row[4]
        }
    
    def get_quiz_by_skill(self, skill: str) -> Optional[Dict[str, Any]]:
        """Get the latest quiz for a skill"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, skill, questions, created_at, total_points
            FROM quizzes
            WHERE skill = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (skill,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'id': row[0],
            'skill': row[1],
            'questions': json.loads(row[2]),
            'created_at': row[3],
            'total_points': row[4]
        }
    
    # ==================== Quiz Submissions ====================
    
    def save_quiz_submission(self, submission: QuizSubmission) -> str:
        """Save a quiz submission"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO quiz_submissions 
            (id, quiz_id, user_answers, score, total_points, passed, feedback, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            submission.id,
            submission.quiz_id,
            json.dumps(submission.user_answers),
            submission.score,
            submission.total_points,
            1 if submission.passed else 0,
            json.dumps(submission.feedback),
            submission.submitted_at
        ))
        
        conn.commit()
        conn.close()
        return submission.id
    
    def get_submission_by_id(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """Get a submission by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, quiz_id, user_answers, score, total_points, passed, feedback, submitted_at
            FROM quiz_submissions
            WHERE id = ?
        """, (submission_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'id': row[0],
            'quiz_id': row[1],
            'user_answers': json.loads(row[2]),
            'score': row[3],
            'total_points': row[4],
            'passed': bool(row[5]),
            'feedback': json.loads(row[6]),
            'submitted_at': row[7]
        }
    
    # ==================== Jobs ====================
    
    def save_job(self, job_data: Dict[str, Any]) -> str:
        """Save a job to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        job_id = job_data.get('id', str(uuid.uuid4()))
        
        try:
            cursor.execute("""
                INSERT INTO jobs 
                (id, url, source, raw_html_path, scraped_at, city, country, 
                 experience_level, job_type, user_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                job_data.get('url'),
                job_data.get('source'),
                job_data.get('raw_html_path'),
                job_data.get('scraped_at'),
                job_data.get('city'),
                job_data.get('country'),
                job_data.get('experience_level'),
                job_data.get('job_type'),
                job_data.get('user_id'),
                job_data.get('status', 'completed')
            ))
            
            conn.commit()
            conn.close()
            return job_id
        except sqlite3.IntegrityError:
            # URL already exists, skip
            conn.close()
            return None
    
    def get_jobs(self, user_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get jobs, optionally filtered by user_id"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute("""
                SELECT id, url, source, raw_html_path, scraped_at, city, country,
                       experience_level, job_type, user_id, status
                FROM jobs
                WHERE user_id = ?
                ORDER BY scraped_at DESC
                LIMIT ?
            """, (user_id, limit))
        else:
            cursor.execute("""
                SELECT id, url, source, raw_html_path, scraped_at, city, country,
                       experience_level, job_type, user_id, status
                FROM jobs
                ORDER BY scraped_at DESC
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        jobs = []
        for row in rows:
            jobs.append({
                'id': row[0],
                'url': row[1],
                'source': row[2],
                'raw_html_path': row[3],
                'scraped_at': row[4],
                'city': row[5],
                'country': row[6],
                'experience_level': row[7],
                'job_type': row[8],
                'user_id': row[9],
                'status': row[10]
            })
        
        return jobs
    
    def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a single job by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, url, source, raw_html_path, scraped_at, city, country,
                   experience_level, job_type, user_id, status
            FROM jobs
            WHERE id = ?
        """, (job_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'id': row[0],
            'url': row[1],
            'source': row[2],
            'raw_html_path': row[3],
            'scraped_at': row[4],
            'city': row[5],
            'country': row[6],
            'experience_level': row[7],
            'job_type': row[8],
            'user_id': row[9],
            'status': row[10]
        }
    
    def url_exists(self, url: str) -> bool:
        """Check if a URL has already been scraped"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM jobs WHERE url = ?", (url,))
        count = cursor.fetchone()[0]
        conn.close()
        
        return count > 0
    
    def save_scrape_log(self, log_data: Dict[str, Any]) -> str:
        """Save a scrape log entry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        log_id = log_data.get('id', str(uuid.uuid4()))
        
        cursor.execute("""
            INSERT INTO scrape_log 
            (id, url, source, timestamp, status_code, file_path, error_message, retry_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            log_id,
            log_data.get('url'),
            log_data.get('source'),
            log_data.get('timestamp'),
            log_data.get('status_code'),
            log_data.get('file_path'),
            log_data.get('error_message'),
            log_data.get('retry_count', 0)
        ))
        
        conn.commit()
        conn.close()
        return log_id
    
    def get_scrape_logs(self, url: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get scrape logs, optionally filtered by URL"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if url:
            cursor.execute("""
                SELECT id, url, source, timestamp, status_code, file_path, 
                       error_message, retry_count
                FROM scrape_log
                WHERE url = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (url, limit))
        else:
            cursor.execute("""
                SELECT id, url, source, timestamp, status_code, file_path, 
                       error_message, retry_count
                FROM scrape_log
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        logs = []
        for row in rows:
            logs.append({
                'id': row[0],
                'url': row[1],
                'source': row[2],
                'timestamp': row[3],
                'status_code': row[4],
                'file_path': row[5],
                'error_message': row[6],
                'retry_count': row[7]
            })
        
        return logs

    # ==================== Enhanced Job Methods ====================
    
    def generate_job_hash(self, company_name: str, title: str, city: str) -> str:
        """Generate composite hash for job deduplication"""
        import hashlib
        if not company_name or not title:
            return None
        key = f"{company_name.lower()}|{title.lower()}|{(city or '').lower()}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def job_hash_exists(self, job_hash: str) -> bool:
        """Check if a job hash already exists"""
        if not job_hash:
            return False
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jobs WHERE job_hash = ?", (job_hash,))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    
    def save_enriched_job(self, job_data: Dict[str, Any]) -> str:
        """Save a job with all enriched fields from JobSpy-style scraping"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        job_id = job_data.get('id', str(uuid.uuid4()))
        
        # Generate job hash if we have the required fields
        job_hash = None
        if job_data.get('company_name') and job_data.get('title'):
            job_hash = self.generate_job_hash(
                job_data.get('company_name'),
                job_data.get('title'),
                job_data.get('city')
            )
        
        # Convert JSON fields
        emails = json.dumps(job_data.get('emails', [])) if job_data.get('emails') else None
        skills = json.dumps(job_data.get('skills', [])) if job_data.get('skills') else None
        company_addresses = json.dumps(job_data.get('company_addresses', [])) if job_data.get('company_addresses') else None
        
        cursor.execute("""
            INSERT INTO jobs (
                id, url, source, raw_html_path, scraped_at, 
                city, country, experience_level, job_type, user_id, status,
                title, company_name, description, job_url_direct, state,
                company_url, company_url_direct, 
                compensation_min, compensation_max, compensation_currency, compensation_interval,
                date_posted, emails, is_remote, listing_type,
                job_level, company_industry, company_logo, banner_photo_url,
                skills, company_addresses, experience_range,
                company_rating, company_reviews_count, vacancy_count,
                work_from_home_type, job_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            job_data.get('url'),
            job_data.get('source'),
            job_data.get('raw_html_path'),
            job_data.get('scraped_at'),
            job_data.get('city'),
            job_data.get('country'),
            job_data.get('experience_level'),
            job_data.get('job_type'),
            job_data.get('user_id'),
            job_data.get('status', 'completed'),
            job_data.get('title'),
            job_data.get('company_name'),
            job_data.get('description'),
            job_data.get('job_url_direct'),
            job_data.get('state'),
            job_data.get('company_url'),
            job_data.get('company_url_direct'),
            job_data.get('compensation_min'),
            job_data.get('compensation_max'),
            job_data.get('compensation_currency', 'USD'),
            job_data.get('compensation_interval'),
            job_data.get('date_posted'),
            emails,
            1 if job_data.get('is_remote') else 0,
            job_data.get('listing_type'),
            job_data.get('job_level'),
            job_data.get('company_industry'),
            job_data.get('company_logo'),
            job_data.get('banner_photo_url'),
            skills,
            company_addresses,
            job_data.get('experience_range'),
            job_data.get('company_rating'),
            job_data.get('company_reviews_count'),
            job_data.get('vacancy_count'),
            job_data.get('work_from_home_type'),
            job_hash
        ))
        
        conn.commit()
        conn.close()
        return job_id

