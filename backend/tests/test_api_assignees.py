"""Assignees catalog API."""


def test_assignees_crud(login_pm):
    r = login_pm.get("/api/plans/assignees")
    assert r.status_code == 200
    names = {a["name"] for a in r.json()}
    assert len(names) > 0

    created = login_pm.post("/api/plans/assignees", json={"name": "Новиков"})
    assert created.status_code == 200, created.text
    assert created.json()["name"] == "Новиков"
    aid = created.json()["id"]

    again = login_pm.get("/api/plans/assignees")
    assert any(a["name"] == "Новиков" for a in again.json())

    deleted = login_pm.delete(f"/api/plans/assignees/{aid}")
    assert deleted.status_code == 200
    final = login_pm.get("/api/plans/assignees")
    assert all(a["name"] != "Новиков" for a in final.json())
