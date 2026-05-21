"""
src/ingestion.py
Handles GitHub repository cloning and validation using GitPython.
"""

import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import git


def validate_repo_url(url: str) -> bool:
    pattern = r"^https://github\.com/[\w.\-]+/[\w.\-]+(\.git)?/?$"
    return bool(re.match(pattern, url.strip()))


def clone_repository(url: str) -> tuple[Path, str]:
    url = url.strip().rstrip("/")
    if not validate_repo_url(url):
        raise ValueError(f"Invalid GitHub URL: {url}")

    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")
    repo_name = f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else parts[-1]
    repo_name = repo_name.replace(".git", "")

    tmp_base = Path(tempfile.gettempdir()) / "codesight_repos"
    tmp_base.mkdir(exist_ok=True)

    safe_name = re.sub(r"[^\w\-]", "_", repo_name)
    dest = tmp_base / safe_name

    # Force delete even if it exists — fixes Windows "already exists" error
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=False, onerror=_force_remove)

    # Recreate clean directory
    dest.mkdir(parents=True, exist_ok=True)

    try:
        git.Repo.clone_from(
            url,
            str(dest),
            depth=1,
            single_branch=True,
        )
    except git.exc.GitCommandError as e:
        raise RuntimeError(f"Git clone failed: {e}") from e

    return dest, repo_name


def _force_remove(func, path, exc_info):
    """Error handler for shutil.rmtree on Windows — clears read-only flags."""
    import stat
    try:
        Path(path).chmod(stat.S_IWRITE)
        func(path)
    except Exception:
        pass