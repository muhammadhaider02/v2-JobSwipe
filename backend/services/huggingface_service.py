"""
HuggingFace Inference API Service
Handles LLM-based resume optimization using Hugging Face Serverless Inference API
"""
import os
import json
import logging
import re
import time
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
            
            response = None
            last_error = None
            for attempt in range(1, 4):
                try:
                    response = self.client.chat_completion(
                        messages=messages,
                        model=self.model_id,
                        max_tokens=2048,
                        temperature=0.1,
                        top_p=0.95
                    )
                    break
                except Exception as e:
                    last_error = e
                    err_text = str(e).lower()
                    is_transient = (
                        "500" in err_text
                        or "503" in err_text
                        or "internal server error" in err_text
                        or "temporarily unavailable" in err_text
                    )
                    if attempt < 3 and is_transient:
                        backoff = attempt
                        logger.warning(
                            f"Summary optimization transient provider error (attempt {attempt}/3). "
                            f"Retrying in {backoff}s..."
                        )
                        time.sleep(backoff)
                        continue
                    raise

            if response is None:
                raise RuntimeError(f"Summary optimization failed after retries: {last_error}")
            
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
            
            # Apply enforcement: add placeholders and trim length if needed
            enforced_result = self._enforce_optimization_rules(
                original_bullets,
                result.get('optimized_bullets', [])
            )
            
            result['optimized_bullets'] = enforced_result['bullets']
            
            # Re-validate after enforcement
            metric_validation_after = self._check_metric_placeholders(result['optimized_bullets'])

            # Hard safety check: optimized bullets must not introduce new concrete numeric facts.
            numeric_fact_validation = self._validate_no_new_numeric_facts(
                original_bullets=original_bullets,
                optimized_bullets=result['optimized_bullets']
            )

            # Revert violating bullets to exact original text.
            reverted_due_to_hallucination = 0
            if not numeric_fact_validation.get('passed', True):
                violating_indices = set(numeric_fact_validation.get('violating_indices', []))
                reverted_bullets = []
                for idx, bullet in enumerate(result['optimized_bullets']):
                    if idx in violating_indices and isinstance(bullet, dict):
                        reverted_due_to_hallucination += 1
                        reverted_bullets.append({
                            'original': bullet.get('original', original_bullets[idx] if idx < len(original_bullets) else ''),
                            'optimized': original_bullets[idx] if idx < len(original_bullets) else bullet.get('original', ''),
                            'reasoning': (bullet.get('reasoning', '') + ' | Reverted: introduced unsupported numeric claim').strip()
                        })
                    else:
                        reverted_bullets.append(bullet)
                result['optimized_bullets'] = reverted_bullets
            
            # Combine validations
            validation_result['metric_check'] = metric_validation_after
            validation_result['numeric_fact_check'] = {
                "passed": numeric_fact_validation.get("passed", True),
                "unsupported_numeric_facts": numeric_fact_validation.get("new_numeric_facts", []),
                "violating_indices": numeric_fact_validation.get("violating_indices", [])
            }
            validation_result['enforcement_applied'] = {
                "placeholders_added": enforced_result['placeholders_added'],
                "bullets_reverted": enforced_result['bullets_reverted'],
                "reverted_due_to_hallucination": reverted_due_to_hallucination
            }
            
            # Update warnings to reflect enforcement
            if enforced_result['placeholders_added'] > 0:
                validation_result['warnings'].append(
                    f"Added {enforced_result['placeholders_added']} editable metric placeholder(s) for bullets lacking quantifiable results"
                )
                logger.info(f"✓ Enforcement: Added {enforced_result['placeholders_added']} editable placeholders")
                
            if enforced_result['bullets_reverted'] > 0:
                validation_result['warnings'].append(
                    f"Reverted {enforced_result['bullets_reverted']} overly verbose bullet(s) to original wording"
                )
                logger.info(f"✓ Enforcement: Reverted {enforced_result['bullets_reverted']} bullets to original")

            if reverted_due_to_hallucination > 0:
                validation_result['warnings'].append(
                    f"Reverted {reverted_due_to_hallucination} bullet(s) due to unsupported numeric claims"
                )
                validation_result['unsupported_fact_detected'] = True
            else:
                validation_result['unsupported_fact_detected'] = False

            validation_result['new_metric_detected'] = not numeric_fact_validation.get('passed', True)
            validation_result['reverted_due_to_hallucination'] = reverted_due_to_hallucination > 0
            
            # Override validation to pass if enforcement successfully addressed issues
            if enforced_result['placeholders_added'] > 0:
                validation_result['passed'] = True
                validation_result['note'] = 'Validation passed after automatic enforcement'
            
            if not metric_validation_after['passed']:
                # Should not happen after enforcement, but log if it does
                validation_result['warnings'].extend(metric_validation_after['warnings'])
            
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

            # Also ensure no unsupported numeric claims are introduced in summary.
            source_summary_facts = " ".join([
                str(original_summary or ""),
                " ".join([str(s) for s in (user_skills or [])]),
                " ".join([
                    str(exp.get('description', ''))
                    for exp in (user_experience or [])
                    if isinstance(exp, dict)
                ])
            ])
            new_numeric_facts = self._find_new_numeric_facts(
                source_text=source_summary_facts,
                candidate_text=result.get('optimized_summary', '')
            )
            if new_numeric_facts:
                result['validation']['passed'] = False
                result['validation'].setdefault('warnings', []).append(
                    "Summary introduced unsupported numeric facts; reverted to original summary"
                )
                result['validation']['unsupported_numeric_facts'] = sorted(list(new_numeric_facts))
                result['validation']['new_metric_detected'] = True
                result['validation']['unsupported_fact_detected'] = True
                result['optimized_summary'] = original_summary
            else:
                result['validation']['new_metric_detected'] = False
                result['validation']['unsupported_fact_detected'] = False
            
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

CRITICAL RULES (FOLLOW EXACTLY OR OUTPUT WILL BE REJECTED):
1. FACTUAL ACCURACY: DO NOT add achievements, projects, metrics, or dates not in the original bullets.
2. PRESERVE MEANING: Keep the core meaning and key details of the original. Only improve word choice.
3. CONCISENESS IS MANDATORY: 
   - Maximum 30% length increase (e.g., 10 chars → max 13 chars, 20 chars → max 26 chars)
   - If you cannot improve within this limit, return the EXACT original wording
   - Examples:
     ✅ "Fixed bugs" → "Resolved bugs" (10→13 chars = 30% ✓)
     ❌ "Fixed bugs" → "Identified and resolved critical bugs" (10→37 chars = 270% ✗)
     ✅ "Built features for product" → "Built core product features" (26→27 chars ✓)
4. MINIMAL CHANGES: Change 1-2 words maximum. Stronger verb + remove filler words ('the', 'and', 'very').
5. NO METRICS NEEDED: Don't add [brackets] or metrics - system handles that automatically.
6. JSON ONLY: Return ONLY valid JSON.

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

CRITICAL RULES (VIOLATIONS WILL BE REJECTED):
1. ABSOLUTE PROHIBITION: DO NOT add ANY new skills. You can ONLY: reorder, rename (React → React.js), or remove skills from the original list.
2. If a JD keyword is NOT in the original skills list, IGNORE IT COMPLETELY. Do not add it.
3. Example VIOLATIONS that will be rejected:
   - Original: ["Python", "React"] → Optimized: ["Python", "React", "Django"] ❌ REJECTED (added Django)
   - Original: ["JavaScript"] → Optimized: ["JavaScript", "Node.js"] ❌ REJECTED (added Node.js)
4. Example ACCEPTABLE changes:
   - Original: ["React", "Python"] → Optimized: ["Python", "React.js", "JavaScript"] ✓ (only if JavaScript was in original)
5. When in doubt, keep the original skills list unchanged.

TARGET JOB DESCRIPTION:
{job_description[:1000]}

REQUIRED KEYWORDS FROM JD: {keywords_text}

OPTIMIZATION RULES:
{rules_text}

ORIGINAL SKILLS (THIS IS YOUR ONLY SOURCE - DO NOT ADD ANYTHING NOT HERE):
{skills_text}

YOUR TASK:
Reorder and refine ONLY the skills above. Do NOT add skills from the JD that aren't in the original list.

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

CRITICAL RULES (VIOLATIONS WILL BE REJECTED):
1. ABSOLUTE PROHIBITION: DO NOT mention ANY technical skills or tools not in the USER_SKILLS list below
2. DO NOT invent job titles, companies, years of experience, or qualifications
3. Example VIOLATIONS that will be rejected:
   - USER_SKILLS: ["Python", "React"] → Summary mentions "Docker" or "AWS" ❌ REJECTED
   - USER_SKILLS: ["JavaScript"] → Summary mentions "TypeScript" or "Node.js" ❌ REJECTED
   - Original: "2 years experience" → Summary says "5+ years" ❌ REJECTED
4. ONLY emphasize relevant aspects of actual experience
5. Keep summary SHORT: 2-3 sentences maximum, 40-60 words

TARGET JOB DESCRIPTION:
{job_description[:1000]}

KEY KEYWORDS: {keywords_text}

OPTIMIZATION RULES:
{rules_text}

USER'S BACKGROUND:
- Recent Roles: {roles_text}
- Original Summary: {original_summary}

USER_SKILLS (ONLY MENTION THESE SKILLS - NOTHING ELSE):
{user_skills_text}

YOUR TASK:
Rewrite the summary using ONLY the skills from USER_SKILLS above. Do NOT use JD keywords that aren't in USER_SKILLS.

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

    def _extract_numeric_facts(self, text: str) -> set:
        """Extract concrete numeric claims, excluding placeholders like [X%]."""
        sanitized = re.sub(r'\[[^\]]*\]', ' ', str(text))
        patterns = [
            r'\b(?:19|20)\d{2}\b',
            r'\b\d+(?:\.\d+)?%\b',
            r'\$\s*\d[\d,]*(?:\.\d+)?(?:[kKmMbB])?',
            r'\b\d+(?:\.\d+)?\s*(?:ms|seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b',
            r'\b\d+(?:\.\d+)?\+?\s*(?:users?|customers?|transactions?|requests?|engineers?|projects?)\b',
            r'\b\d+[xX]\b'
        ]
        facts = set()
        for pattern in patterns:
            for match in re.findall(pattern, sanitized, re.IGNORECASE):
                facts.add(str(match).strip().lower())
        return facts

    def _find_new_numeric_facts(self, source_text: str, candidate_text: str) -> set:
        source_facts = self._extract_numeric_facts(source_text)
        candidate_facts = self._extract_numeric_facts(candidate_text)
        return {f for f in candidate_facts if f not in source_facts}

    def _validate_no_new_numeric_facts(self, original_bullets: List[str], optimized_bullets: List[Dict[str, str]]) -> Dict[str, Any]:
        """Validate each optimized bullet against the corresponding original bullet."""
        validation = {
            "passed": True,
            "new_numeric_facts": [],
            "violating_indices": []
        }

        for idx, bullet in enumerate(optimized_bullets):
            if not isinstance(bullet, dict):
                continue
            source_text = original_bullets[idx] if idx < len(original_bullets) else bullet.get('original', '')
            candidate_text = bullet.get('optimized', '')
            new_facts = self._find_new_numeric_facts(source_text, candidate_text)
            if new_facts:
                validation['passed'] = False
                validation['violating_indices'].append(idx)
                validation['new_numeric_facts'].extend(sorted(list(new_facts)))

        validation['new_numeric_facts'] = sorted(list(set(validation['new_numeric_facts'])))
        return validation
    
    def _check_no_new_skills(self, original_skills: List[str], optimized_skills: List[str]) -> bool:
        """Check that optimized skills are subset/variants of original skills."""

        alias_map = {
            "ml": "machine learning",
            "machine learning": "machine learning",
            "dl": "deep learning",
            "nlp": "nlp",
            "ai": "artificial intelligence",
            "postgres": "postgresql",
            "node": "node.js",
            "js": "javascript",
            "ts": "typescript",
        }

        def split_skill_tokens(skill: str) -> List[str]:
            normalized = str(skill).lower().strip()
            if not normalized:
                return []
            # Split composite labels: "Languages & Libraries: Python" -> ["languages", "libraries", "python"]
            parts = re.split(r'[:/,|]|\band\b|\&', normalized)
            tokens = [p.strip() for p in parts if p.strip()]
            return [t for t in tokens if len(t) > 1]

        def normalize_variants(skill: str) -> set:
            variants = set()
            base = str(skill).lower().strip()
            if not base:
                return variants

            # Include full text and tokenized atoms
            variants.add(base)
            for token in split_skill_tokens(base):
                variants.add(token)

            # Extensions / canonical forms
            snapshot = list(variants)
            for item in snapshot:
                if item.endswith('.js'):
                    variants.add(item[:-3])
                elif item.endswith('.py'):
                    variants.add(item[:-3])
                if item in alias_map:
                    variants.add(alias_map[item])

            return variants

        allowed_skills = set()
        for skill in original_skills:
            allowed_skills.update(normalize_variants(skill))

        for opt_skill in optimized_skills:
            opt_variants = normalize_variants(opt_skill)
            if not opt_variants.intersection(allowed_skills):
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
        
        alias_map = {
            "ml": "machine learning",
            "machine learning": "machine learning",
            "dl": "deep learning",
            "nlp": "nlp",
            "ai": "artificial intelligence",
            "postgres": "postgresql",
        }

        def normalize_with_aliases(skill: str) -> set:
            raw = str(skill).lower().strip()
            if not raw:
                return set()
            values = {raw}
            parts = re.split(r'[:/,|]|\band\b|\&', raw)
            values.update({p.strip() for p in parts if p.strip()})
            expanded = set(values)
            for v in values:
                if v in alias_map:
                    expanded.add(alias_map[v])
            return {v for v in expanded if len(v) > 1}

        # Normalize user skills for comparison, including aliases and tokenized composites
        user_skills_normalized = set()
        for skill in user_skills:
            user_skills_normalized.update(normalize_with_aliases(skill))
        
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
    
    def _enforce_optimization_rules(
        self,
        original_bullets: List[str],
        optimized_bullets: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Post-process optimized bullets to enforce STAR method and length constraints.
        
        ENFORCEMENT RULES:
        1. Length Validation (BEFORE adding placeholders):
           - If optimized bullet exceeds 30% length increase: REVERT to original bullet
           - This prevents verbose, buzzword-filled optimizations
           - Ensures bullets remain concise and readable
           - Example: "Fixed bugs" → "Identified and resolved bugs with systematic approach" 
             (too long) → REVERTED to "Fixed bugs"
           
        2. Metric Placeholders (applied to optimized OR reverted bullet):
           - Only added if ORIGINAL bullet lacks metrics (doesn't replace existing metrics)
           - Contextual placeholders based on bullet content: [X%], [X minutes], [$X], etc.
           - Marked with ⚠️ in reasoning for frontend to highlight as user-editable
           - Example: "Fixed bugs" → "Fixed bugs [quantify result]"
        
        Args:
            original_bullets: Original unoptimized bullets
            optimized_bullets: LLM-optimized bullets (may violate rules)
            
        Returns:
            Dict with:
            - bullets: Enforced bullet list (user-editable)
            - placeholders_added: Count of placeholders added
            - bullets_reverted: Count of bullets reverted to original due to excessive length
        """
        if not optimized_bullets or not isinstance(optimized_bullets[0], dict):
            return {
                'bullets': optimized_bullets,
                'placeholders_added': 0,
                'bullets_reverted': 0
            }
        
        # Patterns that indicate a metric
        metric_patterns = [
            r'\d+%',
            r'\$[\d,]+',
            r'\d+[xX]',
            r'\d+\s*(ms|seconds?|minutes?|hours?|days?|weeks?|months?)',
            r'\d+[kKmMbB]?\+?\s*(users?|customers?|transactions?|requests?)',
            r'\[.*?\]',  # Existing placeholders
        ]
        combined_pattern = '|'.join(metric_patterns)
        metric_regex = re.compile(combined_pattern, re.IGNORECASE)
        
        enforced_bullets = []
        bullets_reverted = 0
        placeholders_added = 0
        
        for idx, bullet_data in enumerate(optimized_bullets):
            original_text = bullet_data.get('original', '')
            optimized_text = bullet_data.get('optimized', '')
            reasoning = bullet_data.get('reasoning', '')
            
            # Get corresponding original bullet
            if idx < len(original_bullets):
                original_bullet = original_bullets[idx]
            else:
                original_bullet = original_text
            
            # Check if original has metrics
            original_has_metric = bool(metric_regex.search(original_bullet))
            optimized_has_metric = bool(metric_regex.search(optimized_text))
            
            # Determine which placeholder to add based on content
            placeholder_to_add = None
            if not original_has_metric and not optimized_has_metric:
                text_lower = optimized_text.lower()
                
                # Check for improvement/optimization keywords (handle word variations)
                if any(re.search(r'\b' + word, text_lower) for word in ['reduc', 'decreas', 'improv', 'increas', 'enhanc', 'optimi', 'boost', 'elevat']):
                    placeholder_to_add = ' by [X%]'
                # Check for time/speed keywords
                elif any(re.search(r'\b' + word, text_lower) for word in ['time', 'speed', 'perform', 'latenc', 'faster', 'quick', 'efficien']):
                    placeholder_to_add = ' to [X minutes/hours]'
                # Check for user/customer keywords
                elif re.search(r'\b(users?|customers?|clients?)\b', text_lower):
                    placeholder_to_add = ' for [X] users'
                # Check for financial keywords
                elif re.search(r'\b(revenue|sales|cost|sav|profit|budget)\b', text_lower):
                    placeholder_to_add = ' saving [$X]'
                # Check for team collaboration keywords
                elif re.search(r'\b(team|engineers?|developers?|collaborat|led|manag)\b', text_lower):
                    placeholder_to_add = ' with [X] team members'
                # Check for database/query keywords
                elif re.search(r'\b(database|query|queries|schema|index)\b', text_lower):
                    placeholder_to_add = ' reducing query time by [X%]'
                else:
                    # Last resort - add generic placeholder
                    placeholder_to_add = ' [quantify result]'
            
            # Rule 1: Length validation before adding placeholder
            # Check if optimized version (before placeholder) is too verbose
            original_len = len(original_bullet)
            max_allowed_len = int(original_len * 1.3)  # 30% max increase
            
            # If optimized is too long, revert to original
            if len(optimized_text) > max_allowed_len:
                logger.info(f"Bullet {idx+1} too verbose ({len(optimized_text)} chars vs original {original_len}), reverting to original")
                optimized_text = original_bullet
                reasoning = f"LLM output too verbose, kept original | {reasoning}"
                bullets_reverted += 1
            
            # Rule 2: Add placeholder if needed (to either optimized or reverted bullet)
            if placeholder_to_add:
                optimized_text += placeholder_to_add
                reasoning += ' | ⚠️ Added editable placeholder - replace [brackets] with actual numbers'
                placeholders_added += 1
                logger.info(f"Added contextual metric placeholder to bullet {idx+1}")
            
            enforced_bullets.append({
                'original': original_text,
                'optimized': optimized_text,
                'reasoning': reasoning
            })
        
        logger.info(f"Enforcement complete: {placeholders_added} placeholders added, {bullets_reverted} bullets reverted to original")
        
        return {
            'bullets': enforced_bullets,
            'placeholders_added': placeholders_added,
            'bullets_reverted': bullets_reverted
        }
    
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