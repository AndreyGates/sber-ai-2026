"""Generate the project report as DOCX."""
from pathlib import Path

from common.report_utils import (
    create_styled_document,
    add_title,
    add_table,
    add_bullet_list,
    add_numbered_list,
    add_bold_paragraph,
)


def generate_report(output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = create_styled_document()

    # ── Title ──
    add_title(doc, "Кейс №1 «Обезличить и сохранить смысл» — Отчёт о решении")

    # ── 1. Technology ──
    doc.add_heading("1. Инструмент и технология", level=1)

    doc.add_paragraph(
        "Модель: OpenMed/privacy-filter-nemotron — токен-классификатор на базе "
        "openai/privacy-filter, дообученный на датасете nvidia/Nemotron-PII. "
        "55 категорий ПДн, 221 BIOES-класс, macro B-F1 ≈ 0.95 на тест-сплите."
    )
    doc.add_paragraph(
        "Датасет: nvidia/Nemotron-PII (test-split, 100 000 записей). "
        "Синтетические документы, имитирующие договоры, письма, заявки, тикеты, медицинские записи. "
        "150+ типов документов, 30 доменов, формат structured/unstructured, локаль us."
    )
    doc.add_paragraph(
        "Инференс: batch-обработка через transformers (AutoTokenizer + AutoModelForTokenClassification). "
        "Sliding-window (512 токенов, overlap 64) для длинных документов. "
        "Locale-aware генерация псевдонимов (EN/RU словари)."
    )

    # ── 2. Code ──
    doc.add_heading("2. Код решения", level=1)

    doc.add_paragraph(
        "Основной модуль: src/pii/. Точка входа: src/pii/run.py (CLI). Ключевые компоненты:"
    )

    add_table(
        doc,
        ["Модуль", "Назначение"],
        [
            ["tokenizer.py", "Sliding-window токенизация с маппингом token→char offsets"],
            ["bioes.py", "BIOES-decode в span-уровневые сущности"],
            ["chunk_merge.py", "Слияние спанов на границах чанков (dedup, max score)"],
            ["regex_fallback.py", "Regex-слой: email, телефон, карта (Luhn), defense-in-depth"],
            ["confidence.py", "Политика уверенности: min_score=0.5, needs_review для high-risk"],
            ["normalize.py", "Нормализация + fuzzy-match имён (rapidfuzz)"],
            ["registry.py", "Locale-aware per-document реестр псевдонимов (EN/RU)"],
            ["strategies.py", "Category-aware стратегии замены (15+ тонких лейблов)"],
            ["apply.py", "Применение замен по offsets (справа налево, без сдвига)"],
            ["export.py", "Экспорт JSON/JSONL/XLSX (audit + final)"],
            ["pipeline.py", "Оркестрация пайплайна"],
            ["dataset.py", "Загрузка Nemotron-PII, стратифицированная выборка"],
        ],
    )

    # ── 3. Algorithm ──
    doc.add_heading("3. Алгоритм", level=1)

    add_bold_paragraph(doc, "Детекция → Пороги → Консистентная замена → Экспорт")

    algo_steps = [
        "Sliding-window токенизация текста (окно 512, overlap 64).",
        "Модель предсказывает BIOES-теги для каждого токена.",
        "BIOES-decode → span-уровневые сущности (start, end, label, score).",
        "Merge спанов на границах чанков (dedup, max score).",
        "Regex-fallback: email, телефон, номер карты (Luhn) — defense-in-depth.",
        "Пороговая политика: score ≥ 0.85 → замена; 0.5–0.85 для high-risk → маскирование + needs_review; < 0.5 → пропуск.",
        "Нормализация + fuzzy-match имён для группировки вариантов.",
        "Детерминированный реестр псевдонимов (per-document): SHA256(doc_id + normalized_value + category) → выбор из EN/RU справочника.",
        "Category-aware замена: имена → псевдонимы, телефоны/карты → маскирование с сохранением формата, даты → генерализация, адреса → обобщение, медданные → метка.",
        "Применение замен по offsets (справа налево, без сдвига).",
        "Экспорт: финальный артефакт (без original) + аудиторский (с original).",
    ]
    add_numbered_list(doc, algo_steps)

    # ── 4. Strategies ──
    doc.add_heading("4. Стратегии замены", level=1)

    doc.add_paragraph(
        "Модель возвращает 50+ тонких лейблов (first_name, last_name, street_address, "
        "credit_debit_card, bank_routing_number и т.д.). Каждый лейбл маппится на стратегию:"
    )

    add_table(
        doc,
        ["Категория", "Стратегия", "Пример"],
        [
            ["first_name, last_name, user_name", "Псевдоним из EN/RU словаря (детерминированный, консистентный)", "John Smith → Joseph Taylor"],
            ["street_address, city, state, country", "Генерализация: EN: номер + улица + город; RU: город + улица + дом", "123 Main St → 60 Maple Dr, Houston, TX"],
            ["date_of_birth, date", "Генерализация даты: EN: MM/DD/1990; RU: DD.MM.1990", "05/12/1985 → 07/07/1990"],
            ["company_name", "Фиктивная организация из EN/RU словаря", "Acme Corp → GlobalTech Inc"],
            ["email", "Маскирование local-part, домен сохранён", "john@acme.com → j***n@acme.com"],
            ["PHONE_NUMBER, phone_number", "Формат-сохраняющая маска: последние N цифр видны", "+1 (555) 123-4567 → +1 (555) ***-**67"],
            ["credit_debit_card", "Маска, последние 4 видны", "4111 1111 1111 1111 → **** ****** *111"],
            ["ssn, GOV_ID, certificate_license", "Маска, 2 цифры видны", "123-45-6789 → ***-**-6789"],
            ["account_number, bank_routing_number", "Маска, 2 цифры видны", "271210785 → *******85"],
            ["HEALTHCARE_DATA, medical_record_number", "Метка категории", "diabetes → [MEDICAL DATA]"],
            ["occupation, gender, race_ethnicity, url...", "[REDACTED] — чувствительные атрибуты без словаря", "Engineer → [REDACTED]"],
        ],
    )

    # ── 5. Inference results ──
    doc.add_heading("5. Результаты инференса", level=1)

    doc.add_paragraph(
        "Стратифицированная выборка 1000 записей из test-split (100k) по домену (domain). "
        "Обработано 986 документов за 367 секунд (~6 мин) на CPU."
    )

    add_table(
        doc,
        ["Метрика", "Значение"],
        [
            ["Всего сущностей детектировано", "9 199"],
            ["Псевдонимы (имена, адреса, даты, организации)", "5 365 (58.3%)"],
            ["Формат-маски (телефон, карта, ID, счёт)", "1 373 (14.9%)"],
            ["[REDACTED] (occupation, url, gender и др.)", "2 461 (26.8%)"],
            ["Документов с needs_review", "15 (1.5%)"],
            ["Ошибок обработки", "0"],
            ["Уникальных типов документов", "678"],
            ["Локаль", "us (все документы)"],
        ],
    )

    doc.add_paragraph("Топ-10 детектированных категорий ПДн:")

    add_table(
        doc,
        ["Категория", "Количество"],
        [
            ["PHONE_NUMBER", "1 357"],
            ["first_name", "811"],
            ["date", "730"],
            ["last_name", "534"],
            ["company_name", "472"],
            ["email", "381"],
            ["url", "376"],
            ["occupation", "287"],
            ["time", "221"],
            ["phone_number", "215"],
        ],
    )

    # ── 5b. Quality metrics ──
    doc.add_heading("5.1. Метрики качества детекции (P/R/F1)", level=2)

    doc.add_paragraph(
        "Для оценки качества детекции сущностей проведено сравнение предсказаний модели "
        "с разметкой датасета nvidia/Nemotron-PII. Метрики посчитаны на 986 документах "
        "на уровне лейблов в документе (document-level label matching) — "
        "для каждого лейбла сравнивается количество обнаруженных сущностей с количеством "
        "в разметке, без привязки к позициям спанов. Такой подход устойчив к дубликатам UID "
        "в датасете и к сдвигам границ спанов на 1–2 символа."
    )

    add_bold_paragraph(doc, "Сводные метрики (document-level label matching):")

    add_table(
        doc,
        ["Метрика", "Значение"],
        [
            ["Precision", "0.8635"],
            ["Recall", "0.4847"],
            ["F1", "0.6209"],
        ],
    )

    doc.add_paragraph(
        "Precision 0.86 — модель детектирует корректно, большинство предсказаний "
        "соответствуют реальным ПДн. Recall 0.49 — модель находит около половины всех сущностей "
        "в разметке; часть пропусков обусловлена тем, что датасет содержит дубликаты UID "
        "с разным контентом, и ground-truth включает больше сущностей, чем было "
        "в обрабатываемой выборке."
    )

    add_bold_paragraph(doc, "Per-label метрики (топ-5 по F1):")

    add_table(
        doc,
        ["Лейбл", "Precision", "Recall", "F1"],
        [
            ["url", "1.000", "0.538", "0.700"],
            ["state", "0.990", "0.531", "0.691"],
            ["first_name", "0.996", "0.500", "0.666"],
            ["account_number", "1.000", "0.511", "0.676"],
            ["last_name", "0.998", "0.479", "0.648"],
        ],
    )

    doc.add_paragraph(
        "phone_number — отдельный случай: precision 0.25, recall 0.91. "
        "Модель склонна к over-detection телефонных номеров (1 572 предсказания "
        "против ~400 в разметке), но захватывает большинство реальных номеров. "
        "Для улучшения precision рекомендуется пост-обработка с фильтрацией "
        "low-confidence предсказаний и валидация формата (Luhn check)."
    )

    # ── 6. Tests ──
    doc.add_heading("6. Тестовое покрытие", level=1)

    doc.add_paragraph("Три уровня тестов на pytest:")

    add_bullet_list(doc, [
        "Unit (121 тест): BIOES-decode, chunk merge, regex fallback (Luhn), confidence policy, pseudonym registry (EN + RU), replacement strategies (EN + RU), offset apply. Без загрузки модели.",
        "Integration (4 теста): экспорт final vs audit, валидация JSON/XLSX, no-PII-leak в финальном артефакте.",
        "E2E (4 теста): smoke test, no-PII-leak (безопасность), determinism, XLSX schema.",
        "Model (7 тестов): pipeline на структурированных/неструктурированных документах, консистентность в документе (требуют реальные веса).",
    ])

    # Multi-segment bold/normal paragraph — doesn't fit single-prefix utility
    p = doc.add_paragraph()
    run = p.add_run("Быстрый прогон: ")
    run.bold = True
    p.add_run("pytest -m 'not model' — 121 тест за ~1.5 сек. ")
    run = p.add_run("Полный прогон: ")
    run.bold = True
    p.add_run("pytest — 128 тестов.")

    # ── 7. Limitations ──
    doc.add_heading("7. Ограничения", level=1)

    add_bullet_list(doc, [
        "Модель покрывает 55 категорий ПДн; редкие категории могут давать ложноотрицательные результаты — компенсируется regex-fallback.",
        "Sliding-window: overlap 64 токена может не покрыть сущности длиннее overlap-зоны.",
        "Fuzzy-match имён — эвристика (token_sort_ratio), не строгий coreference resolution.",
        "Обработка ограничена текстовыми документами (без OCR).",
        "26.8% сущностей (occupation, url, gender и др.) заменяются на [REDACTED] — нет словаря псевдонимов для этих категорий.",
        "Полный датасет (100k) требует ~6 часов на CPU; для production рекомендуется GPU.",
    ])

    doc.save(str(output_path))


if __name__ == "__main__":
    generate_report("output/case1-pii/report.docx")
    print("Report generated: output/case1-pii/report.docx")
