#!/usr/bin/env python3
"""Record BioPlan demo: login → Gantt → Excel import → chat → undo → export → gif."""

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
XLSX = ROOT / "examples" / "plan_biokad_demo.xlsx"
BASE = "http://127.0.0.1:8100"
PROMPT = "Сдвинь всю доклинику на 10 дней и назначь Иванова на все задачи фазы CMC"


def hold(page, seconds: float) -> None:
    page.wait_for_timeout(int(seconds * 1000))


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
        hold(page, 1.2)
        page.get_by_role("button", name="Войти").click()
        page.get_by_text("BioPlan", exact=False).first.wait_for()
        hold(page, 2.0)

        # Ensure chat open
        chat_heading = page.get_by_role("heading", name="Чат с планом")
        if not chat_heading.is_visible():
            page.get_by_role("button", name="Открыть чат с агентом").click()
            chat_heading.wait_for()
        hold(page, 1.5)

        # 2. Show seeded Gantt a bit
        hold(page, 2.0)

        # 3. Import Excel
        page.locator('input[type="file"][accept=".xlsx"]').set_input_files(str(XLSX))
        page.get_by_text("План импортирован").wait_for(timeout=30_000)
        hold(page, 2.5)

        # 4. Chat prompt
        box = page.get_by_placeholder("Сообщение на естественном языке…")
        box.click()
        box.fill(PROMPT)
        hold(page, 1.0)
        page.get_by_role("button", name="Отправить").click()
        page.get_by_text("Агент думает…").wait_for(timeout=15_000)

        # Wait for agent completion (busy indicator gone)
        try:
            page.get_by_text("Агент думает…").wait_for(state="hidden", timeout=180_000)
        except PlaywrightTimeout:
            print("WARN: agent still busy after 180s", file=sys.stderr)

        hold(page, 3.0)

        # 5. Highlight already on chart — pause for viewers
        hold(page, 2.5)

        # 6. Undo (button label like "← Возврат (N)")
        undo = page.get_by_role("button", name=re.compile(r"^← Возврат"))
        if undo.count() and undo.first.is_enabled():
            undo.first.click()
            hold(page, 2.0)

        # 7. Export Excel
        with page.expect_download(timeout=30_000) as dl_info:
            page.get_by_role("button", name="Excel ↓").click()
        download = dl_info.value
        dest = OUT_DIR / (download.suggested_filename or "export.xlsx")
        download.save_as(str(dest))
        hold(page, 1.5)

        # Optional brief journal peek
        page.get_by_role("button", name="Журнал агента").click()
        hold(page, 2.0)
        page.keyboard.press("Escape")
        hold(page, 1.0)

        page.close()
        context.close()
        browser.close()

    videos = list(video_dir.glob("*.webm"))
    if not videos:
        print("ERROR: no video recorded", file=sys.stderr)
        return 1
    webm = videos[0]
    print(f"video: {webm} ({webm.stat().st_size} bytes)")

    # Encode compact looping gif (~12fps, 960px wide, palette)
    palette = OUT_DIR / "palette.png"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(webm),
            "-vf",
            "fps=10,scale=960:-1:flags=lanczos,palettegen=stats_mode=diff",
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
            "fps=10,scale=960:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5",
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
