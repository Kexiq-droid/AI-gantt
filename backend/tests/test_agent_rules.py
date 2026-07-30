"""Rule-based agent: compound multi-intent prompts."""

from backend.app.services.agent import (
    _parse_all_reassigns,
    _parse_all_shifts,
    _parse_reassign,
    _parse_shift,
    _split_intent_clauses,
)
from backend.app.services.patch import apply_plan_patch_dict


GOLDEN = "Сдвинь всю доклинику на 10 дней и назначь Иванова на все задачи фазы CMC"


def _plan():
    return {
        "title": "Demo",
        "start_date": "2026-07-28",
        "tasks": [
            {
                "code": "P2",
                "parent": None,
                "title": "Доклиника",
                "description": "",
                "assignee": "",
                "duration_days": 10,
                "start_date": "2026-07-28",
                "sort_order": 1,
                "predecessors": [],
            },
            {
                "code": "T2.1",
                "parent": "P2",
                "title": "In vitro",
                "description": "",
                "assignee": "Петрова",
                "duration_days": 5,
                "start_date": "2026-07-28",
                "sort_order": 2,
                "predecessors": [],
            },
            {
                "code": "P3",
                "parent": None,
                "title": "CMC",
                "description": "",
                "assignee": "",
                "duration_days": 10,
                "start_date": "2026-08-10",
                "sort_order": 3,
                "predecessors": ["P2"],
            },
            {
                "code": "T3.1",
                "parent": "P3",
                "title": "Синтез",
                "description": "",
                "assignee": "Смирнов",
                "duration_days": 5,
                "start_date": "2026-08-10",
                "sort_order": 4,
                "predecessors": [],
            },
            {
                "code": "T3.2",
                "parent": "P3",
                "title": "Аналитика",
                "description": "",
                "assignee": "Орлова",
                "duration_days": 5,
                "start_date": "2026-08-15",
                "sort_order": 5,
                "predecessors": ["T3.1"],
            },
            {
                "code": "P4",
                "parent": None,
                "title": "Регуляторика",
                "description": "",
                "assignee": "",
                "duration_days": 10,
                "start_date": "2026-08-20",
                "sort_order": 6,
                "predecessors": [],
            },
            {
                "code": "T4.1",
                "parent": "P4",
                "title": "CTD",
                "description": "",
                "assignee": "Васильева",
                "duration_days": 5,
                "start_date": "2026-08-20",
                "sort_order": 7,
                "predecessors": [],
            },
        ],
    }


def test_parse_shift_all_tasks_back():
    text = "Смести все задачи на 5 дней назад"
    shifts = _parse_all_shifts(text)
    assert shifts == [{"filter": {"all": True}, "days": -5}]


def test_is_mass_delete_phrases():
    from backend.app.services.agent import _is_mass_delete, _is_cancel, _is_confirm

    assert _is_mass_delete("Удали все задачи")
    assert _is_mass_delete("удали все")
    assert _is_mass_delete("Очисти план")
    assert _is_mass_delete("очисти весь план")
    assert _is_mass_delete("Удали T2.1") is False
    assert _is_confirm("да")
    assert _is_confirm("подтверждаю")
    assert _is_cancel("нет")
    assert _is_cancel("отмена")


def test_patch_clear_all():
    plan = _plan()
    new_plan, changes, errors = apply_plan_patch_dict(
        plan, {"operations": [{"op": "delete", "filter": {"all": True}}]}
    )
    assert not errors
    assert new_plan["tasks"] == []
    assert set(changes) == {"P2", "T2.1", "P3", "T3.1", "T3.2", "P4", "T4.1"}


def test_parse_shift_whole_plan_forward():
    text = "Сдвинь весь план на 3 дня"
    shifts = _parse_all_shifts(text)
    assert shifts == [{"filter": {"all": True}, "days": 3}]


def test_patch_shift_all_moves_every_task():
    plan = _plan()
    before = {t["code"]: t["start_date"] for t in plan["tasks"]}
    new_plan, changes, errors = apply_plan_patch_dict(
        plan, {"operations": [{"op": "shift", "filter": {"all": True}, "days": -5}]}
    )
    assert not errors
    after = {t["code"]: t["start_date"] for t in new_plan["tasks"]}
    assert set(changes) == set(before)
    assert after["T2.1"] == "2026-07-23"
    assert after["T3.1"] == "2026-08-05"


def test_parse_compound_shift_and_reassign():
    shifts = _parse_all_shifts(GOLDEN)
    reassigns = _parse_all_reassigns(GOLDEN)
    assert shifts == [{"filter": {"phase_code": "P2"}, "days": 10}]
    assert len(reassigns) == 1
    assert reassigns[0]["filter"] == {"phase_code": "P3"}
    assert reassigns[0]["assignee"].startswith("Иванов")


def test_parse_two_task_shifts():
    text = "Сдвинь T2.1 на 5 дней и T3.1 на 3 дня"
    shifts = _parse_all_shifts(text)
    assert {"filter": {"code": "T2.1"}, "days": 5} in shifts
    assert {"filter": {"code": "T3.1"}, "days": 3} in shifts


def test_parse_two_phase_shifts():
    text = "Сдвинь доклинику на 10 дней и CMC на 5 дней"
    shifts = _parse_all_shifts(text)
    assert {"filter": {"phase_code": "P2"}, "days": 10} in shifts
    assert {"filter": {"phase_code": "P3"}, "days": 5} in shifts


def test_parse_two_reassigns():
    text = "Назначь Иванова на CMC и назначь Петрову на регуляторику"
    items = _parse_all_reassigns(text)
    assert len(items) == 2
    phases = {i["filter"]["phase_code"] for i in items}
    assert phases == {"P3", "P4"}


def test_parse_reassign_codes():
    text = "Назначь Иванова на T3.1 и T3.2"
    items = _parse_all_reassigns(text)
    assert len(items) == 1
    assert items[0]["filter"]["codes"] == ["T3.1", "T3.2"]


def test_split_intent_clauses():
    parts = _split_intent_clauses(GOLDEN)
    assert len(parts) == 2
    assert "сдвинь" in parts[0].lower()
    assert "назначь" in parts[1].lower()


def test_compound_patch_shifts_and_reassigns():
    shift = _parse_shift(GOLDEN)
    name, phase = _parse_reassign(GOLDEN)
    assignee = "Иванов" if name.startswith("Иванов") else name
    ops = [
        {"op": "shift", "filter": shift["filter"], "days": shift["days"]},
        {"op": "reassign", "filter": {"phase_code": phase}, "assignee": assignee},
    ]
    new_plan, changes, errors = apply_plan_patch_dict(_plan(), {"operations": ops})
    assert not errors
    by = {t["code"]: t for t in new_plan["tasks"]}
    assert by["T2.1"]["start_date"] == "2026-08-07"
    assert by["T3.1"]["assignee"] == "Иванов"
    assert "T2.1" in changes and "T3.1" in changes


def test_responsible_reassign_with_branch_context():
    text = "Сдвинь всю ветку p2 на 10 дней вперед и назначь смирнова ответсвенным"
    shifts = _parse_all_shifts(text)
    reassigns = _parse_all_reassigns(text)
    assert shifts and shifts[0]["filter"]["phase_code"] == "P2"
    assert any(r.get("needs_context") for r in reassigns)
    from backend.app.services.agent import _infer_reassign_filter_from_context

    filt = _infer_reassign_filter_from_context(text, shifts)
    assert filt == {"phase_code": "P2"}
    name = next(r["assignee"] for r in reassigns if r.get("needs_context"))
    assert name.lower().startswith("смирнов")
    ops = [
        {"op": "shift", "filter": shifts[0]["filter"], "days": shifts[0]["days"]},
        {"op": "reassign", "filter": filt, "assignee": "Смирнов"},
    ]
    new_plan, changes, errors = apply_plan_patch_dict(_plan(), {"operations": ops})
    assert not errors
    by = {t["code"]: t for t in new_plan["tasks"]}
    assert by["T2.1"]["start_date"] == "2026-08-07"
    assert by["T2.1"]["assignee"] == "Смирнов"
    assert by["P2"]["assignee"] == "Смирнов"


def test_ops_limit_requires_clarification():
    from backend.app.services.agent import MAX_BATCH_OPS, _ops_limit_result

    ok = _ops_limit_result([{"op": "shift"}] * MAX_BATCH_OPS)
    assert ok is None
    over = _ops_limit_result([{"op": "shift"}] * (MAX_BATCH_OPS + 1))
    assert over is not None
    assert over["need_chunking"] is True
    assert over["need_clarification"] is False
    assert over["count"] == MAX_BATCH_OPS + 1
    creates = [
        {"op": "create", "code": f"T8.{i}", "title": f"t{i}", "duration_days": 1}
        for i in range(1, 10)
    ]
    assert _ops_limit_result(creates) is None


def test_multi_shift_and_multi_reassign_patch():
    text = (
        "Сдвинь T2.1 на 5 дней и T3.1 на 3 дня "
        "и назначь Иванова на CMC и назначь Петрову на регуляторику"
    )
    ops = []
    for s in _parse_all_shifts(text):
        ops.append({"op": "shift", "filter": s["filter"], "days": s["days"]})
    for r in _parse_all_reassigns(text):
        name = r["assignee"]
        if name.startswith("Иванов"):
            name = "Иванов"
        elif name.startswith("Петров"):
            name = "Петрова"
        ops.append({"op": "reassign", "filter": r["filter"], "assignee": name})
    assert len(ops) >= 4
    new_plan, changes, errors = apply_plan_patch_dict(_plan(), {"operations": ops})
    assert not errors
    by = {t["code"]: t for t in new_plan["tasks"]}
    assert by["T2.1"]["start_date"] == "2026-08-02"
    assert by["T3.1"]["start_date"] == "2026-08-13"
    assert by["T3.1"]["assignee"] == "Иванов"
    assert by["T3.2"]["assignee"] == "Иванов"
    assert by["T4.1"]["assignee"] == "Петрова"
