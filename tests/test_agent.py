"""
tests/test_agent.py
Unit tests for all core modules of the AI Code Review Agent.
Run with: pytest tests/ -v
"""

import ast
import json
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ──────────────────────────────────────────────────────────────────────────────
# Ingestion tests
# ──────────────────────────────────────────────────────────────────────────────
from src.ingestion import validate_repo_url


class TestValidateRepoUrl:
    def test_valid_url(self):
        assert validate_repo_url("https://github.com/pallets/flask") is True

    def test_valid_url_with_git(self):
        assert validate_repo_url("https://github.com/pallets/flask.git") is True

    def test_valid_url_trailing_slash(self):
        assert validate_repo_url("https://github.com/pallets/flask/") is True

    def test_invalid_no_repo(self):
        assert validate_repo_url("https://github.com/pallets") is False

    def test_invalid_not_github(self):
        assert validate_repo_url("https://gitlab.com/pallets/flask") is False

    def test_invalid_empty(self):
        assert validate_repo_url("") is False

    def test_invalid_random_string(self):
        assert validate_repo_url("not-a-url") is False

    def test_valid_org_with_dots(self):
        assert validate_repo_url("https://github.com/some.org/my-repo") is True


# ──────────────────────────────────────────────────────────────────────────────
# Parser tests
# ──────────────────────────────────────────────────────────────────────────────
from src.parser import _cyclomatic_complexity, _chunk_source, parse_python_file


SAMPLE_CODE = textwrap.dedent("""
    import os
    import sys
    from pathlib import Path

    MAGIC = 42

    class MyClass:
        \"\"\"A sample class.\"\"\"

        def __init__(self, value):
            self.value = value

        def compute(self, x):
            if x > 0:
                for i in range(x):
                    if i % 2 == 0:
                        yield i
            elif x < 0:
                return -x
            else:
                return 0

    def risky_function(user_input):
        query = "SELECT * FROM users WHERE id = " + user_input
        return eval(query)

    def undocumented(a, b, c):
        return a + b + c
""").strip()


class TestCyclomaticComplexity:
    def test_simple_function(self):
        code  = "def f(x):\n    return x + 1"
        tree  = ast.parse(code)
        fnode = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        assert _cyclomatic_complexity(fnode) == 1

    def test_branchy_function(self):
        code = textwrap.dedent("""
            def f(x):
                if x > 0:
                    for i in range(x):
                        if i % 2 == 0:
                            pass
                elif x < 0:
                    pass
                else:
                    pass
        """)
        tree  = ast.parse(code)
        fnode = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        assert _cyclomatic_complexity(fnode) >= 4


class TestChunkSource:
    def test_small_source_single_chunk(self):
        source = "x = 1\n" * 10
        chunks = _chunk_source(source, "test.py")
        assert len(chunks) == 1
        assert chunks[0]["chunk_id"] == 0
        assert chunks[0]["start_line"] == 1

    def test_large_source_multiple_chunks(self):
        source = "x = 1  # padding\n" * 300
        chunks = _chunk_source(source, "test.py")
        assert len(chunks) > 1
        for i, c in enumerate(chunks):
            assert c["chunk_id"] == i
            assert "content" in c
            assert "start_line" in c


class TestParsePythonFile:
    def test_parse_valid_file(self, tmp_path):
        f = tmp_path / "sample.py"
        f.write_text(SAMPLE_CODE, encoding="utf-8")
        result = parse_python_file(f)
        assert result is not None
        assert result["num_functions"] >= 3
        assert result["num_classes"] >= 1
        assert result["num_imports"] >= 3
        assert len(result["chunks"]) >= 1

    def test_parse_invalid_syntax(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("def broken(:\n    pass", encoding="utf-8")
        result = parse_python_file(f)
        assert result is None

    def test_parse_empty_file(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("", encoding="utf-8")
        # Empty file is valid Python — should parse but have 0 functions
        result = parse_python_file(f)
        if result:
            assert result["num_functions"] == 0

    def test_complexity_computed(self, tmp_path):
        f = tmp_path / "complex.py"
        f.write_text(SAMPLE_CODE, encoding="utf-8")
        result = parse_python_file(f)
        assert result is not None
        fns = {fn["name"]: fn for fn in result["functions"]}
        # compute() has multiple branches — complexity > 1
        assert fns["compute"]["complexity"] > 1


# ──────────────────────────────────────────────────────────────────────────────
# Reviewer tests
# ──────────────────────────────────────────────────────────────────────────────
from src.reviewer import _parse_llm_response, _validate_comment, ReviewAgent


class TestParseLlmResponse:
    def test_valid_array(self):
        raw = json.dumps([{
            "title": "SQL injection risk",
            "comment": "User input concatenated directly into query.",
            "suggestion": "Use parameterised queries.",
            "severity": "critical",
            "category": "security",
            "location": "risky_function()",
            "confidence": 95,
        }])
        result = _parse_llm_response(raw)
        assert len(result) == 1
        assert result[0]["severity"] == "critical"

    def test_strips_markdown_fences(self):
        raw = "```json\n[]\n```"
        result = _parse_llm_response(raw)
        assert result == []

    def test_empty_array(self):
        assert _parse_llm_response("[]") == []

    def test_garbage_response(self):
        assert _parse_llm_response("Sorry, I cannot review this.") == []

    def test_trailing_comma_recovery(self):
        raw = '[{"title":"x","comment":"y","suggestion":"z","severity":"low","category":"style","location":"f()","confidence":50,}]'
        result = _parse_llm_response(raw)
        # Should recover or return []
        assert isinstance(result, list)

    def test_text_before_array(self):
        raw = 'Here is my review:\n[{"title":"x","comment":"y","suggestion":"z","severity":"low","category":"style","location":"f()","confidence":60}]'
        result = _parse_llm_response(raw)
        assert len(result) == 1


class TestValidateComment:
    def _base(self, **overrides):
        base = {
            "title": "Test issue",
            "comment": "This is a problem.",
            "suggestion": "Fix it this way.",
            "severity": "high",
            "category": "bug",
            "location": "my_function()",
            "confidence": 75,
        }
        base.update(overrides)
        return base

    def test_valid_comment(self):
        result = _validate_comment(self._base(), "test.py")
        assert result is not None
        assert result["severity"] == "high"
        assert result["confidence"] == 75
        assert result["filename"] == "test.py"

    def test_invalid_severity_fallback(self):
        result = _validate_comment(self._base(severity="extreme"), "test.py")
        assert result["severity"] == "info"

    def test_invalid_category_fallback(self):
        result = _validate_comment(self._base(category="unknown_cat"), "test.py")
        assert result["category"] == "style"

    def test_confidence_clamped(self):
        result = _validate_comment(self._base(confidence=150), "test.py")
        assert result["confidence"] == 100
        result2 = _validate_comment(self._base(confidence=-10), "test.py")
        assert result2["confidence"] == 0

    def test_empty_comment_rejected(self):
        result = _validate_comment(self._base(comment=""), "test.py")
        assert result is None

    def test_not_a_dict(self):
        assert _validate_comment("string", "test.py") is None
        assert _validate_comment(42, "test.py") is None


class TestReviewAgent:
    def _make_agent(self):
        return ReviewAgent(api_key="sk-test", model="gpt-4o-mini",
                           confidence_threshold=40)

    def _make_parsed_file(self):
        return {
            "filename":      "test.py",
            "source":        SAMPLE_CODE,
            "lines":         30,
            "functions":     [{"name": "risky_function", "complexity": 2}],
            "classes":       [],
            "imports":       ["os", "sys"],
            "num_functions": 1,
            "num_classes":   0,
            "num_imports":   2,
            "avg_complexity": 2.0,
            "chunks": [{
                "chunk_id":   0,
                "filename":   "test.py",
                "content":    SAMPLE_CODE,
                "start_line": 1,
            }],
        }

    @patch("src.reviewer.OpenAI")
    def test_review_file_returns_list(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        comment_data = [{
            "title":      "SQL injection",
            "comment":    "User input concatenated directly.",
            "suggestion": "Use parameterised queries.",
            "severity":   "critical",
            "category":   "security",
            "location":   "risky_function()",
            "confidence": 92,
        }]
        mock_client.chat.completions.create.return_value.choices[0].message.content = (
            json.dumps(comment_data)
        )

        agent  = self._make_agent()
        result = agent.review_file(self._make_parsed_file())
        assert isinstance(result, list)
        assert len(result) >= 1
        assert result[0]["severity"] == "critical"

    @patch("src.reviewer.OpenAI")
    def test_review_file_handles_empty_response(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value.choices[0].message.content = "[]"

        agent  = self._make_agent()
        result = agent.review_file(self._make_parsed_file())
        assert result == []

    @patch("src.reviewer.OpenAI")
    def test_review_file_handles_api_error(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API error")

        agent  = self._make_agent()
        result = agent.review_file(self._make_parsed_file())
        assert result == []

    @patch("src.reviewer.OpenAI")
    def test_deduplication(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        # Return the same comment twice (simulating two chunks)
        comment_data = json.dumps([{
            "title": "Duplicate Issue", "comment": "Same problem.", "suggestion": "Fix it.",
            "severity": "low", "category": "style", "location": "f()", "confidence": 60,
        }])
        mock_client.chat.completions.create.return_value.choices[0].message.content = comment_data

        # File with 2 chunks
        pf = self._make_parsed_file()
        pf["chunks"] = [
            {"chunk_id": 0, "filename": "test.py", "content": "x=1", "start_line": 1},
            {"chunk_id": 1, "filename": "test.py", "content": "y=2", "start_line": 5},
        ]

        agent  = self._make_agent()
        result = agent.review_file(pf)
        titles = [c["title"] for c in result]
        assert len(titles) == len(set(titles)), "Duplicates not removed"


# ──────────────────────────────────────────────────────────────────────────────
# Report tests
# ──────────────────────────────────────────────────────────────────────────────
from src.report import generate_markdown_report, generate_csv_report

SAMPLE_COMMENTS = [
    {
        "filename":   "app.py",
        "location":   "login()",
        "severity":   "critical",
        "category":   "security",
        "title":      "SQL Injection",
        "comment":    "Unsafe query construction.",
        "suggestion": "Use parameterised queries.",
        "confidence": 95,
    },
    {
        "filename":   "utils.py",
        "location":   "process()",
        "severity":   "medium",
        "category":   "performance",
        "title":      "Nested loop",
        "comment":    "O(n²) complexity.",
        "suggestion": "Use a set for O(1) lookups.",
        "confidence": 30,
    },
]

SAMPLE_PARSED = [
    {"filename": "app.py",   "lines": 100, "num_functions": 5, "num_classes": 1},
    {"filename": "utils.py", "lines": 50,  "num_functions": 3, "num_classes": 0},
]


class TestGenerateMarkdownReport:
    def test_returns_string(self):
        out = generate_markdown_report("test/repo", SAMPLE_COMMENTS, SAMPLE_PARSED)
        assert isinstance(out, str)

    def test_contains_repo_name(self):
        out = generate_markdown_report("test/repo", SAMPLE_COMMENTS, SAMPLE_PARSED)
        assert "test/repo" in out

    def test_contains_severities(self):
        out = generate_markdown_report("test/repo", SAMPLE_COMMENTS, SAMPLE_PARSED)
        assert "critical" in out.lower()
        assert "medium" in out.lower()

    def test_verify_label_for_low_confidence(self):
        out = generate_markdown_report("test/repo", SAMPLE_COMMENTS, SAMPLE_PARSED)
        assert "VERIFY THIS" in out

    def test_empty_comments(self):
        out = generate_markdown_report("test/repo", [], SAMPLE_PARSED)
        assert isinstance(out, str)
        assert "test/repo" in out


class TestGenerateCsvReport:
    def test_returns_csv_string(self):
        out = generate_csv_report(SAMPLE_COMMENTS)
        assert isinstance(out, str)
        lines = out.strip().splitlines()
        # Header + 2 data rows
        assert len(lines) == 3

    def test_header_fields(self):
        out = generate_csv_report(SAMPLE_COMMENTS)
        header = out.splitlines()[0]
        for field in ["filename", "severity", "category", "confidence"]:
            assert field in header

    def test_empty_comments(self):
        out = generate_csv_report([])
        assert isinstance(out, str)
        # Should still have header
        assert "filename" in out
