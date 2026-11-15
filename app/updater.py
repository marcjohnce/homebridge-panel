"""Updates to the latest stable GitHub release.

The panel is installed as a git checkout (deploy/install.sh). An update fetches the tags,
checks out the tag of the latest release (pre-releases and drafts are skipped – GitHub's
"latest release"), installs the requirements into the running Python environment and
then the app restarts (Controller).

A release counts as new when its tag is not part of the installed version yet (so a checkout
of main that is ahead of the release is never "updated" backwards) and its version number is
higher than the installed one.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import __version__

REPO_DIR = Path(__file__).resolve().parent.parent
DEFAULT_REPO = "marcjohnce/homebridge-panel"
_TAG_RE = re.compile(r"^v?\d+(\.\d+){0,3}$")
_GITHUB_RE = re.compile(r"github\.com[:/]+([\w.-]+/[\w.-]+?)(?:\.git)?/?$")


class UpdateError(Exception):
    pass


@dataclass
class UpdateCheck:
    current: str          # installed version, e.g. "0.0.3" or "0.0.3-4-g1a2b3c4"
    latest: str           # tag of the latest release, e.g. "v0.0.4"
    available: bool
    notes: str = ""


def parse_version(tag: str) -> tuple[int, ...] | None:
    m = re.match(r"^v?(\d+(?:\.\d+)*)", tag.strip())
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def _fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "smarthome-panel"})
    with urllib.request.urlopen(req, timeout=15) as resp:     # noqa: S310 (fixed https URL)
        return json.load(resp)


class Updater:
    def __init__(self, repo_dir: Path = REPO_DIR, fetch_json: Callable[[str], Any] = _fetch_json,
                 pip_command: list[str] | None = None):
        self.repo_dir = Path(repo_dir)
        self.fetch_json = fetch_json
        self.pip_command = pip_command or [sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"]

    # ---------- git ----------
    def _run(self, cmd: list[str], timeout: float = 120) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(cmd, cwd=self.repo_dir, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise UpdateError(str(e)) from e

    def _git(self, *args: str, timeout: float = 120) -> str:
        proc = self._run(["git", *args], timeout)
        if proc.returncode != 0:
            lines = (proc.stderr or proc.stdout).strip().splitlines()
            raise UpdateError(lines[-1] if lines else f"git {args[0]} failed")
        return proc.stdout.strip()

    @property
    def supported(self) -> bool:
        """Only a git checkout can be updated."""
        return (self.repo_dir / ".git").exists()

    def github_repo(self) -> str:
        try:
            m = _GITHUB_RE.search(self._git("remote", "get-url", "origin"))
        except UpdateError:
            m = None
        return m.group(1) if m else DEFAULT_REPO

    def installed(self) -> str:
        """Version of the checkout: the nearest tag (plus commits after it), else __version__."""
        try:
            return self._git("describe", "--tags").lstrip("v")
        except UpdateError:
            return __version__

    # ---------- check and install ----------
    def check(self) -> UpdateCheck:
        if not self.supported:
            raise UpdateError("not a git checkout")
        try:
            rel = self.fetch_json(f"https://api.github.com/repos/{self.github_repo()}/releases/latest")
        except Exception as e:      # network, HTTP 404 (no release yet), JSON
            raise UpdateError(str(e)) from e
        tag = str(rel.get("tag_name", "")) if isinstance(rel, dict) else ""
        if not _TAG_RE.match(tag):
            raise UpdateError(f"unexpected release tag {tag!r}")
        self._git("fetch", "--quiet", "--tags", "--force", "origin", timeout=60)
        current = self.installed()
        contained = self._run(["git", "merge-base", "--is-ancestor", f"refs/tags/{tag}", "HEAD"]).returncode == 0
        newer = (parse_version(tag) or ()) > (parse_version(current) or ())
        return UpdateCheck(current, tag, not contained and newer, str(rel.get("body") or ""))

    def install(self, tag: str) -> None:
        """Checks out the release and installs its requirements; goes back on failure."""
        if not _TAG_RE.match(tag):
            raise UpdateError(f"unexpected release tag {tag!r}")
        if self._git("status", "--porcelain", "--untracked-files=no"):
            raise UpdateError("the app folder has local changes")
        try:        # branch to go back to (a checkout of main), else the commit
            old = self._git("symbolic-ref", "--quiet", "--short", "HEAD")
        except UpdateError:
            old = self._git("rev-parse", "HEAD")
        self._git("fetch", "--quiet", "--tags", "--force", "origin", timeout=60)
        self._git("checkout", "--quiet", "--detach", f"refs/tags/{tag}")
        proc = self._run(self.pip_command, timeout=1800)
        if proc.returncode != 0:
            self._git("checkout", "--quiet", old)
            lines = (proc.stderr or proc.stdout).strip().splitlines()
            raise UpdateError(lines[-1] if lines else "pip install failed")
