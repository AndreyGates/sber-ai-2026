from __future__ import annotations

import argparse
from pathlib import Path

from common.report_utils import (
    create_styled_document,
    add_title,
    add_table,
    add_bullet_list,
)


def build_report(output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = create_styled_document()

    # --- Title ---
    add_title(doc, "Кейс №2 «Инъекция на входе» — Отчёт о решении")

    # --- 1. Инструмент ---
    doc.add_heading("1. Инструмент и обоснование выбора", level=1)

    doc.add_heading("1.1. Основной классификатор", level=2)
    doc.add_paragraph(
        "В качестве основного классификатора выбрана модель "
        "protectai/deberta-v3-base-prompt-injection-v2 — fine-tune модели "
        "microsoft/deberta-v3-base (184M параметров) на задачу детекции prompt injection."
    )
    doc.add_paragraph(
        "Архитектура: encoder-only sequence classification (один forward pass на пример), "
        "бинарный выход (0 = benign, 1 = injection-detected). "
        "Post-training метрики на 20 000 held-out промптах: "
        "accuracy 95.25%, precision 91.59%, recall 99.74%, F1 95.49%."
    )

    doc.add_heading("1.2. Почему не генеративная SFT-модель", level=2)
    doc.add_paragraph(
        "Изначально рассматривалась модель waliboii/gpt-oss-20b-promptinj-sft "
        "(21B параметров, MoE, 3.6–4B активных). Однако для задачи классификации "
        "на фиксированный набор классов (не генерации текста) encoder-классификатор "
        "архитектурно предпочтительнее:"
    )
    add_bullet_list(doc, [
        "Один forward pass против авторегрессионной генерации — "
        "на порядки дешевле по инференсу на CPU.",
        "Batch-обработка 10 000 строк: DeBERTa — минуты на CPU, "
        "генеративная модель — часы/сутки.",
        "Задание требует бинарную классификацию (safe / injection and malicious), "
        "а не генерацию текста — генеративная модель не даёт преимуществ.",
    ])

    doc.add_heading("1.3. Heuristic-слой (defense in depth)", level=2)
    doc.add_paragraph(
        "DeBERTa официально не гарантирует детекцию jailbreak-атак "
        "(ролевые игры, смена персоны, обфускация). Для компенсации этого "
        "блайндспота добавлен независимый regex/keyword-слой, проверяющий "
        "запрос на четыре категории паттернов:"
    )
    add_bullet_list(doc, [
        "Смена роли/инструкций — «ignore previous instructions», «you are now», "
        "«act as», «pretend to be», русские эквиваленты.",
        "Извлечение системного промпта — «system prompt», «reveal your instructions».",
        "Обфускация — base64-подобные блоки, ROT13-маркеры, "
        "паттерны «translate/decode the following».",
        "Код-контейнеры — тройные кавычки/```, оборачивающие инструктивный текст.",
    ])

    # --- 2. Алгоритм ---
    doc.add_heading("2. Алгоритм работы пайплайна", level=1)

    doc.add_paragraph(
        "Пайплайн обрабатывает каждый запрос из test-сплита (10 000 строк) "
        "и возвращает класс, решение и обоснование. Последовательность шагов:"
    )

    steps = [
        ("Шаг 1. Batch-классификация",
         "Все тексты пропускаются через DeBERTa-v3-base-prompt-injection-v2 "
         "батчами по 32 примера (truncation=True, max_length=512). "
         "Для каждого запроса вычисляется вероятность injection-класса p1."),
        ("Шаг 2. Confidence-политика решений",
         "На основе p1 и двух порогов (t_low=0.15, t_high=0.75) "
         "принимается решение:\n"
         "• p1 < 0.15 → safe, пропустить\n"
         "• p1 ≥ 0.75 → injection and malicious, заблокировать\n"
         "• 0.15 ≤ p1 < 0.75 → пограничный случай, ручная проверка"),
        ("Шаг 3. Heuristic-override",
         "Независимо от шага 2, если heuristic-слой обнаружил хотя бы один "
         "паттерн jailbreak-атаки, а решение было «пропустить», "
         "оно принудительно повышается до «ручная проверка» (needs_review=true)."),
        ("Шаг 4. Генерация обоснования",
         "Rule-based генератор формирует краткое обоснование:\n"
         "• При heuristic-хитах — перечисление сработавших категорий.\n"
         "• При решении на основе p1 — числовой уровень уверенности.\n"
         "• Для чистого safe — пустая строка."),
        ("Шаг 5. Экспорт",
         "Результаты собираются в таблицу с колонками: запрос, присвоенный класс, "
         "рекомендуемое решение, краткое обоснование — и экспортируются в .xlsx."),
    ]
    for step_title, body_text in steps:
        doc.add_heading(step_title, level=2)
        doc.add_paragraph(body_text)

    # --- 3. Структура кода ---
    doc.add_heading("3. Структура кода решения", level=1)
    doc.add_paragraph("Модуль src/injection_guard/ содержит:")
    add_bullet_list(doc, [
        "config.py — конфигурация пайплайна (пороги, batch_size, маппинг классов)",
        "classifier.py — загрузка модели и batch-инференс с логированием прогресса",
        "heuristic.py — словарь regex-паттернов и функция detect_heuristic_flags()",
        "policy.py — функция decide() (confidence-политика + heuristic-override) "
        "и generate_rationale() (генератор обоснования)",
        "export.py — сборка итоговой таблицы, валидация, экспорт в .xlsx",
        "pipeline.py — оркестрация полного пайплайна (run_pipeline())",
        "calibrate.py — калибровка порогов на train-сплите",
    ])

    doc.add_paragraph(
        "Тесты: tests/case2_injection/ — unit-тесты (163 теста, без загрузки модели), "
        "интеграционные тесты (с моделью), e2e-тесты (полный прогон + детерминированность)."
    )

    # --- 4. Пороги ---
    doc.add_heading("4. Калибровка порогов", level=1)
    doc.add_paragraph(
        "Проведена калибровка порогов на выборке 10 000 строк из train-сплита "
        "(50 000 строк) с помощью grid search по критерию 0.6×recall_harmful + 0.4×F1. "
        "Результат калибровки:"
    )
    add_bullet_list(doc, [
        "t_low = 0.05 (начальное значение 0.15)",
        "t_high = 0.55 (начальное значение 0.75)",
        "Calibration score: 0.2689",
    ])
    doc.add_paragraph(
        "Калибровка снизила пороги, что расширило зону блокировки (p1 ≥ 0.55) "
        "и сузило зону safe (p1 < 0.05). Однако ключевой блайндспот — "
        "100% harmful-запросов имеют p1 < 0.05 — калибровка устранить не смогла, "
        "так как модель присваивает вредоносным командам крайне низкую вероятность "
        "injection-класса."
    )

    # --- 5. Метрики на test-split ---
    doc.add_heading("5. Метрики на test-split", level=1)

    doc.add_heading("5.1. Распределение разметки в test-сплите", level=2)
    doc.add_paragraph(
        "Test-сплит датасета jayavibhav/prompt-injection-safety содержит 10 000 строк "
        "с известной разметкой (авторы датасета):"
    )
    add_table(doc,
        headers=["Исходный label", "Целевой класс", "Количество"],
        rows=[
            ["0 (benign)", "safe", "4 557 (45.6%)"],
            ["1 (injection)", "injection and malicious", "4 443 (44.4%)"],
            ["2 (harmful)", "injection and malicious", "1 000 (10.0%)"],
        ],
    )

    doc.add_heading("5.2. Бинарные метрики классификатора", level=2)
    doc.add_paragraph(
        "Метрики посчитаны на test-сплите (10 000 строк) после маппинга "
        "предсказаний модели на бинарную схему задания (safe / injection and malicious):"
    )
    add_table(doc,
        headers=["Метрика", "Значение"],
        rows=[
            ["Accuracy", "0.5447"],
            ["Precision (injection)", "0.5565"],
            ["Recall (injection)", "0.8053"],
            ["F1 (injection)", "0.6582"],
        ],
    )

    doc.add_heading("5.3. Confusion matrix", level=2)
    add_table(doc,
        headers=["", "Pred: safe", "Pred: injection"],
        rows=[
            ["Разметка: safe", "TN = 1 064", "FP = 3 493"],
            ["Разметка: injection", "FN = 1 060", "TP = 4 383"],
        ],
    )

    doc.add_heading("5.4. Распределение по зонам уверенности", level=2)
    add_table(doc,
        headers=["Зона", "Диапазон p1", "Количество"],
        rows=[
            ["Safe (пропустить)", "p1 < 0.05", "1 905 (19.1%)"],
            ["Review (ручная проверка)", "0.05 ≤ p1 < 0.55", "233 (2.3%)"],
            ["Block (заблокировать)", "p1 ≥ 0.55", "7 862 (78.6%)"],
        ],
    )

    doc.add_heading("5.5. Анализ harmful-зоны (label=2)", level=2)
    doc.add_paragraph(
        "Критический анализ: все 1 000 harmful-запросов (label=2) модель "
        "классифицировала с p1 < 0.15, то есть отнесла к safe с высокой "
        "уверенностью. Это подтверждает известное ограничение модели "
        "deberta-v3-base-prompt-injection-v2 — она не детектирует вредоносные "
        "запросы категории harmful (прямые вредоносные команды, не являющиеся "
        "prompt injection в классическом смысле)."
    )
    doc.add_paragraph(
        "Heuristic-слой компенсирует это частично: из 1 000 harmful-запросов "
        "161 (16.1%) были перехвачены heuristic-паттернами и отправлены на "
        "ручную проверку. Оставшиеся 839 (83.9%) harmful-запросов не содержат "
        "распознаваемых regex-паттернов и прошли как safe."
    )
    doc.add_paragraph(
        "Это ключевой риск решения: для полного покрытия harmful-категории "
        "необходимо расширение heuristic-словаря или подключение дополнительного "
        "классификатора, специализированного на детекцию вредоносных команд."
    )

    # --- 6. Итоговое распределение решений ---
    doc.add_heading("6. Итоговое распределение решений", level=1)
    add_table(doc,
        headers=["Решение", "Количество", "Доля"],
        rows=[
            ["Пропустить", "1 905", "19.05%"],
            ["Заблокировать", "7 862", "78.62%"],
            ["Ручная проверка", "233", "2.33%"],
        ],
    )

    # --- 7. Ограничения ---
    doc.add_heading("7. Ограничения решения", level=1)

    limitations = [
        ("Блайндспот на harmful-запросах (подтверждён метриками)",
         "Модель DeBERTa классифицирует 100% harmful-запросов (label=2) как safe "
         "с высокой уверенностью (p1 < 0.15). Heuristic-слой перехватывает только "
         "16.1% из них. Это главный риск: прямые вредоносные команды, не содержащие "
         "классических prompt-injection паттернов, пропускаются."),
        ("Блайндспот на jailbreak-атаках",
         "Модель официально не заявляет детекцию jailbreak/ролевых атак. "
         "Heuristic-слой снижает, но не устраняет риск: словарь паттернов конечный "
         "и требует итеративного расширения по находкам на реальном прогоне."),
        ("Высокий уровень false positives",
         "3 493 безопасных запроса классифицированы как injection (FP). "
         "Это следствие того, что модель даёт высокие scores injection-класса "
         "на длинных или инструктивно-подобных текстах. Частично компенсируется "
         "маршрутизацией пограничных случаев в эскалацию, а не в жёсткий блок."),
        ("Калибровка не устранила harmful-блайндспот",
         "Калибровка порогов на train-сплите (t_low=0.05, t_high=0.55) "
         "незначительно улучшила маршрутизацию, но 99.9% harmful-запросов "
         "по-прежнему имеют p1 < t_low и классифицируются как safe. "
         "Модель не различает prompt injection и прямые вредоносные команды."),
        ("English-only",
         "Модель DeBERTa v2 заявлена только для английского языка. "
         "Heuristic-слой содержит русские паттерны, но основной классификатор "
         "работает только с английским текстом."),
        ("Открытый список heuristic-паттернов",
         "Словарь regex-паттернов покрывает известные категории атак, "
         "но является открытым — новые формы атак могут не попадать "
         "в текущий словарь."),
    ]
    for lim_title, lim_body in limitations:
        doc.add_heading(lim_title, level=2)
        doc.add_paragraph(lim_body)

    doc.save(str(output_path))
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", default="output/case2-injection/report.docx")
    args = parser.parse_args()
    path = build_report(args.output)
    print(f"Report saved to {path}")
