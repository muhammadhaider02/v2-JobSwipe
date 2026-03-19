"""
Application Boards: Job board-specific form automation modules.
"""

from agents.tools.application_boards.base_applicator import BaseApplicator
from agents.tools.application_boards.indeed_applicator import IndeedApplicator

__all__ = ['BaseApplicator', 'IndeedApplicator']
