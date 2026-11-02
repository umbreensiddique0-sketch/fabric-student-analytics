"""
check_secrets.py
================
Lightweight scan for accidentally committed secrets. Looks for common
high-risk patterns (AWS access-key IDs, private-key blocks, obvious secret
assignments) in source / config files and exits non-zero if any are found.

Patterns are deliberately conservative to avoid false positives on normal
project code. Run locally and in CI:

    python scripts/check_secrets.py
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Directories whose contents we do not scan (envs, caches, generated data/outputs).
EXCLUDE_DIRS = {".venv", "venv", "env", ".git", "__pycache__", ".pytest_cache",
                "data", "outputs", "evidence"}

EXTENSIONS = (".py", ".yml", ".yaml", ".md", ".txt", ".json", ".toml",
              ".cfg", ".ini", ".env")

PATTERNS = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key id"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key block"),
    (
        re.compile(
            r"(?i)(password|passwd|secret|api[_-]?key|auth[_-]?token)\s*=\s*"
            r"['\"][A-Za-z0-9/+=_\-]{12,}['\"]"
        ),
        "secret assignment",
    ),
]


def _iter_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in EXTENSIONS:
                yield os.path.join(dirpath, fn)


def main() -> int:
    findings = []
    for path in _iter_files():
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except OSError:
            continue
        for pattern, label in PATTERNS:
            for match in pattern.finditer(content):
                findings.append((os.path.relpath(path, ROOT), label, match.group(0)[:30]))

    if findings:
        print("Secret scan FAILED - potential secrets found:")
        for rel, label, sample in findings:
            print(f"  {rel}: {label} -> {sample}...")
        return 1

    print("Secret scan PASSED - no high-risk patterns detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
