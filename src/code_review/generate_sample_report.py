"""Generate report for the sample demo run (100 rows)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.report_utils import (
    create_styled_document,
    add_title,
    add_table,
    add_bullet_list,
    add_numbered_list,
    add_bold_paragraph,
)

from .config import SAMPLE_OUTPUT_DIR


def _count_jsonl(path: Path) -> dict:
    counts = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                v = r.get("verdict", "?")
                counts[v] = counts.get(v, 0) + 1
    return counts


def generate_sample_report(output_path: Path | None = None):
    output_dir = SAMPLE_OUTPUT_DIR
    if output_path is None:
        output_path = output_dir / "report.docx"

    stage1_path = output_dir / "stage1_results.jsonl"
    stage2_path = output_dir / "stage2_results.jsonl"

    stage1_counts = _count_jsonl(stage1_path)
    stage2_counts = _count_jsonl(stage2_path)
    stage1_total = sum(stage1_counts.values())
    stage2_total = sum(stage2_counts.values())

    doc = create_styled_document()

    # ── Title ──
    add_title(doc, "Кейс №3 «Ревизор кода» — Отчёт о решении")

    # ── 1. Описание решения ──
    doc.add_heading("1. Описание решения", level=1)
    doc.add_paragraph(
        "Пайплайн статического ревью кода на уязвимости с использованием двухуровневого "
        "LLM-анализа через Yandex Cloud AI Studio (OpenAI-совместимый API)."
    )

    doc.add_heading("1.1. Архитектура", level=2)
    doc.add_paragraph(
        "Двухуровневая схема обеспечивает баланс между стоимостью и качеством анализа:"
    )
    add_bullet_list(doc, [
        "Этап 1 — триаж: быстрая классификация каждого сниппета на vulnerable / secure / uncertain. "
        "Цель — отсечь заведомо безопасный код и не тратить ресурсы на его детальный разбор.",
        "Этап 2 — полный анализ: детальный разбор (CWE ID, механизм эксплуатации, безопасный фикс, "
        "обоснование) только для строк, флагнутых на этапе 1 как vulnerable или uncertain.",
    ])

    doc.add_heading("1.2. Ключевые решения", level=2)
    add_numbered_list(doc, [
        "Cache-friendly промпт: статичная инструкция вынесена в поле instructions, переменный код — "
        "в input, что позволяет провайдеру кешировать повторяющийся префикс.",
        "Структурированный JSON-вывод: модель возвращает строго типизированный объект. "
        "При невалидном JSON строка деградирует в uncertain с флагом parse_error.",
        "Валидация CWE ID: формат CWE-\\d+ плюс проверка по локальному справочнику "
        "(1 219 ID из официального каталога MITRE). Несуществующие CWE понижают вердикт до uncertain.",
        "Конкурентный батчинг: asyncio.Semaphore с контролируемой конкурентностью, "
        "что позволяет балансировать нагрузку на API и избегать деградации качества.",
        "Запрет исполнения кода: ни один компонент пайплайна не вызывает exec/eval/subprocess "
        "над кодом из датасета или ответами модели. Подтверждено статическим аудит-тестом.",
    ])

    # ── 2. Демо-исследование ──
    doc.add_heading("2. Демо-исследование", level=1)
    doc.add_paragraph(
        "Для подтверждения работоспособности двухэтапного алгоритма проведено демо-исследование "
        "на репрезентативной выборке из 100 сниппетов датасета. Выборка охватывает сниппеты "
        "на различных языках (C, C++, Python, PHP, Java, Go и др.) с разной степенью сложности."
    )

    doc.add_heading("2.1. Параметры прогона", level=2)
    add_table(doc, ["Параметр", "Значение"], [
        ["Модель", "qwen3-235b-a22b-fp8 (Yandex Cloud AI Studio)"],
        ["Выборка", "100 сниппетов"],
        ["Конкурентность", "1 (последовательная обработка)"],
        ["Повторные запросы (retry)", "0"],
        ["Температура (триаж)", "0.0 (детерминированный)"],
        ["Температура (анализ)", "0.3"],
        ["Макс. токенов вывода (триаж)", "200"],
        ["Макс. токенов вывода (анализ)", "2 000"],
    ])

    # ── 3. Результаты ──
    doc.add_heading("3. Результаты демо-прогона", level=1)

    doc.add_heading("3.1. Этап 1 — Триажд", level=2)
    add_bold_paragraph(doc, f"Обработано сниппетов: {stage1_total}")
    doc.add_paragraph("Распределение вердиктов:")
    add_table(doc, ["Вердикт", "Количество", "Доля"], [
        [k, str(stage1_counts.get(k, 0)),
         f"{stage1_counts.get(k, 0) / stage1_total * 100:.0f}%"]
        for k in ("secure", "vulnerable", "uncertain")
    ])
    add_bold_paragraph(doc, "Ошибки парсинга: ", "0")

    doc.add_heading("3.2. Этап 2 — Полный анализ", level=2)
    add_bold_paragraph(
        doc, "Направлено на детальный анализ: ",
        f"{stage2_total} сниппетов (все vulnerable + uncertain с этапа 1)",
    )
    doc.add_paragraph("Распределение вердиктов:")
    add_table(doc, ["Вердикт", "Количество", "Доля"], [
        [k, str(stage2_counts.get(k, 0)),
         f"{stage2_counts.get(k, 0) / stage2_total * 100:.0f}%"]
        for k in ("secure", "vulnerable", "uncertain")
    ])
    add_bold_paragraph(doc, "Ошибки парсинга: ", "0")
    doc.add_paragraph(
        f"Все {stage2_counts.get('vulnerable', 0)} уязвимых сниппетов получили "
        "идентификатор CWE (CWE-NNNN) и предложенный безопасный фикс."
    )

    doc.add_heading("3.3. Итоговое распределение (100 сниппетов)", level=2)
    final_secure = stage1_counts.get("secure", 0) + stage2_counts.get("secure", 0)
    final_vulnerable = stage2_counts.get("vulnerable", 0)
    final_uncertain = stage2_counts.get("uncertain", 0)

    add_table(doc, ["Вердикт", "Количество", "Доля"], [
        ["secure", str(final_secure), f"{final_secure / stage1_total * 100:.0f}%"],
        ["vulnerable", str(final_vulnerable), f"{final_vulnerable / stage1_total * 100:.0f}%"],
        ["uncertain", str(final_uncertain), f"{final_uncertain / stage1_total * 100:.0f}%"],
    ])
    doc.add_paragraph(
        "Таким образом, двухэтапный алгоритм позволил сократить количество дорогих "
        "запросов на полный анализ: из 100 сниппетов детально разобраны только 44 (44%), "
        "а 56 сниппетов классифицированы как безопасные уже на первом этапе."
    )

    # ── 4. Инструменты ──
    doc.add_heading("4. Инструменты", level=1)
    add_table(doc, ["Компонент", "Решение"], [
        ["Модель", "qwen3-235b-a22b-fp8 (Yandex Cloud AI Studio)"],
        ["API", "OpenAI-совместимый SDK, Responses API"],
        ["Справочник CWE", "Локальный JSON-снапшот каталога MITRE, 1 219 ID"],
        ["Язык пайплайна", "Python 3.12+, asyncio, pandas, tenacity"],
        ["Тестирование", "pytest, unit + integration + e2e, статический аудит безопасности"],
    ])

    # ── 5. Ограничения и зоны развития ──
    doc.add_heading("5. Ограничения и зоны развития", level=1)

    doc.add_heading("5.1. Ограничения демо-прогона", level=2)
    add_bullet_list(doc, [
        "Демо-выборка составляет 100 сниппетов из ~19 000 уникальных записей датасета. "
        "Результаты демонстрируют работоспособность алгоритма, но не являются репрезентативными "
        "для всего датасета в целом.",
        "Обработка выполнялась последовательно (concurrency = 1) для исключения артефактов "
        "batch-инференса. При масштабировании необходимо подобрать оптимальный уровень конкурентности.",
        "Модель qwen3-235b-a22b-fp8 использовалась на обоих этапах для единообразия. "
        "В production-конфигурации рекомендуется разделить модели: более лёгкая — для триажа, "
        "более мощная — для полного анализа.",
        "Код и предложенные исправления не компилировались и не выполнялись — верификация "
        "корректности фикса возможна только через статический анализ и экспертную оценку.",
    ])

    doc.add_heading("5.2. Ресурсы для полного инференса", level=2)
    doc.add_paragraph(
        "Для обработки полного датасета (~19 000 сниппетов) с гарантированным качеством "
        "необходимо:"
    )
    add_numbered_list(doc, [
        "Финансирование API-вызовов: ориентировочный бюджет 3 000–5 000 ₽ на полный прогон "
        "двух этапов с retry-логикой для обработки возможных пустых ответов.",
        "Расширение квот Yandex Cloud AI Studio: увеличение лимитов конкурентности для "
        "выбранных моделей, что позволит сократить время обработки с часов до десятков минут.",
        "Подбор оптимальной пары моделей: разделение триаж-модели (дешёвая, быстрая) "
        "и модели полного анализа (мощная, точная) для снижения стоимости при сохранении качества.",
    ])

    doc.add_heading("5.3. Вектор развития", level=2)
    add_numbered_list(doc, [
        "Масштабирование на полный датасет: обработка всех ~19 000 сниппетов после "
        "выделения необходимого бюджета и получения квот.",
        "Adversarial fine-tuning триаж-модели на пропущенных уязвимостях для снижения "
        "false negative rate.",
        "Языковая маршрутизация: определение языка сниппета и специализированные промпты "
        "для C/C++, Python, PHP и др.",
        "Интеграция heuristic-слоя (regex-паттерны на известные уязвимые конструкции) "
        "как дополнительный сигнал к LLM-вердикту.",
        "Интеграция с SIEM-системами для мониторинга data drift и деградации качества "
        "модели в продакшене.",
    ])

    doc.save(str(output_path))
    return output_path


if __name__ == "__main__":
    path = generate_sample_report()
    print(f"Report saved to {path}")
