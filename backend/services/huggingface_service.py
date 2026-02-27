"""
HuggingFace Inference API Service
Handles LLM-based resume optimization using Hugging Face Serverless Inference API
"""
import os
import json
import logging
import re
from typing import Dict, List, Optional, Any
from huggingface_hub import InferenceClient


logger = logging.getLogger(__name__)


class HuggingFaceService:
    """Service for interacting with HuggingFace Inference API for resume optimization"""
    
    def __init__(self):
        """Initialize HuggingFace service with API credentials"""
        self.api_key = os.getenv("HUGGINGFACE_API_KEY")
        
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
            
            # Check if parsing failed
            if 'error' in result and 'raw_response' in result:
                logger.error(f"JSON parsing failed. Raw response: {result['raw_response'][:500]}")
                return result  # Return error immediately
            
            # Handle alternative response formats from LLM
            if 'optimized_bullets' not in result:
                logger.warning(f"LLM returned unexpected format. Keys: {list(result.keys())}")
                
                # Try to normalize the response
                normalized = self._normalize_experience_response(result, original_bullets)
                if normalized:
                    result = normalized
                else:
                    logger.error("Could not normalize LLM response to expected format")
                    return {
                        "error": "LLM returned unexpected JSON structure",
                        "raw_response": str(result)[:500],
                        "expected_keys": "optimized_bullets",
                        "received_keys": list(result.keys())
                    }
            
            # Validate no hallucinations
            validation_result = self._validate_no_new_facts(original_bullets, result.get('optimized_bullets', []))
            
            # Also validate metric placeholders for STAR method
            metric_validation = self._check_metric_placeholders(result.get('optimized_bullets', []))
            
            # Combine validations
            validation_result['metric_check'] = metric_validation
            if not metric_validation['passed']:
                validation_result['warnings'].extend(metric_validation['warnings'])
            
            result['validation'] = validation_result
            
            return result
            
        except Exception as e:
            logger.error(f"Error optimizing experience bullets: {str(e)}", exc_info=True)
            return {"error": str(e), "exception_type": type(e).__name__}
    
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
            
            # Check if parsing failed
            if 'error' in result and 'raw_response' in result:
                logger.error(f"Skills JSON parsing failed. Raw response: {result['raw_response'][:500]}")
                return result  # Return error immediately
            
            # Ensure we don't add skills user doesn't have
            result['validation'] = {
                "no_new_skills_added": self._check_no_new_skills(original_skills, result.get('optimized_skills', []))
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error optimizing skills: {str(e)}", exc_info=True)
            return {"error": str(e), "exception_type": type(e).__name__}
    
    def optimize_summary(
        self,
        original_summary: str,
        job_description: str,
        user_experience: List[Dict],
        user_skills: List[str],
        optimization_rules: List[str],
        job_keywords: List[str]
    ) -> Dict[str, Any]:
        """
        Optimize professional summary for a specific job
        
        Args:
            original_summary: Original summary/objective
            job_description: The target job description
            user_experience: User's experience data for context
            user_skills: User's actual skills list (for hallucination prevention)
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
                user_skills,
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
            
            # Check if parsing failed
            if 'error' in result and 'raw_response' in result:
                logger.error(f"Summary JSON parsing failed. Raw response: {result['raw_response'][:500]}")
                return result  # Return error immediately
            
            # Validate no skill hallucinations in summary
            result['validation'] = self._validate_summary_skills(
                result.get('optimized_summary', ''),
                user_skills
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error optimizing summary: {str(e)}", exc_info=True)
            return {"error": str(e), "exception_type": type(e).__name__}
    
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
2. DO NOT invent metrics - if a measurable result is missing, you MUST include a bracketed placeholder.
3. MANDATORY: Every bullet MUST follow STAR format with a Result. If the original lacks a result, add a placeholder: [X%], [Numerical Metric], [Time Reduced], or [Users/Revenue Impact].
4. LENGTH LIMIT: Each optimized bullet MUST be shorter or equal length to the original. Maximum 15% increase allowed. Prefer concise phrasing.
5. Use strong action verbs (Led, Developed, Architected, Optimized, Automated).
6. Return ONLY a valid JSON object.

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

CRITICAL: You must return a JSON object with an "optimized_bullets" array containing ALL bullets.

OUTPUT FORMAT (strict JSON - must include ALL {len(original_bullets)} bullets):
{{
  "optimized_bullets": [
    {{
      "original": "first original bullet",
      "optimized": "improved first bullet",
      "reasoning": "explanation of changes"
    }},
    {{
      "original": "second original bullet",
      "optimized": "improved second bullet",
      "reasoning": "explanation of changes"
    }}
    // ... continue for all {len(original_bullets)} bullets
  ]
}}

Remember: Return ONLY the JSON object above with ALL {len(original_bullets)} bullets in the array.
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
1. DO NOT add skills the user doesn't have - ONLY refine existing skills (e.g., "React" → "React.js").
2. ONLY reorder, rename with minor refinements, or group existing skills from the original list.
3. Match exact keyword phrasing from job description when possible, but ONLY for skills already present.
4. Remove irrelevant skills for this specific job.
5. Prioritize skills mentioned in the job description.

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
        user_skills: List[str],
        optimization_rules: List[str],
        job_keywords: List[str]
    ) -> str:
        """Build prompt for summary/objective optimization"""
        
        rules_text = "\n".join([f"- {rule}" for rule in optimization_rules])
        keywords_text = ", ".join([kw['skill'] if isinstance(kw, dict) else kw for kw in job_keywords[:15]])
        
        # Extract role titles from experience for context
        roles = [exp.get('role', '') for exp in user_experience[:3]]
        roles_text = ", ".join(filter(None, roles))
        
        # Format user skills for explicit constraint
        user_skills_text = ", ".join(user_skills)
        
        prompt = f"""You are an expert resume optimizer. Rewrite the professional summary to align with a specific job posting.

CRITICAL RULES:
1. DO NOT invent job titles, companies, or qualifications not in the user's background
2. ONLY emphasize relevant aspects of their actual experience
3. ONLY mention skills explicitly found in USER_SKILLS list below - DO NOT mention JD keywords the user does not possess
4. Use keywords from the job description naturally ONLY if they appear in user's skills
5. Keep summary concise (2-4 sentences, 50-80 words)
6. Focus on value proposition for THIS specific role

TARGET JOB DESCRIPTION:
{job_description[:1000]}

KEY KEYWORDS: {keywords_text}

OPTIMIZATION RULES:
{rules_text}

USER'S BACKGROUND:
- Recent Roles: {roles_text}
- Original Summary: {original_summary}
- USER_SKILLS (ONLY use skills from this list): {user_skills_text}

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
        """Parse LLM JSON response with robust error handling for markdown blocks and conversational text"""
        try:
            # Try to find JSON in response (sometimes models add explanatory text)
            response = response.strip()
            
            # Remove markdown code blocks if present (```json ... ``` or ``` ... ```)
            markdown_pattern = r'^```(?:json)?\s*\n?(.+?)\n?```$'
            markdown_match = re.search(markdown_pattern, response, re.DOTALL | re.IGNORECASE)
            if markdown_match:
                response = markdown_match.group(1).strip()
            
            # Fix common JSON escape issues from LLMs
            # LLMs often use backslash for line continuation which is invalid in JSON
            # Replace line-ending backslashes (backslash followed by whitespace/newline)
            response = re.sub(r'\\\s*\n\s*', ' ', response)  # Remove line continuation backslashes
            
            # Note: We don't escape all backslashes here as the JSON might have valid escapes
            # Let json.loads handle validation
            
            # Try simple parse first (fastest path)
            try:
                return json.loads(response)
            except json.JSONDecodeError as e:
                logger.debug(f"Simple parse failed: {e}, trying regex extraction...")
            
            # Extract content between first { and last } using regex to handle nested objects
            # This regex captures everything from the first { to the matching last }
            json_pattern = r'\{[^{}]*(?:\{[^{}]*(?:\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}[^{}]*)*\}[^{}]*)*\}'
            json_matches = re.findall(json_pattern, response, re.DOTALL)
            
            if json_matches:
                # Try to parse the longest match (most likely to be the complete JSON)
                json_matches.sort(key=len, reverse=True)
                logger.debug(f"Found {len(json_matches)} potential JSON objects")
                for idx, json_str in enumerate(json_matches):
                    try:
                        parsed = json.loads(json_str)
                        logger.debug(f"Successfully parsed JSON match #{idx+1}")
                        return parsed
                    except json.JSONDecodeError as e:
                        logger.debug(f"Failed to parse match #{idx+1}: {str(e)}")
                        continue
                        
            # Fallback: try parsing entire response
            return json.loads(response)
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response (first 1000 chars): {response[:1000]}")
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
        """Check that optimized skills are subset/variants of original skills using strict set intersection"""
        # Normalize original skills to create an allowed list
        # This creates a base form by removing common suffixes/prefixes
        def normalize_skill(skill: str) -> set:
            """Create multiple normalized forms of a skill for matching"""
            normalized = skill.lower().strip()
            variants = {normalized}
            
            # Add variant without .js/.py extension
            if normalized.endswith('.js'):
                variants.add(normalized[:-3])
            elif normalized.endswith('.py'):
                variants.add(normalized[:-3])
                
            # Add variant with common extensions
            if not ('.' in normalized or '/' in normalized):
                variants.add(normalized + '.js')
                variants.add(normalized + '.py')
            
            return variants
        
        # Build allowed skill variants from original skills
        allowed_skills = set()
        for skill in original_skills:
            allowed_skills.update(normalize_skill(skill))
        
        # Check each optimized skill exists in allowed set
        for opt_skill in optimized_skills:
            opt_normalized_variants = normalize_skill(opt_skill)
            
            # Check if ANY variant of the optimized skill matches the allowed list
            if not opt_normalized_variants.intersection(allowed_skills):
                logger.warning(f"New skill added (not in original resume): {opt_skill}")
                return False
        
        return True
    
    def _validate_summary_skills(self, optimized_summary: str, user_skills: List[str]) -> Dict[str, Any]:
        """
        Validate that the optimized summary only mentions skills from the user's skills list
        Prevents LLM from hallucinating skills from the job description
        """
        validation = {
            "passed": True,
            "warnings": [],
            "hallucinated_skills": []
        }
        
        if not optimized_summary or not user_skills:
            return validation
        
        # Normalize user skills for comparison
        user_skills_normalized = {skill.lower().strip() for skill in user_skills}
        
        # Common technical skill patterns to check for in summary
        # This is a heuristic approach - looks for skill-like capitalized terms
        summary_lower = optimized_summary.lower()
        
        # Build a comprehensive list of potential skill mentions
        # Check for exact matches and common variants
        potential_skills = [
            "docker", "kubernetes", "ci/cd", "jenkins", "terraform", "ansible",
            "aws", "azure", "gcp", "react", "angular", "vue", "node.js", "django",
            "flask", "spring", "java", "python", "javascript", "typescript",
            "postgresql", "mongodb", "redis", "graphql", "rest api", "microservices",
            "machine learning", "deep learning", "nlp", "computer vision"
        ]
        
        for skill in potential_skills:
            if skill in summary_lower:
                # Check if it's in user's skills (or a variant)
                found = False
                for user_skill in user_skills_normalized:
                    if skill in user_skill or user_skill in skill:
                        found = True
                        break
                
                if not found:
                    validation['hallucinated_skills'].append(skill)
                    validation['passed'] = False
        
        if validation['hallucinated_skills']:
            validation['warnings'].append(
                f"Summary mentions skills not in user's skills list: {', '.join(validation['hallucinated_skills'])}"
            )
            logger.warning(f"Summary skill hallucination detected: {validation['hallucinated_skills']}")
        
        return validation
    
    def _check_metric_placeholders(self, optimized_bullets: List) -> Dict[str, Any]:
        """
        Check if bullets lacking metrics have placeholders like [X%] or [Numerical Metric]
        Enforces STAR method's "Result" component
        """
        validation = {
            "passed": True,
            "warnings": [],
            "bullets_needing_metrics": []
        }
        
        # Patterns that indicate a metric or placeholder
        metric_patterns = [
            r'\d+%',  # Percentage
            r'\$[\d,]+',  # Dollar amount
            r'\d+[xX]',  # Multiplier like 3x
            r'\d+\s*(ms|seconds?|minutes?|hours?|days?|weeks?|months?)',  # Time
            r'\d+[kKmMbB]?\+?\s*(users?|customers?|transactions?|requests?)',  # Volume
            r'\[.*?\]',  # Placeholder bracket
        ]
        
        combined_pattern = '|'.join(metric_patterns)
        metric_regex = re.compile(combined_pattern, re.IGNORECASE)
        
        for idx, bullet in enumerate(optimized_bullets):
            if isinstance(bullet, dict):
                bullet_text = bullet.get('optimized', '')
            else:
                bullet_text = str(bullet)
            
            # Check if bullet has any metric or placeholder
            if not metric_regex.search(bullet_text):
                validation['bullets_needing_metrics'].append({
                    "index": idx,
                    "bullet": bullet_text[:100]  # First 100 chars
                })
                validation['passed'] = False
        
        if validation['bullets_needing_metrics']:
            count = len(validation['bullets_needing_metrics'])
            validation['warnings'].append(
                f"{count} bullet(s) lack measurable results or placeholder metrics"
            )
            logger.warning(f"Metric validation failed: {count} bullets need metrics")
        
        return validation
    
    def _normalize_experience_response(self, result: Dict[str, Any], original_bullets: List[str]) -> Optional[Dict[str, Any]]:
        """
        Attempt to normalize non-standard LLM response formats to expected structure
        Handles cases where LLM returns a single object instead of array
        """
        try:
            # Case 1: LLM returned single bullet object instead of array
            if 'original' in result and 'optimized' in result:
                logger.info("Normalizing: LLM returned single bullet object instead of array")
                return {
                    "optimized_bullets": [
                        {
                            "original": result.get('original', ''),
                            "optimized": result.get('optimized', ''),
                            "reasoning": result.get('reasoning', '')
                        }
                    ]
                }
            
            # Case 2: LLM returned bullets as dict keys (bullet_1, bullet_2, etc.)
            bullet_keys = [k for k in result.keys() if k.startswith('bullet_')]
            if bullet_keys:
                logger.info(f"Normalizing: Found {len(bullet_keys)} bullet_* keys")
                bullets = []
                for key in sorted(bullet_keys):
                    bullet_data = result[key]
                    if isinstance(bullet_data, dict):
                        bullets.append(bullet_data)
                return {"optimized_bullets": bullets}
            
            # Case 3: Check if there's a list anywhere in the response
            for key, value in result.items():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    if 'original' in value[0] or 'optimized' in value[0]:
                        logger.info(f"Normalizing: Found bullet array under key '{key}'")
                        return {"optimized_bullets": value}
            
            logger.error("Could not normalize response - no recognizable bullet structure found")
            return None
            
        except Exception as e:
            logger.error(f"Error normalizing response: {e}")
            return None


# Singleton instance
_huggingface_service = None

def get_huggingface_service() -> HuggingFaceService:
    """Get singleton instance of HuggingFace service"""
    global _huggingface_service
    if _huggingface_service is None:
        _huggingface_service = HuggingFaceService()
    return _huggingface_service