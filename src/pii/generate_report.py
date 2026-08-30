"""Generate the project report as PDF."""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_FONT_DIR = "/System/Library/Fonts/Supplemental"

pdfmetrics.registerFont(TTFont("Arial", f"{_FONT_DIR}/Arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", f"{_FONT_DIR}/Arial Bold.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", f"{_FONT_DIR}/Arial Italic.ttf"))
pdfmetrics.registerFont(TTFont("Arial-BoldItalic", f"{_FONT_DIR}/Arial Bold Italic.ttf"))
pdfmetrics.registerFont(TTFont("CourierNew", f"{_FONT_DIR}/Courier New.ttf"))
pdfmetrics.registerFont(TTFont("CourierNew-Bold", f"{_FONT_DIR}/Courier New Bold.ttf"))

from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic", boldItalic="Arial-BoldItalic")
registerFontFamily("CourierNew", normal="CourierNew", bold="CourierNew-Bold")


def generate_report(output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(str(output_path), pagesize=A4)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=18, spaceAfter=12, fontName="Arial-Bold")
    heading_style = ParagraphStyle("Heading", parent=styles["Heading2"], fontSize=14, spaceAfter=8, spaceBefore=12, fontName="Arial-Bold")
    body_style = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Arial", fontSize=10, leading=14)

    story = []

    # ── Title ──
    story.append(Paragraph("Отчёт: Пайплайн анонимизации персональных данных", title_style))
    story.append(Spacer(1, 12))

    # ── 1. Technology ──
    story.append(Paragraph("1. Инструмент и технология", heading_style))
    story.append(Paragraph(
        "Модель: <b>OpenMed/privacy-filter-nemotron</b> — токен-классификатор на базе "
        "<i>openai/privacy-filter</i>, дообученный на датасете <i>nvidia/Nemotron-PII</i>. "
        "55 категорий ПДн, 221 BIOES-класс, macro B-F1 ≈ 0.95 на тест-сплите.",
        body_style,
    ))
    story.append(Paragraph(
        "Датасет: <b>nvidia/Nemotron-PII</b> (test-split, 100 000 записей). "
        "Синтетические документы, имитирующие договоры, письма, заявки, тикеты, медицинские записи. "
        "150+ типов документов, 30 доменов, формат structured/unstructured, локаль us.",
        body_style,
    ))
    story.append(Paragraph(
        "Инференс: batch-обработка через <b>transformers</b> (AutoTokenizer + AutoModelForTokenClassification). "
        "Sliding-window (512 токенов, overlap 64) для длинных документов. "
        "Locale-aware генерация псевдонимов (EN/RU словари).",
        body_style,
    ))
    story.append(Spacer(1, 8))

    # ── 2. Code ──
    story.append(Paragraph("2. Код решения", heading_style))
    story.append(Paragraph(
        "Основной модуль: <font face='CourierNew'>src/pii/</font>. "
        "Точка входа: <font face='CourierNew'>src/pii/run.py</font> (CLI). "
        "Ключевые компоненты:",
        body_style,
    ))

    components = [
        ["Модуль", "Назначение"],
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
    ]
    table = Table(components, colWidths=[140, 340])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Arial"),
        ("FONTNAME", (0, 0), (-1, 0), "Arial-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#D9E2F3")]),
    ]))
    story.append(table)
    story.append(Spacer(1, 12))

    # ── 3. Algorithm ──
    story.append(Paragraph("3. Алгоритм", heading_style))
    story.append(Paragraph(
        "<b>Детекция → Пороги → Консистентная замена → Экспорт</b>",
        body_style,
    ))
    story.append(Paragraph(
        "1) Sliding-window токенизация текста (окно 512, overlap 64). "
        "2) Модель предсказывает BIOES-теги для каждого токена. "
        "3) BIOES-decode → span-уровневые сущности (start, end, label, score). "
        "4) Merge спанов на границах чанков (dedup, max score). "
        "5) Regex-fallback: email, телефон, номер карты (Luhn) — defense-in-depth. "
        "6) Пороговая политика: score ≥ 0.85 → замена; 0.5–0.85 для high-risk → маскирование + needs_review; "
        "&lt; 0.5 → пропуск. "
        "7) Нормализация + fuzzy-match имён для группировки вариантов. "
        "8) Детерминированный реестр псевдонимов (per-document): "
        "SHA256(doc_id + normalized_value + category) → выбор из EN/RU справочника. "
        "9) Category-aware замена (см. раздел 4). "
        "10) Применение замен по offsets (справа налево, без сдвига). "
        "11) Экспорт: финальный артефакт (без original) + аудиторский (с original).",
        body_style,
    ))
    story.append(Spacer(1, 8))

    # ── 4. Strategies ──
    story.append(Paragraph("4. Стратегии замены", heading_style))
    story.append(Paragraph(
        "Модель возвращает 50+ тонких лейблов (first_name, last_name, street_address, "
        "credit_debit_card, bank_routing_number и т.д.). Каждый лейбл маппится на стратегию:",
        body_style,
    ))

    strategies = [
        ["Категория", "Стратегия", "Пример"],
        ["first_name, last_name,\nuser_name", "Псевдоним из EN/RU словаря\n(детерминированный, консистентный)", "John Smith →\nJoseph Taylor"],
        ["street_address, city,\nstate, country", "Генерализация:\nEN: номер + улица + город\nRU: город + улица + дом", "123 Main St →\n60 Maple Dr, Houston, TX"],
        ["date_of_birth, date", "Генерализация даты:\nEN: MM/DD/1990\nRU: DD.MM.1990", "05/12/1985 →\n07/07/1990"],
        ["company_name", "Фиктивная организация\nиз EN/RU словаря", "Acme Corp →\nGlobalTech Inc"],
        ["email", "Маскирование local-part,\nдомен сохранён", "john@acme.com →\nj***n@acme.com"],
        ["PHONE_NUMBER,\nphone_number", "Формат-сохраняющая маска:\nпоследние N цифр видны", "+1 (555) 123-4567 →\n+1 (555) ***-**67"],
        ["credit_debit_card", "Маска, последние 4 видны", "4111 1111 1111 1111 →\n**** ****** *111"],
        ["ssn, GOV_ID,\ncertificate_license", "Маска, 2 цифры видны", "123-45-6789 →\n***-**-6789"],
        ["account_number,\nbank_routing_number", "Маска, 2 цифры видны", "271210785 →\n*******85"],
        ["HEALTHCARE_DATA,\nmedical_record_number", "Метка категории", "diabetes →\n[MEDICAL DATA]"],
        ["occupation, gender,\nrace_ethnicity, url...", "[REDACTED] —\nчувствительные атрибуты\nбез словаря", "Engineer →\n[REDACTED]"],
    ]
    st = Table(strategies, colWidths=[120, 170, 140])
    st.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Arial"),
        ("FONTNAME", (0, 0), (-1, 0), "Arial-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#D9E2F3")]),
    ]))
    story.append(st)
    story.append(Spacer(1, 12))

    # ── 5. Inference results ──
    story.append(Paragraph("5. Результаты инференса", heading_style))
    story.append(Paragraph(
        "Стратифицированная выборка 1000 записей из test-split (100k) по домену (domain). "
        "Обработано 986 документов за 367 секунд (~6 мин) на CPU.",
        body_style,
    ))

    results = [
        ["Метрика", "Значение"],
        ["Всего сущностей детектировано", "9 199"],
        ["Псевдонимы (имена, адреса, даты, организации)", "5 365 (58.3%)"],
        ["Формат-маски (телефон, карта, ID, счёт)", "1 373 (14.9%)"],
        ["[REDACTED] (occupation, url, gender и др.)", "2 461 (26.8%)"],
        ["Документов с needs_review", "15 (1.5%)"],
        ["Ошибок обработки", "0"],
        ["Уникальных типов документов", "678"],
        ["Локаль", "us (все документы)"],
    ]
    rt = Table(results, colWidths=[280, 200])
    rt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Arial"),
        ("FONTNAME", (0, 0), (-1, 0), "Arial-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#D9E2F3")]),
    ]))
    story.append(rt)
    story.append(Spacer(1, 8))

    story.append(Paragraph(
        "Топ-10 детектированных категорий ПДн:",
        body_style,
    ))
    top_labels = [
        ["Категория", "Количество"],
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
    ]
    lt = Table(top_labels, colWidths=[240, 120])
    lt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Arial"),
        ("FONTNAME", (0, 0), (-1, 0), "Arial-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#D9E2F3")]),
    ]))
    story.append(lt)
    story.append(Spacer(1, 12))

    # ── 6. Tests ──
    story.append(Paragraph("6. Тестовое покрытие", heading_style))
    story.append(Paragraph(
        "Три уровня тестов на <b>pytest</b>:",
        body_style,
    ))
    story.append(Paragraph(
        "• <b>Unit (121 тест)</b>: BIOES-decode, chunk merge, regex fallback (Luhn), "
        "confidence policy, pseudonym registry (EN + RU), replacement strategies (EN + RU), "
        "offset apply. Без загрузки модели.<br/>"
        "• <b>Integration (4 теста)</b>: экспорт final vs audit, валидация JSON/XLSX, "
        "no-PII-leak в финальном артефакте.<br/>"
        "• <b>E2E (4 теста)</b>: smoke test, no-PII-leak, determinism, XLSX schema.<br/>"
        "• <b>Model (7 тестов)</b>: pipeline на структурированных/неструктурированных документах, "
        "консистентность (требуют реальные веса).",
        body_style,
    ))
    story.append(Paragraph(
        "Быстрый прогон: <font face='CourierNew'>pytest -m 'not model'</font> — 121 тест за ~1.5 сек. "
        "Полный прогон: <font face='CourierNew'>pytest</font> — 128 тестов.",
        body_style,
    ))
    story.append(Spacer(1, 8))

    # ── 7. Limitations ──
    story.append(Paragraph("7. Ограничения", heading_style))
    story.append(Paragraph(
        "• Модель покрывает 55 категорий ПДн; редкие категории могут давать "
        "ложноотрицательные результаты — компенсируется regex-fallback.<br/>"
        "• Sliding-window: overlap 64 токена может не покрыть сущности длиннее overlap-зоны.<br/>"
        "• Fuzzy-match имён — эвристика (token_sort_ratio), не строгий coreference resolution.<br/>"
        "• Обработка ограничена текстовыми документами (без OCR).<br/>"
        "• 26.8% сущностей (occupation, url, gender и др.) заменяются на [REDACTED] — "
        "нет словаря псевдонимов для этих категорий.<br/>"
        "• Полный датасет (100k) требует ~6 часов на CPU; для production рекомендуется GPU.",
        body_style,
    ))

    doc.build(story)


if __name__ == "__main__":
    generate_report("output/case1-pii/report.pdf")
    print("Report generated: output/case1-pii/report.pdf")
