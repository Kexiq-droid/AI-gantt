# Demo recording checklist

Готовый ролик: [demo.gif](demo.gif) (~28 с, сценарий ниже).

Пересъёмка автоматически:

```bash
. .venv/bin/activate
python scripts/record_demo.py   # пишет docs/demo.gif
```

Вручную: OBS / Peek / Chrome DevTools Recorder (~3 мин).

Шаги:

1. Login `pm` / `pm12345`
2. Показать сид-Gantt
3. Import `examples/plan_biokad_demo.xlsx`
4. Chat prompt про доклинику + CMC / Иванов
5. Highlight + summary
6. Undo («← Возврат»)
7. Export Excel
8. (опционально) Журнал агента

Файл: `docs/demo.gif` (или `docs/demo.mp4`) — ссылка в README.
