"""Tests for the Dependabot triage classifier."""

import json
from pathlib import Path

import pytest

from scripts.security import dep_triage as dt

FIXTURE = Path("tests/fixtures/dep_triage/batch_2026_09_19.json")


def test_load_snapshot_reads_all_prs():
    prs = dt.load_snapshot(FIXTURE)
    assert len(prs) == 7
    assert {p.number for p in prs} == {386, 439, 442, 443, 446, 450, 452}


def test_load_snapshot_parses_checks_and_metadata():
    prs = {p.number: p for p in dt.load_snapshot(FIXTURE)}
    pr = prs[443]
    assert pr.author == "dependabot[bot]"
    assert pr.ecosystem == "npm"
    assert pr.directory == "/frontend"
    assert pr.package == "@vitest/coverage-v8"
    assert pr.from_version == "4.1.11"
    assert pr.to_version == "5.0.0"
    assert all(c.conclusion == "success" for c in pr.checks)


def test_snapshot_is_immutable():
    pr = dt.load_snapshot(FIXTURE)[0]
    with pytest.raises(Exception):
        pr.number = 1  # frozen dataclass
