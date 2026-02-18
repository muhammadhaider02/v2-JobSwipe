"""
Resume Optimization Service - Orchestrates RAG retrieval and LLM-based optimization
Uses metadata-filtered retrieval to apply role-specific resume optimization rules
"""
import os
import json
import pickle
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from models.skill_extractor import SkillExtractor
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
        self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        
        # Initialize skill extractor for JD analysis
        self.skill_extractor = SkillExtractor()
        
        # Get HuggingFace service
        self.hf_service = get_huggingface_service()
    
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
        
        # Check for role keywords
        for keyword, roles in self.ROLE_MAPPINGS.items():
            if keyword in jd_lower:
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
        
        import re
        keywords = set()
        for pattern in tech_patterns:
            matches = re.findall(pattern, text)
            keywords.update(matches)
        
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
        sections_to_optimize: List[str] = None
    ) -> Dict[str, Any]:
        """
        Main method: Optimize resume for a specific job
        
        Args:
            resume_json: User's resume data structure
            job_description: Target job description
            sections_to_optimize: List of sections like ["experience", "skills", "summary"]
            
        Returns:
            Dictionary with optimized resume and metadata
        """
        if sections_to_optimize is None:
            sections_to_optimize = ["experience", "skills", "summary"]
        
        logger.info(f"Starting resume optimization for sections: {sections_to_optimize}")
        
        # Step 1: Detect job role
        role_tags = self.detect_job_role(job_description)
        
        # Step 2: Extract keywords from JD
        jd_keywords = self.extract_jd_keywords(job_description)
        
        # Step 3: Initialize result structure
        result = {
            "original": resume_json.copy(),
            "optimized": resume_json.copy(),
            "metadata": {
                "detected_roles": role_tags,
                "jd_keywords": jd_keywords,
                "sections_optimized": sections_to_optimize,
                "optimization_details": {}
            }
        }
        
        # Step 4: Optimize each section
        if "experience" in sections_to_optimize:
            exp_result = self._optimize_experience_section(
                resume_json.get('experience', []),
                job_description,
                role_tags,
                jd_keywords
            )
            result['optimized']['experience'] = exp_result.get('optimized_experience', [])
            result['metadata']['optimization_details']['experience'] = exp_result
        
        if "skills" in sections_to_optimize:
            skills_result = self._optimize_skills_section(
                resume_json.get('skills', []),
                job_description,
                role_tags,
                jd_keywords
            )
            result['optimized']['skills'] = skills_result.get('optimized_skills', [])
            result['metadata']['optimization_details']['skills'] = skills_result
        
        if "summary" in sections_to_optimize:
            summary_result = self._optimize_summary_section(
                resume_json.get('summary', ''),
                job_description,
                resume_json.get('experience', []),
                role_tags,
                jd_keywords
            )
            result['optimized']['summary'] = summary_result.get('optimized_summary', '')
            result['metadata']['optimization_details']['summary'] = summary_result
        
        logger.info("Resume optimization complete")
        return result
    
    def _optimize_experience_section(
        self,
        experience_list: List[Dict],
        job_description: str,
        role_tags: List[str],
        jd_keywords: List[str]
    ) -> Dict[str, Any]:
        """Optimize experience bullet points"""
        
        # Retrieve relevant rules
        rules = self.retrieve_optimization_rules(
            role_tags,
            query="optimize experience bullets action verbs quantification STAR method",
            top_k=8
        )
        
        # Extract all bullet points from experience
        all_bullets = []
        for exp in experience_list:
            description = exp.get('description', '')
            if description:
                # Split description into bullet points (assuming newline or bullet separated)
                bullets = [b.strip() for b in description.split('\n') if b.strip()]
                all_bullets.extend(bullets)
        
        if not all_bullets:
            return {"optimized_experience": experience_list, "note": "No bullets to optimize"}
        
        # Call HuggingFace service
        optimization_result = self.hf_service.optimize_experience_bullets(
            original_bullets=all_bullets,
            job_description=job_description,
            optimization_rules=rules,
            job_keywords=jd_keywords
        )
        
        # Reconstruct experience with optimized bullets
        # (Simple approach: replace all bullets sequentially)
        if 'optimized_bullets' in optimization_result:
            optimized_exp = []
            bullet_idx = 0
            
            for exp in experience_list:
                new_exp = exp.copy()
                description = exp.get('description', '')
                
                if description:
                    original_bullets = [b.strip() for b in description.split('\n') if b.strip()]
                    num_bullets = len(original_bullets)
                    
                    # Get corresponding optimized bullets
                    opt_bullets_data = optimization_result['optimized_bullets'][bullet_idx:bullet_idx + num_bullets]
                    opt_bullet_texts = [b.get('optimized', b.get('original', '')) for b in opt_bullets_data]
                    
                    # Reconstruct description
                    new_exp['description'] = '\n'.join(opt_bullet_texts)
                    bullet_idx += num_bullets
                
                optimized_exp.append(new_exp)
            
            return {
                "optimized_experience": optimized_exp,
                "rules_used": rules,
                "llm_response": optimization_result
            }
        else:
            return {
                "optimized_experience": experience_list,
                "error": optimization_result.get('error', 'Unknown error')
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
