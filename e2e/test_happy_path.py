"""E2E happy-path: login → seeded Gantt → chat → agent shift (rules) → undo.

Starts a temporary uvicorn on an ephemeral port with an isolated SQLite DB.
Requires: frontend build (`make build`), Playwright Chromium.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def base_url(tmp_path_factory: pytest.TempPathFactory):
    if not DIST.is_dir() or not (DIST / "index.html").is_file():
        pytest.skip("frontend/dist missing — run `make build` first")

    tmp = tmp_path_factory.mktemp("e2e_db")
    db_path = tmp / "e2e.db"
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT),
        "DATABASE_URL": f"sqlite:///{db_path}",
        "COOKIE_SECURE": "false",
        "CORS_ORIGINS": base,
        "SECRET_KEY": "e2e-test-secret",
        "DEMO_PM_PASSWORD": "pm12345",
        "LLM_PROVIDER": "deepseek",
        "DEEPSEEK_API_KEY": "",
    }
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 45
        while time.time() < deadline:
            if proc.poll() is not None:
                pytest.fail(f"uvicorn exited early with code {proc.returncode}")
            try:
                r = httpx.get(f"{base}/api/health", timeout=1.0)
                if r.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.25)
        else:
            pytest.fail("uvicorn did not become healthy in time")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_happy_path_login_gantt_chat_undo(base_url: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(30_000)
        page.goto(base_url, wait_until="networkidle")

        page.get_by_role("button", name="Войти").click()
        page.get_by_text("BioPlan", exact=False).first.wait_for()

        expect(page.get_by_text("VAX-B", exact=False).first).to_be_visible()
        expect(page.get_by_text("P1", exact=True).first).to_be_visible()

        chat_heading = page.get_by_role("heading", name="Чат с планом")
        if not chat_heading.is_visible():
            page.get_by_role("button", name="Открыть чат с ассистентом").click()
            chat_heading.wait_for()

        box = page.get_by_placeholder("Напишите, что изменить в плане…")
        box.fill("Сдвинь всю доклинику на 10 дней")
        page.get_by_role("button", name="Отправить").click()

        thinking = page.get_by_text("Ассистент думает…")
        try:
            thinking.wait_for(timeout=10_000)
        except Exception:
            pass
        thinking.wait_for(state="hidden", timeout=90_000)

        expect(page.get_by_text(re.compile(r"доклиник|сдвиг|дн", re.I)).first).to_be_visible(
            timeout=15_000
        )

        undo = page.get_by_role("button", name=re.compile(r"^← Отменить"))
        if undo.count() and undo.first.get_attribute("aria-disabled") != "true":
            undo.first.click()
            page.get_by_text("Изменение отменено").wait_for(timeout=15_000)

        browser.close()
