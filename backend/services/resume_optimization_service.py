"""
Resume Optimization Service - Orchestrates RAG retrieval and LLM-based optimization
Uses metadata-filtered retrieval to apply role-specific resume optimization rules
"""
import os
import json
import pickle
import logging
import re
import copy
from typing import List, Dict, Any, Optional
from pathlib import Path
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

try:
    from models.skill_extractor import SkillExtractor
    SKILL_EXTRACTOR_AVAILABLE = True
except ImportError:
    SKILL_EXTRACTOR_AVAILABLE = False
    print("SkillExtractor not available, will use fallback keyword extraction")

from services.huggingface_service import get_huggingface_service


logger = logging.getLogger(__name__)


class ResumeOptimizationService:
    """
    Service for job-specific resume optimization using RAG and LLM
    """
    
    # Define role mappings based on JD keywords (from updated_query.py pattern)
    ROLE_MAPPINGS = {
        "software engineer": ["Software Engineer", "Backend", "Full Stack"],
        "full stack": ["Full Stack", "Web Developer", "Frontend", "Backend"],
        "frontend": ["Frontend", "Web Developer", "Full Stack"],
        "backend": ["Backend", "Web Developer", "Full Stack"],
        "mobile": ["Mobile Developer", "iOS Developer", "Android Developer"],
        "ios": ["iOS Developer", "Mobile Developer"],
        "android": ["Android Developer", "Mobile Developer"],
        "game": ["Game Developer"],
        "ui/ux": ["UI/UX Designer", "Product Designer"],
        "data scientist": ["Data Science", "AI/ML", "ML Engineer"],
        "data science": ["Data Science", "AI/ML", "ML Engineer"],
        "machine learning": ["AI/ML", "ML Engineer", "Data Science"],
        "ai": ["AI/ML", "ML Engineer", "Data Science"],
        "ml engineer": ["ML Engineer", "AI/ML", "Data Science"],
        "data analyst": ["Data Analyst", "Business Analyst"],
        "data engineer": ["Data Engineer"],
        "computer vision": ["CV Engineer", "Computer Vision", "AI/ML"],
        "nlp": ["NLP Engineer", "AI/ML"],
        "devops": ["DevOps", "Cloud Engineer", "Site Reliability Engineer"],
        "cloud": ["Cloud Engineer", "DevOps", "Backend"],
        "sre": ["Site Reliability Engineer", "DevOps"],
        "cybersecurity": ["Cybersecurity", "Security Engineer"],
        "security": ["Cybersecurity", "Security Engineer"],
        "blockchain": ["Blockchain Developer", "Web3 Developer"],
        "web3": ["Web3 Developer", "Blockchain Developer"],
        "embedded": ["Embedded Systems Engineer"],
        "robotics": ["Robotics Engineer"],
        "ar/vr": ["AR/VR Developer"],
        "research": ["Research Scientist"],
        "product manager": ["Product Manager"],
        "qa": ["QA Engineer", "Test Engineer", "SDET"],
        "test": ["QA Engineer", "Test Engineer", "SDET"],
    }
    
    def __init__(self):
        """Initialize the resume optimization service"""
        self.base_dir = Path(__file__).resolve().parent.parent
        self.models_dir = self.base_dir / "models"
        
        # Load FAISS index and metadata
        self.faiss_index = None
        self.knowledge_metadata = None
        self._load_knowledge_base()
        
        # Load sentence transformer (same as job embeddings)
        self.model = None
        self._load_embedding_model()
        
        # Initialize skill extractor for JD analysis (optional)
        if SKILL_EXTRACTOR_AVAILABLE:
            self.skill_extractor = SkillExtractor()
            logger.info("SkillExtractor initialized")
        else:
            self.skill_extractor = None
            logger.info("Using fallback keyword extraction (SkillExtractor not available)")
        
        # Get HuggingFace service
        self.hf_service = get_huggingface_service()

    def _load_embedding_model(self) -> None:
        """Best-effort model load with safe fallbacks to keep API responsive."""
        candidates = [
            "sentence-transformers/all-MiniLM-L6-v2",
            "all-MiniLM-L6-v2",
        ]

        logger.info("Loading SentenceTransformer model (this may take 10-30 seconds)...")
        for model_name in candidates:
            try:
                self.model = SentenceTransformer(model_name, device="cpu")
                logger.info(f"✅ SentenceTransformer model loaded successfully: {model_name}")
                return
            except Exception as exc:
                logger.warning(f"Model load failed for {model_name}: {exc}")

        # Keep service alive even if embeddings are unavailable.
        self.model = None
        logger.warning("Embedding model unavailable. Falling back to lexical scoring only.")
    
    def _load_knowledge_base(self):
        """Load FAISS index and metadata for RAG retrieval"""
        faiss_path = self.models_dir / "resume_rules_faiss.index"
        metadata_path = self.models_dir / "resume_rules_metadata.pkl"
        
        if not faiss_path.exists() or not metadata_path.exists():
            logger.warning(
                f"Knowledge base not found. Please run: "
                f"python src/build_resume_knowledge_embeddings.py --force"
            )
            return
        
        try:
            self.faiss_index = faiss.read_index(str(faiss_path))
            with open(metadata_path, 'rb') as f:
                self.knowledge_metadata = pickle.load(f)
            
            logger.info(
                f"Loaded knowledge base: {self.faiss_index.ntotal} chunks, "
                f"dimension {self.faiss_index.d}"
            )
        except Exception as e:
            logger.error(f"Error loading knowledge base: {e}")
    
    def detect_job_role(self, job_description: str) -> List[str]:
        """
        Detect the primary job role(s) from job description
        
        Args:
            job_description: The job posting text
            
        Returns:
            List of detected role tags (e.g., ["Data Science", "AI/ML"])
        """
        jd_lower = job_description.lower()
        detected_roles = set()
        
        # Check for role keywords using boundary-aware matching to avoid false positives
        # Example: keyword "ai" should not match inside "maintain".
        for keyword, roles in self.ROLE_MAPPINGS.items():
            pattern = r"\\b" + re.escape(keyword) + r"\\b"
            if re.search(pattern, jd_lower, re.IGNORECASE):
                detected_roles.update(roles)
        
        # If no specific role detected, use General
        if not detected_roles:
            logger.info("No specific role detected, using General rules")
            return ["General"]
        
        result = list(detected_roles)
        logger.info(f"Detected roles: {result}")
        return result
    
    def extract_jd_keywords(self, job_description: str, top_k: int = 20) -> List[str]:
        """
        Extract key skills and technologies from job description
        
        Args:
            job_description: The job posting text
            top_k: Number of top keywords to return
            
        Returns:
            List of important keywords/skills
        """
        # Use fallback if SkillExtractor not available
        if not self.skill_extractor:
            logger.info("Using fallback keyword extraction")
            return self._simple_keyword_extraction(job_description, top_k)
        
        try:
            # Use skill extractor to find technical skills
            extracted_skills = self.skill_extractor.extract_skills(job_description)
            
            # Handle both dict and list return types
            if isinstance(extracted_skills, dict):
                skills_with_conf = extracted_skills.get('skills_with_confidence', [])
                top_skills = [s['skill'] for s in skills_with_conf[:top_k]]
            elif isinstance(extracted_skills, list):
                # If it returns a list of dicts, extract skill names
                if extracted_skills and isinstance(extracted_skills[0], dict):
                    top_skills = [s.get('skill', s.get('name', str(s))) for s in extracted_skills[:top_k]]
                else:
                    # If it's a list of strings, use directly
                    top_skills = extracted_skills[:top_k]
            else:
                top_skills = []
            
            logger.info(f"Extracted {len(top_skills)} key skills from JD")
            return top_skills
            
        except Exception as e:
            logger.error(f"Error extracting JD keywords: {e}")
            # Fallback: simple keyword extraction
            return self._simple_keyword_extraction(job_description, top_k)
    
    def _simple_keyword_extraction(self, text: str, top_k: int) -> List[str]:
        """Simple fallback keyword extraction"""
        # Common technical keywords pattern
        tech_patterns = [
            r'\b[A-Z][a-z]+(?:\.[a-z]{2,3})?\b',  # React.js, Node.js
            r'\b[A-Z]{2,}\b',  # SQL, AWS, API
            r'\b(?:Python|Java|JavaScript|TypeScript|Go|Ruby|PHP|C\+\+|C#)\b'
        ]
        
        keywords = set()
        blocked_tokens = {
            "job", "context", "original", "description", "company", "position",
            "skills", "critical", "unknown", "mid", "senior", "junior", "we"
        }
        for pattern in tech_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                token = str(match).strip()
                if not token:
                    continue
                if token.lower() in blocked_tokens:
                    continue
                keywords.add(token)
        
        return list(keywords)[:top_k]
    
    def retrieve_optimization_rules(
        self,
        role_tags: List[str],
        query: str = "optimize resume experience bullets",
        top_k: int = 10
    ) -> List[str]:
        """
        Retrieve relevant optimization rules using metadata-filtered RAG
        
        Args:
            role_tags: Detected job roles (e.g., ["Data Science", "AI/ML"])
            query: The retrieval query
            top_k: Number of rules to retrieve
            
        Returns:
            List of relevant optimization rule texts
        """
        if not self.faiss_index or not self.knowledge_metadata:
            logger.error("Knowledge base not loaded")
            return []
        
        try:
            # Step 1: Filter metadata by role tags
            filtered_indices = []
            filtered_chunks = []
            
            for idx, chunk in enumerate(self.knowledge_metadata):
                chunk_roles = chunk.get('role_tags', [])
                
                # Include if chunk is General OR matches any detected role
                if "General" in chunk_roles or any(role in chunk_roles for role in role_tags):
                    filtered_indices.append(idx)
                    filtered_chunks.append(chunk)
            
            if not filtered_indices:
                logger.warning(f"No rules found for roles: {role_tags}")
                return []
            
            logger.info(
                f"Filtered to {len(filtered_indices)} chunks for roles: {role_tags}"
            )
            
            # Step 2: Get embeddings for filtered chunks
            # Note: FAISS doesn't support metadata filtering directly, so we filter post-search
            # For better performance, could rebuild filtered index on-the-fly
            
            # If embedding model is unavailable, use deterministic metadata-filtered fallback.
            if self.model is None:
                rules = [chunk.get('chunk_text', '') for chunk in filtered_chunks[:top_k] if chunk.get('chunk_text')]
                logger.info(f"Retrieved {len(rules)} optimization rules (fallback mode)")
                return rules

            # Embed the query
            query_embedding = self.model.encode([query], convert_to_numpy=True)
            faiss.normalize_L2(query_embedding)

            # Search in full index, then filter results
            k_search = min(top_k * 3, self.faiss_index.ntotal)  # Oversample then filter
            distances, indices = self.faiss_index.search(query_embedding, k_search)

            # Filter search results to only include filtered_indices
            filtered_results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx in filtered_indices:
                    filtered_results.append((dist, idx))
                    if len(filtered_results) >= top_k:
                        break

            # Extract rule texts
            rules = []
            for dist, idx in filtered_results:
                chunk = self.knowledge_metadata[idx]
                rules.append(chunk['chunk_text'])

            logger.info(f"Retrieved {len(rules)} optimization rules")
            return rules
            
        except Exception as e:
            logger.error(f"Error retrieving rules: {e}")
            return []
    
    def optimize_resume(
        self,
        resume_json: Dict[str, Any],
        job_description: str,
        sections_to_optimize: List[str] = None,
        job_context: Optional[Dict[str, Any]] = None,
        optimization_feedback: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main method: Optimize resume for a specific job
        
        Args:
            resume_json: User's resume data structure
            job_description: Target job description
            sections_to_optimize: List of sections like ["experience", "skills", "summary"]
            job_context: Optional job analysis context from JobAnalyzer (enhances optimization)
            
        Returns:
            Dictionary with optimized resume and metadata
        """
        if sections_to_optimize is None:
            sections_to_optimize = ["experience", "skills", "summary"]
        
        logger.info(f"Starting resume optimization for sections: {sections_to_optimize}")
        
        # Extract job context for enhanced optimization
        company_name = job_context.get("company_name", "") if job_context else ""
        critical_skills = job_context.get("critical_skills", []) if job_context else []
        seniority_level = job_context.get("seniority_level", "") if job_context else ""
        
        if job_context:
            logger.info(f"Using job context: {company_name}, {seniority_level}, {len(critical_skills)} critical skills")
        
        # Step 1: Detect job role
        role_tags = self.detect_job_role(job_description)
        
        # Step 2: Extract keywords from JD
        jd_keywords = self.extract_jd_keywords(job_description)
        
        # Enhance keywords with critical skills from job context
        if critical_skills:
            jd_keywords = list(set(jd_keywords + critical_skills))
            logger.info(f"Enhanced keywords with {len(critical_skills)} critical skills from context")
        
        # Step 3: Initialize result structure
        result = {
            "success": True,
            "original": copy.deepcopy(resume_json),
            "optimized": copy.deepcopy(resume_json),
            "metadata": {
                "detected_roles": role_tags,
                "jd_keywords": jd_keywords,
                "sections_optimized": sections_to_optimize,
                "optimization_details": {},
                "job_context_used": bool(job_context),
                "company_name": company_name,
                "seniority_level": seniority_level,
                "optimization_feedback_used": bool(optimization_feedback)
            }
        }
        
        # Build context hints for prompts
        context_hints = self._build_context_hints(job_context) if job_context else ""
        if optimization_feedback:
            feedback_hints = self._build_feedback_hints(optimization_feedback)
            if feedback_hints:
                context_hints = f"{context_hints}\n{feedback_hints}".strip() if context_hints else feedback_hints
        
        # Step 4: Optimize each section
        if "experience" in sections_to_optimize:
            original_experience = resume_json.get('experience', [])
            logger.info(f"\n{'='*60}")
            logger.info(f"OPTIMIZING EXPERIENCE SECTION")
            logger.info(f"{'='*60}")
            logger.info(f"Original experience entries: {len(original_experience)}")
            
            exp_result = self._optimize_experience_section(
                original_experience,
                job_description,
                role_tags,
                jd_keywords,
                context_hints
            )
            
            # Log RAG rules used
            rules_used = exp_result.get('rules_used', [])
            logger.info(f"\n📚 RAG Rules Retrieved ({len(rules_used)} rules):")
            for i, rule in enumerate(rules_used[:3], 1):
                if isinstance(rule, dict):
                    rule_text = rule.get('content') or rule.get('chunk_text') or str(rule)
                else:
                    rule_text = str(rule)
                logger.info(f"  Rule {i}: {rule_text[:100]}...")
            
            # Log LLM response
            llm_response = exp_result.get('llm_response', {})
            optimized_exp = exp_result.get('optimized_experience', [])
            logger.info(f"\n🤖 LLM Output:")
            logger.info(f"  Optimized experience entries: {len(optimized_exp)}")
            if optimized_exp:
                logger.info(f"  First entry highlights: {optimized_exp[0].get('highlights', [])[:2] if optimized_exp[0] else []}")
            logger.info(f"  LLM validation: {llm_response.get('validation', {})}")
            if 'error' in llm_response:
                logger.error(f"  LLM error: {llm_response['error']}")
            
            # Check for errors or validation failures
            if 'error' in exp_result:
                # LLM response error - keep original
                logger.warning(f"❌ Experience optimization failed: {exp_result.get('error')} - keeping original")
                result['optimized']['experience'] = original_experience
                exp_result['optimized_experience'] = original_experience
            else:
                # Check validation for length and metrics
                validation = llm_response.get('validation', {})
                
                # Allow experience optimization even with warnings, but log them
                if not validation.get('passed', True):
                    logger.warning(f"⚠️  Experience validation warnings: {validation.get('warnings', [])}")
                else:
                    logger.info(f"✅ Experience optimization validated")
                
                result['optimized']['experience'] = optimized_exp
            
            logger.info(f"\n✨ Final experience entries: {len(result['optimized']['experience'])}")
            result['metadata']['optimization_details']['experience'] = exp_result
        
        if "skills" in sections_to_optimize:
            original_skills = resume_json.get('skills', [])
            logger.info(f"\n{'='*60}")
            logger.info(f"OPTIMIZING SKILLS SECTION")
            logger.info(f"{'='*60}")
            logger.info(f"Original skills ({len(original_skills)}): {original_skills}")
            logger.info(f"Job keywords ({len(jd_keywords)}): {jd_keywords}")
            
            skills_result = self._optimize_skills_section(
                original_skills,
                job_description,
                role_tags,
                jd_keywords
            )
            
            # Log RAG rules used
            rules_used = skills_result.get('rules_used', [])
            logger.info(f"\n📚 RAG Rules Retrieved ({len(rules_used)} rules):")
            for i, rule in enumerate(rules_used[:3], 1):
                if isinstance(rule, dict):
                    rule_text = rule.get('content') or rule.get('chunk_text') or str(rule)
                else:
                    rule_text = str(rule)
                logger.info(f"  Rule {i}: {rule_text[:100]}...")
            
            # Log LLM response
            llm_response = skills_result.get('llm_response', {})
            optimized_skills = skills_result.get('optimized_skills', [])
            logger.info(f"\n🤖 LLM Output:")
            logger.info(f"  Optimized skills ({len(optimized_skills)}): {optimized_skills}")
            logger.info(f"  LLM validation: {llm_response.get('validation', {})}")
            if 'error' in llm_response:
                logger.error(f"  LLM error: {llm_response['error']}")
            
            # Check validation
            validation = llm_response.get('validation', {})
            # Compute new skills defensively if backend validator did not provide explicit list
            new_skills_added = validation.get('new_skills_added', [])
            if not new_skills_added and not validation.get('no_new_skills_added', True):
                original_norm = {str(s).lower().strip() for s in original_skills}
                optimized_norm = {str(s).lower().strip() for s in optimized_skills}
                new_skills_added = sorted(list(optimized_norm - original_norm))
            
            # Allow optimization if:
            # 1. No LLM error
            # 2. Original skills was empty (allow populating from job requirements)
            # 3. New skills are from job requirements (in jd_keywords)
            if llm_response.get('error'):
                logger.warning(f"❌ LLM error detected - reverting to original skills")
                result['optimized']['skills'] = original_skills
                skills_result['optimized_skills'] = original_skills
            elif len(original_skills) == 0:
                logger.warning("❌ Original skills are empty - strict mode prevents adding unverified skills")
                result['optimized']['skills'] = original_skills
                skills_result['optimized_skills'] = original_skills
                if 'llm_response' in skills_result:
                    skills_result['llm_response']['reverted_to_original'] = True
                    skills_result['llm_response']['reason'] = 'Strict user-data-only mode: cannot add new skills when source skills are empty'
            elif validation.get('no_new_skills_added', True):
                logger.info(f"✅ Skills optimization validated - no hallucinations")
                result['optimized']['skills'] = optimized_skills
            elif new_skills_added and all(skill in jd_keywords for skill in new_skills_added):
                # New skills are from job requirements
                logger.info(f"✅ New skills are from job requirements: {new_skills_added}")
                result['optimized']['skills'] = optimized_skills
            else:
                # Validation failed - hallucinated skills
                logger.warning(f"❌ Skills validation failed - hallucinated skills detected: {new_skills_added}")
                result['optimized']['skills'] = original_skills
                skills_result['optimized_skills'] = original_skills
                if 'llm_response' in skills_result:
                    skills_result['llm_response']['reverted_to_original'] = True
                    skills_result['llm_response']['reason'] = f'Hallucinated skills: {new_skills_added}'
            
            logger.info(f"\n✨ Final skills ({len(result['optimized']['skills'])}): {result['optimized']['skills']}")
            result['metadata']['optimization_details']['skills'] = skills_result
        
        if "summary" in sections_to_optimize:
            original_summary = resume_json.get('summary', '')
            logger.info(f"\n{'='*60}")
            logger.info(f"OPTIMIZING SUMMARY SECTION")
            logger.info(f"{'='*60}")
            logger.info(f"Original summary: {original_summary[:200]}...")
            
            summary_result = self._optimize_summary_section(
                original_summary,
                job_description,
                resume_json.get('experience', []),
                resume_json.get('skills', []),
                role_tags,
                jd_keywords
            )
            
            # Log RAG rules used
            rules_used = summary_result.get('rules_used', [])
            logger.info(f"\n📚 RAG Rules Retrieved ({len(rules_used)} rules):")
            for i, rule in enumerate(rules_used[:3], 1):
                if isinstance(rule, dict):
                    rule_text = rule.get('content') or rule.get('chunk_text') or str(rule)
                else:
                    rule_text = str(rule)
                logger.info(f"  Rule {i}: {rule_text[:100]}...")
            
            # Log LLM response
            llm_response = summary_result.get('llm_response', {})
            optimized_summary = summary_result.get('optimized_summary', '')
            logger.info(f"\n🤖 LLM Output:")
            logger.info(f"  Optimized summary: {optimized_summary[:200]}...")
            logger.info(f"  LLM validation: {llm_response.get('validation', {})}")
            if 'error' in llm_response:
                logger.error(f"  LLM error: {llm_response['error']}")
            
            # Check validation
            validation = llm_response.get('validation', {})
            
            if validation.get('passed', True) and not llm_response.get('error'):
                logger.info(f"✅ Summary optimization validated")
                result['optimized']['summary'] = optimized_summary
            else:
                # Validation failed - keep original summary
                logger.warning(f"❌ Summary validation failed - reverting to original: {validation.get('warnings', [])}")
                result['optimized']['summary'] = original_summary
                
                # Update metadata to reflect revert
                summary_result['optimized_summary'] = original_summary
                if 'llm_response' in summary_result:
                    summary_result['llm_response']['reverted_to_original'] = True
                    summary_result['llm_response']['reason'] = validation.get('warnings', ['Validation failed or LLM error'])[0]
            
            logger.info(f"\n✨ Final summary: {result['optimized']['summary'][:200]}...")
            result['metadata']['optimization_details']['summary'] = summary_result
        
        ats_simulation = self._simulate_ats_score(
            original_resume=resume_json,
            optimized_resume=result["optimized"],
            job_description=job_description,
            jd_keywords=jd_keywords
        )
        result["metadata"]["ats_simulation"] = ats_simulation

        logger.info("Resume optimization complete")
        return result

    def _build_feedback_hints(self, optimization_feedback: Dict[str, Any]) -> str:
        """Convert scorer feedback into tightly-scoped rewrite hints."""
        missing_keywords = optimization_feedback.get("missing_keywords", [])
        weak_sections = optimization_feedback.get("weak_sections", [])

        hints = []
        if missing_keywords:
            hints.append(
                "ATS Missing Keywords (use only if already present in user-provided resume facts): "
                + ", ".join(missing_keywords[:8])
            )
        if weak_sections:
            hints.append("Weak Sections: " + ", ".join(weak_sections[:3]))

        return "\n".join(hints)

    def _simulate_ats_score(
        self,
        original_resume: Dict[str, Any],
        optimized_resume: Dict[str, Any],
        job_description: str,
        jd_keywords: List[str]
    ) -> Dict[str, Any]:
        """
        Deterministic ATS simulator.

        Uses only:
        1. User-provided original resume content
        2. Optimized output
        3. Job description + extracted keywords
        """
        optimized_text = self._resume_to_text(optimized_resume)
        original_text = self._resume_to_text(original_resume)

        keyword_score, missing_keywords = self._keyword_coverage_score(optimized_text, jd_keywords)
        semantic_score = self._semantic_similarity_score(optimized_text, job_description)

        weak_sections = self._detect_weak_sections(optimized_resume, jd_keywords)
        new_numeric_facts = self._find_new_numeric_facts(original_text, optimized_text)

        combined_score = (keyword_score * 0.6) + (semantic_score * 0.4)
        if new_numeric_facts:
            # Hard penalty if optimization introduced unsupported numeric claims.
            combined_score = max(0.0, combined_score - 0.25)

        return {
            "score": round(combined_score, 4),
            "score_percent": round(combined_score * 100, 2),
            "keyword_score": round(keyword_score, 4),
            "semantic_score": round(semantic_score, 4),
            "missing_keywords": missing_keywords,
            "weak_sections": weak_sections,
            "unsupported_numeric_facts_detected": bool(new_numeric_facts),
            "unsupported_numeric_facts": sorted(list(new_numeric_facts))[:10],
            "data_policy": "scorer_uses_only_user_resume_and_jd"
        }

    def _resume_to_text(self, resume: Dict[str, Any]) -> str:
        """Flatten resume JSON into deterministic text for scoring."""
        parts = []

        summary = str(resume.get("summary", "")).strip()
        if summary:
            parts.append(summary)

        for skill in resume.get("skills", []) or []:
            token = str(skill).strip()
            if token:
                parts.append(token)

        for exp in resume.get("experience", []) or []:
            if not isinstance(exp, dict):
                continue
            role = str(exp.get("role", "")).strip()
            if role:
                parts.append(role)
            desc = str(exp.get("description", "")).strip()
            if desc:
                parts.append(desc)

        return "\n".join(parts)

    def _normalize_token(self, value: str) -> str:
        return re.sub(r"[^a-z0-9+.#]+", " ", str(value).lower()).strip()

    def _keyword_coverage_score(self, optimized_text: str, jd_keywords: List[str]) -> tuple[float, List[str]]:
        """Compute deterministic keyword coverage score and missing keywords."""
        if not jd_keywords:
            return 0.0, []

        text = self._normalize_token(optimized_text)
        matched = 0
        missing = []

        for kw in jd_keywords:
            norm_kw = self._normalize_token(str(kw))
            if not norm_kw:
                continue
            pattern = r"\b" + re.escape(norm_kw) + r"\b"
            if re.search(pattern, text, re.IGNORECASE):
                matched += 1
            else:
                missing.append(str(kw))

        score = matched / max(len([k for k in jd_keywords if str(k).strip()]), 1)
        return float(score), missing

    def _semantic_similarity_score(self, optimized_text: str, job_description: str) -> float:
        """Compute semantic similarity using the existing embedding model."""
        if not optimized_text.strip() or not job_description.strip():
            return 0.0
        if self.model is None:
            return 0.0
        try:
            embeddings = self.model.encode([optimized_text, job_description], normalize_embeddings=True)
            similarity = float(np.dot(embeddings[0], embeddings[1]))
            return max(0.0, min(1.0, similarity))
        except Exception as exc:
            logger.warning(f"ATS semantic scoring failed: {exc}")
            return 0.0

    def _detect_weak_sections(self, optimized_resume: Dict[str, Any], jd_keywords: List[str]) -> List[str]:
        """Identify low-coverage resume sections deterministically."""
        weak = []

        section_texts = {
            "summary": str(optimized_resume.get("summary", "") or ""),
            "skills": " ".join([str(s) for s in (optimized_resume.get("skills", []) or [])]),
            "experience": " ".join([
                str(exp.get("description", ""))
                for exp in (optimized_resume.get("experience", []) or [])
                if isinstance(exp, dict)
            ])
        }

        for section_name, section_text in section_texts.items():
            score, _missing = self._keyword_coverage_score(section_text, jd_keywords)
            if score < 0.30:
                weak.append(section_name)

        return weak

    def _extract_numeric_facts(self, text: str) -> set:
        """Extract concrete numeric claims, excluding placeholders like [X%]."""
        sanitized = re.sub(r"\[[^\]]*\]", " ", str(text))
        patterns = [
            r"\b(?:19|20)\d{2}\b",  # years
            r"\b\d+(?:\.\d+)?%\b",  # percentages
            r"\$\s*\d[\d,]*(?:\.\d+)?(?:[kKmMbB])?",  # money
            r"\b\d+(?:\.\d+)?\s*(?:ms|seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b",
            r"\b\d+(?:\.\d+)?\+?\s*(?:users?|customers?|transactions?|requests?|engineers?|projects?)\b",
            r"\b\d+[xX]\b"
        ]
        facts = set()
        for pattern in patterns:
            for match in re.findall(pattern, sanitized, re.IGNORECASE):
                facts.add(str(match).strip().lower())
        return facts

    def _find_new_numeric_facts(self, source_text: str, candidate_text: str) -> set:
        """Return numeric claims present in candidate but absent from source."""
        source_facts = self._extract_numeric_facts(source_text)
        candidate_facts = self._extract_numeric_facts(candidate_text)
        return {f for f in candidate_facts if f not in source_facts}
    
    def _build_context_hints(self, job_context: Dict[str, Any]) -> str:
        """
        Build context hints string for prompt enhancement.
        
        Args:
            job_context: Job analysis results from JobAnalyzer
            
        Returns:
            Context hints string to inject into prompts
        """
        hints = []
        
        company = job_context.get("company_name", "")
        if company:
            hints.append(f"Target Company: {company}")
        
        seniority = job_context.get("seniority_level", "")
        if seniority:
            hints.append(f"Seniority: {seniority.capitalize()}")
        
        critical_skills = job_context.get("critical_skills", [])
        if critical_skills:
            skills_str = ", ".join(critical_skills[:5])
            hints.append(f"CRITICAL SKILLS TO EMPHASIZE: {skills_str}")
        
        culture_signals = job_context.get("culture_signals", {})
        if culture_signals:
            cultures = [c.replace("_", " ").title() for c in culture_signals.keys()]
            hints.append(f"Company Culture: {', '.join(cultures)}")
        
        return "\n".join(hints) if hints else ""
    
    def _optimize_experience_section(
        self,
        experience_list: List[Dict],
        job_description: str,
        role_tags: List[str],
        jd_keywords: List[str],
        context_hints: str = ""
    ) -> Dict[str, Any]:
        """Optimize experience bullet points"""

        # Enhance job description with context hints for better optimization
        enhanced_jd = job_description
        if context_hints:
            enhanced_jd = f"{context_hints}\n\n{job_description}"
            logger.info("Added context hints to experience optimization")
        
        # Extract all bullet points from experience. Support either:
        # 1) description string with newline-delimited bullets
        # 2) highlights array
        all_bullets = []
        exp_bullet_map = []
        for exp in experience_list:
            description = exp.get('description', '')
            if description:
                # Split description into bullet points (assuming newline or bullet separated)
                bullets = [b.strip() for b in description.split('\n') if b.strip()]
                all_bullets.extend(bullets)
                exp_bullet_map.append({"source": "description", "count": len(bullets)})
                continue

            highlights = exp.get('highlights', [])
            if isinstance(highlights, list) and highlights:
                bullets = [str(b).strip() for b in highlights if str(b).strip()]
                all_bullets.extend(bullets)
                exp_bullet_map.append({"source": "highlights", "count": len(bullets)})
            else:
                exp_bullet_map.append({"source": "none", "count": 0})
        
        if not all_bullets:
            return {
                "optimized_experience": experience_list,
                "rules_used": [],
                "note": "No bullets to optimize"
            }

        # Retrieve relevant rules only when there are bullets to optimize
        rules = self.retrieve_optimization_rules(
            role_tags,
            query="optimize experience bullets action verbs quantification STAR method",
            top_k=8
        )
        
        # Call HuggingFace service
        optimization_result = self.hf_service.optimize_experience_bullets(
            original_bullets=all_bullets,
            job_description=enhanced_jd,  # Use enhanced JD with context
            optimization_rules=rules,
            job_keywords=jd_keywords
        )
        
        # Check if optimization_result is valid
        if not optimization_result or not isinstance(optimization_result, dict):
            logger.error(f"Invalid optimization_result: {optimization_result}")
            return {
                "optimized_experience": experience_list,
                "error": "Invalid response from optimization service",
                "llm_response": {"error": "Empty or invalid optimization result"}
            }
        
        # Log the full response for debugging
        logger.debug(f"Experience optimization result keys: {optimization_result.keys()}")
        
        # Reconstruct experience with optimized bullets
        # Replace bullets sequentially while preserving original field shape.
        if 'optimized_bullets' in optimization_result:
            optimized_exp = []
            bullet_idx = 0
            
            for exp_idx, exp in enumerate(experience_list):
                new_exp = exp.copy()
                map_entry = exp_bullet_map[exp_idx] if exp_idx < len(exp_bullet_map) else {"source": "none", "count": 0}
                source = map_entry.get("source", "none")
                num_bullets = int(map_entry.get("count", 0))
                
                if num_bullets > 0:
                    # Get corresponding optimized bullets
                    opt_bullets_data = optimization_result['optimized_bullets'][bullet_idx:bullet_idx + num_bullets]
                    opt_bullet_texts = [b.get('optimized', b.get('original', '')) for b in opt_bullets_data]

                    if source == "description":
                        new_exp['description'] = '\n'.join(opt_bullet_texts)
                    elif source == "highlights":
                        new_exp['highlights'] = opt_bullet_texts

                    bullet_idx += num_bullets
                
                optimized_exp.append(new_exp)
            
            return {
                "optimized_experience": optimized_exp,
                "rules_used": rules,
                "llm_response": optimization_result
            }
        else:
            # LLM didn't return optimized_bullets - could be error or unexpected response
            error_msg = optimization_result.get('error', 'Unknown error')
            
            # Log what we actually received for debugging
            logger.error(f"Experience optimization failed - no optimized_bullets in response. Error: {error_msg}")
            logger.error(f"Response keys present: {list(optimization_result.keys())}")
            if 'raw_response' in optimization_result:
                logger.error(f"Raw LLM response (first 500 chars): {optimization_result['raw_response'][:500]}")
            
            return {
                "optimized_experience": experience_list,
                "error": error_msg,
                "llm_response": optimization_result  # Include full response for debugging
            }
    
    def _optimize_skills_section(
        self,
        skills_list: List[str],
        job_description: str,
        role_tags: List[str],
        jd_keywords: List[str]
    ) -> Dict[str, Any]:
        """Optimize skills list"""
        
        # Retrieve relevant rules
        rules = self.retrieve_optimization_rules(
            role_tags,
            query="optimize skills section match keywords exact phrasing",
            top_k=6
        )
        
        # Call HuggingFace service
        optimization_result = self.hf_service.optimize_skills_section(
            original_skills=skills_list,
            job_description=job_description,
            job_keywords=jd_keywords,
            optimization_rules=rules
        )
        
        return {
            "optimized_skills": optimization_result.get('optimized_skills', skills_list),
            "rules_used": rules,
            "llm_response": optimization_result
        }
    
    def _optimize_summary_section(
        self,
        summary: str,
        job_description: str,
        experience_list: List[Dict],
        user_skills: List[str],
        role_tags: List[str],
        jd_keywords: List[str]
    ) -> Dict[str, Any]:
        """Optimize professional summary"""
        
        # Retrieve relevant rules
        rules = self.retrieve_optimization_rules(
            role_tags,
            query="optimize professional summary highlight relevant experience value proposition",
            top_k=5
        )
        
        # Call HuggingFace service
        optimization_result = self.hf_service.optimize_summary(
            original_summary=summary,
            job_description=job_description,
            user_experience=experience_list,
            user_skills=user_skills,
            optimization_rules=rules,
            job_keywords=jd_keywords
        )
        
        return {
            "optimized_summary": optimization_result.get('optimized_summary', summary),
            "rules_used": rules,
            "llm_response": optimization_result
        }


# Singleton instance
_optimization_service = None

def get_resume_optimization_service() -> ResumeOptimizationService:
    """Get singleton instance of resume optimization service"""
    global _optimization_service
    if _optimization_service is None:
        _optimization_service = ResumeOptimizationService()
    return _optimization_service
