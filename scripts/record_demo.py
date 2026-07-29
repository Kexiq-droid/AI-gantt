#!/usr/bin/env python3
"""Record BioPlan agent demo GIF: login → Gantt → agent actions → undo → gif.

Shows the main chat/agent capabilities (shift, reassign, create, analysis, undo).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "_demo_capture"
GIF_PATH = ROOT / "docs" / "demo.gif"
BASE = "http://127.0.0.1:8100"

# Main agent demo beats (order matters for a readable story)
PROMPTS: list[tuple[str, float]] = [
    # (message, hold_after_seconds)
    ("Сдвинь всю доклинику на 10 дней", 3.0),
    ("Назначь Иванова на все задачи фазы CMC", 3.0),
    (
        "Добавь задачу «Резервный анализ антигена» в доклинику на 5 дней после T2.3",
        3.0,
    ),
    ("Кто перегружен по числу задач?", 3.5),
    ("Отмени последнее", 2.5),
]


def hold(page, seconds: float) -> None:
    page.wait_for_timeout(int(seconds * 1000))


def ensure_chat_open(page) -> None:
    chat_heading = page.get_by_role("heading", name="Чат с планом")
    if not chat_heading.is_visible():
        open_chat = page.get_by_role(
            "button", name=re.compile(r"Открыть чат с ассистентом|Ассистент")
        )
        open_chat.first.click()
        chat_heading.wait_for()
    hold(page, 0.8)


def type_chat(page, text: str) -> None:
    """Type into chat so the GIF shows the prompt being entered."""
    box = page.get_by_placeholder("Напишите, что изменить в плане…")
    box.click()
    box.fill("")
    # Character-ish pacing without being painfully slow
    chunk = 3
    for i in range(0, len(text), chunk):
        box.press_sequentially(text[i : i + chunk], delay=18)
    hold(page, 0.6)


def send_and_wait(page, prompt: str, hold_after: float) -> None:
    type_chat(page, prompt)
    page.get_by_role("button", name="Отправить").click()
    thinking = page.get_by_text("Ассистент думает…")
    try:
        thinking.wait_for(timeout=15_000)
    except PlaywrightTimeout:
        pass
    try:
        thinking.wait_for(state="hidden", timeout=180_000)
    except PlaywrightTimeout:
        print(f"WARN: still busy after 180s for: {prompt[:60]}", file=sys.stderr)
    # Scroll chat to latest reply
    panel = page.locator("div").filter(has_text="Чат с планом").first
    try:
        page.evaluate(
            """() => {
              const roots = [...document.querySelectorAll('div')];
              const scrollables = roots.filter(el => el.scrollHeight > el.clientHeight + 40);
              const chat = scrollables.find(el => el.closest && el.innerText.includes('Чат'));
              if (chat) chat.scrollTop = chat.scrollHeight;
            }"""
        )
    except Exception:
        pass
    hold(page, hold_after)


def main() -> int:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    video_dir = OUT_DIR / "video"
    video_dir.mkdir(parents=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="ru-RU",
            record_video_dir=str(video_dir),
            record_video_size={"width": 1440, "height": 900},
            accept_downloads=True,
        )
        page = context.new_page()
        page.set_default_timeout(60_000)

        # 1. Login
        page.goto(BASE, wait_until="networkidle")
        hold(page, 1.0)
        page.get_by_role("button", name="Войти").click()
        page.get_by_text("BioPlan", exact=False).first.wait_for()
        hold(page, 1.5)

        # Clean seed so demo starts predictable
        page.get_by_role("button", name="Сбросить демо").click()
        dialog = page.get_by_role("dialog", name="Восстановить демо-план?")
        dialog.get_by_role("button", name="Сбросить", exact=True).click()
        page.get_by_text("Демо-план восстановлен").wait_for(timeout=15_000)
        hold(page, 1.5)

        ensure_chat_open(page)

        # 2. Show seeded VAX-B Gantt
        hold(page, 2.5)

        # 3–7. Agent prompts
        for prompt, pause in PROMPTS:
            send_and_wait(page, prompt, pause)

        # 8. UI undo (stack) — visible control
        undo = page.get_by_role("button", name=re.compile(r"^← Отменить"))
        if undo.count() and undo.first.get_attribute("aria-disabled") != "true":
            undo.first.click()
            try:
                page.get_by_text("Изменение отменено").wait_for(timeout=10_000)
            except PlaywrightTimeout:
                pass
            hold(page, 2.0)

        # 9. Journal peek
        journal = page.get_by_role("button", name="Журнал ассистента")
        if journal.count():
            journal.first.click()
            hold(page, 2.5)
            overlay = page.locator(".fixed.inset-0").filter(has_text="Журнал ассистента")
            if overlay.count():
                overlay.first.click(position={"x": 12, "y": 12})
            hold(page, 1.0)

        hold(page, 1.2)
        page.close()
        context.close()
        browser.close()

    videos = list(video_dir.glob("*.webm"))
    if not videos:
        print("ERROR: no video recorded", file=sys.stderr)
        return 1
    webm = max(videos, key=lambda p: p.stat().st_mtime)
    print(f"video: {webm} ({webm.stat().st_size} bytes)")

    # Readable size for README embeds
    palette = OUT_DIR / "palette.png"
    vf = "fps=10,scale=960:-1:flags=lanczos"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(webm),
            "-vf",
            f"{vf},palettegen=stats_mode=diff",
            str(palette),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(webm),
            "-i",
            str(palette),
            "-lavfi",
            f"{vf}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5",
            "-loop",
            "0",
            str(GIF_PATH),
        ],
        check=True,
        capture_output=True,
    )
    print(f"gif: {GIF_PATH} ({GIF_PATH.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
