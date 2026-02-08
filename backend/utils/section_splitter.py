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
        # Filter out common section headings
        if key in ['skills', 'skill', 'technical skills', 'core skills']:
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


