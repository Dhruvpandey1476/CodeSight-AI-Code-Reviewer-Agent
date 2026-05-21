# 🔍 CodeSight — AI Code Review Agent

> An autonomous, AST-powered AI agent that clones GitHub repositories, analyses Python source code, and generates confidence-rated review comments via a sleek Streamlit dashboard.

**Built for CipherSchools — AI/ML Mentor Role Assignment**

---

## 🚀 Live Demo

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app.streamlit.app)

---

## 📸 Features

| Feature | Detail |
|---|---|
| 🏗 Autonomous pipeline | Clone → Parse → Review → Display in one click |
| 🌲 AST parsing | Extracts functions, classes, imports, cyclomatic complexity |
| 🤖 LLM review | GPT-4o-mini generates structured JSON review comments |
| 📊 Confidence scoring | Every comment rated 0–100%; low-confidence flagged with ⚠ **verify this** |
| 🎛 Live filters | Filter by severity, category, confidence threshold |
| 💾 Export | Download full report as Markdown or CSV |
| 🌙 Dark UI | Polished dark-mode Streamlit dashboard |

---

## 🏛 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Streamlit Dashboard                      │
│  Input: GitHub URL + API Key   →   Output: Review Dashboard │
└────────────────────┬────────────────────────────────────────┘
                     │
          ┌──────────▼──────────┐
          │   1. INGESTION      │  src/ingestion.py
          │   GitPython clone   │  • validate_repo_url()
          │   (depth=1, fast)   │  • clone_repository()
          └──────────┬──────────┘
                     │
          ┌──────────▼──────────┐
          │   2. AST PARSING    │  src/parser.py
          │   Python ast module │  • parse_python_file()
          │   per .py file      │  • _cyclomatic_complexity()
          │                     │  • _chunk_source()
          │   Extracts:         │  • parse_repository()
          │   • Functions       │
          │   • Classes         │
          │   • Imports         │
          │   • Complexity      │
          │   • Code chunks     │
          └──────────┬──────────┘
                     │
          ┌──────────▼──────────┐
          │   3. LLM REVIEW     │  src/reviewer.py
          │   Groq LLama 7 B    │  • ReviewAgent.review_file()
          │   Per chunk         │  • _build_user_prompt()
          │                     │  • _parse_llm_response()
          │   Outputs JSON:     │  • _validate_comment()
          │   • title           │
          │   • comment         │
          │   • suggestion      │
          │   • severity        │
          │   • category        │
          │   • confidence 0-100│
          └──────────┬──────────┘
                     │
          ┌──────────▼──────────┐
          │   4. REPORT GEN     │  src/report.py
          │   Markdown + CSV    │  • generate_markdown_report()
          │   Downloadable      │  • generate_csv_report()
          └──────────┬──────────┘
                     │
          ┌──────────▼──────────┐
          │   5. DASHBOARD      │  app.py
          │   Metrics, filters  │  • Severity/category filters
          │   Comment cards     │  • Confidence bar per comment
          │   Low-conf section  │  • ⚠ verify this labels
          │   Download buttons  │  • MD + CSV export
          └─────────────────────┘
```

---

## ⚡ Quick Start

### 1. Clone this repo
```bash
git clone https://github.com/YOUR_USERNAME/ai-code-review-agent
cd ai-code-review-agent
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set your API key
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

### 4. Run the app
```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

All 30+ unit tests cover:
- URL validation (ingestion)
- AST parsing (functions, classes, imports, complexity)
- Code chunking logic
- LLM response parsing & robustness (malformed JSON, empty, fenced)
- Comment validation & normalisation
- Report generation (Markdown + CSV)

---

## 🗂 Project Structure

```
ai_code_review_agent/
├── app.py                    # Streamlit entry point & UI
├── requirements.txt          # Python dependencies
├── .env.example              # API key template
├── .gitignore
├── .streamlit/
│   ├── config.toml           # Theme configuration
│   └── secrets.toml.example  # Streamlit Cloud secrets template
├── src/
│   ├── __init__.py
│   ├── ingestion.py          # GitHub clone via GitPython
│   ├── parser.py             # AST parsing + chunking
│   ├── reviewer.py           # OpenAI LLM review agent
│   └── report.py             # Markdown + CSV report generation
└── tests/
    ├── __init__.py
    └── test_agent.py         # 30+ unit tests (pytest)
```

---

## 🔧 Configuration

| Setting | Default | Description |
|---|---|---|
| Max files | 20 | Max Python files to review per repo |
| Model | gpt-4o-mini | OpenAI model (cost-efficient) |
| Low-confidence threshold | 40% | Below this → "verify this" label |

---

## 📊 Confidence Scoring

Every comment is self-rated by the LLM:

| Range | Meaning |
|---|---|
| 90–100% | Definitive bug or security hole |
| 70–89% | Clear improvement, likely real |
| 50–69% | Probable issue, context-dependent |
| 30–49% | Needs human verification → ⚠ verify this |
| 0–29% | Speculative → ⚠ verify this |

Low-confidence comments are visually separated in a dedicated panel with a red "⚠ verify this" badge — demonstrating production-grade epistemic humility.

---

## ☁️ Deployment (Streamlit Cloud)

1. Push your repo to GitHub (public).
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Select your repo and set **Main file path** to `app.py`.
4. In **Advanced settings → Secrets**, add:
   ```toml
   OPENAI_API_KEY = "sk-your-key-here"
   ```
5. Click **Deploy**.

---

## ⚠️ Known Limitations

1. **Python only** — The AST parser currently supports Python files. JavaScript/TypeScript support can be added with `tree-sitter`.
2. **Public repos only** — GitPython clones public repos without auth. Private repos require a GitHub PAT.
3. **Large repos** — Very large repositories are sampled (max N files, configurable). Full monorepo coverage would need pagination and batching.
4. **LLM hallucination** — GPT-4o-mini occasionally flags non-issues at low confidence. The confidence system is designed to surface this.
5. **Rate limits** — Heavy usage may hit OpenAI rate limits. Adding exponential backoff retry is planned.
6. **No diff/PR mode** — Currently reviews full files. PR diff-only mode (via GitHub API) would reduce noise for incremental reviews.

---

## 🔮 What I'd Build Next

- **GitHub PR integration** — Post inline comments directly to pull requests via the GitHub REST API.
- **Multi-language support** — Add `tree-sitter` parsers for JavaScript, TypeScript, Go, and Java.
- **Incremental review** — Review only changed lines in a PR diff, not the full file.
- **Historical tracking** — Store results in SQLite and show issue trends over time.
- **Custom rule sets** — Let teams define project-specific rules (e.g., "always check for `logger.exception`").
- **Batch mode CLI** — Headless CLI for CI/CD pipeline integration.
- **Fine-tuned model** — Fine-tune on real GitHub code review datasets for higher precision.

---

## 📚 Data Sources & References

- Test repositories used for validation:
  - `pallets/flask` (MIT)
  - `psf/requests` (Apache 2.0)
  - `tiangolo/fastapi` (MIT)
- OpenAI GPT-4o-mini — LLM backbone
- Python `ast` module — Standard library AST parser
- GitPython — Python Git interface

---

## 🪪 License

MIT — see `LICENSE`.

---

*Built with ❤️ for CipherSchools AI/ML Mentor Role Assignment.*
