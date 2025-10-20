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
    "You are an expert information extraction system that converts raw resume text into a standardized JSON format.\n"
    "You will receive ONLY the Education and Experience sections from a resume.\n\n"
    "Your tasks:\n"
    "- Extract fields strictly following the schema provided below.\n"
    "- If a field is not present, leave it as an empty string.\n"
    "- Remove irrelevant or repeated data.\n"
    "- Never fabricate data such as companies, roles, degrees, or dates that are not present in the input.\n"
    "- Preserve the JSON structure exactly as defined below.\n"
    "- Output ONLY a single top-level JSON value matching the schema (no prose, no markdown, no extra characters before or after).\n\n"
    "Schema:\n"
    + json.dumps(SCHEMA, indent=2)
)


def build_user_prompt(resume_text: str, ner_json: Optional[Dict[str, Any]] = None) -> str:
    prompt = (
        "Resume Text:\n====\n"
        f"{resume_text}\n"
        "====\n\n"
        "Return ONLY the JSON strictly following the schema above.\n"
        "Ensure the JSON is syntactically valid and contains no commentary or markdown formatting."
    )
    # Don't append NER hints - we're not using them anymore
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
            "llama3:latest" if backend == "ollama" else ""
        )
        self.base_url = base_url or (
            ("http://localhost:11434" if backend == "ollama" else "http://localhost:11434/v1")
            if backend in {"ollama", "openai_compat"}
            else "http://localhost:1234/v1"
        )
        self.temperature = temperature
        self.max_new_tokens = max_new_tokens
        self.request_timeout_s = request_timeout_s

        # Lazy init for HF
        self._hf_pipeline = None
        self._hf_tokenizer = None
        self._hf_model = None

    def refine_resume(self, resume_text: str, ner_output: Dict[str, Any]) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(resume_text, ner_output)},
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
        return normalized

    # --- Backends ---
    def _call_openai_compatible(self, messages: List[Dict[str, str]]) -> str:
        import requests  # local dep

        url = f"{self.base_url.rstrip('/')}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            # LM Studio/Ollama usually ignore auth; keep optional support
            "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', 'sk-no-key')}",
        }

        payload: Dict[str, Any] = {
            "model": self.model or "llama3:latest",
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

        resp = requests.post(url, headers=headers, json=payload, timeout=self.request_timeout_s)
        if resp.status_code == 404 and "11434" in self.base_url:
            # Likely talking to Ollama without OpenAI proxy; fallback to native API
            return self._call_ollama_native(messages)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        return text

    def _call_ollama_native(self, messages: List[Dict[str, str]]) -> str:
        import requests

        # Ensure base without /v1
        base = self.base_url
        if base.endswith("/v1"):
            base = base[:-3]
        url = f"{base.rstrip('/')}/api/chat"

        payload: Dict[str, Any] = {
            "model": self.model or "llama3:latest",
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
            "model": self.model or "llama3:latest",
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


# Convenience functional API
def refine_resume(
    resume_text: str,
    ner_output: Dict[str, Any],
    backend: str = "ollama",
    model: Optional[str] = "llama3:latest",
    base_url: Optional[str] = "http://localhost:11434",
    temperature: float = 0.1,
    max_new_tokens: int = 1200,
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
    return ref.refine_resume(resume_text, ner_output)




