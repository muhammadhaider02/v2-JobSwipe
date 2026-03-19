# """
# Browser tool backed by PinchTab.

# Implements campaign form-fill behavior with human review handoff. v1 intentionally
# stops before submit.
# """

# from __future__ import annotations

# from datetime import datetime
# import re
# import time
# from pathlib import Path
# from typing import Any, Dict, List, Optional, Tuple

# from agents.tools.browser_manager import BrowserManager
# from config.settings import get_settings
# from services.pinchtab_service import PinchTabError, get_pinchtab_service


# class MustakbilFormAgent:
#     """State-aware form helper for Mustakbil wizard switches."""

#     def __init__(self, service, manager: Optional[BrowserManager] = None):
#         self.service = service
#         self.manager = manager

#     def _snapshot(self, tab_id: str, filter_mode: str = "interactive") -> Dict[str, Any]:
#         return self.service.snapshot(tab_id=tab_id, filter_mode=filter_mode, format_mode="compact")

#     def _iter_nodes(self, node: Any):
#         if isinstance(node, dict):
#             yield node
#             for value in node.values():
#                 yield from self._iter_nodes(value)
#         elif isinstance(node, list):
#             for item in node:
#                 yield from self._iter_nodes(item)

#     def _extract_ref(self, node: Dict[str, Any]) -> str:
#         for key in ("ref", "stable_ref", "stableRef", "nodeRef", "id"):
#             value = node.get(key)
#             if isinstance(value, str) and value.strip():
#                 return value.strip()
#         return ""

#     def _extract_checked(self, node: Dict[str, Any]) -> Optional[bool]:
#         attributes = node.get("attributes") if isinstance(node.get("attributes"), dict) else {}
#         for key in ("checked", "ariaChecked", "aria-checked", "aria_checked"):
#             raw = node.get(key)
#             if raw is None:
#                 raw = attributes.get(key)
#             if isinstance(raw, bool):
#                 return raw
#             if isinstance(raw, str):
#                 lowered = raw.strip().lower()
#                 if lowered in {"true", "checked", "on", "yes", "1"}:
#                     return True
#                 if lowered in {"false", "off", "no", "0"}:
#                     return False
#         return None

#     def _extract_formcontrol(self, node: Dict[str, Any]) -> str:
#         attributes = node.get("attributes") if isinstance(node.get("attributes"), dict) else {}
#         formcontrol = str(
#             node.get("formcontrolname")
#             or node.get("formControlName")
#             or attributes.get("formcontrolname")
#             or attributes.get("formControlName")
#             or ""
#         ).strip().lower()
#         if formcontrol:
#             return formcontrol
#         blob = str(node).lower()
#         match = re.search(r"formcontrolname[^a-z0-9_:-]+([a-z0-9_:-]+)", blob)
#         return match.group(1).strip().lower() if match else ""

#     def _extract_text(self, node: Dict[str, Any]) -> str:
#         parts: List[str] = []
#         for key in ("text", "name", "label", "ariaLabel", "description", "title"):
#             value = node.get(key)
#             if isinstance(value, str) and value.strip():
#                 parts.append(value.strip().lower())
#         if parts:
#             return " ".join(parts)
#         return str(node).lower()

#     def _switch_nodes(self, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
#         found: List[Dict[str, Any]] = []
#         seen = set()
#         for node in self._iter_nodes(snapshot):
#             if not isinstance(node, dict):
#                 continue
#             role = str(node.get("role") or "").strip().lower()
#             blob = str(node).lower()
#             if "switch" not in role and 'role="switch"' not in blob and "'role': 'switch'" not in blob:
#                 continue
#             ref = self._extract_ref(node)
#             if not ref or ref in seen:
#                 continue
#             seen.add(ref)
#             found.append(
#                 {
#                     "ref": ref,
#                     "checked": self._extract_checked(node),
#                     "formcontrol": self._extract_formcontrol(node),
#                     "text": self._extract_text(node),
#                 }
#             )
#         return found

#     def _human_click(self, tab_id: str, ref: str) -> bool:
#         if not ref:
#             return False
#         try:
#             if self.manager is not None:
#                 self.manager.human_click(tab_id=tab_id, ref=ref)
#             else:
#                 self.service.action(tab_id=tab_id, kind="humanClick", ref=ref)
#             return True
#         except PinchTabError:
#             return False

#     def _resolve_target(self, switches: List[Dict[str, Any]], key: str) -> Optional[Dict[str, Any]]:
#         key_norm = key.strip().lower()
#         for sw in switches:
#             if key_norm and key_norm == str(sw.get("formcontrol") or "").strip().lower():
#                 return sw
#         for sw in switches:
#             text = str(sw.get("text") or "").strip().lower()
#             if key_norm and text and key_norm in text:
#                 return sw
#         return None

#     def process_step(self, tab_id: str, answer_map: Dict[str, Any]) -> Dict[str, Any]:
#         result = {"switches_changed": 0, "continue_clicked": False, "warnings": []}

#         try:
#             snapshot = self._snapshot(tab_id=tab_id, filter_mode="interactive")
#             switches = self._switch_nodes(snapshot)
#             if not switches:
#                 snapshot = self._snapshot(tab_id=tab_id, filter_mode="all")
#                 switches = self._switch_nodes(snapshot)
#         except PinchTabError as exc:
#             result["warnings"].append(f"Snapshot failed while reading Mustakbil switches: {exc}")
#             return result

#         if not switches:
#             result["warnings"].append("No role='switch' controls found in current Mustakbil step.")
#             return result

#         for key, value in (answer_map or {}).items():
#             value_norm = str(value).strip().lower()
#             if value_norm in {"true", "1", "yes", "y"}:
#                 desired = True
#             elif value_norm in {"false", "0", "no", "n"}:
#                 desired = False
#             else:
#                 continue

#             target = self._resolve_target(switches, str(key))
#             if not target:
#                 result["warnings"].append(f"Switch target not found for key: {key}")
#                 continue

#             current = target.get("checked")
#             if isinstance(current, bool) and current == desired:
#                 continue

#             ref = str(target.get("ref") or "").strip()
#             if not self._human_click(tab_id=tab_id, ref=ref):
#                 result["warnings"].append(f"Failed to click switch ref: {ref}")
#                 continue

#             time.sleep(0.5)

#             # Verification step: re-snap and ensure state changed.
#             try:
#                 verify_snapshot = self._snapshot(tab_id=tab_id, filter_mode="interactive")
#                 verify_switches = self._switch_nodes(verify_snapshot)
#                 verify_target = self._resolve_target(verify_switches, str(key))
#                 verify_checked = verify_target.get("checked") if verify_target else None
#                 if isinstance(verify_checked, bool) and verify_checked == desired:
#                     result["switches_changed"] += 1
#                 elif not isinstance(verify_checked, bool):
#                     # If state isn't exposed after click, count successful action but warn.
#                     result["switches_changed"] += 1
#                     result["warnings"].append(f"Switch state not readable after click for: {key}")
#                 else:
#                     result["warnings"].append(f"Switch verification mismatch for: {key}")
#             except PinchTabError as exc:
#                 result["warnings"].append(f"Switch verification failed for {key}: {exc}")

#         # Continue button handling for moving to next step.
#         try:
#             find_res = self.service.find(tab_id=tab_id, query="Continue")
#             continue_ref = str(find_res.get("best_ref") or "").strip()
#             if continue_ref and self._human_click(tab_id=tab_id, ref=continue_ref):
#                 time.sleep(0.5)
#                 result["continue_clicked"] = True
#             else:
#                 result["warnings"].append("Continue button not found on current Mustakbil step.")
#         except PinchTabError as exc:
#             result["warnings"].append(f"Continue click failed: {exc}")

#         return result


# class BrowserTool:
#     """High-level browser actions used by campaign routes."""

#     def __init__(self, headless: Optional[bool] = None):
#         settings = get_settings()
#         self.service = get_pinchtab_service()
#         self.mode = "headless" if bool(headless) else settings.pinchtab_mode
#         self.profile_prefix = settings.pinchtab_profile_prefix
#         self.manager: Optional[BrowserManager] = None

#     def _profile_name(self, user_profile: Dict[str, Any]) -> str:
#         email = (user_profile.get("email") or "anonymous").strip().lower()
#         safe_email = "".join(ch for ch in email if ch.isalnum() or ch in {"-", "_"})
#         if not safe_email:
#             safe_email = "anonymous"
#         return f"{self.profile_prefix}-{safe_email}"

#     def _save_screenshot(self, screenshot_bytes: bytes, job_board: str) -> Optional[str]:
#         if not screenshot_bytes:
#             return None

#         settings = get_settings()
#         screenshots_dir = settings.backend_dir / "screenshots"
#         screenshots_dir.mkdir(parents=True, exist_ok=True)

#         ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
#         file_path = screenshots_dir / f"{job_board}_fill_{ts}.png"
#         file_path.write_bytes(screenshot_bytes)
#         return f"/screenshots/{file_path.name}"

#     def _fill_if_found(self, tab_id: str, query: str, text: str) -> bool:
#         if not text:
#             return False

#         if self.manager is not None:
#             try:
#                 return self.manager.fill_with_stable_ref(tab_id=tab_id, query=query, value=text)
#             except PinchTabError:
#                 return False

#         try:
#             match = self._with_tab_retry(lambda: self.service.find(tab_id=tab_id, query=query))
#             ref = match.get("best_ref")
#             if not ref:
#                 return False

#             self._with_tab_retry(lambda: self.service.action(tab_id=tab_id, kind="fill", ref=ref, text=text))
#             return True
#         except PinchTabError:
#             return False

#     def _click_if_found(self, tab_id: str, query: str) -> bool:
#         try:
#             if self.manager is not None:
#                 ref = self.manager.find_stable_ref(tab_id=tab_id, query=query)
#                 if not ref:
#                     return False
#                 self.manager.human_click(tab_id=tab_id, ref=ref)
#                 return True

#             match = self._with_tab_retry(lambda: self.service.find(tab_id=tab_id, query=query))
#             ref = match.get("best_ref")
#             if not ref:
#                 return False
#             self._with_tab_retry(lambda: self.service.action(tab_id=tab_id, kind="humanClick", ref=ref))
#             return True
#         except PinchTabError:
#             return False

#     def _collect_toggle_refs(self, node: Any, choice: str) -> List[str]:
#         refs: List[str] = []
#         if isinstance(node, dict):
#             subtree_blob = str(node).lower()
#             text_parts: List[str] = []
#             for key in ("text", "name", "label", "ariaLabel", "value", "title"):
#                 value = node.get(key)
#                 if isinstance(value, str):
#                     text_parts.append(value.strip().lower())
#             text_blob = " ".join(part for part in text_parts if part)
#             if not text_blob:
#                 text_blob = subtree_blob

#             ref = None
#             for ref_key in ("ref", "stable_ref", "stableRef", "nodeRef", "id"):
#                 ref_value = node.get(ref_key)
#                 if isinstance(ref_value, str) and ref_value.strip():
#                     ref = ref_value.strip()
#                     break

#             choice_pattern = rf"(^|[^a-z0-9]){re.escape(choice)}([^a-z0-9]|$)"
#             if ref and text_blob and re.search(choice_pattern, text_blob):
#                 refs.append(ref)

#             for value in node.values():
#                 refs.extend(self._collect_toggle_refs(value, choice))

#         elif isinstance(node, list):
#             for item in node:
#                 refs.extend(self._collect_toggle_refs(item, choice))

#         return refs

#     def _collect_refs_by_text_contains(self, node: Any, phrases: List[str]) -> List[str]:
#         refs: List[str] = []
#         lowered_phrases = [p.strip().lower() for p in phrases if p and p.strip()]
#         if not lowered_phrases:
#             return refs

#         if isinstance(node, dict):
#             text_parts: List[str] = []
#             for key in ("text", "name", "label", "ariaLabel", "value", "title", "role"):
#                 value = node.get(key)
#                 if isinstance(value, str):
#                     text_parts.append(value.strip().lower())
#             text_blob = " ".join(part for part in text_parts if part)

#             ref = None
#             for ref_key in ("ref", "stable_ref", "stableRef", "nodeRef", "id"):
#                 ref_value = node.get(ref_key)
#                 if isinstance(ref_value, str) and ref_value.strip():
#                     ref = ref_value.strip()
#                     break

#             if ref and text_blob and any(phrase in text_blob for phrase in lowered_phrases):
#                 refs.append(ref)

#             for value in node.values():
#                 refs.extend(self._collect_refs_by_text_contains(value, lowered_phrases))

#         elif isinstance(node, list):
#             for item in node:
#                 refs.extend(self._collect_refs_by_text_contains(item, lowered_phrases))

#         return refs

#     def _snapshot_contains_any(self, node: Any, phrases: List[str]) -> bool:
#         lowered_phrases = [p.strip().lower() for p in phrases if p and p.strip()]
#         if not lowered_phrases:
#             return False
#         blob = str(node).lower()
#         return any(phrase in blob for phrase in lowered_phrases)

#     def _collect_apply_button_candidates(self, node: Any) -> List[Tuple[str, int, str]]:
#         candidates: List[Tuple[str, int, str]] = []

#         if isinstance(node, dict):
#             text_parts: List[str] = []
#             for key in ("text", "name", "label", "ariaLabel", "value", "title"):
#                 value = node.get(key)
#                 if isinstance(value, str):
#                     text_parts.append(value.strip().lower())
#             text_blob = " ".join(part for part in text_parts if part)

#             role = str(node.get("role") or "").strip().lower()
#             class_blob = " ".join(
#                 str(node.get(k) or "").strip().lower() for k in ("class", "className")
#             ).strip()
#             tag_blob = " ".join(
#                 str(node.get(k) or "").strip().lower() for k in ("tag", "tagName", "nodeName")
#             ).strip()

#             ref = None
#             for ref_key in ("ref", "stable_ref", "stableRef", "nodeRef", "id"):
#                 ref_value = node.get(ref_key)
#                 if isinstance(ref_value, str) and ref_value.strip():
#                     ref = ref_value.strip()
#                     break

#             if ref:
#                 score = 0
#                 if "apply now" in text_blob:
#                     score += 10
#                 if "apply" in text_blob:
#                     score += 4
#                 if "button" in role or "button" in tag_blob:
#                     score += 6
#                 if "md-button" in class_blob:
#                     score += 4
#                 if "primary" in class_blob:
#                     score += 2
#                 if "icon-send" in class_blob or "send" in text_blob:
#                     score += 1
#                 if score > 0:
#                     candidates.append((ref, score, text_blob))

#             for value in node.values():
#                 candidates.extend(self._collect_apply_button_candidates(value))

#         elif isinstance(node, list):
#             for item in node:
#                 candidates.extend(self._collect_apply_button_candidates(item))

#         # Deduplicate while keeping highest score per ref.
#         best: Dict[str, Tuple[int, str]] = {}
#         for ref, score, text in candidates:
#             current = best.get(ref)
#             if current is None or score > current[0]:
#                 best[ref] = (score, text)

#         ranked = sorted(((ref, data[0], data[1]) for ref, data in best.items()), key=lambda x: x[1], reverse=True)
#         return ranked

#     def _collect_switch_controls(self, node: Any) -> List[Dict[str, Any]]:
#         controls: List[Dict[str, Any]] = []

#         if isinstance(node, dict):
#             attributes = node.get("attributes") if isinstance(node.get("attributes"), dict) else {}
#             subtree_blob = str(node).lower()

#             text_parts: List[str] = []
#             for key in ("text", "name", "label", "ariaLabel", "title"):
#                 value = node.get(key)
#                 if isinstance(value, str):
#                     text_parts.append(value.strip().lower())
#             text_blob = " ".join(part for part in text_parts if part)
#             if not text_blob and "md-switch__label" in subtree_blob:
#                 text_blob = subtree_blob

#             role = str(node.get("role") or attributes.get("role") or "").strip().lower()
#             class_blob = " ".join(
#                 str(v).strip().lower() for v in (
#                     node.get("class"),
#                     node.get("className"),
#                     attributes.get("class"),
#                 ) if v
#             )
#             formcontrol = str(
#                 node.get("formcontrolname")
#                 or node.get("formControlName")
#                 or attributes.get("formcontrolname")
#                 or attributes.get("formControlName")
#                 or ""
#             ).strip().lower()
#             if not formcontrol:
#                 match = re.search(r"formcontrolname[^a-z0-9_:-]+([a-z0-9_:-]+)", subtree_blob)
#                 if match:
#                     formcontrol = match.group(1).strip().lower()

#             tag_blob = " ".join(str(node.get(k) or "").strip().lower() for k in ("tag", "tagName", "nodeName"))
#             input_type = str(node.get("type") or attributes.get("type") or "").strip().lower()

#             checked: Optional[bool] = None
#             raw_checked = node.get("checked")
#             if raw_checked is None:
#                 raw_checked = attributes.get("checked")
#             raw_aria_checked = node.get("ariaChecked")
#             if raw_checked is None:
#                 raw_checked = node.get("aria-checked")
#             if raw_checked is None:
#                 raw_checked = attributes.get("aria-checked")
#             if raw_aria_checked is None:
#                 raw_aria_checked = node.get("aria_checked")
#             if raw_aria_checked is None:
#                 raw_aria_checked = attributes.get("aria_checked")
#             for candidate in (raw_checked, raw_aria_checked):
#                 if isinstance(candidate, bool):
#                     checked = candidate
#                     break
#                 if isinstance(candidate, str):
#                     lowered = candidate.strip().lower()
#                     if lowered in {"true", "checked", "on", "yes", "1"}:
#                         checked = True
#                         break
#                     if lowered in {"false", "off", "no", "0"}:
#                         checked = False
#                         break

#             ref = None
#             for ref_key in ("ref", "stable_ref", "stableRef", "nodeRef", "id"):
#                 ref_value = node.get(ref_key)
#                 if isinstance(ref_value, str) and ref_value.strip():
#                     ref = ref_value.strip()
#                     break

#             if ref:
#                 looks_like_switch = (
#                     "switch" in role
#                     or "md-switch" in class_blob
#                     or formcontrol.startswith("ques")
#                     or input_type == "checkbox"
#                     or ("input" in tag_blob and "switch" in class_blob)
#                     or "md-switch" in subtree_blob
#                     or 'role="switch"' in subtree_blob
#                     or "'role': 'switch'" in subtree_blob
#                 )
#                 if looks_like_switch:
#                     controls.append(
#                         {
#                             "ref": ref,
#                             "formcontrol": formcontrol,
#                             "text": text_blob,
#                             "checked": checked,
#                         }
#                     )

#             for value in node.values():
#                 controls.extend(self._collect_switch_controls(value))

#         elif isinstance(node, list):
#             for item in node:
#                 controls.extend(self._collect_switch_controls(item))

#         deduped: List[Dict[str, Any]] = []
#         seen = set()
#         for item in controls:
#             ref = str(item.get("ref") or "").strip()
#             if ref in seen:
#                 continue
#             seen.add(ref)
#             deduped.append(item)
#         return deduped

#     def _click_switch_to_value(self, tab_id: str, control: Dict[str, Any], desired_yes: bool) -> bool:
#         ref = str(control.get("ref") or "").strip()
#         if not ref:
#             return False
#         checked = control.get("checked")

#         # If state is known and already desired, skip click.
#         if isinstance(checked, bool) and checked == desired_yes:
#             return False

#         return self._mustakbil_try_click_ref(tab_id=tab_id, ref=ref)

#     def _detect_mustakbil_transition(self, snapshot: Dict[str, Any]) -> Tuple[bool, str]:
#         markers = [
#             "apply-container",
#             "apply-header",
#             "wizard-step",
#             "step 1 of 3",
#             "confirm your eligibility",
#             "question-card",
#             "md-switch",
#             "role=\"switch\"",
#             "application progress",
#         ]
#         if self._snapshot_contains_any(snapshot, markers):
#             return True, "Mustakbil apply wizard detected (step/switch markers present)."
#         return False, ""

#     def _check_mustakbil_transition(self, tab_id: str) -> Tuple[bool, str, Dict[str, Any], List[str]]:
#         try:
#             snapshot = self._with_tab_retry(
#                 lambda: self.service.snapshot(tab_id=tab_id, filter_mode="all", format_mode="compact"),
#                 retries=2,
#             )
#         except PinchTabError:
#             snapshot = {}

#         switch_controls = self._collect_switch_controls(snapshot)
#         transitioned, reason = self._detect_mustakbil_transition(snapshot)
#         if transitioned:
#             return True, reason, snapshot, switch_controls

#         if switch_controls:
#             return True, "Switch controls detected in apply wizard.", snapshot, switch_controls

#         try:
#             raw_text_payload = self._with_tab_retry(
#                 lambda: self.service.text(tab_id=tab_id, mode="raw"),
#                 retries=2,
#             )
#             raw_text = str(raw_text_payload.get("text") or "").lower()
#         except PinchTabError:
#             raw_text = ""

#         text_markers = [
#             "step 1 of 3",
#             "confirm your eligibility",
#             "application progress",
#             "continue",
#             "qualification match",
#             "experience level",
#         ]
#         if any(marker in raw_text for marker in text_markers):
#             return True, "Apply wizard detected from raw text markers.", snapshot, switch_controls

#         return False, "", snapshot, switch_controls

#     def _mustakbil_try_click_ref(self, tab_id: str, ref: str) -> bool:
#         try:
#             self._with_tab_retry(lambda: self.service.action(tab_id=tab_id, kind="click", ref=ref), retries=2)
#             return True
#         except PinchTabError:
#             pass

#         try:
#             if self.manager is not None:
#                 self.manager.human_click(tab_id=tab_id, ref=ref)
#             else:
#                 self._with_tab_retry(lambda: self.service.action(tab_id=tab_id, kind="humanClick", ref=ref), retries=2)
#             return True
#         except PinchTabError:
#             return False

#     def _apply_mustakbil_flow(self, tab_id: str, materials: Dict[str, Any]) -> Dict[str, Any]:
#         actions: Dict[str, Any] = {
#             "apply_clicked": False,
#             "apply_transition_detected": False,
#             "apply_transition_reason": "",
#             "question_answers_clicked": 0,
#             "warnings": [],
#         }

#         # Phase 1: ranked button-ref clicking (more reliable for Angular nested buttons).
#         try:
#             apply_snapshot = self._with_tab_retry(
#                 lambda: self.service.snapshot(tab_id=tab_id, filter_mode="all", format_mode="compact"),
#                 retries=2,
#             )
#         except PinchTabError:
#             apply_snapshot = {}

#         ranked_candidates = self._collect_apply_button_candidates(apply_snapshot)
#         for ref, score, text_blob in ranked_candidates[:10]:
#             if score < 8:
#                 continue
#             if not self._mustakbil_try_click_ref(tab_id=tab_id, ref=ref):
#                 continue
#             actions["apply_clicked"] = True
#             transitioned, reason, latest_snapshot, _ = self._check_mustakbil_transition(tab_id)
#             if transitioned:
#                 actions["apply_transition_detected"] = True
#                 actions["apply_transition_reason"] = reason
#                 apply_snapshot = latest_snapshot
#                 break
#             actions["warnings"].append(
#                 f"Apply ref clicked but no transition yet (score={score}, ref={ref}, text='{text_blob[:80]}')."
#             )
#             time.sleep(0.8)

#         # Phase 2: semantic query clicking fallback.
#         if not actions["apply_transition_detected"]:
#             for query in (
#                 "Apply Now",
#                 "apply now",
#                 "Apply",
#                 "button Apply Now",
#                 "Apply Now button",
#                 "send Apply Now",
#                 "icon send Apply Now",
#                 "md-button primary Apply Now",
#             ):
#                 if not self._click_if_found(tab_id, query):
#                     continue
#                 actions["apply_clicked"] = True
#                 transitioned, reason, latest_snapshot, _ = self._check_mustakbil_transition(tab_id)
#                 if transitioned:
#                     actions["apply_transition_detected"] = True
#                     actions["apply_transition_reason"] = reason
#                     apply_snapshot = latest_snapshot
#                     break
#                 time.sleep(0.8)

#         if not actions["apply_clicked"]:
#             actions["warnings"].append("Could not find 'Apply Now' button on Mustakbil page.")
#             return actions

#         # Mustakbil often renders screening questions with a delay after Apply Now.
#         # Poll briefly so we don't miss toggle buttons that appear asynchronously.
#         toggle_snapshot: Dict[str, Any] = apply_snapshot if isinstance(apply_snapshot, dict) else {}
#         yes_refs: List[str] = []
#         no_refs: List[str] = []
#         switch_controls: List[Dict[str, Any]] = []
#         wait_deadline = time.time() + 10.0
#         while time.time() < wait_deadline:
#             transitioned, reason, toggle_snapshot, _ = self._check_mustakbil_transition(tab_id)
#             switch_controls = self._collect_switch_controls(toggle_snapshot)
#             if transitioned:
#                 actions["apply_transition_detected"] = True
#                 actions["apply_transition_reason"] = reason

#             yes_refs = self._collect_toggle_refs(toggle_snapshot, "yes")
#             no_refs = self._collect_toggle_refs(toggle_snapshot, "no")
#             if yes_refs or no_refs or switch_controls:
#                 if not actions["apply_transition_reason"]:
#                     actions["apply_transition_reason"] = "Apply wizard controls detected after Apply Now click."
#                 break

#             time.sleep(1.0)

#         # If the first click did not transition, retry top ranked button-like refs.
#         if not actions["apply_transition_detected"]:
#             ranked_candidates = self._collect_apply_button_candidates(toggle_snapshot)
#             for ref, score, _ in ranked_candidates[:6]:
#                 if score < 8:
#                     continue
#                 if not self._mustakbil_try_click_ref(tab_id=tab_id, ref=ref):
#                     continue
#                 time.sleep(1.2)
#                 try:
#                     retry_snapshot = self._with_tab_retry(
#                         lambda: self.service.snapshot(tab_id=tab_id, filter_mode="all", format_mode="compact"),
#                         retries=2,
#                     )
#                 except PinchTabError:
#                     retry_snapshot = {}

#                 transitioned, reason = self._detect_mustakbil_transition(retry_snapshot)
#                 switch_controls_retry = self._collect_switch_controls(retry_snapshot)
#                 if transitioned or switch_controls_retry:
#                     actions["apply_transition_detected"] = True
#                     actions["apply_transition_reason"] = reason or "Transition detected after ranked re-click."
#                     toggle_snapshot = retry_snapshot
#                     break

#         screening_answers = materials.get("screening_answers") or {}
#         if not screening_answers:
#             # Default behavior for Mustakbil eligibility wizard is to set known toggles to Yes.
#             screening_answers = {"ques1": "yes", "ques2": "yes"}

#         form_agent = MustakbilFormAgent(service=self.service, manager=self.manager)
#         agent_result = form_agent.process_step(tab_id=tab_id, answer_map=screening_answers)
#         if int(agent_result.get("switches_changed") or 0) > 0:
#             actions["question_answers_clicked"] = int(agent_result.get("switches_changed") or 0)
#             if not actions.get("apply_transition_reason"):
#                 actions["apply_transition_reason"] = "Mustakbil form agent processed switch controls."
#         actions["warnings"].extend(agent_result.get("warnings") or [])

#         explicit_answers = 0
#         for question, answer in screening_answers.items():
#             choice = str(answer).strip().lower()
#             if choice in {"true", "1", "yes", "y"}:
#                 choice = "yes"
#             elif choice in {"false", "0", "no", "n"}:
#                 choice = "no"
#             if choice not in {"yes", "no"}:
#                 continue
#             if self._click_if_found(tab_id, f"{question} {choice}"):
#                 explicit_answers += 1

#         if explicit_answers:
#             actions["question_answers_clicked"] = explicit_answers
#             return actions

#         if not (yes_refs or no_refs or switch_controls):
#             try:
#                 toggle_snapshot = self._with_tab_retry(
#                     lambda: self.service.snapshot(tab_id=tab_id, filter_mode="all", format_mode="compact"),
#                     retries=2,
#                 )
#             except PinchTabError:
#                 toggle_snapshot = {}
#             yes_refs = self._collect_toggle_refs(toggle_snapshot, "yes")
#             no_refs = self._collect_toggle_refs(toggle_snapshot, "no")
#             switch_controls = self._collect_switch_controls(toggle_snapshot)
#         clicked_refs = set()
#         toggle_refs_to_click = list(yes_refs)
#         if not toggle_refs_to_click and no_refs:
#             # Mustakbil switch controls often show "No" label by default;
#             # clicking it toggles the underlying checkbox to Yes.
#             toggle_refs_to_click = list(no_refs)
#             actions["warnings"].append("Using 'No' switch label refs to toggle answers to Yes.")

#         for ref in toggle_refs_to_click:
#             if ref in clicked_refs:
#                 continue
#             try:
#                 if self.manager is not None:
#                     self.manager.human_click(tab_id=tab_id, ref=ref)
#                 else:
#                     self._with_tab_retry(lambda: self.service.action(tab_id=tab_id, kind="humanClick", ref=ref))
#                 clicked_refs.add(ref)
#             except PinchTabError:
#                 continue

#         # Mustakbil uses role="switch" checkbox controls (ques1, ques2...).
#         # Set switches to desired yes/no using screening answers when provided.
#         answer_map = materials.get("screening_answers") or {}
#         for control in switch_controls:
#             ref = str(control.get("ref") or "").strip()
#             if not ref or ref in clicked_refs:
#                 continue

#             control_key = str(control.get("formcontrol") or "").strip().lower()
#             control_text = str(control.get("text") or "").strip().lower()

#             desired_yes = True  # default requested behavior
#             for key, value in answer_map.items():
#                 key_norm = str(key).strip().lower()
#                 value_norm = str(value).strip().lower()
#                 if value_norm in {"true", "1", "yes", "y"}:
#                     desired = True
#                 elif value_norm in {"false", "0", "no", "n"}:
#                     desired = False
#                 else:
#                     continue

#                 if key_norm and (
#                     key_norm == control_key
#                     or (control_key and key_norm in control_key)
#                     or (control_text and key_norm in control_text)
#                 ):
#                     desired_yes = desired
#                     break

#             try:
#                 changed = self._click_switch_to_value(tab_id=tab_id, control=control, desired_yes=desired_yes)
#                 if changed:
#                     clicked_refs.add(ref)
#             except PinchTabError:
#                 continue

#         actions["question_answers_clicked"] = len(clicked_refs)
#         if actions["apply_clicked"] and not actions["apply_transition_detected"]:
#             actions["warnings"].append(
#                 "Apply click was acknowledged, but no transition to screening state was detected. "
#                 "This usually means a non-actionable element was clicked or the site blocked progression."
#             )
#         if not clicked_refs:
#             actions["warnings"].append("No screening switch/toggle controls were auto-detected on Mustakbil apply flow.")
#         return actions

#     def _with_tab_retry(self, call, retries: int = 4, delay_sec: float = 0.75):
#         """Retry short-lived PinchTab tab lookup races after navigation."""
#         last_exc: Optional[Exception] = None
#         for attempt in range(retries + 1):
#             try:
#                 return call()
#             except PinchTabError as exc:
#                 msg = str(exc).lower()
#                 last_exc = exc
#                 if "tab" in msg and "not found" in msg and attempt < retries:
#                     time.sleep(delay_sec)
#                     continue
#                 raise
#         if last_exc:
#             raise last_exc

#     def fill_application(
#         self,
#         job_url: str,
#         job_board: str,
#         materials: Dict[str, Any],
#         user_profile: Dict[str, Any],
#         instance_id: Optional[str] = None,
#         tab_id: Optional[str] = None,
#         require_preauth: bool = True,
#     ) -> Dict[str, Any]:
#         """Fill common fields and produce screenshot evidence for HITL review."""
#         if not job_url:
#             return {"error": "Job URL is missing."}

#         try:
#             self.service.health()
#             self.manager = BrowserManager(board=job_board)

#             session: Dict[str, Any] = {}
#             provided_instance = bool(instance_id)
#             if not instance_id:
#                 session = self.manager.ensure_session(user_profile=user_profile, rotate_ip=True)
#                 instance_id = session.get("instance_id")

#             if tab_id:
#                 try:
#                     nav = self.manager.navigate(
#                         instance_id=instance_id,
#                         url=job_url,
#                         tab_id=tab_id,
#                         new_tab=False,
#                     )
#                     tab_id = nav.get("tab_id")
#                 except PinchTabError as tab_nav_exc:
#                     tab_nav_msg = str(tab_nav_exc).lower()
#                     if "tab" in tab_nav_msg and "not found" in tab_nav_msg:
#                         tab_id = None
#                     else:
#                         raise

#             if not tab_id:
#                 try:
#                     nav = self.manager.navigate(instance_id=instance_id, url=job_url)
#                     tab_id = nav.get("tab_id")
#                 except PinchTabError as nav_exc:
#                     nav_msg = str(nav_exc).lower()
#                     can_recover = (
#                         ("context canceled" in nav_msg or "context deadline exceeded" in nav_msg)
#                         and not provided_instance
#                         and bool(instance_id)
#                     )
#                     if not can_recover:
#                         raise

#                     # Recover once from stale browser context by recreating session.
#                     self.manager.stop_session(str(instance_id))
#                     session = self.manager.ensure_session(user_profile=user_profile, rotate_ip=False)
#                     instance_id = session.get("instance_id")
#                     nav = self.manager.navigate(instance_id=instance_id, url=job_url)
#                     tab_id = nav.get("tab_id")

#             # Auth validation is intentionally skipped for mirrored-profile mode.
#             # The session is assumed to be pre-authenticated when PinchTab starts.

#             fields_filled = {
#                 "name": False,
#                 "email": False,
#                 "phone": False,
#                 "location": False,
#                 "cover_letter": False,
#             }

#             full_name = user_profile.get("name") or ""
#             email = user_profile.get("email") or ""
#             phone = user_profile.get("phone") or ""
#             location = user_profile.get("location") or ""
#             cover_letter = materials.get("cover_letter") or ""

#             fields_filled["name"] = self._fill_if_found(tab_id, "full name", full_name)
#             fields_filled["email"] = self._fill_if_found(tab_id, "email", email)
#             fields_filled["phone"] = self._fill_if_found(tab_id, "phone", phone)
#             fields_filled["location"] = self._fill_if_found(tab_id, "location", location)
#             fields_filled["cover_letter"] = self._fill_if_found(tab_id, "cover letter", cover_letter)

#             board_actions: Dict[str, Any] = {}
#             board_warnings: List[str] = []
#             if (job_board or "").lower() == "mustakbil":
#                 board_actions = self._apply_mustakbil_flow(tab_id=tab_id, materials=materials)
#                 board_warnings = board_actions.pop("warnings", []) if isinstance(board_actions, dict) else []

#             # Keep an interactive snapshot for debugging and observability.
#             try:
#                 self._with_tab_retry(lambda: self.service.snapshot_interactive(tab_id=tab_id), retries=2)
#             except PinchTabError:
#                 pass

#             screenshot = self._with_tab_retry(lambda: self.service.screenshot_bytes(tab_id=tab_id), retries=2)
#             screenshot_path = self._save_screenshot(screenshot, job_board)

#             return {
#                 "status": "filled",
#                 "fields_filled": fields_filled,
#                 "screenshot_path": screenshot_path,
#                 "instance_id": instance_id,
#                 "tab_id": tab_id,
#                 "proxy_rotated": bool(session.get("proxy_rotated")),
#                 "proxy_server": session.get("proxy_server"),
#                 "board_actions": board_actions,
#                 "warnings": (
#                     [] if any(fields_filled.values()) else ["No known fields auto-filled."]
#                 ) + board_warnings,
#             }

#         except PinchTabError as exc:
#             msg = str(exc)
#             if "context canceled" in msg.lower() or "context deadline exceeded" in msg.lower():
#                 return {
#                     "error": (
#                         "PinchTab could not create a browser tab (context timeout). "
#                         "Retry with an already-authenticated session or restart PinchTab and retry."
#                     ),
#                     "diagnostic": msg,
#                 }
#             return {"error": msg}
#         except Exception as exc:  # pragma: no cover - defensive safety net
#             return {"error": f"Unexpected browser tool failure: {exc}"}

#     def submit_application(self, job_id: str) -> Dict[str, Any]:
#         """v1 intentionally disables auto-submit for safety."""
#         return {
#             "error": "Auto-submit is disabled in v1. Manual submission is required.",
#             "job_id": job_id,
#             "status": "manual_required",
#         }



"""
Browser tool backed by PinchTab.

Implements campaign form-fill behavior with human review handoff. v1 intentionally
stops before submit.
"""

from __future__ import annotations

from datetime import datetime
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agents.tools.browser_manager import BrowserManager
from config.settings import get_settings
from services.pinchtab_service import PinchTabError, get_pinchtab_service


class MustakbilFormAgent:
    """State-aware form helper for Mustakbil wizard switches."""

    def __init__(self, service, manager: Optional[BrowserManager] = None):
        self.service = service
        self.manager = manager

    def _snapshot(self, tab_id: str, filter_mode: str = "interactive") -> Dict[str, Any]:
        return self.service.snapshot(tab_id=tab_id, filter_mode=filter_mode, format_mode="compact")

    def _iter_nodes(self, node: Any):
        if isinstance(node, dict):
            yield node
            for value in node.values():
                yield from self._iter_nodes(value)
        elif isinstance(node, list):
            for item in node:
                yield from self._iter_nodes(item)

    def _extract_ref(self, node: Dict[str, Any]) -> str:
        for key in ("ref", "stable_ref", "stableRef", "nodeRef", "id"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _extract_checked(self, node: Dict[str, Any]) -> Optional[bool]:
        attributes = node.get("attributes") if isinstance(node.get("attributes"), dict) else {}
        for key in ("checked", "ariaChecked", "aria-checked", "aria_checked"):
            raw = node.get(key)
            if raw is None:
                raw = attributes.get(key)
            if isinstance(raw, bool):
                return raw
            if isinstance(raw, str):
                lowered = raw.strip().lower()
                if lowered in {"true", "checked", "on", "yes", "1"}:
                    return True
                if lowered in {"false", "off", "no", "0"}:
                    return False
        return None

    def _extract_formcontrol(self, node: Dict[str, Any]) -> str:
        attributes = node.get("attributes") if isinstance(node.get("attributes"), dict) else {}
        formcontrol = str(
            node.get("formcontrolname")
            or node.get("formControlName")
            or attributes.get("formcontrolname")
            or attributes.get("formControlName")
            or ""
        ).strip().lower()
        if formcontrol:
            return formcontrol
        blob = str(node).lower()
        match = re.search(r"formcontrolname[^a-z0-9_:-]+([a-z0-9_:-]+)", blob)
        return match.group(1).strip().lower() if match else ""

    def _extract_text(self, node: Dict[str, Any]) -> str:
        parts: List[str] = []
        for key in ("text", "name", "label", "ariaLabel", "description", "title"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip().lower())
        if parts:
            return " ".join(parts)
        return str(node).lower()

    def _switch_nodes(self, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        found: List[Dict[str, Any]] = []
        seen = set()
        for node in self._iter_nodes(snapshot):
            if not isinstance(node, dict):
                continue
            role = str(node.get("role") or "").strip().lower()
            blob = str(node).lower()
            if "switch" not in role and 'role="switch"' not in blob and "'role': 'switch'" not in blob:
                continue
            ref = self._extract_ref(node)
            if not ref or ref in seen:
                continue
            seen.add(ref)
            found.append(
                {
                    "ref": ref,
                    "checked": self._extract_checked(node),
                    "formcontrol": self._extract_formcontrol(node),
                    "text": self._extract_text(node),
                }
            )
        return found

    def _human_click(self, tab_id: str, ref: str) -> bool:
        if not ref:
            return False
        try:
            if self.manager is not None:
                self.manager.human_click(tab_id=tab_id, ref=ref)
            else:
                self.service.action(tab_id=tab_id, kind="humanClick", ref=ref)
            return True
        except PinchTabError:
            return False

    def _resolve_target(self, switches: List[Dict[str, Any]], key: str) -> Optional[Dict[str, Any]]:
        key_norm = key.strip().lower()
        for sw in switches:
            if key_norm and key_norm == str(sw.get("formcontrol") or "").strip().lower():
                return sw
        for sw in switches:
            text = str(sw.get("text") or "").strip().lower()
            if key_norm and text and key_norm in text:
                return sw
        return None

    def process_step(self, tab_id: str, answer_map: Dict[str, Any]) -> Dict[str, Any]:
        result = {"switches_changed": 0, "continue_clicked": False, "warnings": []}

        try:
            snapshot = self._snapshot(tab_id=tab_id, filter_mode="interactive")
            switches = self._switch_nodes(snapshot)
            if not switches:
                snapshot = self._snapshot(tab_id=tab_id, filter_mode="all")
                switches = self._switch_nodes(snapshot)
        except PinchTabError as exc:
            result["warnings"].append(f"Snapshot failed while reading Mustakbil switches: {exc}")
            return result

        if not switches:
            result["warnings"].append("No role='switch' controls found in current Mustakbil step.")
            return result

        for key, value in (answer_map or {}).items():
            value_norm = str(value).strip().lower()
            if value_norm in {"true", "1", "yes", "y"}:
                desired = True
            elif value_norm in {"false", "0", "no", "n"}:
                desired = False
            else:
                continue

            target = self._resolve_target(switches, str(key))
            if not target:
                result["warnings"].append(f"Switch target not found for key: {key}")
                continue

            current = target.get("checked")
            if isinstance(current, bool) and current == desired:
                continue

            ref = str(target.get("ref") or "").strip()
            if not self._human_click(tab_id=tab_id, ref=ref):
                result["warnings"].append(f"Failed to click switch ref: {ref}")
                continue

            time.sleep(0.5)

            # Verification step: re-snap and ensure state changed.
            try:
                verify_snapshot = self._snapshot(tab_id=tab_id, filter_mode="interactive")
                verify_switches = self._switch_nodes(verify_snapshot)
                verify_target = self._resolve_target(verify_switches, str(key))
                verify_checked = verify_target.get("checked") if verify_target else None
                if isinstance(verify_checked, bool) and verify_checked == desired:
                    result["switches_changed"] += 1
                elif not isinstance(verify_checked, bool):
                    # If state isn't exposed after click, count successful action but warn.
                    result["switches_changed"] += 1
                    result["warnings"].append(f"Switch state not readable after click for: {key}")
                else:
                    result["warnings"].append(f"Switch verification mismatch for: {key}")
            except PinchTabError as exc:
                result["warnings"].append(f"Switch verification failed for {key}: {exc}")

        # Continue button handling for moving to next step.
        try:
            find_res = self.service.find(tab_id=tab_id, query="Continue")
            continue_ref = str(find_res.get("best_ref") or "").strip()
            if continue_ref and self._human_click(tab_id=tab_id, ref=continue_ref):
                time.sleep(0.5)
                result["continue_clicked"] = True
            else:
                result["warnings"].append("Continue button not found on current Mustakbil step.")
        except PinchTabError as exc:
            result["warnings"].append(f"Continue click failed: {exc}")

        return result


class BrowserTool:
    """High-level browser actions used by campaign routes."""

    def __init__(self, headless: Optional[bool] = None):
        settings = get_settings()
        self.service = get_pinchtab_service()
        self.mode = "headless" if bool(headless) else settings.pinchtab_mode
        self.profile_prefix = settings.pinchtab_profile_prefix
        self.manager: Optional[BrowserManager] = None

    def _profile_name(self, user_profile: Dict[str, Any]) -> str:
        email = (user_profile.get("email") or "anonymous").strip().lower()
        safe_email = "".join(ch for ch in email if ch.isalnum() or ch in {"-", "_"})
        if not safe_email:
            safe_email = "anonymous"
        return f"{self.profile_prefix}-{safe_email}"

    def _save_screenshot(self, screenshot_bytes: bytes, job_board: str) -> Optional[str]:
        if not screenshot_bytes:
            return None

        settings = get_settings()
        screenshots_dir = settings.backend_dir / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        file_path = screenshots_dir / f"{job_board}_fill_{ts}.png"
        file_path.write_bytes(screenshot_bytes)
        return f"/screenshots/{file_path.name}"

    def _fill_if_found(self, tab_id: str, query: str, text: str) -> bool:
        if not text:
            return False

        if self.manager is not None:
            try:
                return self.manager.fill_with_stable_ref(tab_id=tab_id, query=query, value=text)
            except PinchTabError:
                return False

        try:
            match = self._with_tab_retry(lambda: self.service.find(tab_id=tab_id, query=query))
            ref = match.get("best_ref")
            if not ref:
                return False

            self._with_tab_retry(lambda: self.service.action(tab_id=tab_id, kind="fill", ref=ref, text=text))
            return True
        except PinchTabError:
            return False

    def _click_if_found(self, tab_id: str, query: str) -> bool:
        try:
            if self.manager is not None:
                ref = self.manager.find_stable_ref(tab_id=tab_id, query=query)
                if not ref:
                    return False
                self.manager.human_click(tab_id=tab_id, ref=ref)
                return True

            match = self._with_tab_retry(lambda: self.service.find(tab_id=tab_id, query=query))
            ref = match.get("best_ref")
            if not ref:
                return False
            self._with_tab_retry(lambda: self.service.action(tab_id=tab_id, kind="humanClick", ref=ref))
            return True
        except PinchTabError:
            return False

    def _collect_toggle_refs(self, node: Any, choice: str) -> List[str]:
        refs: List[str] = []
        if isinstance(node, dict):
            subtree_blob = str(node).lower()
            text_parts: List[str] = []
            for key in ("text", "name", "label", "ariaLabel", "value", "title"):
                value = node.get(key)
                if isinstance(value, str):
                    text_parts.append(value.strip().lower())
            text_blob = " ".join(part for part in text_parts if part)
            if not text_blob:
                text_blob = subtree_blob

            ref = None
            for ref_key in ("ref", "stable_ref", "stableRef", "nodeRef", "id"):
                ref_value = node.get(ref_key)
                if isinstance(ref_value, str) and ref_value.strip():
                    ref = ref_value.strip()
                    break

            choice_pattern = rf"(^|[^a-z0-9]){re.escape(choice)}([^a-z0-9]|$)"
            if ref and text_blob and re.search(choice_pattern, text_blob):
                refs.append(ref)

            for value in node.values():
                refs.extend(self._collect_toggle_refs(value, choice))

        elif isinstance(node, list):
            for item in node:
                refs.extend(self._collect_toggle_refs(item, choice))

        return refs

    def _collect_refs_by_text_contains(self, node: Any, phrases: List[str]) -> List[str]:
        refs: List[str] = []
        lowered_phrases = [p.strip().lower() for p in phrases if p and p.strip()]
        if not lowered_phrases:
            return refs

        if isinstance(node, dict):
            text_parts: List[str] = []
            for key in ("text", "name", "label", "ariaLabel", "value", "title", "role"):
                value = node.get(key)
                if isinstance(value, str):
                    text_parts.append(value.strip().lower())
            text_blob = " ".join(part for part in text_parts if part)

            ref = None
            for ref_key in ("ref", "stable_ref", "stableRef", "nodeRef", "id"):
                ref_value = node.get(ref_key)
                if isinstance(ref_value, str) and ref_value.strip():
                    ref = ref_value.strip()
                    break

            if ref and text_blob and any(phrase in text_blob for phrase in lowered_phrases):
                refs.append(ref)

            for value in node.values():
                refs.extend(self._collect_refs_by_text_contains(value, lowered_phrases))

        elif isinstance(node, list):
            for item in node:
                refs.extend(self._collect_refs_by_text_contains(item, lowered_phrases))

        return refs

    def _snapshot_contains_any(self, node: Any, phrases: List[str]) -> bool:
        lowered_phrases = [p.strip().lower() for p in phrases if p and p.strip()]
        if not lowered_phrases:
            return False
        blob = str(node).lower()
        return any(phrase in blob for phrase in lowered_phrases)

    def _collect_apply_button_candidates(self, node: Any) -> List[Tuple[str, int, str]]:
        candidates: List[Tuple[str, int, str]] = []

        if isinstance(node, dict):
            text_parts: List[str] = []
            for key in ("text", "name", "label", "ariaLabel", "value", "title"):
                value = node.get(key)
                if isinstance(value, str):
                    text_parts.append(value.strip().lower())
            text_blob = " ".join(part for part in text_parts if part)

            role = str(node.get("role") or "").strip().lower()
            class_blob = " ".join(
                str(node.get(k) or "").strip().lower() for k in ("class", "className")
            ).strip()
            tag_blob = " ".join(
                str(node.get(k) or "").strip().lower() for k in ("tag", "tagName", "nodeName")
            ).strip()

            ref = None
            for ref_key in ("ref", "stable_ref", "stableRef", "nodeRef", "id"):
                ref_value = node.get(ref_key)
                if isinstance(ref_value, str) and ref_value.strip():
                    ref = ref_value.strip()
                    break

            if ref:
                score = 0
                if "apply now" in text_blob:
                    score += 10
                if "apply" in text_blob:
                    score += 4
                if "button" in role or "button" in tag_blob:
                    score += 6
                if "md-button" in class_blob:
                    score += 4
                if "primary" in class_blob:
                    score += 2
                if "icon-send" in class_blob or "send" in text_blob:
                    score += 1
                if score > 0:
                    candidates.append((ref, score, text_blob))

            for value in node.values():
                candidates.extend(self._collect_apply_button_candidates(value))

        elif isinstance(node, list):
            for item in node:
                candidates.extend(self._collect_apply_button_candidates(item))

        # Deduplicate while keeping highest score per ref.
        best: Dict[str, Tuple[int, str]] = {}
        for ref, score, text in candidates:
            current = best.get(ref)
            if current is None or score > current[0]:
                best[ref] = (score, text)

        ranked = sorted(((ref, data[0], data[1]) for ref, data in best.items()), key=lambda x: x[1], reverse=True)
        return ranked

    def _collect_switch_controls(self, node: Any) -> List[Dict[str, Any]]:
        controls: List[Dict[str, Any]] = []

        if isinstance(node, dict):
            attributes = node.get("attributes") if isinstance(node.get("attributes"), dict) else {}
            subtree_blob = str(node).lower()

            text_parts: List[str] = []
            for key in ("text", "name", "label", "ariaLabel", "title"):
                value = node.get(key)
                if isinstance(value, str):
                    text_parts.append(value.strip().lower())
            text_blob = " ".join(part for part in text_parts if part)
            if not text_blob and "md-switch__label" in subtree_blob:
                text_blob = subtree_blob

            role = str(node.get("role") or attributes.get("role") or "").strip().lower()
            class_blob = " ".join(
                str(v).strip().lower() for v in (
                    node.get("class"),
                    node.get("className"),
                    attributes.get("class"),
                ) if v
            )
            formcontrol = str(
                node.get("formcontrolname")
                or node.get("formControlName")
                or attributes.get("formcontrolname")
                or attributes.get("formControlName")
                or ""
            ).strip().lower()
            if not formcontrol:
                match = re.search(r"formcontrolname[^a-z0-9_:-]+([a-z0-9_:-]+)", subtree_blob)
                if match:
                    formcontrol = match.group(1).strip().lower()

            tag_blob = " ".join(str(node.get(k) or "").strip().lower() for k in ("tag", "tagName", "nodeName"))
            input_type = str(node.get("type") or attributes.get("type") or "").strip().lower()

            checked: Optional[bool] = None
            raw_checked = node.get("checked")
            if raw_checked is None:
                raw_checked = attributes.get("checked")
            raw_aria_checked = node.get("ariaChecked")
            if raw_checked is None:
                raw_checked = node.get("aria-checked")
            if raw_checked is None:
                raw_checked = attributes.get("aria-checked")
            if raw_aria_checked is None:
                raw_aria_checked = node.get("aria_checked")
            if raw_aria_checked is None:
                raw_aria_checked = attributes.get("aria_checked")
            for candidate in (raw_checked, raw_aria_checked):
                if isinstance(candidate, bool):
                    checked = candidate
                    break
                if isinstance(candidate, str):
                    lowered = candidate.strip().lower()
                    if lowered in {"true", "checked", "on", "yes", "1"}:
                        checked = True
                        break
                    if lowered in {"false", "off", "no", "0"}:
                        checked = False
                        break

            ref = None
            for ref_key in ("ref", "stable_ref", "stableRef", "nodeRef", "id"):
                ref_value = node.get(ref_key)
                if isinstance(ref_value, str) and ref_value.strip():
                    ref = ref_value.strip()
                    break

            if ref:
                looks_like_switch = (
                    "switch" in role
                    or "md-switch" in class_blob
                    or formcontrol.startswith("ques")
                    or input_type == "checkbox"
                    or ("input" in tag_blob and "switch" in class_blob)
                    or "md-switch" in subtree_blob
                    or 'role="switch"' in subtree_blob
                    or "'role': 'switch'" in subtree_blob
                )
                if looks_like_switch:
                    controls.append(
                        {
                            "ref": ref,
                            "formcontrol": formcontrol,
                            "text": text_blob,
                            "checked": checked,
                        }
                    )

            for value in node.values():
                controls.extend(self._collect_switch_controls(value))

        elif isinstance(node, list):
            for item in node:
                controls.extend(self._collect_switch_controls(item))

        deduped: List[Dict[str, Any]] = []
        seen = set()
        for item in controls:
            ref = str(item.get("ref") or "").strip()
            if ref in seen:
                continue
            seen.add(ref)
            deduped.append(item)
        return deduped

    def _click_switch_to_value(self, tab_id: str, control: Dict[str, Any], desired_yes: bool) -> bool:
        ref = str(control.get("ref") or "").strip()
        if not ref:
            return False
        checked = control.get("checked")

        # If state is known and already desired, skip click.
        if isinstance(checked, bool) and checked == desired_yes:
            return False

        return self._mustakbil_try_click_ref(tab_id=tab_id, ref=ref)

    def _detect_mustakbil_transition(self, snapshot: Dict[str, Any]) -> Tuple[bool, str]:
        markers = [
            "apply-container",
            "apply-header",
            "wizard-step",
            "step 1 of 3",
            "confirm your eligibility",
            "question-card",
            "md-switch",
            "role=\"switch\"",
            "application progress",
        ]
        if self._snapshot_contains_any(snapshot, markers):
            return True, "Mustakbil apply wizard detected (step/switch markers present)."
        return False, ""

    def _check_mustakbil_transition(self, tab_id: str) -> Tuple[bool, str, Dict[str, Any], List[str]]:
        try:
            snapshot = self._with_tab_retry(
                lambda: self.service.snapshot(tab_id=tab_id, filter_mode="all", format_mode="compact"),
                retries=2,
            )
        except PinchTabError:
            snapshot = {}

        switch_controls = self._collect_switch_controls(snapshot)
        transitioned, reason = self._detect_mustakbil_transition(snapshot)
        if transitioned:
            return True, reason, snapshot, switch_controls

        if switch_controls:
            return True, "Switch controls detected in apply wizard.", snapshot, switch_controls

        try:
            raw_text_payload = self._with_tab_retry(
                lambda: self.service.text(tab_id=tab_id, mode="raw"),
                retries=2,
            )
            raw_text = str(raw_text_payload.get("text") or "").lower()
        except PinchTabError:
            raw_text = ""

        text_markers = [
            "step 1 of 3",
            "confirm your eligibility",
            "application progress",
            "continue",
            "qualification match",
            "experience level",
        ]
        if any(marker in raw_text for marker in text_markers):
            return True, "Apply wizard detected from raw text markers.", snapshot, switch_controls

        return False, "", snapshot, switch_controls

    def _mustakbil_try_click_ref(self, tab_id: str, ref: str) -> bool:
        try:
            self._with_tab_retry(lambda: self.service.action(tab_id=tab_id, kind="click", ref=ref), retries=2)
            return True
        except PinchTabError:
            pass

        try:
            if self.manager is not None:
                self.manager.human_click(tab_id=tab_id, ref=ref)
            else:
                self._with_tab_retry(lambda: self.service.action(tab_id=tab_id, kind="humanClick", ref=ref), retries=2)
            return True
        except PinchTabError:
            return False

    def _apply_mustakbil_flow(self, tab_id: str, materials: Dict[str, Any]) -> Dict[str, Any]:
        actions: Dict[str, Any] = {
            "apply_clicked": False,
            "apply_transition_detected": False,
            "apply_transition_reason": "",
            "question_answers_clicked": 0,
            "warnings": [],
        }

        # Phase 1: ranked button-ref clicking (more reliable for Angular nested buttons).
        try:
            apply_snapshot = self._with_tab_retry(
                lambda: self.service.snapshot(tab_id=tab_id, filter_mode="all", format_mode="compact"),
                retries=2,
            )
        except PinchTabError:
            apply_snapshot = {}

        ranked_candidates = self._collect_apply_button_candidates(apply_snapshot)
        for ref, score, text_blob in ranked_candidates[:10]:
            if score < 8:
                continue
            if not self._mustakbil_try_click_ref(tab_id=tab_id, ref=ref):
                continue
            actions["apply_clicked"] = True
            transitioned, reason, latest_snapshot, _ = self._check_mustakbil_transition(tab_id)
            if transitioned:
                actions["apply_transition_detected"] = True
                actions["apply_transition_reason"] = reason
                apply_snapshot = latest_snapshot
                break
            actions["warnings"].append(
                f"Apply ref clicked but no transition yet (score={score}, ref={ref}, text='{text_blob[:80]}')."
            )
            time.sleep(0.8)

        # Phase 2: semantic query clicking fallback.
        if not actions["apply_transition_detected"]:
            for query in (
                "Apply Now",
                "apply now",
                "Apply",
                "button Apply Now",
                "Apply Now button",
                "send Apply Now",
                "icon send Apply Now",
                "md-button primary Apply Now",
            ):
                if not self._click_if_found(tab_id, query):
                    continue
                actions["apply_clicked"] = True
                transitioned, reason, latest_snapshot, _ = self._check_mustakbil_transition(tab_id)
                if transitioned:
                    actions["apply_transition_detected"] = True
                    actions["apply_transition_reason"] = reason
                    apply_snapshot = latest_snapshot
                    break
                time.sleep(0.8)

        if not actions["apply_clicked"]:
            actions["warnings"].append("Could not find 'Apply Now' button on Mustakbil page.")
            return actions

        # Mustakbil often renders screening questions with a delay after Apply Now.
        # Poll briefly so we don't miss toggle buttons that appear asynchronously.
        toggle_snapshot: Dict[str, Any] = apply_snapshot if isinstance(apply_snapshot, dict) else {}
        yes_refs: List[str] = []
        no_refs: List[str] = []
        switch_controls: List[Dict[str, Any]] = []
        wait_deadline = time.time() + 10.0
        while time.time() < wait_deadline:
            transitioned, reason, toggle_snapshot, _ = self._check_mustakbil_transition(tab_id)
            switch_controls = self._collect_switch_controls(toggle_snapshot)
            if transitioned:
                actions["apply_transition_detected"] = True
                actions["apply_transition_reason"] = reason

            yes_refs = self._collect_toggle_refs(toggle_snapshot, "yes")
            no_refs = self._collect_toggle_refs(toggle_snapshot, "no")
            if yes_refs or no_refs or switch_controls:
                if not actions["apply_transition_reason"]:
                    actions["apply_transition_reason"] = "Apply wizard controls detected after Apply Now click."
                break

            time.sleep(1.0)

        # If the first click did not transition, retry top ranked button-like refs.
        if not actions["apply_transition_detected"]:
            ranked_candidates = self._collect_apply_button_candidates(toggle_snapshot)
            for ref, score, _ in ranked_candidates[:6]:
                if score < 8:
                    continue
                if not self._mustakbil_try_click_ref(tab_id=tab_id, ref=ref):
                    continue
                time.sleep(1.2)
                try:
                    retry_snapshot = self._with_tab_retry(
                        lambda: self.service.snapshot(tab_id=tab_id, filter_mode="all", format_mode="compact"),
                        retries=2,
                    )
                except PinchTabError:
                    retry_snapshot = {}

                transitioned, reason = self._detect_mustakbil_transition(retry_snapshot)
                switch_controls_retry = self._collect_switch_controls(retry_snapshot)
                if transitioned or switch_controls_retry:
                    actions["apply_transition_detected"] = True
                    actions["apply_transition_reason"] = reason or "Transition detected after ranked re-click."
                    toggle_snapshot = retry_snapshot
                    break

        screening_answers = materials.get("screening_answers") or {}
        if not screening_answers:
            # Default behavior for Mustakbil eligibility wizard is to set known toggles to Yes.
            screening_answers = {"ques1": "yes", "ques2": "yes"}

        form_agent = MustakbilFormAgent(service=self.service, manager=self.manager)
        agent_result = form_agent.process_step(tab_id=tab_id, answer_map=screening_answers)
        if int(agent_result.get("switches_changed") or 0) > 0:
            actions["question_answers_clicked"] = int(agent_result.get("switches_changed") or 0)
            if not actions.get("apply_transition_reason"):
                actions["apply_transition_reason"] = "Mustakbil form agent processed switch controls."
        actions["warnings"].extend(agent_result.get("warnings") or [])

        explicit_answers = 0
        for question, answer in screening_answers.items():
            choice = str(answer).strip().lower()
            if choice in {"true", "1", "yes", "y"}:
                choice = "yes"
            elif choice in {"false", "0", "no", "n"}:
                choice = "no"
            if choice not in {"yes", "no"}:
                continue
            if self._click_if_found(tab_id, f"{question} {choice}"):
                explicit_answers += 1

        if explicit_answers:
            actions["question_answers_clicked"] = explicit_answers
            return actions

        if not (yes_refs or no_refs or switch_controls):
            try:
                toggle_snapshot = self._with_tab_retry(
                    lambda: self.service.snapshot(tab_id=tab_id, filter_mode="all", format_mode="compact"),
                    retries=2,
                )
            except PinchTabError:
                toggle_snapshot = {}
            yes_refs = self._collect_toggle_refs(toggle_snapshot, "yes")
            no_refs = self._collect_toggle_refs(toggle_snapshot, "no")
            switch_controls = self._collect_switch_controls(toggle_snapshot)
        clicked_refs = set()
        toggle_refs_to_click = list(yes_refs)
        if not toggle_refs_to_click and no_refs:
            # Mustakbil switch controls often show "No" label by default;
            # clicking it toggles the underlying checkbox to Yes.
            toggle_refs_to_click = list(no_refs)
            actions["warnings"].append("Using 'No' switch label refs to toggle answers to Yes.")

        for ref in toggle_refs_to_click:
            if ref in clicked_refs:
                continue
            try:
                if self.manager is not None:
                    self.manager.human_click(tab_id=tab_id, ref=ref)
                else:
                    self._with_tab_retry(lambda: self.service.action(tab_id=tab_id, kind="humanClick", ref=ref))
                clicked_refs.add(ref)
            except PinchTabError:
                continue

        # Mustakbil uses role="switch" checkbox controls (ques1, ques2...).
        # Set switches to desired yes/no using screening answers when provided.
        answer_map = materials.get("screening_answers") or {}
        for control in switch_controls:
            ref = str(control.get("ref") or "").strip()
            if not ref or ref in clicked_refs:
                continue

            control_key = str(control.get("formcontrol") or "").strip().lower()
            control_text = str(control.get("text") or "").strip().lower()

            desired_yes = True  # default requested behavior
            for key, value in answer_map.items():
                key_norm = str(key).strip().lower()
                value_norm = str(value).strip().lower()
                if value_norm in {"true", "1", "yes", "y"}:
                    desired = True
                elif value_norm in {"false", "0", "no", "n"}:
                    desired = False
                else:
                    continue

                if key_norm and (
                    key_norm == control_key
                    or (control_key and key_norm in control_key)
                    or (control_text and key_norm in control_text)
                ):
                    desired_yes = desired
                    break

            try:
                changed = self._click_switch_to_value(tab_id=tab_id, control=control, desired_yes=desired_yes)
                if changed:
                    clicked_refs.add(ref)
            except PinchTabError:
                continue

        actions["question_answers_clicked"] = len(clicked_refs)
        if actions["apply_clicked"] and not actions["apply_transition_detected"]:
            actions["warnings"].append(
                "Apply click was acknowledged, but no transition to screening state was detected. "
                "This usually means a non-actionable element was clicked or the site blocked progression."
            )
        if not clicked_refs:
            actions["warnings"].append("No screening switch/toggle controls were auto-detected on Mustakbil apply flow.")
        return actions

    def _with_tab_retry(self, call, retries: int = 4, delay_sec: float = 0.75):
        """Retry short-lived PinchTab tab lookup races after navigation."""
        last_exc: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                return call()
            except PinchTabError as exc:
                msg = str(exc).lower()
                last_exc = exc
                if "tab" in msg and "not found" in msg and attempt < retries:
                    time.sleep(delay_sec)
                    continue
                raise
        if last_exc:
            raise last_exc

    def fill_application(
        self,
        job_url: str,
        job_board: str,
        materials: Dict[str, Any],
        user_profile: Dict[str, Any],
        instance_id: Optional[str] = None,
        tab_id: Optional[str] = None,
        require_preauth: bool = True,
    ) -> Dict[str, Any]:
        """Fill common fields and produce screenshot evidence for HITL review."""
        if not job_url:
            return {"error": "Job URL is missing."}

        try:
            self.service.health()
            self.manager = BrowserManager(board=job_board)

            session: Dict[str, Any] = {}
            provided_instance = bool(instance_id)
            if not instance_id:
                session = self.manager.ensure_session(user_profile=user_profile, rotate_ip=True)
                instance_id = session.get("instance_id")

            if tab_id:
                try:
                    nav = self.manager.navigate(
                        instance_id=instance_id,
                        url=job_url,
                        tab_id=tab_id,
                        new_tab=False,
                    )
                    tab_id = nav.get("tab_id")
                except PinchTabError as tab_nav_exc:
                    tab_nav_msg = str(tab_nav_exc).lower()
                    if "tab" in tab_nav_msg and "not found" in tab_nav_msg:
                        tab_id = None
                    else:
                        raise

            if not tab_id:
                try:
                    nav = self.manager.navigate(instance_id=instance_id, url=job_url)
                    tab_id = nav.get("tab_id")
                except PinchTabError as nav_exc:
                    nav_msg = str(nav_exc).lower()
                    can_recover = (
                        ("context canceled" in nav_msg or "context deadline exceeded" in nav_msg)
                        and not provided_instance
                        and bool(instance_id)
                    )
                    if not can_recover:
                        raise

                    # Recover once from stale browser context by recreating session.
                    self.manager.stop_session(str(instance_id))
                    session = self.manager.ensure_session(user_profile=user_profile, rotate_ip=False)
                    instance_id = session.get("instance_id")
                    nav = self.manager.navigate(instance_id=instance_id, url=job_url)
                    tab_id = nav.get("tab_id")

            # Auth validation is intentionally skipped for mirrored-profile mode.
            # The session is assumed to be pre-authenticated when PinchTab starts.

            fields_filled = {
                "name": False,
                "email": False,
                "phone": False,
                "location": False,
                "cover_letter": False,
            }

            full_name = user_profile.get("name") or ""
            email = user_profile.get("email") or ""
            phone = user_profile.get("phone") or ""
            location = user_profile.get("location") or ""
            cover_letter = materials.get("cover_letter") or ""

            fields_filled["name"] = self._fill_if_found(tab_id, "full name", full_name)
            fields_filled["email"] = self._fill_if_found(tab_id, "email", email)
            fields_filled["phone"] = self._fill_if_found(tab_id, "phone", phone)
            fields_filled["location"] = self._fill_if_found(tab_id, "location", location)
            fields_filled["cover_letter"] = self._fill_if_found(tab_id, "cover letter", cover_letter)

            board_actions: Dict[str, Any] = {}
            board_warnings: List[str] = []
            if (job_board or "").lower() == "mustakbil":
                board_actions = self._apply_mustakbil_flow(tab_id=tab_id, materials=materials)
                board_warnings = board_actions.pop("warnings", []) if isinstance(board_actions, dict) else []

            # Keep an interactive snapshot for debugging and observability.
            try:
                self._with_tab_retry(lambda: self.service.snapshot_interactive(tab_id=tab_id), retries=2)
            except PinchTabError:
                pass

            screenshot = self._with_tab_retry(lambda: self.service.screenshot_bytes(tab_id=tab_id), retries=2)
            screenshot_path = self._save_screenshot(screenshot, job_board)

            return {
                "status": "filled",
                "fields_filled": fields_filled,
                "screenshot_path": screenshot_path,
                "instance_id": instance_id,
                "tab_id": tab_id,
                "proxy_rotated": bool(session.get("proxy_rotated")),
                "proxy_server": session.get("proxy_server"),
                "board_actions": board_actions,
                "warnings": (
                    [] if any(fields_filled.values()) else ["No known fields auto-filled."]
                ) + board_warnings,
            }

        except PinchTabError as exc:
            msg = str(exc)
            if "context canceled" in msg.lower() or "context deadline exceeded" in msg.lower():
                return {
                    "error": (
                        "PinchTab could not create a browser tab (context timeout). "
                        "Retry with an already-authenticated session or restart PinchTab and retry."
                    ),
                    "diagnostic": msg,
                }
            return {"error": msg}
        except Exception as exc:  # pragma: no cover - defensive safety net
            return {"error": f"Unexpected browser tool failure: {exc}"}

    def submit_application(self, job_id: str) -> Dict[str, Any]:
        """v1 intentionally disables auto-submit for safety."""
        return {
            "error": "Auto-submit is disabled in v1. Manual submission is required.",
            "job_id": job_id,
            "status": "manual_required",
        }
