"""RBAC: viewer role is read-only; editor may mutate."""


def test_viewer_me_has_role(login_viewer):
    r = login_viewer.get("/api/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["login"] == "viewer"
    assert body["role"] == "viewer"


def test_pm_me_has_editor_role(login_pm):
    r = login_pm.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["role"] == "editor"


def test_viewer_can_read_and_export(login_viewer):
    r = login_viewer.get("/api/plans/current")
    assert r.status_code == 200
    assert len(r.json()["tasks"]) > 0
    r = login_viewer.get("/api/plans/current/export")
    assert r.status_code == 200
    r = login_viewer.get("/api/chat/messages")
    assert r.status_code == 200


def test_viewer_cannot_mutate(login_viewer):
    plan = login_viewer.get("/api/plans/current").json()
    task = next(t for t in plan["tasks"] if t.get("parent_id") is not None)

    r = login_viewer.patch(f"/api/plans/tasks/{task['id']}", json={"title": "Nope"})
    assert r.status_code == 403

    r = login_viewer.post("/api/plans/current/undo")
    assert r.status_code == 403

    r = login_viewer.post("/api/chat", data={"message": "отмени"})
    assert r.status_code == 403

    r = login_viewer.post("/api/plans/current/reset-seed")
    assert r.status_code == 403
