"""
Unit tests for resume optimization with mocked Hugging Face LLM responses.

Why this exists:
- Avoid token usage and rate limits in tests.
- Validate how internal optimization logic handles deterministic response shapes.
"""

import os
import sys
import logging
import unittest
from unittest.mock import Mock

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.resume_optimization_service import ResumeOptimizationService


logger = logging.getLogger(__name__)


class TestResumeOptimizationWithMocking(unittest.TestCase):
    def setUp(self):
        # Build service without heavy __init__ (models/index loading).
        self.service = object.__new__(ResumeOptimizationService)
        self.service.retrieve_optimization_rules = Mock(return_value=["Use STAR bullets"])
        self.service.hf_service = Mock()

        self.experience_list = [
            {
                "role": "Data Analyst",
                "company": "Acme",
                "description": "Built ETL jobs\nImproved dashboard latency",
            }
        ]
        self.job_description = "Looking for a data engineer with SQL and Python experience"
        self.role_tags = ["Data Engineer"]
        self.jd_keywords = ["SQL", "Python", "ETL"]

    def test_perfect_json_response_is_applied(self):
        logger.info("Scenario: perfect JSON response from mocked LLM")

        self.service.hf_service.optimize_experience_bullets.return_value = {
            "optimized_bullets": [
                {
                    "original": "Built ETL jobs",
                    "optimized": "Built and maintained ETL pipelines that improved data freshness.",
                    "reasoning": "Adds impact and clearer ownership",
                },
                {
                    "original": "Improved dashboard latency",
                    "optimized": "Reduced dashboard latency by optimizing SQL queries and caching.",
                    "reasoning": "Adds action verbs and technical detail",
                },
            ],
            "validation": {"passed": True, "warnings": []},
        }

        result = self.service._optimize_experience_section(
            experience_list=self.experience_list,
            job_description=self.job_description,
            role_tags=self.role_tags,
            jd_keywords=self.jd_keywords,
        )

        self.service.hf_service.optimize_experience_bullets.assert_called_once()
        self.assertIn("optimized_experience", result)
        self.assertNotIn("error", result)

        optimized_description = result["optimized_experience"][0]["description"]
        self.assertIn("Built and maintained ETL pipelines", optimized_description)
        self.assertIn("Reduced dashboard latency", optimized_description)
        logger.info("Perfect JSON applied successfully")

    def test_malformed_response_falls_back_to_original(self):
        logger.info("Scenario: malformed LLM response")

        # Mimics parse failure propagated by HuggingFaceService.
        self.service.hf_service.optimize_experience_bullets.return_value = {
            "error": "Invalid JSON response from LLM",
            "raw_response": "not a json payload",
        }

        result = self.service._optimize_experience_section(
            experience_list=self.experience_list,
            job_description=self.job_description,
            role_tags=self.role_tags,
            jd_keywords=self.jd_keywords,
        )

        self.service.hf_service.optimize_experience_bullets.assert_called_once()
        self.assertIn("error", result)
        self.assertEqual(result["optimized_experience"], self.experience_list)
        self.assertIn("Invalid JSON response", result["error"])
        logger.info("Malformed response correctly reverted to original experience")

    def test_timeout_error_falls_back_to_original(self):
        logger.info("Scenario: network timeout from mocked LLM client")

        # Mimics service-level timeout handling payload from HuggingFaceService.
        self.service.hf_service.optimize_experience_bullets.return_value = {
            "error": "ReadTimeout while contacting HuggingFace provider",
            "exception_type": "TimeoutError",
        }

        result = self.service._optimize_experience_section(
            experience_list=self.experience_list,
            job_description=self.job_description,
            role_tags=self.role_tags,
            jd_keywords=self.jd_keywords,
        )

        self.service.hf_service.optimize_experience_bullets.assert_called_once()
        self.assertIn("error", result)
        self.assertEqual(result["optimized_experience"], self.experience_list)
        self.assertIn("timeout", result["error"].lower())
        logger.info("Timeout response correctly reverted to original experience")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    unittest.main(verbosity=2)
