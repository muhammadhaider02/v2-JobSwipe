"""
LLM service with rate limiting for SambaNova API.

Provides JSON-enforced text generation with token bucket rate limiting and retry logic.
"""

import time
import json
from typing import Dict, Optional, Any
from openai import OpenAI, APIError, RateLimitError, APITimeoutError
from config.settings import get_settings


class RateLimiter:
    """Token bucket rate limiter for API calls."""
    
    def __init__(self, calls_per_minute: int, cooldown_seconds: float):
        """
        Initialize rate limiter.
        
        Args:
            calls_per_minute: Maximum calls allowed per minute
            cooldown_seconds: Minimum delay between calls
        """
        self.calls_per_minute = calls_per_minute
        self.cooldown_seconds = cooldown_seconds
        self.last_call_time = 0.0
        self.tokens = float(calls_per_minute)
        self.max_tokens = float(calls_per_minute)
        self.refill_rate = calls_per_minute / 60.0  # Tokens per second
    
    def _refill_tokens(self) -> None:
        """Refill tokens based on time elapsed."""
        now = time.time()
        elapsed = now - self.last_call_time
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_call_time = now
    
    def acquire(self) -> None:
        """
        Acquire token to make API call. Blocks if rate limit reached.
        """
        while True:
            self._refill_tokens()
            
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                
                # Enforce minimum cooldown
                now = time.time()
                time_since_last = now - self.last_call_time
                if time_since_last < self.cooldown_seconds:
                    time.sleep(self.cooldown_seconds - time_since_last)
                
                self.last_call_time = time.time()
                return
            else:
                # Wait until next token available
                wait_time = (1.0 - self.tokens) / self.refill_rate
                print(f"⏳ Rate limit reached. Waiting {wait_time:.1f}s...")
                time.sleep(wait_time)


class LLMService:
    """SambaNova LLM client with rate limiting and JSON enforcement."""
    
    def __init__(self):
        """Initialize LLM client."""
        self.settings = get_settings()
        
        # Initialize OpenAI client (SambaNova-compatible)
        self.client = OpenAI(
            api_key=self.settings.sambanova_api_key,
            base_url=self.settings.sambanova_base_url
        )
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            calls_per_minute=self.settings.rate_limit_calls_per_minute,
            cooldown_seconds=self.settings.rate_limit_cooldown_seconds
        )
        
        print(f"✅ LLM Service initialized: {self.settings.sambanova_model}")
    
    def generate_json(
        self,
        prompt: str,
        schema: Dict[str, Any],
        max_retries: int = 3,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> Optional[Dict]:
        """
        Generate JSON response with enforced schema.
        
        Args:
            prompt: User prompt
            schema: JSON schema for response validation
            max_retries: Maximum retry attempts
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum response tokens
            
        Returns:
            Parsed JSON dictionary or None on failure
        """
        # Build system prompt with schema
        system_prompt = f"""You are a helpful assistant that ALWAYS responds with valid JSON.
Your response must strictly follow this JSON schema:
{json.dumps(schema, indent=2)}

IMPORTANT: 
- Output ONLY valid JSON
- No markdown code blocks
- No additional text
- Follow the schema exactly"""
        
        for attempt in range(max_retries):
            try:
                # Acquire rate limit token
                self.rate_limiter.acquire()
                
                # Make API call
                response = self.client.chat.completions.create(
                    model=self.settings.sambanova_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"}  # Force JSON output
                )
                
                # Parse response
                content = response.choices[0].message.content
                result = json.loads(content)
                
                # Validate against schema (basic validation)
                if self._validate_schema(result, schema):
                    return result
                else:
                    print(f"⚠️  Response doesn't match schema (attempt {attempt + 1})")
                    if attempt == max_retries - 1:
                        return None
                
            except json.JSONDecodeError as e:
                print(f"⚠️  Invalid JSON response (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    return None
            
            except RateLimitError as e:
                print(f"⚠️  Rate limit error (attempt {attempt + 1}): {e}")
                wait_time = 60  # Wait 1 minute
                print(f"   Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            
            except APITimeoutError as e:
                print(f"⚠️  API timeout (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    return None
                time.sleep(2 ** attempt)  # Exponential backoff
            
            except APIError as e:
                print(f"❌ API error (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    return None
                time.sleep(2 ** attempt)  # Exponential backoff
            
            except Exception as e:
                print(f"❌ Unexpected error (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    return None
        
        return None
    
    def _validate_schema(self, data: Dict, schema: Dict) -> bool:
        """
        Basic schema validation.
        
        Args:
            data: Data to validate
            schema: JSON schema
            
        Returns:
            True if data matches schema structure
        """
        if "properties" not in schema:
            return True
        
        # Check all required properties exist
        required = schema.get("required", [])
        for prop in required:
            if prop not in data:
                return False
        
        # Check all properties in data are defined in schema
        for key in data.keys():
            if key not in schema["properties"]:
                return False
        
        return True
    
    def generate_reasoning(
        self,
        user_skills: list[str],
        job_skills: list[str],
        job_title: str,
        match_score: float,
        experience_years: int = 0
    ) -> Optional[Dict]:
        """
        Generate reasoning for job fit.
        
        Args:
            user_skills: User's skills
            job_skills: Job's required skills
            job_title: Job title
            match_score: Skill match score (0-1)
            experience_years: User's years of experience
            
        Returns:
            Dictionary with reasoning and confidence
        """
        skill_gaps = [s for s in job_skills if s not in user_skills]
        matching_skills = [s for s in job_skills if s in user_skills]
        
        prompt = f"""Analyze this job fit:

Job Title: {job_title}
Match Score: {match_score:.1%}
User Experience: {experience_years} years

Matching Skills: {', '.join(matching_skills) if matching_skills else 'None'}
Missing Skills: {', '.join(skill_gaps) if skill_gaps else 'None'}

Explain in 2-3 sentences why this is a good/borderline/poor fit. 
Highlight transferable skills and growth potential if applicable."""
        
        schema = {
            "type": "object",
            "properties": {
                "reasoning": {"type": "string"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "recommendation": {"type": "string", "enum": ["strong_fit", "moderate_fit", "weak_fit"]}
            },
            "required": ["reasoning", "confidence", "recommendation"]
        }
        
        return self.generate_json(prompt, schema, max_tokens=300)
    
    def generate_cover_letter(
        self,
        user_profile: Dict,
        job_description: str,
        job_title: str,
        company: str
    ) -> Optional[str]:
        """
        Generate tailored cover letter.
        
        Args:
            user_profile: User profile dictionary
            job_description: Job description text
            job_title: Job title
            company: Company name
            
        Returns:
            Cover letter text or None
        """
        user_summary = user_profile.get('summary', '')
        user_skills = ', '.join(user_profile.get('skills', [])[:10])
        
        prompt = f"""Write a professional cover letter for this job application:

Job Title: {job_title}
Company: {company}

User Background:
{user_summary}

Key Skills: {user_skills}

Job Requirements:
{job_description[:500]}

Write a concise, compelling cover letter (200-250 words) that:
1. Shows enthusiasm for the role
2. Highlights relevant experience
3. Connects user skills to job requirements
4. Demonstrates knowledge of the company (if applicable)"""
        
        schema = {
            "type": "object",
            "properties": {
                "cover_letter": {"type": "string"},
                "key_points": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["cover_letter"]
        }
        
        result = self.generate_json(prompt, schema, max_tokens=800)
        return result['cover_letter'] if result else None


# Global service instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """
    Get or create global LLM service instance.
    
    Returns:
        LLMService instance
    """
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
