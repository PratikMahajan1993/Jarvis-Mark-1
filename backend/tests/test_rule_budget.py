"""Enforce .cursor/rules tiering budgets (manifest §2.9 + owner 2026-09-23 ruling)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_DIR = REPO_ROOT / ".cursor" / "rules"

T0_FILE = "00-jarvis-core.mdc"
T0_MAX_WORDS = 200
STANDARD_MAX_WORDS = 400
DOMAIN_MAX_WORDS = 750

DOMAIN_EXPANDED = {
    "domain/30-quote-playbook.mdc",
    "domain/31-gcode-optimiser.mdc",
    "domain/34-drawing-vision.mdc",
}

T2_DESCRIPTION_ONLY = {
    "ops/41-living-notes.mdc",
    "ops/42-dispatch.mdc",
}

LEGACY_ALWAYS_ON = {
    "jarvis-core.mdc",
    "jarvis-capability-run.mdc",
    "jarvis-subagent-dispatch.mdc",
    "jarvis-living-notes.mdc",
    "jarvis-react-bits.mdc",
}

EXPECTED_RULE_FILES = {
    T0_FILE,
    "backend/10-api-python.mdc",
    "backend/11-hitl-safety.mdc",
    "backend/12-data-schema.mdc",
    "backend/13-turn-ledger.mdc",
    "frontend/20-hud-shell.mdc",
    "frontend/21-react-bits.mdc",
    "frontend/22-frontend-uiux.mdc",
    *DOMAIN_EXPANDED,
    "domain/32-master-data.mdc",
    "domain/33-knowledge-rag.mdc",
    "ops/40-tests.mdc",
    *T2_DESCRIPTION_ONLY,
}


def _word_count(text: str) -> int:
    return len(text.split())


def _rel_path(path: Path) -> str:
    return path.relative_to(RULES_DIR).as_posix()


def _parse_frontmatter(content: str) -> dict[str, str]:
    match = re.match(r"^---\r?\n(.*?)\r?\n---", content, re.DOTALL)
    if not match:
        return {}
    fm: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip()
    return fm


def _all_rule_files() -> list[Path]:
    return sorted(RULES_DIR.rglob("*.mdc"))


@pytest.fixture(scope="module")
def rule_files() -> list[Path]:
    return _all_rule_files()


def test_no_legacy_always_on_rules(rule_files: list[Path]) -> None:
    names = {p.name for p in rule_files}
    assert not names & LEGACY_ALWAYS_ON, f"Remove legacy rules: {names & LEGACY_ALWAYS_ON}"


def test_expected_tree_only(rule_files: list[Path]) -> None:
    rel = {_rel_path(p) for p in rule_files}
    assert rel == EXPECTED_RULE_FILES, f"Unexpected rules: extra={rel - EXPECTED_RULE_FILES} missing={EXPECTED_RULE_FILES - rel}"


def test_t0_word_budget(rule_files: list[Path]) -> None:
    core = next(p for p in rule_files if p.name == T0_FILE)
    text = core.read_text(encoding="utf-8")
    count = _word_count(text)
    assert count < T0_MAX_WORDS, f"{T0_FILE}: {count} words (max {T0_MAX_WORDS - 1})"


def test_only_t0_always_apply(rule_files: list[Path]) -> None:
    always_on = []
    for path in rule_files:
        fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if fm.get("alwaysApply") == "true":
            always_on.append(_rel_path(path))
    assert always_on == [T0_FILE], f"alwaysApply: true only on T0, got {always_on}"


def test_t1_files_have_globs(rule_files: list[Path]) -> None:
    missing = []
    for path in rule_files:
        rel = _rel_path(path)
        if rel == T0_FILE or rel in T2_DESCRIPTION_ONLY:
            continue
        fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if not fm.get("globs"):
            missing.append(rel)
    assert not missing, f"T1 rules must declare globs: {missing}"


def test_t2_files_omit_globs(rule_files: list[Path]) -> None:
    bad = []
    for path in rule_files:
        rel = _rel_path(path)
        if rel not in T2_DESCRIPTION_ONLY:
            continue
        fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if fm.get("globs"):
            bad.append(rel)
        assert fm.get("alwaysApply") == "false", f"{rel} must set alwaysApply: false"
    assert not bad, f"T2 rules must omit globs: {bad}"


def test_word_budgets(rule_files: list[Path]) -> None:
    violations = []
    for path in rule_files:
        rel = _rel_path(path)
        text = path.read_text(encoding="utf-8")
        count = _word_count(text)
        if rel in DOMAIN_EXPANDED:
            cap = DOMAIN_MAX_WORDS
        else:
            cap = STANDARD_MAX_WORDS
        if count > cap:
            violations.append(f"{rel}: {count} > {cap}")
    assert not violations, "\n".join(violations)
