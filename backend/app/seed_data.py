"""Seed plan: вывод препарата-кандидата BIO-X на КИ (фаза I)."""

from datetime import date, timedelta

# code, parent_code, title, description, assignee, duration_days, predecessor_codes, sort_order
SEED_TASKS: list[tuple] = [
    ("P1", None, "Аналитика и целеполагание", "Формирование целевого профиля препарата", "", 15, [], 10),
    ("T1.1", "P1", "Анализ рынка и unmet need", "Обзор конкурентов и unmet medical need", "Петрова", 5, [], 11),
    ("T1.2", "P1", "TPP draft", "Целевой профиль продукта (TPP)", "Петрова", 5, ["T1.1"], 12),
    ("T1.3", "P1", "Kick-off R&D", "Установочное совещание команд", "Сидоров", 2, ["T1.2"], 13),
    ("P2", None, "Доклинические исследования", "In vitro / in vivo пакет", "", 40, ["P1"], 20),
    ("T2.1", "P2", "In vitro эффективность", "Скрининг активности", "Иванов", 10, [], 21),
    ("T2.2", "P2", "Токсикология", "Предварительная токсикология", "Иванов", 14, ["T2.1"], 22),
    ("T2.3", "P2", "PK/PD модель", "Фармакокинетика / фармакодинамика", "Козлова", 10, ["T2.1"], 23),
    ("T2.4", "P2", "Отчёт доклиники", "Сводный отчёт для регуляторики", "Иванов", 7, ["T2.2", "T2.3"], 24),
    ("P3", None, "CMC / производство", "Химия, производство и контроль", "", 35, ["P2"], 30),
    ("T3.1", "P3", "Процесс синтеза DS", "Разработка процесса субстанции", "Смирнов", 12, [], 31),
    ("T3.2", "P3", "Аналитические методы", "Методы контроля качества", "Смирнов", 10, ["T3.1"], 32),
    ("T3.3", "P3", "Pilot batch", "Пилотная партия", "Орлова", 10, ["T3.2"], 33),
    ("T3.4", "P3", "Стабильность (ускор.)", "Ускоренные исследования стабильности", "Орлова", 14, ["T3.3"], 34),
    ("P4", None, "Регуляторика", "Подготовка досье", "", 25, ["P2", "P3"], 40),
    ("T4.1", "P4", "CTD Module 2/3 draft", "Черновик модулей CTD", "Васильева", 12, [], 41),
    ("T4.2", "P4", "Gap analysis", "Анализ пробелов досье", "Васильева", 5, ["T4.1"], 42),
    ("T4.3", "P4", "Pre-IND briefing", "Материалы pre-IND", "Сидоров", 8, ["T4.2", "T2.4"], 43),
    ("P5", None, "Клиника I (подготовка)", "Подготовка к FIH", "", 20, ["P4"], 50),
    ("T5.1", "P5", "Протокол FIH draft", "Черновик протокола фазы I", "Морозов", 10, [], 51),
    ("T5.2", "P5", "Выбор клинической базы", "Отбор сайта исследования", "Морозов", 7, ["T5.1"], 52),
    ("T5.3", "P5", "Этика / ИРБ пакет", "Пакет для этического комитета", "Васильева", 8, ["T5.1"], 53),
]

PLAN_TITLE = "Вывод препарата-кандидата BIO-X на клинические исследования (фаза I)"
PLAN_START = date(2026, 3, 2)


def compute_schedule(tasks: list[dict], plan_start: date) -> dict[str, date]:
    """tasks: dicts with code, parent, duration_days, predecessors."""
    by_code = {t["code"]: t for t in tasks}
    starts: dict[str, date] = {}

    def end_of(code: str) -> date:
        return starts[code] + timedelta(days=by_code[code]["duration_days"])

    remaining = set(by_code)
    guard = 0
    while remaining and guard < 500:
        guard += 1
        progressed = False
        for code in list(remaining):
            t = by_code[code]
            preds = t.get("predecessors") or []
            if any(p not in starts for p in preds):
                continue
            if t.get("parent") and t["parent"] not in starts and t["parent"] in by_code:
                # parent can start when first child ready; allow parent without waiting children
                pass
            candidate = plan_start
            if preds:
                candidate = max(end_of(p) for p in preds)
            if t.get("parent") and t["parent"] in starts:
                candidate = max(candidate, starts[t["parent"]])
            starts[code] = candidate
            remaining.remove(code)
            progressed = True
        if not progressed:
            for code in list(remaining):
                starts[code] = plan_start
                remaining.remove(code)
    return starts
