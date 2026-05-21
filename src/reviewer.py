"""
src/reviewer.py
LLM-powered code review using Groq (free, fast, works globally).
"""

import json
import re
from typing import Any
from groq import Groq

SYSTEM_PROMPT = """You are a senior software engineer doing a thorough code review.

CRITICAL: You MUST return a JSON array. Even for clean code, find at least 2-3 observations.

Return ONLY a raw JSON array — no markdown, no backticks, no prose. Start with [ end with ].

Each item must have ALL these exact fields:
{
  "title": "short title under 10 words",
  "comment": "explanation of the issue in 1-3 sentences",
  "suggestion": "concrete actionable fix",
  "severity": "critical|high|medium|low|info",
  "category": "bug|security|performance|style|maintainability|documentation",
  "location": "function name or line range e.g. my_func() or lines 5-10",
  "confidence": 85
}

Confidence guide:
- 90-100: definite bug or security hole
- 70-89:  clear issue, very likely real
- 50-69:  probable, context dependent
- 30-49:  possible, needs human judgment
- 0-29:   speculative

Start your response with [ and end with ]"""


def _build_user_prompt(parsed_file: dict, chunk: dict) -> str:
    meta_lines = []
    if parsed_file.get("functions"):
        names = [f["name"] for f in parsed_file["functions"][:15]]
        meta_lines.append(f"Functions: {', '.join(names)}")
    if parsed_file.get("classes"):
        names = [c["name"] for c in parsed_file["classes"][:8]]
        meta_lines.append(f"Classes: {', '.join(names)}")
    if parsed_file.get("imports"):
        meta_lines.append(f"Imports: {', '.join(parsed_file['imports'][:20])}")
    high_cc = [
        f"{f['name']}() cc={f['complexity']}"
        for f in parsed_file.get("functions", [])
        if f.get("complexity", 0) >= 5
    ]
    if high_cc:
        meta_lines.append(f"High-complexity functions: {', '.join(high_cc)}")

    meta = "\n".join(meta_lines) if meta_lines else "No metadata."
    return f"""Review this Python file and return a JSON array of issues.

File: {chunk['filename']} | Chunk {chunk.get('chunk_id', 0) + 1} | Starting line {chunk.get('start_line', 1)}

AST Metadata:
{meta}

Source code:
```python
{chunk['content']}
```

Return a JSON array starting with ["""


def _parse_llm_response(raw: str) -> list[dict]:
    if not raw or not raw.strip():
        return []
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    raw = re.sub(r"```", "", raw).strip()
    start = raw.find("[")
    end   = raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    json_str = raw[start:end + 1]
    json_str = re.sub(r",\s*\]", "]", json_str)
    json_str = re.sub(r",\s*\}", "}", json_str)
    try:
        data = json.loads(json_str)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}
VALID_CATEGORIES = {"bug", "security", "performance", "style", "maintainability", "documentation"}


def _validate_comment(raw: Any, filename: str) -> dict | None:
    if not isinstance(raw, dict):
        return None
    severity = str(raw.get("severity", "info")).lower().strip()
    category = str(raw.get("category", "style")).lower().strip()
    if severity not in VALID_SEVERITIES:
        severity = "info"
    if category not in VALID_CATEGORIES:
        category = "style"
    try:
        confidence = max(0, min(100, int(raw.get("confidence", 50))))
    except (TypeError, ValueError):
        confidence = 50
    comment = str(raw.get("comment", "")).strip()
    if not comment:
        return None
    return {
        "title":      str(raw.get("title", "Issue"))[:120].strip(),
        "comment":    comment[:600],
        "suggestion": str(raw.get("suggestion", ""))[:400].strip(),
        "severity":   severity,
        "category":   category,
        "location":   str(raw.get("location", "unknown"))[:100].strip(),
        "confidence": confidence,
        "filename":   filename,
    }


class ReviewAgent:
    def __init__(self, api_key, model="llama-3.3-70b-versatile",
                 confidence_threshold=40, max_comments_per_file=10):
        self.client = Groq(api_key=api_key)
        self.model_name = "llama-3.3-70b-versatile"
        self.confidence_threshold = confidence_threshold
        self.max_comments_per_file = max_comments_per_file

    def review_file(self, parsed_file: dict) -> list[dict]:
        all_comments: list[dict] = []
        seen_titles: set[str] = set()

        for chunk in parsed_file.get("chunks", []):
            raw_comments = self._review_chunk(parsed_file, chunk)
            for c in raw_comments:
                validated = _validate_comment(c, parsed_file["filename"])
                if validated and validated["title"] not in seen_titles:
                    seen_titles.add(validated["title"])
                    all_comments.append(validated)

        sev_order = ["critical", "high", "medium", "low", "info"]
        all_comments.sort(key=lambda c: (
            sev_order.index(c["severity"]) if c["severity"] in sev_order else 99,
            -c["confidence"],
        ))
        return all_comments[:self.max_comments_per_file]

    def _review_chunk(self, parsed_file: dict, chunk: dict) -> list[dict]:
        import time
        time.sleep(2)
        prompt = _build_user_prompt(parsed_file, chunk)
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        raw = response.choices[0].message.content or ""
        return _parse_llm_response(raw)