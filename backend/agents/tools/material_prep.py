"""
Material Preparation Tool: Orchestrates tailored resume and cover letter generation.

Integrates Job Analyzer, Resume Optimization Service, and Cover Letter Service
to produce job-specific application materials.
"""

import os
from typing import Dict, Any, Optional
from datetime import datetime

from utils.job_analyzer import JobAnalyzer
from services.resume_optimization_service import ResumeOptimizationService
from services.cover_letter_service import CoverLetterService
from services.supabase_service import get_supabase_service


class MaterialPreparationTool:
    """
    Tool for preparing tailored application materials for specific jobs.
    
    Workflow:
    1. Analyze job description for context
    2. Enhance RAG retrieval with job-specific signals
    3. Optimize resume sections with job context
    4. Generate tailored cover letter
    5. Validate materials (keyword presence, quality checks)
    """
    
    def __init__(self):
        """Initialize material preparation tool."""
        self.job_analyzer = JobAnalyzer()
        self.resume_service = ResumeOptimizationService()
        self.cover_letter_service = CoverLetterService()
        self.supabase = get_supabase_service()
    
    def prepare_materials(
        self,
        user_id: str,
        job_data: Dict[str, Any],
        user_profile: Optional[Dict[str, Any]] = None,
        sections_to_optimize: Optional[list] = None,
        optimization_feedback: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Prepare complete application materials for a specific job.
        
        Args:
            user_id: Supabase user UUID
            job_data: Job dictionary with title, company, description, skills, etc.
            user_profile: Optional cached user profile (fetched if not provided)
            sections_to_optimize: Resume sections to optimize (default: ["experience", "skills", "summary"])
            
        Returns:
            Dict with:
            {
                "optimized_resume": Dict,  # Full resume JSON with optimized sections
                "cover_letter": str,  # Generated cover letter text
                "metadata": Dict,  # Analysis results, keywords matched, confidence scores
                "job_context": Dict,  # Extracted job context
                "error": Optional[str]  # Error message if failed
            }
        """
        
        print(f"\n🔍 Analyzing job: {job_data.get('title')} at {job_data.get('company')}")
        
        # Step 1: Analyze job for context
        try:
            job_analysis = self.job_analyzer.analyze_job(job_data)
            optimization_hints = self.job_analyzer.get_optimization_hints(job_analysis)
            
            print(f"   ✓ Seniority: {job_analysis['seniority_level']}")
            print(f"   ✓ Critical skills: {len(job_analysis['critical_skills'])} identified")
            print(f"   ✓ Culture signals: {list(job_analysis['culture_signals'].keys())}")
            
        except Exception as e:
            error_msg = f"Job analysis failed: {str(e)}"
            print(f"   ❌ {error_msg}")
            return {"error": error_msg}
        
        # Step 2: Fetch user profile if not provided
        if not user_profile:
            try:
                user_profile = self.supabase.get_user_profile(user_id)
                if not user_profile:
                    return {"error": f"User profile not found for user_id: {user_id}"}
            except Exception as e:
                return {"error": f"Failed to fetch user profile: {str(e)}"}
        
        # Extract resume JSON from user profile
        resume_json = user_profile.get("resume_json")
        if not resume_json:
            # Create a basic resume structure from user profile data
            print("   ⚠️  No resume_json found, creating structure from profile columns")
            resume_json = {
                "personal_info": {
                    "name": user_profile.get("name", ""),
                    "email": user_profile.get("email", ""),
                    "phone": user_profile.get("phone", ""),
                    "location": user_profile.get("location", ""),
                    "github": user_profile.get("github", ""),
                    "linkedin": user_profile.get("linkedin", ""),
                    "portfolio": user_profile.get("portfolio", "")
                },
                "summary": user_profile.get("summary", "Motivated professional seeking opportunities."),
                "experience": user_profile.get("experience", []),
                "education": user_profile.get("education", []),
                "skills": user_profile.get("skills", []),
                "projects": user_profile.get("projects", []),
                "certifications": user_profile.get("certificates", []),
                "years_of_experience": user_profile.get("years_of_experience", 0),
                "previous_roles": user_profile.get("previous_roles", [])
            }
            
            print(f"   📊 Profile data loaded:")
            print(f"      - Skills: {len(resume_json['skills'])} skills")
            print(f"      - Experience: {len(resume_json['experience'])} positions")
            print(f"      - Education: {len(resume_json['education'])} entries")
            print(f"      - Projects: {len(resume_json['projects'])} projects")
            print(f"      - Certifications: {len(resume_json['certifications'])} certifications")
        
        # Step 3: Optimize resume with job-specific context
        print(f"\n📄 Optimizing resume sections...")
        
        if sections_to_optimize is None:
            sections_to_optimize = ["experience", "skills", "summary"]
        
        try:
            # Use raw JD text for retrieval/keyword extraction and pass context separately.
            # This avoids polluting keyword extraction with synthetic prefix tokens.
            raw_jd = job_data.get("job_description") or job_data.get("description", "")

            # Call resume optimization service with raw JD + structured context
            optimization_result = self.resume_service.optimize_resume(
                resume_json=resume_json,
                job_description=raw_jd,
                sections_to_optimize=sections_to_optimize,
                job_context=job_analysis,  # Pass full analysis as context
                optimization_feedback=optimization_feedback
            )
            
            if not optimization_result.get("success"):
                error_msg = optimization_result.get("error", "Resume optimization failed")
                print(f"   ❌ {error_msg}")
                return {"error": error_msg}
            
            optimized_resume = optimization_result["optimized"]
            resume_metadata = optimization_result["metadata"]
            
            print(f"   ✓ Sections optimized: {resume_metadata.get('sections_optimized', [])}")
            
        except Exception as e:
            error_msg = f"Resume optimization error: {str(e)}"
            print(f"   ❌ {error_msg}")
            import traceback
            traceback.print_exc()
            return {"error": error_msg}
        
        # Step 4: Generate cover letter
        print(f"\n✉️  Generating cover letter...")
        
        try:
            # Select template based on seniority and culture
            template_name = self._select_cover_letter_template(
                job_analysis["seniority_level"],
                job_analysis["culture_signals"]
            )
            
            print(f"   ✓ Template selected: {template_name}")
            
            # Generate cover letter using template service
            # Note: Current service uses templates; could be enhanced with LLM in future
            cover_letter = self.cover_letter_service.generate_cover_letter(
                user_id=user_id,
                job_id=job_data.get("job_id", "temp_job"),  # Use job_id if available
                template_name=template_name
            )
            
            if not cover_letter:
                print(f"   ⚠️  Cover letter generation failed, using fallback")
                cover_letter = self._generate_fallback_cover_letter(
                    user_profile, job_data, job_analysis
                )
            
            print(f"   ✓ Cover letter generated ({len(cover_letter)} chars)")
            
        except Exception as e:
            # Don't fail the entire workflow if cover letter fails
            print(f"   ⚠️  Cover letter error: {str(e)}, using fallback")
            cover_letter = self._generate_fallback_cover_letter(
                user_profile, job_data, job_analysis
            )
        
        # Step 5: Validate materials
        print(f"\n✅ Validating materials...")
        
        validation = self._validate_materials(
            optimized_resume,
            cover_letter,
            optimization_hints["priority_keywords"]
        )
        
        print(f"   ✓ Keywords matched: {validation['keywords_matched']}/{validation['keywords_total']}")
        print(f"   ✓ Overall confidence: {validation['overall_confidence']:.1%}")
        
        # Compile final result
        result = {
            "original_resume": optimization_result.get("original", resume_json),
            "optimized_resume": optimized_resume,
            "cover_letter": cover_letter,
            "metadata": {
                **resume_metadata,
                **validation,
                "template_used": template_name if 'template_name' in locals() else "fallback",
                "optimization_hints": optimization_hints,
                "generated_at": datetime.utcnow().isoformat()
            },
            "job_context": job_analysis
        }
        
        return result
    
    def _build_enhanced_job_description(
        self, original_jd: str, job_analysis: Dict[str, Any]
    ) -> str:
        """
        Enhance job description with structured context for better RAG retrieval.
        
        Args:
            original_jd: Original job description text
            job_analysis: Output from JobAnalyzer
            
        Returns:
            Enhanced JD string with prepended context
        """
        context_prefix = f"""
JOB CONTEXT:
Company: {job_analysis['company_name']}
Position: {job_analysis['job_title']} ({job_analysis['seniority_level'].capitalize()})
Critical Skills: {', '.join(job_analysis['critical_skills'][:5])}

ORIGINAL JOB DESCRIPTION:
{original_jd}
"""
        return context_prefix.strip()
    
    def _select_cover_letter_template(
        self, seniority: str, culture_signals: Dict[str, list]
    ) -> str:
        """
        Select appropriate cover letter template based on job characteristics.
        
        Templates available:
        - template1.txt: Professional, reliable (default)
        - template2.txt: Motivated, practical
        - template3.txt: Results-oriented (uses portfolio)
        - template4.txt: Dependable, quality-focused (concise)
        - template5.txt: Direct, impactful (minimal)
        
        Args:
            seniority: Seniority level (intern, junior, mid, senior, lead)
            culture_signals: Culture keywords detected
            
        Returns:
            Template filename (e.g., "template1.txt")
        """
        # Map seniority and culture to templates
        if seniority in ["senior", "lead"]:
            # Senior roles: use results-oriented or direct templates
            return "template3.txt" if "data-driven" in culture_signals else "template5.txt"
        elif seniority == "intern":
            # Interns: use motivated, practical template
            return "template2.txt"
        elif "innovative" in culture_signals or "fast-paced" in culture_signals:
            # Startup/dynamic culture: use direct template
            return "template5.txt"
        else:
            # Default: professional, reliable
            return "template1.txt"
    
    def _generate_fallback_cover_letter(
        self, user_profile: Dict, job_data: Dict, job_analysis: Dict
    ) -> str:
        """
        Generate a basic cover letter if template service fails.
        
        Args:
            user_profile: User profile dict
            job_data: Job data dict
            job_analysis: Job analysis results
            
        Returns:
            Simple cover letter string
        """
        name = user_profile.get("name", "Applicant")
        email = user_profile.get("email", "")
        phone = user_profile.get("phone", "")
        company = job_analysis["company_name"]
        title = job_analysis["job_title"]
        skills = job_analysis["critical_skills"][:3]
        
        cover_letter = f"""Dear Hiring Manager,

I am writing to express my strong interest in the {title} position at {company}. With expertise in {', '.join(skills)}, I am confident that my skills and experience make me an excellent fit for this role.

I am excited about the opportunity to contribute to {company}'s team and would welcome the chance to discuss how my background aligns with your needs.

Thank you for considering my application.

Best regards,
{name}
{email}
{phone}
"""
        return cover_letter.strip()
    
    def _validate_materials(
        self, resume: Dict, cover_letter: str, priority_keywords: list
    ) -> Dict[str, Any]:
        """
        Validate generated materials for quality and keyword presence.
        
        Args:
            resume: Optimized resume JSON
            cover_letter: Generated cover letter text
            priority_keywords: List of keywords that should appear
            
        Returns:
            Validation dict with metrics
        """
        # Combine all resume text for keyword checking
        resume_text = ""
        if resume.get("summary"):
            resume_text += resume["summary"] + " "
        if resume.get("experience"):
            for exp in resume["experience"]:
                resume_text += exp.get("description", "") + " "
        if resume.get("skills"):
            resume_text += " ".join(resume["skills"]) + " "
        
        combined_text = (resume_text + " " + cover_letter).lower()
        
        # Check keyword presence
        keywords_matched = 0
        for keyword in priority_keywords:
            if keyword.lower() in combined_text:
                keywords_matched += 1
        
        keywords_total = len(priority_keywords)
        keyword_coverage = keywords_matched / keywords_total if keywords_total > 0 else 0
        
        # Calculate overall confidence
        # Factors: keyword coverage, resume completeness, cover letter length
        has_summary = bool(resume.get("summary"))
        has_experience = bool(resume.get("experience"))
        has_skills = bool(resume.get("skills"))
        completeness = sum([has_summary, has_experience, has_skills]) / 3
        
        cover_letter_quality = min(len(cover_letter) / 300, 1.0)  # Normalize to 300 chars
        
        overall_confidence = (
            keyword_coverage * 0.5 +
            completeness * 0.3 +
            cover_letter_quality * 0.2
        )
        
        return {
            "keywords_matched": keywords_matched,
            "keywords_total": keywords_total,
            "keyword_coverage": keyword_coverage,
            "resume_completeness": completeness,
            "cover_letter_quality": cover_letter_quality,
            "overall_confidence": overall_confidence
        }
