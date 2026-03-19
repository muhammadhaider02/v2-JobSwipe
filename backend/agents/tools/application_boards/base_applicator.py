"""
Base Applicator Interface: Abstract class for job board-specific form automation.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

try:
    from playwright.sync_api import Page
except ImportError:
    Page = None


class BaseApplicator(ABC):
    """
    Abstract base class for job board-specific application automation.
    
    Each job board (LinkedIn, Indeed, etc.) should implement this interface.
    """
    
    @abstractmethod
    def fill_form(
        self,
        page: Page,
        materials: Dict[str, Any],
        user_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fill application form for this specific job board.
        
        Args:
            page: Playwright page object (already navigated to job page)
            materials: Dict with optimized_resume and cover_letter
            user_profile: User profile with contact info
            
        Returns:
            Dict with:
            {
                "fields_filled": Dict[str, bool],  # Which fields were filled
                "warnings": List[str],  # Any warnings encountered
                "error": Optional[str]  # Error message if failed
            }
        """
        pass
    
    @abstractmethod
    def click_apply_button(self, page: Page) -> bool:
        """
        Find and click the initial "Apply" button.
        
        Args:
            page: Playwright page object
            
        Returns:
            True if apply button found and clicked
        """
        pass
    
    @abstractmethod
    def detect_multi_step(self, page: Page) -> bool:
        """
        Detect if this is a multi-step application form.
        
        Args:
            page: Playwright page object
            
        Returns:
            True if multi-step form detected
        """
        pass
