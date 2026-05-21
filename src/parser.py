"""
src/parser.py
AST-based source code analysis for Python files.
Extracts functions, classes, imports, and code chunks for LLM review.
"""

import ast
import textwrap
from pathlib import Path
from typing import Any

# Max characters per chunk sent to the LLM
MAX_CHUNK_CHARS = 3500
# Max lines for a single file to be included
MAX_FILE_LINES = 800


def _safe_read(path: Path) -> str | None:
    """Read a file with UTF-8 fallback."""
    for enc in ("utf-8", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, OSError):
            continue
    return None


def parse_python_file(path: Path) -> dict[str, Any] | None:
    """
    Parse a Python source file with the built-in `ast` module.

    Returns a structured dict with:
        filename, source, lines, functions, classes, imports,
        num_functions, num_classes, num_imports, chunks
    Returns None if parsing fails.
    """
    source = _safe_read(path)
    if source is None:
        return None

    lines = source.splitlines()
    if len(lines) > MAX_FILE_LINES:
        # Trim to keep review focused
        source = "\n".join(lines[:MAX_FILE_LINES])
        lines  = lines[:MAX_FILE_LINES]

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    functions  = []
    classes    = []
    imports    = []
    complexities = []

    for node in ast.walk(tree):
        # ── Functions ────────────────────────────────────────────────────
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            decorators = [ast.unparse(d) for d in node.decorator_list]
            docstring = ast.get_docstring(node) or ""
            complexity = _cyclomatic_complexity(node)
            complexities.append(complexity)

            func_src = ast.get_source_segment(source, node) or ""
            functions.append({
                "name":        node.name,
                "lineno":      node.lineno,
                "end_lineno":  getattr(node, "end_lineno", node.lineno),
                "args":        args,
                "decorators":  decorators,
                "docstring":   docstring[:200],
                "source":      func_src[:1500],
                "complexity":  complexity,
                "is_async":    isinstance(node, ast.AsyncFunctionDef),
            })

        # ── Classes ──────────────────────────────────────────────────────
        elif isinstance(node, ast.ClassDef):
            bases = [ast.unparse(b) for b in node.bases]
            methods = [n.name for n in ast.walk(node)
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            docstring = ast.get_docstring(node) or ""
            classes.append({
                "name":      node.name,
                "lineno":    node.lineno,
                "bases":     bases,
                "methods":   methods,
                "docstring": docstring[:200],
            })

        # ── Imports ──────────────────────────────────────────────────────
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}")

    avg_complexity = sum(complexities) / len(complexities) if complexities else 0

    # Chunk the source for LLM review
    chunks = _chunk_source(source, path.name)

    return {
        "filename":        str(path.name),
        "filepath":        str(path),
        "source":          source,
        "lines":           len(lines),
        "functions":       functions,
        "classes":         classes,
        "imports":         imports,
        "num_functions":   len(functions),
        "num_classes":     len(classes),
        "num_imports":     len(imports),
        "avg_complexity":  round(avg_complexity, 2),
        "chunks":          chunks,
    }


def _cyclomatic_complexity(node: ast.AST) -> int:
    """Estimate cyclomatic complexity of a function node."""
    complexity = 1
    branching = (ast.If, ast.For, ast.While, ast.ExceptHandler,
                 ast.With, ast.Assert, ast.comprehension)
    for child in ast.walk(node):
        if isinstance(child, branching):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
    return complexity


def _chunk_source(source: str, filename: str) -> list[dict]:
    """
    Split source into overlapping chunks suitable for LLM review.
    Each chunk is at most MAX_CHUNK_CHARS characters.
    """
    if len(source) <= MAX_CHUNK_CHARS:
        return [{"chunk_id": 0, "filename": filename, "content": source, "start_line": 1}]

    lines      = source.splitlines()
    chunks     = []
    chunk_lines: list[str] = []
    char_count = 0
    start_line = 1
    chunk_id   = 0

    for i, line in enumerate(lines, start=1):
        chunk_lines.append(line)
        char_count += len(line) + 1

        if char_count >= MAX_CHUNK_CHARS:
            chunks.append({
                "chunk_id":   chunk_id,
                "filename":   filename,
                "content":    "\n".join(chunk_lines),
                "start_line": start_line,
            })
            # 10-line overlap
            overlap    = chunk_lines[-10:]
            chunk_lines = overlap[:]
            char_count = sum(len(l) + 1 for l in overlap)
            start_line = i - 9
            chunk_id  += 1

    if chunk_lines:
        chunks.append({
            "chunk_id":   chunk_id,
            "filename":   filename,
            "content":    "\n".join(chunk_lines),
            "start_line": start_line,
        })

    return chunks


def parse_repository(repo_path: Path, max_files: int = 20) -> list[dict]:
    """
    Walk a repository and parse all Python files.

    Args:
        repo_path: Root path of the cloned repo
        max_files: Maximum number of files to process

    Returns:
        List of parsed file dicts
    """
    repo_path = Path(repo_path)
    skip_dirs = {".git", "__pycache__", ".venv", "venv", "env",
                 "node_modules", ".tox", "dist", "build", "eggs",
                 ".eggs", "site-packages"}

    py_files: list[Path] = []
    for f in repo_path.rglob("*.py"):
        # Skip hidden dirs and common non-source dirs
        if any(part in skip_dirs or part.startswith(".") for part in f.parts):
            continue
        # Skip tiny files (likely __init__.py with just a comment)
        if f.stat().st_size < 30:
            continue
        py_files.append(f)

    # Prioritise files that are more likely to contain interesting logic
    py_files.sort(key=lambda p: -p.stat().st_size)
    py_files = py_files[:max_files]

    parsed = []
    for f in py_files:
        result = parse_python_file(f)
        if result:
            # Make filename relative to repo root for cleaner display
            try:
                result["filename"] = str(f.relative_to(repo_path))
            except ValueError:
                pass
            parsed.append(result)

    return parsed
