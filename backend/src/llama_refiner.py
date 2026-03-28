import json
import os
import re
import time
from typing import Any, Dict, List, Optional


SCHEMA: Dict[str, Any] = {
    "education": [
        {"degree": "", "institution": "", "duration": "", "location": ""}
    ],
    "experience": [
        {"role": "", "company": "", "duration": "", "location": "", "description": ""}
    ]
}


SYSTEM_PROMPT = (
    "You are a precise resume data extraction AI. Your output must be valid JSON matching the schema below.\n\n"

    "STEP 1 — INTERNAL SCRATCHPAD (mandatory before writing any JSON):\n"
    "PDF extraction scrambles multi-column layouts. Follow this exact process:\n"
    "  A. Extract every (job title, company) pair IN ORDER of appearance.\n"
    "  B. Extract every (date range, location) pair IN ORDER of appearance.\n"
    "     CRITICAL: Date and location are ALWAYS paired together in the PDF column. Extract them as a unit, never separately.\n"
    "     Example unit: ('Feb 2025 - Jul 2025', 'Islamabad, Pakistan')\n"
    "  C. Match sequentially: 1st job pair → 1st date/location unit, 2nd job pair → 2nd unit, etc.\n"
    "  D. Before writing JSON, list your matches explicitly:\n"
    "     Job 1: [title] at [company] | [date] | [location]\n"
    "     Job 2: [title] at [company] | [date] | [location]\n"
    "     ...and so on.\n"
    "  E. Check: does any (date, location) unit appear more than once in your list? If yes, you have a mapping error. Fix it before proceeding.\n\n"

    "HARD RULES:\n"
    "1. DATE AND LOCATION ARE A UNIT: Never assign a date from one (date, location) pair with the location from a different pair. They travel together.\n"
    "2. ONE ENTRY PER JOB: Same company appearing twice in output is always wrong.\n"
    "3. NO DATE COPYING: Same date range assigned to two different jobs is always wrong.\n"
    "4. NO GHOST ENTRIES: No experience entry without a matching job title.\n"
    "5. NO FABRICATION: Missing fields get an empty string.\n"
    "6. OUTPUT FORMAT: Valid JSON only. No markdown, no commentary.\n\n"

    "Schema:\n"
    + json.dumps(SCHEMA, indent=2)
)

def build_user_prompt(resume_text: str) -> str:
    prompt = (
        "Resume Text:\n====\n"
        f"{resume_text}\n"
        "====\n\n"
        "Return ONLY the JSON strictly following the schema above.\n"
        "Ensure the JSON is syntactically valid and contains no commentary or markdown formatting."
    )
    return prompt


def _deep_merge_schema(default_schema: Any, data: Any) -> Any:
    if isinstance(default_schema, dict):
        result = {}
        data = data if isinstance(data, dict) else {}
        for key, default_value in default_schema.items():
            result[key] = _deep_merge_schema(default_value, data.get(key))
        return result
    if isinstance(default_schema, list):
        # If the schema expects a list, ensure the item shape is respected
        if not isinstance(data, list):
            return default_schema if default_schema else []
        if not default_schema:
            return data
        item_schema = default_schema[0]
        normalized_list = []
        for item in data:
            normalized_list.append(_deep_merge_schema(item_schema, item))
        return normalized_list
    # Primitive
    if data is None:
        return default_schema
    return data


def _extract_json(text: str) -> Any:
    """
    Extract the first valid top-level JSON object or array from arbitrary model output.
    - Handles extra prose before/after JSON
    - Handles code fences
    - Returns parsed Python object (dict or list)
    """
    raw = text.strip()
    # Remove code fences (start/end)
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```\s*$", "", raw)

    # Find first JSON opener ('{' or '['), whichever appears first
    brace_pos = raw.find('{')
    bracket_pos = raw.find('[')
    if brace_pos == -1 and bracket_pos == -1:
        # No obvious JSON - try direct parse (may raise)
        return json.loads(raw)

    if brace_pos == -1 or (bracket_pos != -1 and bracket_pos < brace_pos):
        start_pos = bracket_pos
        opener, closer = '[', ']'
    else:
        start_pos = brace_pos
        opener, closer = '{', '}'

    # Scan to find the matching closer using a simple stack, respecting strings
    depth = 0
    i = start_pos
    in_string = False
    escape = False
    while i < len(raw):
        ch = raw[i]
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    snippet = raw[start_pos:i+1]
                    break
        i += 1
    else:
        # Fallback: could not balance, try to parse the whole tail
        snippet = raw[start_pos:]

    # First attempt
    try:
        return json.loads(snippet)
    except Exception:
        # Attempt to remove trailing commas inside objects/arrays
        snippet2 = re.sub(r",\s*([}\]])", r"\1", snippet)
        try:
            return json.loads(snippet2)
        except Exception:
            pass

    # Fallback: iterate over all potential JSON starts and try balanced parse
    starts: List[int] = [m.start() for m in re.finditer(r"[\[{]", raw)]
    for s in starts:
        # determine opener/closer at s
        ch = raw[s]
        opener, closer = ('{', '}') if ch == '{' else ('[', ']')
        depth = 0
        i = s
        in_string = False
        escape = False
        while i < len(raw):
            c = raw[i]
            if in_string:
                if escape:
                    escape = False
                elif c == '\\':
                    escape = True
                elif c == '"':
                    in_string = False
            else:
                if c == '"':
                    in_string = True
                elif c == opener:
                    depth += 1
                elif c == closer:
                    depth -= 1
                    if depth == 0:
                        candidate = raw[s:i+1]
                        try:
                            return json.loads(candidate)
                        except Exception:
                            # try trailing-comma cleanup
                            candidate2 = re.sub(r",\s*([}\]])", r"\1", candidate)
                            try:
                                return json.loads(candidate2)
                            except Exception:
                                break
            i += 1

    # Last resort
    return json.loads(raw)


class LlamaRefiner:
    def __init__(
        self,
        backend: str = "ollama",  # 'ollama' | 'lmstudio' | 'openai_compat' | 'huggingface'
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.2,
        max_new_tokens: int = 800,
        request_timeout_s: float = 60.0,
    ) -> None:
        self.backend = backend
        self.model = model or (
            "llama3:8b-instruct-q4_K_M" if backend == "ollama" else ""
        )
        self.base_url = base_url or (
            (("http://localhost:11434" if backend == "ollama" else "http://localhost:11434/v1")
            if backend in {"ollama", "openai_compat"}
            else "http://localhost:1234/v1")
        )
        self.temperature = temperature
        self.max_new_tokens = max_new_tokens
        self.request_timeout_s = request_timeout_s

        # Lazy init for HF
        self._hf_pipeline = None
        self._hf_tokenizer = None
        self._hf_model = None

    def refine_resume(self, resume_text: str) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(resume_text)},
        ]

        # Debug: print final messages being sent
        try:
            print("\n==== LLM MESSAGES (system + user) ====", flush=True)
            print(json.dumps(messages, indent=2, ensure_ascii=False), flush=True)
        except Exception:
            pass

        if self.backend in {"lmstudio", "openai_compat"}:
            raw = self._call_openai_compatible(messages)
        elif self.backend == "ollama":
            # Prefer native Ollama API; fallback to OpenAI-compatible if available
            try:
                raw = self._call_ollama_native(messages)
            except Exception:
                raw = self._call_openai_compatible(messages)
        elif self.backend == "huggingface":
            raw = self._call_huggingface(messages)
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

        # Debug: print raw model output
        try:
            print("\n==== LLM RAW OUTPUT ====", flush=True)
            # Trim to avoid flooding terminal
            print((raw[:4000] + ('... [truncated]' if len(raw) > 4000 else '')), flush=True)
        except Exception:
            pass

        try:
            parsed = _extract_json(raw)
        except Exception as e:
            raise RuntimeError(f"Model did not return valid JSON: {e}\nRaw: {raw[:300]}")

        # Normalize to schema
        # If schema has exactly one top-level array key and model returned a bare array, wrap it
        if isinstance(parsed, list) and isinstance(SCHEMA, dict) and len(SCHEMA) == 1:
            only_key = next(iter(SCHEMA.keys()))
            parsed = { only_key: parsed }
        normalized = _deep_merge_schema(SCHEMA, parsed)

        # Post-process: remove ghost entries — entries where the LLM extracted a stray
        # date range but left company+role (or institution+degree) both empty.
        exp_list = normalized.get("experience", [])
        normalized["experience"] = [
            e for e in exp_list
            if (e.get("company", "").strip() or e.get("role", "").strip())
        ]
        edu_list = normalized.get("education", [])
        normalized["education"] = [
            e for e in edu_list
            if (e.get("institution", "").strip() or e.get("degree", "").strip())
        ]

        return normalized

    # --- Backends ---
    def _call_openai_compatible(self, messages: List[Dict[str, str]]) -> str:
        import requests  # local dep

        url = f"{self.base_url.rstrip('/')}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            # Use SambaNova key if set, otherwise fall back to OPENAI_API_KEY
            "Authorization": f"Bearer {os.environ.get('SAMBANOVA_API_KEY') or os.environ.get('OPENAI_API_KEY', 'sk-no-key')}",
        }

        payload: Dict[str, Any] = {
            "model": self.model or "llama3:8b-instruct-q4_K_M",
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_new_tokens,
        }

        # Prefer JSON mode when supported (OpenAI-style)
        payload["response_format"] = {"type": "json_object"}

        # Debug: print full HTTP request
        try:
            print("\n==== LLM HTTP (OpenAI-compatible) URL ====", flush=True)
            print(url, flush=True)
            print("\n==== LLM HTTP (OpenAI-compatible) Payload ====", flush=True)
            print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)
        except Exception:
            pass

        max_attempts = 5
        last_resp = None
        current_payload = payload

        for attempt in range(1, max_attempts + 1):
            resp = requests.post(url, headers=headers, json=current_payload, timeout=self.request_timeout_s)
            last_resp = resp

            if resp.status_code == 404 and "11434" in self.base_url:
                return self._call_ollama_native(messages)

            if resp.status_code == 400 and "response_format" in current_payload:
                print("[LLM] 400 with response_format — retrying without it", flush=True)
                current_payload = {k: v for k, v in current_payload.items() if k != "response_format"}
                resp = requests.post(url, headers=headers, json=current_payload, timeout=self.request_timeout_s)
                last_resp = resp

            if resp.status_code == 429:
                delay = attempt * 3  # 3s, 6s, 9s, 12s delay
                print(f"[LLM] 429 Too Many Requests (attempt {attempt}/{max_attempts}) — retrying in {delay}s", flush=True)
                if attempt < max_attempts:
                    time.sleep(delay)
                continue

            if resp.status_code >= 500:
                print(f"[LLM] {resp.status_code} server error (attempt {attempt}/{max_attempts}) — retrying in 2s", flush=True)
                if attempt < max_attempts:
                    time.sleep(2)
                continue

            resp.raise_for_status()
            data = resp.json()
            if "choices" not in data:
                raise RuntimeError(
                    f"Unexpected API response (no 'choices'): {str(data)[:300]}"
                )
            return data["choices"][0]["message"]["content"]

        # All retries exhausted — raise the last response error
        last_resp.raise_for_status()


    def _call_ollama_native(self, messages: List[Dict[str, str]]) -> str:
        import requests

        # Ensure base without /v1
        base = self.base_url
        if base.endswith("/v1"):
            base = base[:-3]
        url = f"{base.rstrip('/')}/api/chat"

        payload: Dict[str, Any] = {
            "model": self.model or "llama3:8b-instruct-q4_K_M",
            "messages": messages,
            "stream": False,
            # Don't force JSON format - it causes 500 errors with complex prompts
            # "format": "json",  # REMOVED - causes Ollama to fail on large/complex inputs
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_new_tokens,
                "keep_alive": "5m",
            },
        }

        # Debug: print full HTTP request
        try:
            print("\n==== LLM HTTP (Ollama /api/chat) URL ====", flush=True)
            print(url, flush=True)
            print("\n==== LLM HTTP (Ollama /api/chat) Payload ====", flush=True)
            print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)
        except Exception:
            pass

        try:
            resp = requests.post(url, json=payload, timeout=self.request_timeout_s)
            resp.raise_for_status()
        except requests.HTTPError as e:
            # Log the actual error from Ollama
            error_body = ""
            try:
                error_body = resp.text if resp else ""
                print(f"\n==== OLLAMA ERROR ====", flush=True)
                print(f"Status: {resp.status_code if resp else 'N/A'}", flush=True)
                print(f"Body: {error_body}", flush=True)
            except Exception:
                pass
            
            if resp.status_code == 404:
                # Older Ollama versions: use /api/generate fallback
                try:
                    return self._call_ollama_generate(messages)
                except Exception as gen_error:
                    raise RuntimeError(f"Ollama /api/chat failed (404) and /api/generate also failed: {gen_error}")
            
            raise RuntimeError(f"{e} - Ollama response: {error_body[:500]}")
        
        data = resp.json()
        # Ollama returns { message: { role, content }, done: true }
        if isinstance(data, dict) and data.get("message", {}).get("content"):
            return data["message"]["content"]
        # Some versions may return stream chunks as a list
        if isinstance(data, list):
            contents = [ch.get("message", {}).get("content", "") for ch in data]
            return "".join(contents)
        raise RuntimeError("Unexpected Ollama response format")

    def _render_messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        parts: List[str] = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                parts.append("System:\n" + content)
            elif role == "user":
                parts.append("User:\n" + content)
            else:
                parts.append("Assistant:\n" + content)
        parts.append("Assistant:")
        return "\n\n".join(parts)

    def _call_ollama_generate(self, messages: List[Dict[str, str]]) -> str:
        import requests

        base = self.base_url
        if base.endswith("/v1"):
            base = base[:-3]
        url = f"{base.rstrip('/')}/api/generate"

        prompt = self._render_messages_to_prompt(messages)

        payload: Dict[str, Any] = {
            "model": self.model or "llama3:8b-instruct-q4_K_M",
            "prompt": prompt,
            "stream": False,
            # Don't force JSON format - same issue as /api/chat
            # "format": "json",  # REMOVED
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_new_tokens,
                "keep_alive": "5m",
            },
        }

        # Debug: print full HTTP request with rendered prompt
        try:
            print("\n==== LLM HTTP (Ollama /api/generate) URL ====", flush=True)
            print(url, flush=True)
            print("\n==== LLM PROMPT (rendered) ====", flush=True)
            print(prompt, flush=True)
            print("\n==== LLM HTTP (Ollama /api/generate) Options ====", flush=True)
            print(json.dumps(payload.get("options", {}), indent=2, ensure_ascii=False), flush=True)
        except Exception:
            pass

        try:
            resp = requests.post(url, json=payload, timeout=self.request_timeout_s)
            resp.raise_for_status()
        except Exception as e:
            body = resp.text if hasattr(resp, 'text') else ''
            print(f"\n==== OLLAMA /api/generate ERROR ====", flush=True)
            print(f"Error: {e}", flush=True)
            print(f"Body: {body[:500]}", flush=True)
            raise RuntimeError(f"{e} Body: {body[:500]}")
            
        data = resp.json()
        # /api/generate returns { response: "...", done: true }
        if isinstance(data, dict) and data.get("response") is not None:
            return data["response"]
        raise RuntimeError("Unexpected Ollama /api/generate response format")

    def _call_huggingface(self, messages: List[Dict[str, str]]) -> str:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        model_id = self.model or "meta-llama/Meta-Llama-3-8B-Instruct"
        if self._hf_model is None:
            self._hf_tokenizer = AutoTokenizer.from_pretrained(model_id)
            self._hf_model = AutoModelForCausalLM.from_pretrained(
                model_id,
                torch_dtype=torch.float16 if torch.cuda.is_available() else None,
                device_map="auto",
            )

        tokenizer = self._hf_tokenizer
        model = self._hf_model

        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                temperature=self.temperature,
                do_sample=False,
            )
        text = tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Extract only the assistant's last turn if template includes prior text
        # Try to get JSON body
        return text.split("</s>")[-1].strip()


# Convenience functional API — Education + Experience
def refine_resume(
    resume_text: str,
    backend: str = "ollama",
    model: Optional[str] = "llama3:8b-instruct-q4_K_M",
    base_url: Optional[str] = "http://localhost:11434",
    temperature: float = 0.1,
    max_new_tokens: int = 1500,
    request_timeout_s: float = 300.0,
) -> Dict[str, Any]:
    ref = LlamaRefiner(
        backend=backend,
        model=model,
        base_url=base_url,
        temperature=temperature,
        max_new_tokens=max_new_tokens,
        request_timeout_s=request_timeout_s,
    )
    return ref.refine_resume(resume_text)


# ─────────────────────────────────────────────────────────────
# PROJECTS — separate schema, prompt, and convenience function
# ─────────────────────────────────────────────────────────────

PROJECTS_SCHEMA: Dict[str, Any] = {
    "projects": [
        {"name": "", "description": "", "link": ""}
    ]
}

PROJECTS_SYSTEM_PROMPT = (
    "You are an expert information extraction system that converts raw resume text into a standardized JSON format.\n"
    "You will receive ONLY the Projects section from a resume.\n\n"
    "CRITICAL REQUIREMENTS:\n"
    "- Extract EVERY project listed. Do not skip any.\n"
    "- 'name' is REQUIRED — the project title.\n"
    "- 'description' is REQUIRED — a concise summary of what the project does/did. Preserve technical details.\n"
    "- 'link' is OPTIONAL — only fill if a URL (GitHub, live demo, etc.) is explicitly present next to this project. Leave empty string otherwise.\n"
    "- Never fabricate project names, descriptions, or links not present in the input.\n"
    "- Output ONLY a single top-level JSON value matching the schema (no prose, no markdown, no extra characters).\n\n"
    "Schema:\n"
    + json.dumps(PROJECTS_SCHEMA, indent=2) +
    "\n\nREMEMBER: Extract ALL projects with complete name and description."
)


def _build_projects_user_prompt(projects_text: str) -> str:
    return (
        "Projects Section Text:\n====\n"
        f"{projects_text}\n"
        "====\n\n"
        "Return ONLY the JSON strictly following the schema above.\n"
        "Ensure the JSON is syntactically valid and contains no commentary or markdown formatting."
    )


def refine_projects(
    projects_text: str,
    backend: str = "ollama",
    model: Optional[str] = "llama3:8b-instruct-q4_K_M",
    base_url: Optional[str] = "http://localhost:11434",
    temperature: float = 0.1,
    max_new_tokens: int = 1200,
    request_timeout_s: float = 300.0,
) -> List[Dict[str, str]]:
    """
    Extract structured project entries from the Projects section text.
    Returns a list of {name, description, link} dicts.
    """
    if not projects_text or not projects_text.strip():
        return []

    # Cap input to avoid exceeding SambaNova's context/response_format limits.
    # 4000 chars covers ~10-15 projects comfortably.
    PROJECTS_CHAR_LIMIT = 4000
    if len(projects_text) > PROJECTS_CHAR_LIMIT:
        print(
            f"[PROJECTS LLM] Projects text truncated from {len(projects_text)} "
            f"to {PROJECTS_CHAR_LIMIT} chars to stay within API limits.",
            flush=True,
        )
        projects_text = projects_text[:PROJECTS_CHAR_LIMIT]

    ref = LlamaRefiner(
        backend=backend,
        model=model,
        base_url=base_url,
        temperature=temperature,
        max_new_tokens=2000,
        request_timeout_s=request_timeout_s,
    )

    messages = [
        {"role": "system", "content": PROJECTS_SYSTEM_PROMPT},
        {"role": "user", "content": _build_projects_user_prompt(projects_text)},
    ]

    print("\n==== [PROJECTS LLM] Sending request ====", flush=True)

    if ref.backend in {"lmstudio", "openai_compat"}:
        raw = ref._call_openai_compatible(messages)
    elif ref.backend == "ollama":
        try:
            raw = ref._call_ollama_native(messages)
        except Exception:
            raw = ref._call_openai_compatible(messages)
    else:
        raise ValueError(f"Unsupported backend: {ref.backend}")

    print("\n==== [PROJECTS LLM] Raw output ====", flush=True)
    print(raw[:3000] + ("... [truncated]" if len(raw) > 3000 else ""), flush=True)

    try:
        parsed = _extract_json(raw)
    except Exception as e:
        raise RuntimeError(f"Projects LLM did not return valid JSON: {e}\nRaw: {raw[:300]}")

    # Normalise
    if isinstance(parsed, list):
        parsed = {"projects": parsed}
    normalized = _deep_merge_schema(PROJECTS_SCHEMA, parsed)

    # Strip ghost entries (no name and no description)
    projects = normalized.get("projects", [])
    projects = [
        p for p in projects
        if (p.get("name", "").strip() or p.get("description", "").strip())
    ]
    return projects