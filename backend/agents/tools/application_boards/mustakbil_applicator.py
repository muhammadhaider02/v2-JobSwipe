"""
Mustakbil Applicator: Mustakbil Apply form automation.

Handles Mustakbil-specific form filling with support for:
- Apply Now button detection
- Screening question toggles (Yes/No)
- Standard contact fields
"""

from typing import Dict, Any

try:
    from playwright.sync_api import Page
except ImportError:
    Page = None

from agents.tools.application_boards.base_applicator import BaseApplicator

class MustakbilApplicator(BaseApplicator):
    def __init__(self, page):
        self.page = page
        self.platform_name = "Mustakbil"

    def click_apply_button(self, page):
        """
        Find and click the initial "Apply Now" button on Mustakbil job page.
        Returns True if found and clicked, else False.
        """
        try:
            selectors = [
                'button:has-text("Apply Now")',
                'a:has-text("Apply Now")',
                'input[type="submit"][value*="Apply Now"]',
            ]
            for selector in selectors:
                btn = page.query_selector(selector)
                if btn:
                    btn.click()
                    return True
        except Exception:
            pass
        return False

    def fill_form(
        self,
        page,
        materials: Dict[str, Any],
        user_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fill Mustakbil application form fields with provided materials and user profile.
        Returns dict with fields_filled, warnings, error.
        """
        fields_filled = {}
        warnings = []
        error = None
        try:
            # Fill contact fields
            contact_fields = {
                'input[name="name"]': user_profile.get('name', ''),
                'input[name="email"]': user_profile.get('email', ''),
                'input[name="phone"]': user_profile.get('phone', ''),
                'input[name="location"]': user_profile.get('location', ''),
            }
            for selector, value in contact_fields.items():
                try:
                    el = page.query_selector(selector)
                    if el:
                        el.fill(value)
                        fields_filled[selector] = True
                    else:
                        fields_filled[selector] = False
                        warnings.append(f"Field not found: {selector}")
                except Exception as exc:
                    fields_filled[selector] = False
                    warnings.append(f"Error filling {selector}: {exc}")

            # Fill cover letter if textarea exists
            cover_letter = materials.get('cover_letter', '')
            try:
                cl_el = page.query_selector('textarea[name*="cover"]')
                if cl_el:
                    cl_el.fill(cover_letter)
                    fields_filled['cover_letter'] = True
                else:
                    fields_filled['cover_letter'] = False
            except Exception as exc:
                fields_filled['cover_letter'] = False
                warnings.append(f"Error filling cover letter: {exc}")

            # Screening questions (Yes/No toggles)
            screening_answers = materials.get('screening_answers', {})
            for question_fragment, answer in screening_answers.items():
                try:
                    # Find label or question containing the fragment
                    label = page.query_selector(f'label:has-text("{question_fragment}")')
                    if label:
                        # Find the associated input (radio/checkbox)
                        input_el = label.query_selector('input[type="radio"], input[type="checkbox"]')
                        if input_el:
                            # Try to match value (yes/no)
                            if input_el.get_attribute('value').lower() == answer.lower():
                                input_el.check()
                                fields_filled[question_fragment] = True
                            else:
                                # Try to find sibling input with correct value
                                parent = label.evaluate_handle('el => el.parentElement')
                                if parent:
                                    inputs = parent.query_selector_all('input[type="radio"], input[type="checkbox"]')
                                    for inp in inputs:
                                        if inp.get_attribute('value').lower() == answer.lower():
                                            inp.check()
                                            fields_filled[question_fragment] = True
                                            break
                                    else:
                                        fields_filled[question_fragment] = False
                                        warnings.append(f"No matching input for {question_fragment}={answer}")
                                else:
                                    fields_filled[question_fragment] = False
                                    warnings.append(f"No parent for label {question_fragment}")
                        else:
                            fields_filled[question_fragment] = False
                            warnings.append(f"No input for label {question_fragment}")
                    else:
                        fields_filled[question_fragment] = False
                        warnings.append(f"No label found for {question_fragment}")
                except Exception as exc:
                    fields_filled[question_fragment] = False
                    warnings.append(f"Error answering {question_fragment}: {exc}")

        except Exception as exc:
            error = str(exc)

        return {
            "fields_filled": fields_filled,
            "warnings": warnings,
            "error": error
        }

    def detect_multi_step(self, page) -> bool:
        """
        Detect if the Mustakbil application form is multi-step.
        Returns True if multi-step detected, else False.
        """
        try:
            # Look for a "Next" or "Continue" button
            next_btn = page.query_selector('button:has-text("Next")')
            continue_btn = page.query_selector('button:has-text("Continue")')
            if next_btn or continue_btn:
                return True
        except Exception:
            pass
        return False
