"""
HuggingFace Inference API Service
Handles LLM-based resume optimization using Hugging Face Serverless Inference API
"""
import os
import json
import logging
from typing import Dict, List, Optional, Any
from huggingface_hub import InferenceClient


logger = logging.getLogger(__name__)


class HuggingFaceService:
    """Service for interacting with HuggingFace Inference API for resume optimization"""
    
    def __init__(self):
        """Initialize HuggingFace service with API credentials"""
        self.api_key = os.getenv("HUGGINGFACE_API_KEY")
        
        # CHOICE: Meta-Llama-3.1-8B-Instruct via SambaNova
        # Reasoning: Best balance of speed (sub-second responses) and instruction following
        # for complex JSON formatting tasks like resume optimization.
        self.model_id = "meta-llama/Meta-Llama-3.1-8B-Instruct"
        
        if not self.api_key:
            logger.warning("HUGGINGFACE_API_KEY not set. LLM optimization will not work.")
            self.client = None
        else:
            # We use SambaNova because it is significantly faster than the default HF fleet
            # and highly reliable for Llama 3.1 models.
            self.client = InferenceClient(
                token=self.api_key,
                provider="sambanova"
            )
        
        # Generation parameters for deterministic JSON output
        self.generation_config = {
            "max_new_tokens": 2048,
            "temperature": 0.1,
            "do_sample": False,
            "top_p": 0.95
        }
    
    def optimize_experience_bullets(
        self,
        original_bullets: List[str],
        job_description: str,
        optimization_rules: List[str],
        job_keywords: List[str]
    ) -> Dict[str, Any]:
        """
        Optimize experience section bullet points for a specific job
        
        Args:
            original_bullets: List of original resume bullet points
            job_description: The target job description
            optimization_rules: Retrieved RAG context rules
            job_keywords: Key skills/keywords from the job description
            
        Returns:
            Dictionary with optimized_bullets and reasoning chains
        """
        if not self.client:
            logger.error("HuggingFace client not initialized")
            return {"error": "HuggingFace API not configured"}
        
        try:
            prompt = self._build_experience_optimization_prompt(
                original_bullets,
                job_description,
                optimization_rules,
                job_keywords
            )
            
            # Use chat_completion for better control and provider selection
            messages = [{"role": "user", "content": prompt}]
            
            response = self.client.chat_completion(
                messages=messages,
                model=self.model_id,
                max_tokens=2048,
                temperature=0.1,
                top_p=0.95
            )
            
            # Extract the message content
            response_text = response.choices[0].message.content
            
            # Parse JSON response
            result = self._parse_json_response(response_text)
            
            # Validate no hallucinations
            validation_result = self._validate_no_new_facts(original_bullets, result.get('optimized_bullets', []))
            result['validation'] = validation_result
            
            return result
            
        except Exception as e:
            logger.error(f"Error optimizing experience bullets: {str(e)}")
            return {"error": str(e)}
    
    def optimize_skills_section(
        self,
        original_skills: List[str],
        job_description: str,
        job_keywords: List[str],
        optimization_rules: List[str]
    ) -> Dict[str, Any]:
        """
        Optimize skills section to match job requirements
        
        Args:
            original_skills: List of original skills
            job_description: The target job description
            job_keywords: Required skills from JD
            optimization_rules: Retrieved RAG context rules
            
        Returns:
            Dictionary with optimized_skills and reasoning
        """
        if not self.client:
            logger.error("HuggingFace client not initialized")
            return {"error": "HuggingFace API not configured"}
        
        try:
            prompt = self._build_skills_optimization_prompt(
                original_skills,
                job_description,
                job_keywords,
                optimization_rules
            )
            
            # Use chat_completion for better control and provider selection
            messages = [{"role": "user", "content": prompt}]
            
            response = self.client.chat_completion(
                messages=messages,
                model=self.model_id,
                max_tokens=2048,
                temperature=0.1,
                top_p=0.95
            )
            
            # Extract the message content
            response_text = response.choices[0].message.content
            
            result = self._parse_json_response(response_text)
            
            # Ensure we don't add skills user doesn't have
            result['validation'] = {
                "no_new_skills_added": self._check_no_new_skills(original_skills, result.get('optimized_skills', []))
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error optimizing skills: {str(e)}")
            return {"error": str(e)}
    
    def optimize_summary(
        self,
        original_summary: str,
        job_description: str,
        user_experience: List[Dict],
        optimization_rules: List[str],
        job_keywords: List[str]
    ) -> Dict[str, Any]:
        """
        Optimize professional summary for a specific job
        
        Args:
            original_summary: Original summary/objective
            job_description: The target job description
            user_experience: User's experience data for context
            optimization_rules: Retrieved RAG context rules
            job_keywords: Key requirements from JD
            
        Returns:
            Dictionary with optimized_summary and reasoning
        """
        if not self.client:
            logger.error("HuggingFace client not initialized")
            return {"error": "HuggingFace API not configured"}
        
        try:
            prompt = self._build_summary_optimization_prompt(
                original_summary,
                job_description,
                user_experience,
                optimization_rules,
                job_keywords
            )
            
            # Use chat_completion for better control and provider selection
            messages = [{"role": "user", "content": prompt}]
            
            response = self.client.chat_completion(
                messages=messages,
                model=self.model_id,
                max_tokens=2048,
                temperature=0.1,
                top_p=0.95
            )
            
            # Extract the message content
            response_text = response.choices[0].message.content
            
            result = self._parse_json_response(response_text)
            return result
            
        except Exception as e:
            logger.error(f"Error optimizing summary: {str(e)}")
            return {"error": str(e)}
    
    def _build_experience_optimization_prompt(
        self,
        original_bullets: List[str],
        job_description: str,
        optimization_rules: List[str],
        job_keywords: List[str]
    ) -> str:
        """Build prompt for experience bullet optimization"""
        
        rules_text = "\n".join([f"- {rule}" for rule in optimization_rules])
        keywords_text = ", ".join([kw['skill'] if isinstance(kw, dict) else kw for kw in job_keywords[:15]])
        bullets_text = "\n".join([f"{i+1}. {bullet}" for i, bullet in enumerate(original_bullets)])
        
        # Added a strict JSON instruction at the end of the system block for Llama-3.1
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are an expert resume optimizer. Your task is to rewrite resume experience bullet points to better match a specific job description while maintaining complete factual accuracy.

CRITICAL RULES:
1. DO NOT add achievements, projects, or dates not present in the original bullets.
2. DO NOT invent metrics.
3. Use strong action verbs.
4. Return ONLY a valid JSON object.

TARGET JOB DESCRIPTION:
{job_description[:1000]}

KEY KEYWORDS: {keywords_text}

OPTIMIZATION RULES:
{rules_text}
<|eot_id|><|start_header_id|>user<|end_header_id|>
ORIGINAL RESUME BULLETS:
{bullets_text}

YOUR TASK:
Rewrite each bullet point. Explain reasoning, then provide the optimized version.

OUTPUT FORMAT (strict JSON):
{{
  "optimized_bullets": [
    {{
      "original": "...",
      "optimized": "...",
      "reasoning": "..."
    }}
  ]
}}
<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""
        
        return prompt
    
    def _build_skills_optimization_prompt(
        self,
        original_skills: List[str],
        job_description: str,
        job_keywords: List[str],
        optimization_rules: List[str]
    ) -> str:
        """Build prompt for skills section optimization"""
        
        rules_text = "\n".join([f"- {rule}" for rule in optimization_rules])
        skills_text = ", ".join(original_skills)
        keywords_text = ", ".join([kw['skill'] if isinstance(kw, dict) else kw for kw in job_keywords[:20]])
        
        prompt = f"""You are an expert resume optimizer. Optimize the skills section to match the job description's requirements.

CRITICAL RULES:
1. DO NOT add skills the user doesn't have
2. ONLY reorder, rename (e.g., "React" → "React.js"), or group existing skills
3. Match exact keyword phrasing from job description when possible
4. Remove irrelevant skills for this specific job
5. Prioritize skills mentioned in the job description

TARGET JOB DESCRIPTION:
{job_description[:1000]}

REQUIRED KEYWORDS FROM JD: {keywords_text}

OPTIMIZATION RULES:
{rules_text}

ORIGINAL SKILLS:
{skills_text}

YOUR TASK:
Reorder and refine the skills list to match the job requirements. Explain your reasoning.

OUTPUT FORMAT (strict JSON):
{{
  "optimized_skills": ["skill1", "skill2", "skill3"],
  "reasoning": "explanation of changes: what was reordered, renamed, or removed and why",
  "keyword_matches": ["which JD keywords are now matched"]
}}

Return ONLY valid JSON."""
        
        return prompt
    
    def _build_summary_optimization_prompt(
        self,
        original_summary: str,
        job_description: str,
        user_experience: List[Dict],
        optimization_rules: List[str],
        job_keywords: List[str]
    ) -> str:
        """Build prompt for summary/objective optimization"""
        
        rules_text = "\n".join([f"- {rule}" for rule in optimization_rules])
        keywords_text = ", ".join([kw['skill'] if isinstance(kw, dict) else kw for kw in job_keywords[:15]])
        
        # Extract role titles from experience for context
        roles = [exp.get('role', '') for exp in user_experience[:3]]
        roles_text = ", ".join(filter(None, roles))
        
        prompt = f"""You are an expert resume optimizer. Rewrite the professional summary to align with a specific job posting.

CRITICAL RULES:
1. DO NOT invent job titles, companies, or qualifications not in the user's background
2. ONLY emphasize relevant aspects of their actual experience
3. Use keywords from the job description naturally
4. Keep summary concise (2-4 sentences, 50-80 words)
5. Focus on value proposition for THIS specific role

TARGET JOB DESCRIPTION:
{job_description[:1000]}

KEY KEYWORDS: {keywords_text}

OPTIMIZATION RULES:
{rules_text}

USER'S BACKGROUND:
- Recent Roles: {roles_text}
- Original Summary: {original_summary}

YOUR TASK:
Rewrite the summary to highlight relevant experience for this job.

OUTPUT FORMAT (strict JSON):
{{
  "optimized_summary": "the rewritten summary text",
  "reasoning": "why this framing was chosen, which keywords incorporated, what was emphasized"
}}

Return ONLY valid JSON."""
        
        return prompt
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM JSON response with error handling"""
        try:
            # Try to find JSON in response (sometimes models add explanatory text)
            response = response.strip()
            
            # Find JSON object boundaries
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx+1]
                return json.loads(json_str)
            else:
                # Fallback: try parsing entire response
                return json.loads(response)
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}\nResponse: {response}")
            return {"error": "Invalid JSON response from LLM", "raw_response": response}
    
    def _validate_no_new_facts(self, original_bullets: List[str], optimized_bullets: List) -> Dict[str, bool]:
        """
        Basic validation to check if new companies/degrees were added
        Returns validation flags
        """
        original_text = " ".join(original_bullets).lower()
        
        validation = {
            "passed": True,
            "warnings": []
        }
        
        # Extract optimized text
        if isinstance(optimized_bullets, list):
            if optimized_bullets and isinstance(optimized_bullets[0], dict):
                optimized_text = " ".join([b.get('optimized', '') for b in optimized_bullets]).lower()
            else:
                optimized_text = " ".join(optimized_bullets).lower()
        else:
            optimized_text = str(optimized_bullets).lower()
        
        # Check for common hallucination patterns (basic heuristic)
        # This is a simple check - could be enhanced with NER or more sophisticated validation
        
        # Check if optimized is substantially longer (possible hallucination)
        if len(optimized_text) > len(original_text) * 1.5:
            validation['warnings'].append("Optimized content is 50%+ longer than original")
            validation['passed'] = False
        
        return validation
    
    def _check_no_new_skills(self, original_skills: List[str], optimized_skills: List[str]) -> bool:
        """Check that optimized skills are subset/variants of original skills"""
        # Normalize for comparison
        original_normalized = {skill.lower().strip() for skill in original_skills}
        
        # Check each optimized skill has a match in original (fuzzy)
        for opt_skill in optimized_skills:
            opt_normalized = opt_skill.lower().strip()
            
            # Check if it's in original or is a variant (contains or is contained)
            found_match = False
            for orig_skill in original_normalized:
                if opt_normalized in orig_skill or orig_skill in opt_normalized:
                    found_match = True
                    break
            
            if not found_match:
                logger.warning(f"Potential new skill added: {opt_skill}")
                return False
        
        return True


# Singleton instance
_huggingface_service = None

def get_huggingface_service() -> HuggingFaceService:
    """Get singleton instance of HuggingFace service"""
    global _huggingface_service
    if _huggingface_service is None:
        _huggingface_service = HuggingFaceService()
    return _huggingface_service