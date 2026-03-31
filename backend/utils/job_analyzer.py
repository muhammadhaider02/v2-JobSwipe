"""
Job Analyzer: Extract structured context from job descriptions.

Extracts company information, critical skills, requirements, and cultural signals
to enhance resume/cover letter tailoring with job-specific context.
"""

import re
from typing import Dict, Any, List, Optional, Set
from collections import Counter


class JobAnalyzer:
    """
    Analyzes job descriptions to extract actionable context for personalization.
    """
    
    # Keywords indicating critical/required skills vs nice-to-have
    CRITICAL_KEYWORDS = [
        "required", "must have", "must-have", "essential", "mandatory",
        "critical", "necessary", "needed", "expects", "demands"
    ]
    
    NICE_TO_HAVE_KEYWORDS = [
        "preferred", "nice to have", "nice-to-have", "bonus", "plus",
        "desirable", "optional", "helpful", "beneficial", "advantage"
    ]
    
    # Company culture indicators
    CULTURE_KEYWORDS = {
        "innovative": ["innovative", "cutting-edge", "pioneering", "forward-thinking", "disruptive"],
        "collaborative": ["collaborative", "team-player", "teamwork", "cross-functional", "cooperation"],
        "fast-paced": ["fast-paced", "dynamic", "agile", "startup", "rapidly growing"],
        "flexible": ["flexible", "remote", "work-life balance", "hybrid", "autonomous"],
        "growth-oriented": ["growth", "learning", "development", "mentorship", "career advancement"],
        "data-driven": ["data-driven", "metrics", "analytical", "measurement", "insights"],
        "customer-focused": ["customer", "client", "user-centric", "customer-first", "satisfaction"]
    }
    
    # Seniority level indicators
    SENIORITY_PATTERNS = {
        "intern": r"\b(intern|internship|trainee)\b",
        "junior": r"\b(junior|jr|entry[-\s]level|graduate|associate)\b",
        "mid": r"\b(mid[-\s]level|intermediate|engineer|developer)\b",
        "senior": r"\b(senior|sr|experienced|lead|principal)\b",
        "lead": r"\b(lead|principal|staff|architect|director|head|manager)\b"
    }
    
    def __init__(self):
        """Initialize job analyzer."""
        pass
    
    def analyze_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform comprehensive job analysis.
        
        Args:
            job_data: Job dictionary with title, company, description, skills, etc.
            
        Returns:
            Analysis dict with extracted context:
            {
                "company_name": str,
                "job_title": str,
                "seniority_level": str,
                "critical_skills": List[str],
                "nice_to_have_skills": List[str],
                "culture_signals": Dict[str, List[str]],
                "key_requirements": List[str],
                "key_responsibilities": List[str],
                "keywords": List[str],  # Top keywords for optimization
                "context_summary": str  # Human-readable summary
            }
        """
        
        # Support both database column names and normalized names
        description = job_data.get("job_description") or job_data.get("description", "")
        title = job_data.get("job_title") or job_data.get("title", "")
        company = job_data.get("company", "Unknown Company")
        skills = job_data.get("skills_required") or job_data.get("skills", [])
        
        # Extract components
        company_name = self._clean_company_name(company)
        seniority = self._detect_seniority(title, description)
        critical_skills, nice_to_have_skills = self._categorize_skills(description, skills)
        culture_signals = self._detect_culture(description)
        requirements = self._extract_requirements(description)
        responsibilities = self._extract_responsibilities(description)
        keywords = self._extract_keywords(description, title, skills)
        
        # Generate context summary
        context_summary = self._generate_context_summary(
            company_name, title, seniority, critical_skills, culture_signals
        )
        
        return {
            "company_name": company_name,
            "job_title": title,
            "seniority_level": seniority,
            "critical_skills": critical_skills[:10],  # Top 10 critical
            "nice_to_have_skills": nice_to_have_skills[:5],  # Top 5 optional
            "culture_signals": culture_signals,
            "key_requirements": requirements[:5],  # Top 5 requirements
            "key_responsibilities": responsibilities[:5],  # Top 5 responsibilities
            "keywords": keywords[:15],  # Top 15 keywords for optimization
            "context_summary": context_summary
        }
    
    def _clean_company_name(self, company: str) -> str:
        """Clean company name (remove suffixes like Inc., Ltd.)."""
        if not company:
            return "Unknown Company"
        
        company = company.strip()
        # Remove common suffixes
        suffixes = [", Inc.", " Inc.", ", LLC", " LLC", ", Ltd.", " Ltd.", " Corporation", " Corp."]
        for suffix in suffixes:
            if company.endswith(suffix):
                company = company[:-len(suffix)]
        return company.strip()
    
    def _detect_seniority(self, title: str, description: str) -> str:
        """
        Detect seniority level from title and description.
        
        Returns:
            "intern" | "junior" | "mid" | "senior" | "lead"
        """
        text = (title + " " + description).lower()
        
        # Check patterns in priority order (most specific first)
        for level in ["lead", "senior", "mid", "junior", "intern"]:
            pattern = self.SENIORITY_PATTERNS[level]
            if re.search(pattern, text, re.IGNORECASE):
                return level
        
        # Default to mid if no clear indicators
        return "mid"
    
    def _categorize_skills(
        self, description: str, skills: List[str]
    ) -> tuple[List[str], List[str]]:
        """
        Categorize skills into critical vs nice-to-have.
        
        Since skills come from database's skills_required column, 
        they are already vetted as required skills.
        
        Args:
            description: Job description text (not used)
            skills: List of skill tags from database
            
        Returns:
            (critical_skills, nice_to_have_skills)
        """
        # Skills from database are already required/critical
        # Return them all as critical skills
        critical_skills = skills if skills else []
        nice_to_have_skills = []
        
        return critical_skills, nice_to_have_skills
    
    def _detect_culture(self, description: str) -> Dict[str, List[str]]:
        """
        Detect company culture signals from description.
        
        Returns:
            Dict mapping culture type to matching keywords found
        """
        description_lower = description.lower()
        detected_cultures = {}
        
        for culture_type, keywords in self.CULTURE_KEYWORDS.items():
            found_keywords = [kw for kw in keywords if kw in description_lower]
            if found_keywords:
                detected_cultures[culture_type] = found_keywords
        
        return detected_cultures
    
    def _extract_requirements(self, description: str) -> List[str]:
        """
        Extract key requirements from description.
        
        Looks for sections like "Requirements:", "Qualifications:", etc.
        """
        requirements = []
        
        # Common section headers
        req_patterns = [
            r"(?:requirements|qualifications|prerequisite|you have|you bring)[\s:]+(.+?)(?=\n\n|\Z)",
            r"(?:what we're looking for|what you'll need|minimum requirements)[\s:]+(.+?)(?=\n\n|\Z)"
        ]
        
        for pattern in req_patterns:
            matches = re.findall(pattern, description, re.IGNORECASE | re.DOTALL)
            for match in matches:
                # Split by bullets or newlines (avoid splitting hyphenated words)
                items = re.split(r'\n+|(?:\s+[•\*\-]\s+)', match)
                items = [item.strip(" -*•\t\n") for item in items if item.strip(" -*•\t\n")]
                requirements.extend(items[:5])  # Take first 5 from this section
        
        # Deduplicate while preserving order
        seen = set()
        requirements = [x for x in requirements if not (x in seen or seen.add(x))]
        
        return requirements
    
    def _extract_responsibilities(self, description: str) -> List[str]:
        """
        Extract key responsibilities from description.
        
        Looks for sections like "Responsibilities:", "You will:", etc.
        """
        responsibilities = []
        
        # Common section headers
        resp_patterns = [
            r"(?:responsibilities|duties|you will|role description|what you'll do)[\s:]+(.+?)(?=\n\n|\Z)"
        ]
        
        for pattern in resp_patterns:
            matches = re.findall(pattern, description, re.IGNORECASE | re.DOTALL)
            for match in matches:
                # Split by bullets or newlines (avoid splitting hyphenated words)
                items = re.split(r'\n+|(?:\s+[•\*\-]\s+)', match)
                items = [item.strip(" -*•\t\n") for item in items if item.strip(" -*•\t\n")]
                responsibilities.extend(items[:5])
        
        # Deduplicate
        seen = set()
        responsibilities = [x for x in responsibilities if not (x in seen or seen.add(x))]
        
        return responsibilities
    
    def _extract_keywords(
        self, description: str, title: str, skills: List[str]
    ) -> List[str]:
        """
        Extract top keywords for optimization context.
        
        Returns keywords sorted by relevance/frequency.
        """
        # Combine all text
        text = f"{title} {description}"
        
        # Add skills as high-priority keywords
        keywords = set(skill.lower() for skill in skills)
        
        # Extract additional keywords from description (nouns, tech terms)
        # Simple approach: find capitalized words and common tech terms
        tech_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*|[A-Z]{2,}|\w+\+{1,2}|\.NET)\b'
        tech_matches = re.findall(tech_pattern, description)
        
        # Count frequency
        counter = Counter(tech_matches)
        
        # Add top frequent terms
        for term, count in counter.most_common(20):
            if count > 1 and len(term) > 2:  # Mentioned multiple times
                keywords.add(term.lower())
        
        # Also extract from title
        title_words = [w.lower() for w in title.split() if len(w) > 3]
        keywords.update(title_words)
        
        return list(keywords)
    
    def _generate_context_summary(
        self,
        company: str,
        title: str,
        seniority: str,
        critical_skills: List[str],
        culture_signals: Dict[str, List[str]]
    ) -> str:
        """
        Generate human-readable context summary for prompt augmentation.
        
        Returns:
            Multi-line summary string suitable for prompt injection
        """
        summary_parts = []
        
        # Company and role
        summary_parts.append(f"Target Role: {title} at {company}")
        summary_parts.append(f"Seniority Level: {seniority.capitalize()}")
        
        # Critical skills
        if critical_skills:
            skills_str = ", ".join(critical_skills[:5])
            summary_parts.append(f"Critical Skills Required: {skills_str}")
        
        # Culture signals
        if culture_signals:
            cultures = []
            for culture_type, keywords in culture_signals.items():
                cultures.append(culture_type.replace("_", " ").title())
            culture_str = ", ".join(cultures)
            summary_parts.append(f"Company Culture: {culture_str}")
        
        return "\n".join(summary_parts)
    
    def get_optimization_hints(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate optimization hints for RAG prompt injection.
        
        Args:
            analysis: Output from analyze_job()
            
        Returns:
            Dict with hints for resume/cover letter optimization:
            {
                "resume_hints": str,  # Guidance for resume optimization
                "cover_letter_hints": str,  # Guidance for cover letter
                "priority_keywords": List[str]  # Keywords to emphasize
            }
        """
        critical_skills = analysis.get("critical_skills", [])
        culture_signals = analysis.get("culture_signals", {})
        seniority = analysis.get("seniority_level", "mid")
        
        # Resume hints
        resume_hints = []
        if critical_skills:
            resume_hints.append(
                f"Emphasize these critical skills: {', '.join(critical_skills[:5])}"
            )
        if seniority in ["senior", "lead"]:
            resume_hints.append("Highlight leadership, mentorship, and strategic contributions")
        elif seniority in ["junior", "intern"]:
            resume_hints.append("Emphasize learning agility, academic projects, and growth potential")
        
        # Cover letter hints
        cover_letter_hints = []
        if "innovative" in culture_signals:
            cover_letter_hints.append("Mention innovative projects or creative problem-solving")
        if "collaborative" in culture_signals:
            cover_letter_hints.append("Emphasize teamwork and cross-functional collaboration")
        if "fast-paced" in culture_signals:
            cover_letter_hints.append("Demonstrate adaptability and ability to deliver under pressure")
        
        return {
            "resume_hints": " | ".join(resume_hints) if resume_hints else "Focus on relevant experience and skills",
            "cover_letter_hints": " | ".join(cover_letter_hints) if cover_letter_hints else "Express genuine interest and cultural fit",
            "priority_keywords": critical_skills[:10]
        }
