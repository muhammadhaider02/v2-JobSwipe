"""
Unit tests for vetting 5-component scoring formula.

Focus: validate weighted math with controlled data (no UI, no scraping).
"""

import os
import sys
import unittest
import logging

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.nodes.vetting import calculate_final_score, WEIGHTS


logger = logging.getLogger(__name__)


class TestVettingScoringFormula(unittest.TestCase):
    def score_fit_percentage(self, user_profile: dict, job_description: dict) -> float:
        """
        Convert controlled component scores to a final fit percentage.

        This mirrors the production weighted formula exactly.
        """
        components = {
            "title_similarity": user_profile["component_scores"]["title_similarity"],
            "skill_match": job_description["component_scores"]["skill_match"],
            "quiz_score": user_profile["component_scores"]["quiz_score"],
            "experience_alignment": user_profile["component_scores"]["experience_alignment"],
            "location_fit": job_description["component_scores"]["location_fit"],
        }

        final_score = calculate_final_score(components)
        return final_score * 100.0

    def test_weights_sum_to_one(self):
        logger.info("Validating scoring weights sum to 1.0")
        self.assertAlmostEqual(sum(WEIGHTS.values()), 1.0, places=9)

    def test_perfect_match_returns_100_percent(self):
        logger.info("Running scenario: perfect match")
        user_profile = {
            "name": "Perfect Candidate",
            "component_scores": {
                "title_similarity": 1.0,
                "quiz_score": 1.0,
                "experience_alignment": 1.0,
            },
        }
        job_description = {
            "title": "Data Engineer",
            "component_scores": {
                "skill_match": 1.0,
                "location_fit": 1.0,
            },
        }

        fit_pct = self.score_fit_percentage(user_profile, job_description)
        logger.info("Perfect match fit: expected=100.00 actual=%.2f", fit_pct)

        # Paper math: 0.35*1 + 0.25*1 + 0.20*1 + 0.15*1 + 0.05*1 = 1.00 -> 100%
        self.assertAlmostEqual(fit_pct, 100.0, places=6)

    def test_total_mismatch_returns_0_percent(self):
        logger.info("Running scenario: total mismatch")
        user_profile = {
            "name": "Mismatch Candidate",
            "component_scores": {
                "title_similarity": 0.0,
                "quiz_score": 0.0,
                "experience_alignment": 0.0,
            },
        }
        job_description = {
            "title": "Data Engineer",
            "component_scores": {
                "skill_match": 0.0,
                "location_fit": 0.0,
            },
        }

        fit_pct = self.score_fit_percentage(user_profile, job_description)
        logger.info("Total mismatch fit: expected=0.00 actual=%.2f", fit_pct)

        # Paper math: all components are 0 -> 0%
        self.assertAlmostEqual(fit_pct, 0.0, places=6)

    def test_edge_case_mixed_scores_matches_paper_math(self):
        logger.info("Running scenario: edge case mixed scores")
        user_profile = {
            "name": "Mixed Candidate",
            "component_scores": {
                "title_similarity": 0.80,
                "quiz_score": 0.90,
                "experience_alignment": 0.70,
            },
        }
        job_description = {
            "title": "Data Engineer",
            "component_scores": {
                "skill_match": 0.50,
                "location_fit": 0.40,
            },
        }

        fit_pct = self.score_fit_percentage(user_profile, job_description)

        expected = (
            0.35 * 0.80
            + 0.25 * 0.50
            + 0.20 * 0.90
            + 0.15 * 0.70
            + 0.05 * 0.40
        ) * 100.0

        logger.info("Edge case fit: expected=%.2f actual=%.2f", expected, fit_pct)

        self.assertAlmostEqual(fit_pct, expected, places=6)
        self.assertAlmostEqual(fit_pct, 71.0, places=6)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    unittest.main(verbosity=2)
