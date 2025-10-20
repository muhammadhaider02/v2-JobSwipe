import re
from typing import Dict, List, Tuple


SECTION_ALIASES = {
    'Profile': [
        r"^profile$", r"^summary$", r"^professional summary$", r"^about me$",
        r"^objective$", r"^career objective$", r"^overview$"
    ],
    'Experience': [
        r"^experience$", r"^work experience$", r"^professional experience$",
        r"^employment history$", r"^work history$", r"^work$"
    ],
    'Education': [
        r"^education$", r"^academics$", r"^academic background$", r"^academic qualifications$",
        r"^qualifications$", r"^education & certifications$"
    ],
    'Skills': [
        r"^skills$", r"^technical skills$", r"^skills & competencies$", r"^core competencies$",
        r"^tooling$", r"^technologies$", r"^tech stack$", r"^skills & interests$"
    ],
    'Projects': [
        r"^projects$", r"^personal projects$", r"^academic projects$", r"^selected projects$",
        r"^notable projects$", r"^project experience$"
    ],
}


def _compile_section_regex() -> List[Tuple[str, re.Pattern]]:
    compiled: List[Tuple[str, re.Pattern]] = []
    for canonical, patterns in SECTION_ALIASES.items():
        for pat in patterns:
            compiled.append((
                canonical,
                re.compile(rf"\n?\s*{pat}\s*:?\s*$", re.IGNORECASE | re.MULTILINE)
            ))
    return compiled


SECTION_HEADERS = _compile_section_regex()


def _find_headers(text: str) -> List[Tuple[int, str]]:
    positions: List[Tuple[int, str]] = []
    for canonical, pattern in SECTION_HEADERS:
        for m in pattern.finditer(text):
            positions.append((m.start(), canonical))
    positions.sort(key=lambda x: x[0])
    return positions


def split_resume_into_sections(text: str) -> Dict[str, str]:
    if not text:
        return {'Profile': '', 'Experience': '', 'Education': '', 'Skills': '', 'Projects': '' }

    normalized_text = text.replace('\r\n', '\n')
    headers = _find_headers(normalized_text)

    # If no explicit headers, use heuristics: treat entire text as Profile
    if not headers:
        return {
            'Profile': normalized_text.strip(),
            'Experience': '',
            'Education': '',
            'Skills': '',
            'Projects': ''
        }

    # Build ranges between headers
    ranges: List[Tuple[str, int, int]] = []
    for i, (start_idx, canonical) in enumerate(headers):
        end_idx = headers[i + 1][0] if i + 1 < len(headers) else len(normalized_text)
        ranges.append((canonical, start_idx, end_idx))

    sections: Dict[str, List[str]] = {'Profile': [], 'Experience': [], 'Education': [], 'Skills': [], 'Projects': [] }

    for canonical, start_idx, end_idx in ranges:
        section_chunk = normalized_text[start_idx:end_idx]
        # Remove the header line itself from the chunk
        section_body = re.sub(r"^.*$\n?", "", section_chunk, count=1, flags=re.MULTILINE)
        sections[canonical].append(section_body.strip())

    # Join multiple occurrences
    joined_sections: Dict[str, str] = {k: "\n\n".join(v).strip() for k, v in sections.items()}
    return joined_sections


def print_sections(sections: Dict[str, str]) -> None:
    print("\n==== Detected Sections ====")
    for name in ['Profile', 'Experience', 'Education', 'Skills', 'Projects']:
        content = sections.get(name, '') or ''
        preview = content[:200] + ("..." if len(content) > 200 else "")
        print(f"\n{name}:\n{'-'*len(name)}\n{preview}")


def preprocess_text_for_ner(text: str, section_name: str) -> str:
    if not text:
        return ''
    # Basic cleanup
    cleaned = re.sub(r"[\t\r]", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Light section-aware tweaks
    if section_name in ('Experience', 'Education'):
        # Keep bullet separators as periods for better sentence boundaries
        cleaned = cleaned.replace('•', '. ').replace('·', '. ')
    # Strip residual section headers if present at the start
    cleaned = re.sub(r"^\s*(education|experience|skills|projects)\s*:?[\s\-–]*",
                     "",
                     cleaned,
                     flags=re.IGNORECASE)
    return cleaned


def merge_subword_entities(entities: List[Dict]) -> List[Dict]:
    if not entities:
        return []
    merged: List[Dict] = []
    buffer: Dict = None
    for ent in entities:
        word = ent.get('text') or ent.get('word') or ''
        label = ent.get('entity') or ent.get('entity_group')
        score = ent.get('score', 0.0)
        # Normalize stray BERT subword prefix even for first token
        if word.startswith('##'):
            word = word[2:]
        if buffer is None:
            buffer = { 'entity': label, 'text': word, 'score': score }
            continue
        if label == buffer['entity'] and (word.startswith('##') or (word and not word[0].isalnum())):
            token = word[2:] if word.startswith('##') else word
            buffer['text'] += token
            buffer['score'] = max(buffer['score'], score)
        else:
            merged.append(buffer)
            buffer = { 'entity': label, 'text': word, 'score': score }
    if buffer is not None:
        merged.append(buffer)
    return merged


def normalize_entity_labels(entities: List[Dict], section_name: str) -> List[Dict]:
    if not entities:
        return []
    normalized: List[Dict] = []
    for e in entities:
        label = e.get('entity', '')
        text_val = e.get('text', '')
        mapped = label
        if section_name == 'Education' and label in {'ORG', 'MISC', 'Organization', 'Institute'}:
            mapped = 'EDU_ORG'
        if section_name == 'Experience' and label in {'ORG', 'MISC', 'Organization', 'Company', 'Companies worked at'}:
            mapped = 'COMPANY'
        # Guard against month-like tokens misclassified as Degree within Experience
        if section_name == 'Experience' and label == 'Degree':
            if re.fullmatch(r"(?i)(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b", text_val.strip()) or re.search(r"\b(?:19|20)\d{2}\b", text_val):
                mapped = 'DATE'
        normalized.append({ 'entity': mapped, 'text': text_val, 'score': e.get('score', 0.0) })
    return normalized


def split_experience_into_jobs(experience_text: str) -> List[str]:
    """
    Segment Experience into job-level chunks:
    [Role] [at Company]
    [Dates], [Location]
    [Bulleted description for this job]
    """
    if not experience_text:
        return []

    role_rx = re.compile(r"\b(Engineer|Developer|Manager|Analyst|Consultant|Architect|Intern|Scientist|Lead|Specialist)\b", re.IGNORECASE)
    title_at_company_rx = re.compile(r"\b(Engineer|Developer|Manager|Analyst|Consultant|Architect|Intern|Scientist|Lead|Specialist)\b\s+(?:at|@)\s+(.+)$", re.IGNORECASE)
    date_line_rx = re.compile(r"(?i)(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec).*\b(?:19|20)\d{2}\b.*(Present|(?:19|20)\d{2})")

    lines = [l.rstrip() for l in experience_text.replace('\r', '').split('\n')]
    lines = [l for l in lines if l.strip()]

    jobs: List[List[str]] = []
    current: List[str] = []

    def start_new_job():
        nonlocal current
        if current:
            jobs.append(current)
        current = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            # Blank line signals potential boundary
            if current:
                jobs.append(current)
                current = []
            continue

        is_role_header = bool(role_rx.search(stripped))
        is_title_at_company = bool(title_at_company_rx.search(stripped))

        # Start a new job when we see an obvious role header line
        if is_title_at_company or (is_role_header and (not current or len(current) >= 2)):
            start_new_job()
            current.append(stripped)
            continue

        # Otherwise, append to current job
        current.append(stripped)

        # If we just captured a date/location line, keep appending next lines as description
        # until we detect a new role header in the subsequent iteration
        # (handled implicitly by the header condition above)

    # Flush last job
    if current:
        jobs.append(current)

    # Join each job into a compact paragraph
    job_chunks: List[str] = []
    for parts in jobs:
        # Merge short lines together to form a cohesive chunk
        chunk = ' '.join(parts)
        chunk = re.sub(r"\s+", " ", chunk).strip()
        if chunk:
            job_chunks.append(chunk)

    # Deduplicate while preserving order
    seen = set()
    result: List[str] = []
    for c in job_chunks:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result


def _looks_like_company_name(text: str) -> bool:
    if not text:
        return False
    if len(text) > 64:
        return False
    if re.search(r"(using|with|via|for|and|to|from|of|on|in|by|through|pipeline|API|LangChain|RAG|workflow)", text, re.IGNORECASE):
        return False
    if re.search(r"[0-9]", text):
        return False
    words = [w for w in re.split(r"\s+", text.strip()) if w]
    if not (1 <= len(words) <= 6):
        return False
    # Accept common company suffixes
    if re.search(r"(Inc\.?|LLC|Ltd\.?|Technologies|Solutions|Systems|Labs|AI|Analytics|Data|Software)$", text):
        return True
    # General capitalization heuristic
    capitalized = sum(1 for w in words if re.match(r"^[A-Z][A-Za-z&.'-]*$", w) or w.isupper())
    return capitalized >= max(1, len(words) - 1)


def _extract_company_from_job(job_text: str) -> str:
    lines = [l.strip() for l in job_text.replace('\r', '').split('\n') if l.strip()]
    # Heuristic 1: Role on first line, company on second
    role_rx = re.compile(r"\b(Engineer|Developer|Manager|Analyst|Consultant|Architect|Intern|Scientist|Lead|Specialist)\b", re.IGNORECASE)
    date_line_rx = re.compile(r"(?i)(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec).*\b(?:19|20)\d{2}\b.*(Present|(?:19|20)\d{2})")
    if lines:
        if role_rx.search(lines[0]) and len(lines) >= 2 and not date_line_rx.search(lines[1]):
            if _looks_like_company_name(lines[1]):
                return lines[1]
        # Heuristic 2: "Role at Company"
        m = re.search(r"\b(?:Engineer|Developer|Manager|Analyst|Consultant|Architect|Intern|Scientist|Lead|Specialist)\b\s+(?:at|@)\s+(.{2,64})", lines[0], re.IGNORECASE)
        if m:
            candidate = m.group(1).strip().rstrip('.,')
            if _looks_like_company_name(candidate):
                return candidate
    # Heuristic 3: Search lines for a plausible company
    for l in lines[:3]:
        cand = re.sub(r"\(.*?\)", "", l).strip()
        cand = re.sub(r"[,;]+$", "", cand)
        if _looks_like_company_name(cand):
            return cand
    return ''


def postprocess_experience_entities(entities: List[Dict], experience_text: str) -> List[Dict]:
    """
    Improve COMPANY extraction in Experience by:
    - Deriving company names per job block via heuristics
    - Removing obviously spurious COMPANY spans from long bullet text
    - Cleaning leftover subword markers
    """
    if not experience_text:
        return entities

    jobs = split_experience_into_jobs(experience_text)

    derived_companies = []
    for job in jobs:
        c = _extract_company_from_job(job)
        if c:
            derived_companies.append(c)

    # Clean existing entities and filter spurious COMPANY
    cleaned: List[Dict] = []
    for e in entities:
        txt = (e.get('text') or '').replace('##', '')
        ent = e.get('entity')
        if ent == 'COMPANY' and not _looks_like_company_name(txt):
            continue
        new_e = { 'entity': ent, 'text': txt.strip(), 'score': e.get('score', 0.0) }
        if 'source' in e:
            new_e['source'] = e['source']
        cleaned.append(new_e)

    # Add derived companies with high confidence
    for c in derived_companies:
        cleaned.append({ 'entity': 'COMPANY', 'text': c, 'score': 0.96, 'source': 'post' })

    return deduplicate_entities(cleaned)


def parse_skills_from_text(skills_text: str) -> List[str]:
    if not skills_text:
        return []
    # Normalize bullets and newlines
    text = skills_text.replace('\r', '\n')
    # Split on common delimiters: comma, pipe, slash, semicolon, bullets, newlines
    raw = re.split(r"[\n,\|/;·•]+", text)
    skills: List[str] = []
    for item in raw:
        token = item.strip().strip('-').strip()
        if not token:
            continue
        # Remove trailing punctuation
        token = re.sub(r"[\s\-–•·]+$", "", token)
        # Collapse multiple spaces
        token = re.sub(r"\s+", " ", token)
        if token:
            skills.append(token)
    # Deduplicate preserving order (case-insensitive)
    seen = set()
    unique: List[str] = []
    for s in skills:
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)
    return unique


def parse_projects_from_text(projects_text: str) -> List[Dict[str, str]]:
    if not projects_text:
        return []

    text = projects_text.replace('\r', '')

    entries: List[Dict[str, str]] = []

    # Pattern A: "Name: description" (same line)
    pattern_a = re.compile(r"^\s*([^\n:]{2,120}?)\s*:\s*(.+?)(?=\n{2,}|\Z)", re.IGNORECASE | re.MULTILINE | re.DOTALL)
    # Pattern B: "Name. description" (same line)
    pattern_b = re.compile(r"^\s*([^\n]{2,120}?)\s*\.\s+(.+?)(?=\n{2,}|\Z)", re.IGNORECASE | re.MULTILINE | re.DOTALL)
    # Pattern C: "Name:\nDescription ..." (next lines)
    pattern_c = re.compile(r"^\s*([^\n:]{2,120}?)\s*:\s*$\n+(.+?)(?=\n{2,}|\Z)", re.IGNORECASE | re.MULTILINE | re.DOTALL)

    consumed = [False] * (len(text))  # placeholder, not exact mapping; we'll avoid double-add via spans
    used_spans: List[tuple] = []

    def add_matches(pat: re.Pattern):
        for m in pat.finditer(text):
            span = m.span()
            # Skip overlaps
            if any(not (span[1] <= s0 or span[0] >= s1) for (s0, s1) in used_spans):
                continue
            name = re.sub(r"\s+", " ", m.group(1)).strip().rstrip('.:')
            desc = re.sub(r"\s+", " ", m.group(2)).strip()
            if name and desc:
                used_spans.append(span)
                entries.append({"name": name, "description": desc})

    add_matches(pattern_a)
    add_matches(pattern_b)
    add_matches(pattern_c)

    # Fallback: split blocks by blank lines and infer name as first short line
    if not entries:
        blocks = [b.strip() for b in re.split(r"\n{2,}", text) if b.strip()]
        for b in blocks:
            lines = [l.strip() for l in b.split('\n') if l.strip()]
            if not lines:
                continue
            header = lines[0].rstrip('.:').strip()
            body = ' '.join(lines[1:]).strip()
            # If body is empty, attempt to split first line by period or dash
            if not body and '.' in lines[0]:
                parts = [p.strip() for p in lines[0].split('.', 1)]
                if len(parts) == 2:
                    header, body = parts[0], parts[1]
            if header and body:
                entries.append({"name": re.sub(r"\s+", " ", header), "description": re.sub(r"\s+", " ", body)})

    # Deduplicate by name+description
    seen = set()
    unique_entries: List[Dict[str, str]] = []
    for e in entries:
        key = (e["name"].lower(), e["description"].lower())
        if key in seen:
            continue
        seen.add(key)
        unique_entries.append(e)

    return unique_entries


def filter_low_confidence_entities(entities: List[Dict], threshold: float) -> List[Dict]:
    if not entities:
        return []
    return [e for e in entities if e.get('score', 0.0) >= threshold]


def _extract_years(text: str) -> List[str]:
    return re.findall(r"\b(?:19|20)\d{2}\b", text)


def extract_with_regex_fallback(text: str, section_name: str) -> List[Dict]:
    fallback: List[Dict] = []
    if section_name == 'Education':
        degrees = re.findall(r"\b(B\.?Sc\.?|M\.?Sc\.?|B\.?E\.?|B\.?Tech\.?|M\.?Tech\.?|MBA|PhD|Bachelor|Master|Doctorate)\b", text, flags=re.IGNORECASE)
        for d in set(degrees):
            fallback.append({'entity': 'DEGREE', 'text': d, 'score': 0.5, 'source': 'regex'})
    if section_name == 'Experience':
        titles = re.findall(r"\b(Engineer|Developer|Manager|Analyst|Consultant|Architect)\b", text, flags=re.IGNORECASE)
        for t in set(titles):
            fallback.append({'entity': 'TITLE', 'text': t, 'score': 0.5, 'source': 'regex'})
    years = re.findall(r"\b(?:19|20)\d{2}\b", text)
    for y in set(years):
        fallback.append({'entity': 'YEAR', 'text': y, 'score': 0.4, 'source': 'regex'})
    return fallback


def deduplicate_entities(entities: List[Dict]) -> List[Dict]:
    seen = set()
    unique: List[Dict] = []
    for e in entities:
        key = (e.get('entity'), e.get('text').lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)
    return unique


def postprocess_education_entities(entities: List[Dict], section_text: str) -> List[Dict]:
    """
    Split overly broad Education entities into degree, institution, duration, and location.
    - Detects composite 'Degree' entities that also contain institution keywords, dates, or locations
    - Extracts structured fields from the full Education section text for robustness
    """
    if not section_text:
        return entities

    text = section_text.replace('\n', ' ').strip()

    # Patterns
    month = r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
    duration_regex = re.compile(
        rf"((?:{month})[a-z]*\s+(?:19|20)\d{{2}}\s*[-–]\s*(?:{month})[a-z]*\s+(?:19|20)\d{{2}}|(?:19|20)\d{{4}}\s*[-–]\s*(?:19|20)\d{{4}})",
        re.IGNORECASE,
    )
    institution_regex = re.compile(
        r"([A-Z][A-Za-z&()\-., ]{2,}?(?:University|College|Institute|School|Academy|Polytechnic)[A-Za-z&()\-., ]*)",
        re.IGNORECASE,
    )
    degree_regex = re.compile(
        r"\b((?:Bachelor|Master|B\.?Sc\.?|M\.?Sc\.?|B\.?E\.?|B\.?Tech\.?|M\.?Tech\.?|MBA|PhD|BS|MS)\b[\w .()\-]*?(?: in [\w .()\-]+)?)",
        re.IGNORECASE,
    )
    location_regex = re.compile(r"([A-Z][A-Za-z .\-]+,\s*[A-Z][A-Za-z .\-]+)$")

    # Try to extract from the full section text for stability
    found_duration = None
    m = duration_regex.search(text)
    if m:
        found_duration = m.group(1).strip()
        text_wo_duration = (text[:m.start()] + ' ' + text[m.end():]).strip()
    else:
        text_wo_duration = text

    found_institution = None
    m = institution_regex.search(text_wo_duration)
    if m:
        found_institution = m.group(1).strip()
        text_wo_inst = (text_wo_duration[:m.start()] + ' ' + text_wo_duration[m.end():]).strip()
    else:
        text_wo_inst = text_wo_duration

    found_degree = None
    m = degree_regex.search(text_wo_inst)
    if m:
        found_degree = m.group(1).strip()
        text_wo_deg = (text_wo_inst[:m.start()] + ' ' + text_wo_inst[m.end():]).strip()
    else:
        text_wo_deg = text_wo_inst

    found_location = None
    m = location_regex.search(text_wo_duration)
    if m:
        found_location = m.group(1).strip()

    # Decide if we should remove composite Degree entities
    refined: List[Dict] = []
    for e in entities:
        if e.get('entity') == 'Degree':
            text_val = e.get('text', '')
            looks_composite = bool(
                re.search(r"University|College|Institute|School|Academy|Polytechnic", text_val, re.IGNORECASE)
                or duration_regex.search(text_val)
                or re.search(r"\b(?:19|20)\d{2}\b", text_val)
            )
            if looks_composite and (found_degree or found_institution or found_duration or found_location):
                # Skip adding this composite; will replace with structured fields
                continue
        refined.append(e)

    # Add structured fields if found
    def add_entity(label: str, value: str, score: float = 0.95):
        if value and value.strip():
            refined.append({'entity': label, 'text': value.strip(), 'score': score, 'source': 'post'})

    add_entity('Degree', found_degree)
    add_entity('Institution', found_institution)
    add_entity('Duration', found_duration)
    add_entity('Location', found_location)

    return refined


