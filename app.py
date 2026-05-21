"""
AI Code Review Agent — Main Streamlit Application
CipherSchools Assignment
"""

import streamlit as st
import json
import os
import time
from pathlib import Path

from src.ingestion import clone_repository, validate_repo_url
from src.parser import parse_repository
from src.reviewer import ReviewAgent
from src.report import generate_markdown_report, generate_csv_report

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CodeSight — AI Review Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

:root {
    --bg: #0d0f14;
    --surface: #161a22;
    --border: #252b38;
    --accent: #4fffb0;
    --accent2: #ff6b6b;
    --accent3: #ffd93d;
    --text: #e2e8f0;
    --muted: #6b7280;
    --critical: #ef4444;
    --high: #f97316;
    --medium: #eab308;
    --low: #22c55e;
    --info: #3b82f6;
}

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background-color: var(--bg);
    color: var(--text);
}

.stApp { background-color: var(--bg); }

/* Header */
.hero-header {
    text-align: center;
    padding: 2.5rem 0 1.5rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 2rem;
}
.hero-title {
    font-family: 'Space Mono', monospace;
    font-size: 2.8rem;
    font-weight: 700;
    color: var(--accent);
    letter-spacing: -1px;
    margin: 0;
}
.hero-subtitle {
    color: var(--muted);
    font-size: 1rem;
    margin-top: 0.4rem;
    font-weight: 300;
}

/* Cards */
.metric-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    text-align: center;
}
.metric-value {
    font-family: 'Space Mono', monospace;
    font-size: 2.2rem;
    font-weight: 700;
    color: var(--accent);
}
.metric-label {
    font-size: 0.78rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 0.2rem;
}

/* Severity badges */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 99px;
    font-size: 0.72rem;
    font-weight: 600;
    font-family: 'Space Mono', monospace;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.badge-critical { background: rgba(239,68,68,0.15); color: #ef4444; border: 1px solid rgba(239,68,68,0.3); }
.badge-high     { background: rgba(249,115,22,0.15); color: #f97316; border: 1px solid rgba(249,115,22,0.3); }
.badge-medium   { background: rgba(234,179,8,0.15);  color: #eab308; border: 1px solid rgba(234,179,8,0.3); }
.badge-low      { background: rgba(34,197,94,0.15);  color: #22c55e; border: 1px solid rgba(34,197,94,0.3); }
.badge-info     { background: rgba(59,130,246,0.15); color: #3b82f6; border: 1px solid rgba(59,130,246,0.3); }

/* Verify label */
.verify-label {
    display: inline-block;
    background: rgba(255,107,107,0.12);
    color: #ff6b6b;
    border: 1px solid rgba(255,107,107,0.3);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.7rem;
    font-family: 'Space Mono', monospace;
    margin-left: 6px;
}

/* Comment card */
.comment-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 0.8rem;
    transition: border-color 0.2s;
}
.comment-card:hover { border-color: var(--accent); }
.comment-card.low-confidence { border-left: 3px solid #ff6b6b; }

.comment-title {
    font-family: 'Space Mono', monospace;
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--accent);
    margin-bottom: 0.4rem;
}
.comment-body {
    font-size: 0.88rem;
    color: var(--text);
    line-height: 1.6;
    margin-bottom: 0.6rem;
}
.comment-suggestion {
    background: rgba(79,255,176,0.06);
    border-left: 2px solid var(--accent);
    padding: 0.5rem 0.8rem;
    border-radius: 0 6px 6px 0;
    font-size: 0.83rem;
    color: #a7f3d0;
    margin-top: 0.5rem;
}
.comment-meta {
    display: flex;
    gap: 0.8rem;
    align-items: center;
    flex-wrap: wrap;
    margin-top: 0.6rem;
}
.meta-chip {
    font-size: 0.72rem;
    color: var(--muted);
    font-family: 'Space Mono', monospace;
}

/* Confidence bar */
.conf-bar-wrapper { display: flex; align-items: center; gap: 8px; margin-top: 4px; }
.conf-bar-bg {
    flex: 1; height: 5px; background: var(--border); border-radius: 99px; overflow: hidden;
}
.conf-bar-fill {
    height: 100%; border-radius: 99px; transition: width 0.4s;
}

/* Section headers */
.section-header {
    font-family: 'Space Mono', monospace;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.5rem;
    margin: 1.5rem 0 1rem;
}

/* Sidebar tweaks */
[data-testid="stSidebar"] {
    background-color: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
}

/* Input overrides */
.stTextInput input, .stSelectbox select {
    background-color: #1e2330 !important;
    border-color: var(--border) !important;
    color: var(--text) !important;
}

/* Buttons */
.stButton button {
    background: var(--accent) !important;
    color: #0d0f14 !important;
    border: none !important;
    font-family: 'Space Mono', monospace !important;
    font-weight: 700 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.5px !important;
    border-radius: 8px !important;
    transition: opacity 0.2s !important;
}
.stButton button:hover { opacity: 0.85 !important; }

/* Progress & spinner */
.stProgress > div > div { background-color: var(--accent) !important; }

/* Low confidence section */
.verify-section {
    background: rgba(255,107,107,0.04);
    border: 1px dashed rgba(255,107,107,0.3);
    border-radius: 12px;
    padding: 1.2rem;
    margin-top: 1.5rem;
}
.verify-section-title {
    font-family: 'Space Mono', monospace;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: #ff6b6b;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-header">
    <div class="hero-title">🔍 CodeSight</div>
    <div class="hero-subtitle">Autonomous AI Code Review Agent · AST-powered · Confidence-rated</div>
</div>
""", unsafe_allow_html=True)


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")

    repo_url = st.text_input(
        "GitHub Repository URL",
        placeholder="https://github.com/user/repo",
        help="Public GitHub repository to review",
    )

    api_key = st.text_input(
        "Groq API Key",
        type="password",
        help="Your Groq API key",
        value=os.environ.get("GROQ_API_KEY", ""),
    )

    model_choice = st.selectbox(
        "LLM Model",
        ["llama3-70b-8192"],

        index=0,
    )

    max_files = st.slider("Max files to review", 5, 50, 20)
    confidence_threshold = st.slider("Low-confidence threshold", 10, 60, 40,
                                      help="Comments below this % get 'verify' label")

    st.markdown("---")
    st.markdown("### 🔎 Filters (post-analysis)")
    severity_filter = st.multiselect(
        "Severity",
        ["critical", "high", "medium", "low", "info"],
        default=["critical", "high", "medium", "low", "info"],
    )
    category_filter = st.multiselect(
        "Category",
        ["bug", "security", "performance", "style", "maintainability", "documentation"],
        default=["bug", "security", "performance", "style", "maintainability", "documentation"],
    )
    show_low_conf_only = st.checkbox("Show low-confidence only")

    st.markdown("---")
    st.caption("Built for CipherSchools · AI/ML Assignment")

# ── Main Area ──────────────────────────────────────────────────────────────────
run_col, _ = st.columns([1, 3])
with run_col:
    run_btn = st.button("▶ Run Analysis", use_container_width=True)

if run_btn:
    # Validation
    if not repo_url:
        st.error("Please enter a GitHub repository URL.")
        st.stop()
    if not api_key:
        st.error("Please enter your OpenAI API key.")
        st.stop()
    if not validate_repo_url(repo_url):
        st.error("Invalid GitHub URL. Use format: https://github.com/owner/repo")
        st.stop()

    os.environ["OPENAI_API_KEY"] = api_key

    # ── Pipeline ────────────────────────────────────────────────────────────
    progress = st.progress(0, text="Initializing...")
    status   = st.empty()

    # Step 1: Clone
    status.info("📥 Cloning repository…")
    progress.progress(10, text="Cloning repository…")
    try:
        repo_path, repo_name = clone_repository(repo_url)
        status.success(f"✅ Cloned `{repo_name}`")
    except Exception as e:
        st.error(f"Failed to clone repository: {e}")
        st.stop()

    # Step 2: Parse
    progress.progress(30, text="Parsing source files…")
    status.info("🌲 Parsing AST…")
    try:
        parsed_files = parse_repository(repo_path, max_files=max_files)
        status.success(f"✅ Parsed {len(parsed_files)} files")
    except Exception as e:
        st.error(f"Failed to parse repository: {e}")
        st.stop()

    if not parsed_files:
        st.warning("No Python files found in repository.")
        st.stop()

    # Step 3: LLM Review
    # Step 3: LLM Review
    progress.progress(50, text="Sending to LLM for review…")
    status.info("🤖 AI reviewing code…")

    agent = ReviewAgent(api_key=api_key, model=model_choice,
                        confidence_threshold=confidence_threshold)
    all_comments = []
    total = len(parsed_files)
    error_log = []

    for i, pf in enumerate(parsed_files):
        pct = 50 + int((i / total) * 40)
        progress.progress(pct, text=f"Reviewing {pf['filename']} ({i+1}/{total})…")
        try:
            comments = agent.review_file(pf)
            all_comments.extend(comments)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            error_log.append(f"**{pf['filename']}**: `{type(e).__name__}: {e}`\n```\n{tb}\n```")

    if error_log:
        with st.expander("⚠️ Errors during review", expanded=True):       
            for err in error_log:
                st.markdown(err)

    if not all_comments:
        st.error("❌ No comments generated. See debug log above for the exact error.")
        st.stop()

    status.success(f"✅ Generated {len(all_comments)} review comments")
    
    # Step 4: Reports
    md_report  = generate_markdown_report(repo_name, all_comments, parsed_files)
    csv_report = generate_csv_report(all_comments)

    progress.progress(100, text="Done!")
    time.sleep(0.4)
    progress.empty()
    status.empty()

    # ── Store in session ─────────────────────────────────────────────────────
    st.session_state["results"] = {
        "repo_name":   repo_name,
        "comments":    all_comments,
        "parsed":      parsed_files,
        "md_report":   md_report,
        "csv_report":  csv_report,
        "conf_thresh": confidence_threshold,
    }

# ── Results Display ─────────────────────────────────────────────────────────
if "results" in st.session_state:
    R            = st.session_state["results"]
    all_comments = R["comments"]
    repo_name    = R["repo_name"]
    conf_thresh  = R.get("conf_thresh", confidence_threshold)

    # Apply filters
    filtered = [
        c for c in all_comments
        if c.get("severity", "info") in severity_filter
        and c.get("category", "style") in category_filter
    ]
    if show_low_conf_only:
        filtered = [c for c in filtered if c.get("confidence", 100) < conf_thresh]

    # ── Metrics row ───────────────────────────────────────────────────────
    st.markdown(f'<div class="section-header">📊 Summary — {repo_name}</div>', unsafe_allow_html=True)

    counts = {s: sum(1 for c in all_comments if c.get("severity") == s)
              for s in ["critical", "high", "medium", "low", "info"]}
    avg_conf = (sum(c.get("confidence", 50) for c in all_comments) / len(all_comments)
                if all_comments else 0)
    low_conf_count = sum(1 for c in all_comments if c.get("confidence", 100) < conf_thresh)

    cols = st.columns(6)
    metrics = [
        ("Total Issues", len(all_comments), "#4fffb0"),
        ("Critical",     counts["critical"], "#ef4444"),
        ("High",         counts["high"],     "#f97316"),
        ("Medium",       counts["medium"],   "#eab308"),
        ("Avg Confidence", f"{avg_conf:.0f}%", "#3b82f6"),
        ("Verify These",  low_conf_count,    "#ff6b6b"),
    ]
    for col, (label, val, color) in zip(cols, metrics):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value" style="color:{color}">{val}</div>
                <div class="metric-label">{label}</div>
            </div>""", unsafe_allow_html=True)

    # ── Downloads ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">💾 Export</div>', unsafe_allow_html=True)
    dl1, dl2, _ = st.columns([1, 1, 3])
    with dl1:
        st.download_button("📄 Download Markdown", R["md_report"],
                           file_name="review_report.md", mime="text/markdown")
    with dl2:
        st.download_button("📊 Download CSV", R["csv_report"],
                           file_name="review_comments.csv", mime="text/csv")

    # ── High-confidence comments ──────────────────────────────────────────
    high_conf = [c for c in filtered if c.get("confidence", 100) >= conf_thresh]
    low_conf  = [c for c in filtered if c.get("confidence", 100) < conf_thresh]

    st.markdown(f'<div class="section-header">🔍 Review Comments ({len(filtered)} shown)</div>',
                unsafe_allow_html=True)

    def severity_color(s):
        return {"critical": "#ef4444", "high": "#f97316",
                "medium": "#eab308", "low": "#22c55e", "info": "#3b82f6"}.get(s, "#6b7280")

    def render_comment(c, low=False):
        sev   = c.get("severity", "info")
        conf  = c.get("confidence", 50)
        color = severity_color(sev)
        bar_color = "#4fffb0" if conf >= 70 else "#ffd93d" if conf >= 40 else "#ff6b6b"
        verify_html = '<span class="verify-label">⚠ verify this</span>' if low else ""

        suggestion_html = ""
        if c.get("suggestion"):
            suggestion_html = f'<div class="comment-suggestion">💡 {c["suggestion"]}</div>'

        st.markdown(f"""
        <div class="comment-card {'low-confidence' if low else ''}">
            <div class="comment-title">
                <span class="badge badge-{sev}">{sev}</span>
                &nbsp; {c.get('title', 'Issue')} {verify_html}
            </div>
            <div class="comment-body">{c.get('comment', '')}</div>
            {suggestion_html}
            <div class="comment-meta">
                <span class="meta-chip">📁 {c.get('filename','')}</span>
                <span class="meta-chip">📌 {c.get('location','')}</span>
                <span class="meta-chip">🏷 {c.get('category','')}</span>
            </div>
            <div class="conf-bar-wrapper">
                <span class="meta-chip">Confidence</span>
                <div class="conf-bar-bg">
                    <div class="conf-bar-fill" style="width:{conf}%;background:{bar_color}"></div>
                </div>
                <span class="meta-chip">{conf}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    if high_conf:
        for c in high_conf:
            render_comment(c, low=False)
    else:
        st.info("No high-confidence comments match current filters.")

    # ── Low-confidence section ─────────────────────────────────────────────
    if low_conf:
        st.markdown(f"""
        <div class="verify-section">
            <div class="verify-section-title">⚠ Verify These — Low Confidence ({len(low_conf)})</div>
        """, unsafe_allow_html=True)
        for c in low_conf:
            render_comment(c, low=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Parsed file details (expandable) ──────────────────────────────────
    with st.expander("📂 Parsed File Details"):
        for pf in R["parsed"]:
            st.markdown(f"**`{pf['filename']}`** — "
                        f"{pf.get('num_functions',0)} functions · "
                        f"{pf.get('num_classes',0)} classes · "
                        f"{pf.get('num_imports',0)} imports · "
                        f"{pf.get('lines',0)} lines")
