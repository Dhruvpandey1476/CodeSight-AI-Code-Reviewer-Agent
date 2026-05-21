# Suggested Git Commit History
# Run these in order to demonstrate incremental, meaningful commits across 3 days.
# Each block represents one logical commit.

# ── Day 1 ────────────────────────────────────────────────────────────────────

git init
git add .gitignore README.md requirements.txt LICENSE
git commit -m "chore: project scaffold, requirements, README skeleton"

git add src/__init__.py src/ingestion.py
git commit -m "feat(ingestion): add GitPython clone + URL validation"

git add src/parser.py
git commit -m "feat(parser): AST-based Python file parser with chunking"

git add tests/__init__.py tests/test_agent.py
git commit -m "test: unit tests for ingestion and parser modules"

# ── Day 2 ────────────────────────────────────────────────────────────────────

git add src/reviewer.py
git commit -m "feat(reviewer): OpenAI LLM review agent with structured JSON prompts"

git add src/report.py
git commit -m "feat(report): Markdown and CSV report generation"

git add tests/test_agent.py
git commit -m "test: add reviewer and report unit tests"

# ── Day 3 ────────────────────────────────────────────────────────────────────

git add app.py .streamlit/config.toml .streamlit/secrets.toml.example
git commit -m "feat(ui): Streamlit dashboard with filters, confidence bars, verify labels"

git add README.md
git commit -m "docs: complete README with architecture diagram, limitations, roadmap"

git add .
git commit -m "chore: deployment config, .env.example, final cleanup"
