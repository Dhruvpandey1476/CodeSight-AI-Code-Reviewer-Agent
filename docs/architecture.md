# CodeSight — Architecture Notes

## Pipeline Flow

```
GitHub URL
    │
    ▼
┌─────────────────────────────┐
│  INGESTION  (ingestion.py)  │
│  • validate_repo_url()      │
│  • clone_repository()       │    Uses: GitPython (depth=1 shallow)
│  • Returns: Path, repo_name │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  PARSING  (parser.py)       │
│  • parse_repository()       │    Uses: Python built-in ast module
│  • parse_python_file()      │
│  • _cyclomatic_complexity() │    Metric: McCabe complexity per fn
│  • _chunk_source()          │    Chunk size: 3500 chars w/ 10-line overlap
│                             │
│  Extracts per file:         │
│    functions[]              │
│      name, args, lineno,    │
│      docstring, complexity, │
│      source snippet         │
│    classes[]                │
│      name, bases, methods   │
│    imports[]                │
│    chunks[]  ← sent to LLM  │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  LLM REVIEW (reviewer.py)   │
│  • ReviewAgent              │    Uses: OpenAI GPT-4o-mini
│  • review_file()            │    Temp: 0.2 (deterministic)
│  • _review_chunk()          │    Max tokens: 1500 per chunk
│  • _parse_llm_response()    │    Robust JSON extraction
│  • _validate_comment()      │    Schema enforcement
│                             │
│  Per comment:               │
│    title, comment,          │
│    suggestion, severity,    │
│    category, location,      │
│    confidence (0-100)       │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  REPORT GEN (report.py)     │
│  • generate_markdown_report │
│  • generate_csv_report      │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  DASHBOARD  (app.py)        │
│  • Streamlit UI             │
│  • Metric cards             │
│  • Severity/category filter │
│  • Confidence bar per card  │
│  • Low-conf verify section  │
│  • MD + CSV download        │
└─────────────────────────────┘
```

## Confidence Bucketing Logic

```python
if confidence >= 70:
    bar_color = "#4fffb0"   # green — trustworthy
elif confidence >= 40:
    bar_color = "#ffd93d"   # amber — review recommended
else:
    bar_color = "#ff6b6b"   # red — ⚠ verify this
    show_verify_label = True
```

## Chunking Strategy

Large files are split into overlapping chunks:
- Max chunk size: 3500 characters
- Overlap: last 10 lines carried into next chunk
- Ensures functions spanning chunk boundaries are not cut off
- Each chunk reviewed independently; results de-duplicated by title

## Prompt Design

The system prompt:
1. Specifies strict JSON-only output (no prose, no fences)
2. Defines exact schema with all required fields
3. Gives confidence scoring rubric with explicit bands
4. Prioritises review categories (security > bugs > perf > style)
5. Temperature 0.2 ensures consistent, schema-valid responses

## Deduplication

After reviewing all chunks of a file:
- Comments with identical `title` strings are deduplicated
- Final list sorted by: severity ASC, confidence DESC
- Capped at `max_comments_per_file` (default 10)
