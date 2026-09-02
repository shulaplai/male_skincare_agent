"""Tests for the fixed attribute schema + deterministic change detection (Q21/Q24).

The functions here operate on duck-typed entries ({date, attributes}), so tests
build tiny stand-ins instead of real ORM rows.
"""
import datetime
from types import SimpleNamespace

from app.agent.attributes import (
    build_change_lines,
    diff_attributes,
    find_anchor_entry,
    find_previous_entry,
    is_notable,
    severity_map,
)
from app.agent.schemas import SkinAnalysis


def _entry(date: str, attributes: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(date=datetime.date.fromisoformat(date), attributes=attributes)


def _day(date: str) -> datetime.date:
    return datetime.date.fromisoformat(date)


# --- severity_map / diff -----------------------------------------------------

def test_severity_map_extracts_key_severity():
    attrs = [{"key": "acne", "severity": 2}, {"key": "oiliness", "severity": 1, "note": "T"}]
    assert severity_map(attrs) == {"acne": 2, "oiliness": 1}


def test_diff_attributes_only_changed_keys():
    cur = {"acne": 1, "oiliness": 2, "redness": 1}
    prev = {"acne": 2, "oiliness": 2, "redness": 1}
    diffs = diff_attributes(cur, prev)
    assert len(diffs) == 1
    assert diffs[0]["key"] == "acne"
    assert diffs[0]["delta"] == -1  # improvement


def test_notable_threshold():
    # 1->2 with one side >= 2 is notable.
    assert is_notable({"delta": 1, "old": 1, "new": 2})
    # 0->1 never clears the floor -> noise, not an event.
    assert not is_notable({"delta": 1, "old": 0, "new": 1})
    assert not is_notable({"delta": 0, "old": 2, "new": 2})


# --- anchor lookup (Q12) -----------------------------------------------------

def test_find_previous_entry():
    today = _day("2026-03-10")
    entries = [_entry("2026-03-01", []), _entry("2026-03-09", []), _entry("2026-03-08", [])]
    assert find_previous_entry(entries, today).date == _day("2026-03-09")


def test_find_anchor_entry_fallback_within_tolerance():
    today = _day("2026-03-10")  # target ~2026-02-10 (28d)
    entries = [_entry("2026-02-05", []), _entry("2026-02-14", []), _entry("2026-01-01", [])]
    # 2026-02-14 is 4 days off target -> accepted (within +-7); 02-05 is 5 off -> also fine, nearest wins.
    anchor = find_anchor_entry(entries, today, 28)
    assert anchor.date == _day("2026-02-14")


def test_find_anchor_entry_skips_outside_tolerance():
    today = _day("2026-03-10")
    entries = [_entry("2025-11-01", []), _entry("2026-03-08", [])]
    # Nothing near 28d ago (2026-02-10): nearest candidate 03-08 is 26d away -> None.
    assert find_anchor_entry(entries, today, 28) is None


# --- build_change_lines (Q24: sparse, notable-only) --------------------------

def test_build_change_lines_empty_without_notable_changes():
    today = _day("2026-03-10")
    prev = _entry("2026-03-09", [{"key": "oiliness", "severity": 2}])
    cur = {"oiliness": 2}
    assert build_change_lines(cur, [prev], today) == []


def test_build_change_lines_reports_notable_previous_change():
    today = _day("2026-03-10")
    prev = _entry("2026-03-09", [{"key": "acne", "severity": 2}])
    cur = {"acne": 3}
    lines = build_change_lines(cur, [prev], today)
    assert len(lines) == 1
    assert "暗瘡" in lines[0]
    assert "惡化" in lines[0]
    assert "同上次比" in lines[0]


def test_build_change_lines_reports_long_anchor_change():
    today = _day("2026-03-10")
    # Recent entry unchanged vs today -> isolates the ~1M anchor signal.
    recent = _entry("2026-03-09", [{"key": "redness", "severity": 1}])
    month_ago = _entry("2026-02-10", [{"key": "redness", "severity": 3}])
    cur = {"redness": 1}
    lines = build_change_lines(cur, [recent, month_ago], today)
    assert any("改善" in l and "1 個月" in l for l in lines)


def test_build_change_lines_dedupes_repeated_anchors():
    today = _day("2026-03-10")
    prev = _entry("2026-03-09", [{"key": "acne", "severity": 2}])
    month_ago = _entry("2026-02-10", [{"key": "acne", "severity": 2}])
    cur = {"acne": 3}
    lines = build_change_lines(cur, [prev, month_ago], today)
    # Only the "vs previous" line survives; same change vs 1M ago is deduped.
    assert len(lines) == 1


# --- schema sanity -----------------------------------------------------------

def test_skin_analysis_accepts_fixed_attribute_keys():
    a = SkinAnalysis(
        summary="x",
        attributes=[
            {"key": "acne", "severity": 2},
            {"key": "texture", "severity": 1, "note": "粗糙"},
        ],
    )
    assert [x.key for x in a.attributes] == ["acne", "texture"]


def test_skin_analysis_rejects_unknown_attribute_key():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SkinAnalysis(summary="x", attributes=[{"key": "glowiness", "severity": 1}])
