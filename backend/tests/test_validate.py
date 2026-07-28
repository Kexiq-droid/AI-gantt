from __future__ import annotations

from backend.app.services.patch import apply_plan_patch_dict
from backend.app.services.validate import validate_plan_dict


def test_validate_unique_and_cycle():
    plan = {
        "title": "t",
        "start_date": "2026-03-01",
        "tasks": [
            {
                "code": "A",
                "parent": None,
                "title": "A",
                "duration_days": 1,
                "start_date": "2026-03-01",
                "sort_order": 1,
                "predecessors": ["B"],
            },
            {
                "code": "B",
                "parent": None,
                "title": "B",
                "duration_days": 1,
                "start_date": "2026-03-01",
                "sort_order": 2,
                "predecessors": ["A"],
            },
        ],
    }
    errs = validate_plan_dict(plan)
    assert any("цикл" in e.lower() or "Цикл" in e for e in errs)


def test_validate_bad_parent():
    plan = {
        "title": "t",
        "start_date": "2026-03-01",
        "tasks": [
            {
                "code": "A",
                "parent": "Z",
                "title": "A",
                "duration_days": 2,
                "start_date": "2026-03-01",
                "sort_order": 1,
                "predecessors": [],
            }
        ],
    }
    errs = validate_plan_dict(plan)
    assert errs


def test_patch_shift_and_validate():
    plan = {
        "title": "t",
        "start_date": "2026-03-01",
        "tasks": [
            {
                "code": "P2",
                "parent": None,
                "title": "Doc",
                "duration_days": 10,
                "start_date": "2026-03-01",
                "sort_order": 1,
                "predecessors": [],
            },
            {
                "code": "T2.1",
                "parent": "P2",
                "title": "In vitro",
                "duration_days": 5,
                "start_date": "2026-03-01",
                "sort_order": 2,
                "predecessors": [],
            },
        ],
    }
    new_plan, changes, errors = apply_plan_patch_dict(
        plan,
        {"operations": [{"op": "shift", "filter": {"phase_code": "P2"}, "days": 10}]},
    )
    assert not errors
    assert "P2" in changes and "T2.1" in changes
    assert new_plan["tasks"][0]["start_date"] == "2026-03-11"


def test_update_flat_duration_days():
    plan = {
        "title": "t",
        "start_date": "2026-03-01",
        "tasks": [
            {
                "code": "P1",
                "parent": None,
                "title": "Analytics",
                "duration_days": 15,
                "start_date": "2026-03-01",
                "sort_order": 1,
                "predecessors": [],
            }
        ],
    }
    new_plan, changes, errors = apply_plan_patch_dict(
        plan,
        {"operations": [{"op": "update", "code": "P1", "duration_days": 12}]},
    )
    assert not errors
    assert changes == ["P1"]
    assert new_plan["tasks"][0]["duration_days"] == 12


def test_shift_alias_type_and_by_days():
    plan = {
        "title": "t",
        "start_date": "2026-03-01",
        "tasks": [
            {
                "code": "P2",
                "parent": None,
                "title": "Doc",
                "duration_days": 10,
                "start_date": "2026-03-01",
                "sort_order": 1,
                "predecessors": [],
            }
        ],
    }
    new_plan, changes, errors = apply_plan_patch_dict(
        plan,
        {"operations": [{"type": "shift", "filter": {"phase_code": "P2"}, "by_days": 5}]},
    )
    assert not errors
    assert changes == ["P2"]
    assert new_plan["tasks"][0]["start_date"] == "2026-03-06"


def test_shift_filter_code_singular():
    plan = {
        "title": "t",
        "start_date": "2026-03-01",
        "tasks": [
            {
                "code": "T2.1",
                "parent": None,
                "title": "Leaf",
                "duration_days": 5,
                "start_date": "2026-03-01",
                "sort_order": 1,
                "predecessors": [],
            }
        ],
    }
    new_plan, changes, errors = apply_plan_patch_dict(
        plan,
        {"operations": [{"op": "shift", "filter": {"code": "T2.1"}, "days": 7}]},
    )
    assert not errors
    assert changes == ["T2.1"]
    assert new_plan["tasks"][0]["start_date"] == "2026-03-08"


def test_shift_empty_match_is_error():
    plan = {
        "title": "t",
        "start_date": "2026-03-01",
        "tasks": [
            {
                "code": "T2.1",
                "parent": None,
                "title": "Leaf",
                "duration_days": 5,
                "start_date": "2026-03-01",
                "sort_order": 1,
                "predecessors": [],
            }
        ],
    }
    new_plan, changes, errors = apply_plan_patch_dict(
        plan,
        {"operations": [{"op": "shift", "filter": {"code": "NOPE"}, "days": 7}]},
    )
    assert errors
    assert changes == []
    assert new_plan["tasks"][0]["start_date"] == "2026-03-01"
