# services/cover_letter_service.py
"""Service for generating cover letters from templates.
It fetches user profile and job details from Supabase and replaces placeholders
in the selected template. Missing data is replaced with an empty string.
"""

import os
import re
from typing import Dict, Any
from .supabase_service import SupabaseService
from utils.job_analyzer import JobAnalyzer

class CoverLetterService:
    """Generate personalized cover letters.

    Placeholders in templates should be in the form ``{{field}}`` where *field*
    corresponds to a key in the user profile or job dictionary. Example:
    ``{{name}}``, ``{{email}}``, ``{{job_title}}``.
    """

    TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "uploads", "cover-letter-templates")

    def __init__(self, supabase_service: SupabaseService | None = None):
        # Allow injection of a mock SupabaseService for testing.
        # Use service_role to bypass RLS policies when fetching user profiles
        self.supabase = supabase_service or SupabaseService()

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def generate_cover_letter(self, user_id: str, job_id: str, template_name: str) -> str:
        """Generate a cover letter.

        Args:
            user_id: The ``user_id`` column from ``user_profiles``.
            job_id: The ``job_id`` column from ``jobs``.
            template_name: Filename of the template located in ``uploads/cover-letter-templates``.
        Returns:
            Rendered cover letter string.
        Raises:
            FileNotFoundError: If the template file does not exist.
            Exception: Propagates any Supabase errors.
        """
        # Fetch data
        user_profile = self.supabase.get_user_profile(user_id)
        job = self.supabase.get_job_by_id(job_id)
        # If the job is not found, use an empty dict so placeholder replacement works without error
        if job is None:
            job = {}
        # Render
        return self._render_template(template_name, user_profile, job)

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    def _render_template(self, template_name: str, user_profile: Dict[str, Any], job: Dict[str, Any]) -> str:
        """Load the template file and replace placeholders.

        Missing keys are replaced with an empty string. List‑type fields are joined
        with commas.
        """
        template_path = os.path.join(self.TEMPLATE_DIR, template_name)
        if not os.path.isfile(template_path):
            raise FileNotFoundError(f"Template '{template_name}' not found in {self.TEMPLATE_DIR}")
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Build a flat mapping of placeholders to values.
        data_map: Dict[str, str] = {}
        # User profile fields
        for key, value in user_profile.items():
            if isinstance(value, list):
                data_map[key] = ", ".join(map(str, value))
            else:
                data_map[key] = str(value) if value is not None else ""
        # Job fields – use raw keys (no prefix)
        for key, value in job.items():
            if isinstance(value, list):
                data_map[key] = ", ".join(map(str, value))
            else:
                data_map[key] = str(value) if value is not None else ""
        # Additional placeholder mappings expected in templates
        # Full name
        data_map["FULL_NAME"] = data_map.get("name", "")
        data_map["EMAIL"] = data_map.get("email", "")
        data_map["PHONE"] = data_map.get("phone", "")
        data_map["LINKEDIN"] = data_map.get("linkedin", "")
        data_map["CITY_COUNTRY"] = data_map.get("location", "")
        
        # Portfolio fallback logic
        portfolio_link = data_map.get("portfolio", "") or data_map.get("github", "")
        if portfolio_link:
            data_map["PORTFOLIO"] = f"{portfolio_link}"
        else:
            data_map["PORTFOLIO"] = "my portfolio"
            
        # Current date in a readable format
        from datetime import datetime
        data_map["DATE"] = datetime.now().strftime("%B %d, %Y")
        # Skills – take first three if available
        skills = user_profile.get("skills", [])
        if isinstance(skills, list):
            for i in range(3):
                key = f"SKILL_{i+1}"
                data_map[key] = skills[i] if i < len(skills) else ""
        # Project – first project name if available
        projects = user_profile.get("projects", [])
        if isinstance(projects, list) and projects:
            first_proj = projects[0]
            # projects may be dicts with a 'name' field
            if isinstance(first_proj, dict):
                data_map["PROJECT"] = first_proj.get("name", "")
            else:
                data_map["PROJECT"] = str(first_proj)
        else:
            data_map["PROJECT"] = ""
        # Job specific placeholders
        data_map["JOB_TITLE"] = data_map.get("job_title", "")
        # Uppercase aliases so [COMPANY] and [JOB_TITLE] resolve correctly in templates
        data_map["COMPANY"] = data_map.get("company", "") or "Unknown Company"
        # Job requirement – derive a clean, human-readable gerund phrase from the job
        # via JobAnalyzer rather than dumping the raw skills list.
        data_map["JOB_REQUIREMENT"] = self._extract_job_requirement(job)

        # Replace placeholders of the form {{key}} or [KEY]
        def replacer(match: re.Match) -> str:
            # match group 1 is for {{}} style, group 2 for [] style
            key = (match.group(1) or match.group(2)).strip()
            return data_map.get(key, "")
        # Regex matches {{key}} or [KEY]
        rendered = re.sub(r"{{\s*(.*?)\s*}}|\[\s*([A-Z0-9_]+)\s*\]", replacer, content)
        return rendered

    def _extract_job_requirement(self, job: Dict[str, Any]) -> str:
        """Derive a clean, human-readable job requirement phrase.

        Uses JobAnalyzer to extract the first key responsibility from the JD.
        Falls back to the top 3 technical skills if no responsibilities found.
        """
        SOFT_SKILLS = {
            "integrity", "reliability", "communication", "teamwork", "collaboration",
            "leadership", "problem solving", "problem-solving", "critical thinking",
            "time management", "adaptability", "creativity", "flexibility",
            "attention to detail", "work ethic", "professionalism", "responsibility",
            "accountability", "self-motivated", "self-driven", "motivated",
            "cross-functional collaboration", "product management", "compliance",
            "security testing", "api management", "version control",
        }

        try:
            analyzer = JobAnalyzer()
            analysis = analyzer.analyze_job(job)

            # Prefer the first concrete responsibility sentence from the JD
            responsibilities = analysis.get("key_responsibilities", [])
            if responsibilities:
                first = responsibilities[0].strip()
                
                # Drop trailing subordinate clauses to keep the responsibility punchy and clear
                split_keywords = [r"\busing\b", r"\bsuch as\b", r"\bincluding\b", r"\bto\b", r"\bby\b", r"\bthrough\b"]
                for kw in split_keywords:
                    match = re.search(kw, first, re.IGNORECASE)
                    if match and match.start() > 30:  # Only split if we have a solid base clause first
                        first = first[:match.start()].strip().rstrip(" ,;")
                        break
                        
                # Keep it to one clean sentence – hard trim if STILL extremely long
                if len(first) > 120:
                    first = first[:120].rsplit(" ", 1)[0]
                # Convert imperative verb form to gerund so it reads naturally
                # after "where I worked on ..."
                first = self._to_gerund_phrase(first.rstrip("."))
                return first

            # Fallback: top 3 hard technical skills only
            all_skills = analysis.get("critical_skills", [])
            tech_skills = [s for s in all_skills if s.strip().lower() not in SOFT_SKILLS]
            if tech_skills:
                return ", ".join(tech_skills[:3])

        except Exception:
            pass

        return "software development"

    # ------------------------------------------------------------------
    # Gerund conversion helper
    # ------------------------------------------------------------------
    @staticmethod
    def _to_gerund(word: str) -> str:
        """Convert a single base verb to its gerund (-ing) form."""
        w = word.lower()
        if w.endswith("ie"):
            return w[:-2] + "ying"
        if w.endswith("e") and not w.endswith("ee"):
            return w[:-1] + "ing"
        return w + "ing"

    def _to_gerund_phrase(self, text: str) -> str:
        """Convert a responsibility sentence that starts with an imperative verb
        (e.g. "Design and develop X") to gerund form ("designing and developing X").
        Leaves the text unchanged if it already starts with a lowercase/gerund word.
        """
        # Only transform if the sentence starts with a capitalised word (imperative)
        match = re.match(r'^([A-Z][a-z]+)\s+and\s+([a-z]+)(.*)', text)
        if match:
            v1, v2, rest = match.group(1), match.group(2), match.group(3)
            return f"{self._to_gerund(v1)} and {self._to_gerund(v2)}{rest}"
        match = re.match(r'^([A-Z][a-z]+)(\s+.*)', text)
        if match:
            v1, rest = match.group(1), match.group(2)
            return f"{self._to_gerund(v1)}{rest}"
        return text
