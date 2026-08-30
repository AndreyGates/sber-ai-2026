# Sber AI Hackathon 2026

Решения трёх независимых кейсов AI-хакатона Сбер. Каждый кейс — отдельная капобилити с собственным пайплайном, тестами и артефактами.

## Кейсы

| # | Название | Описание | Статус |
|---|---------|----------|--------|
| 1 | [Обезличить и сохранить смысл](#кейс-1-обезличить-и-сохранить-смысл) | Batch-анонимизация ПДн в документах | ✅ |
| 2 | Инъекция на входе | Классификация prompt-injection запросов | — |
| 3 | Ревизор кода | AI-аудит Python-кода на уязвимости (CWE) | — |

---

## Кейс 1: Обезличить и сохранить смысл

### Суть задачи

Разработать AI-инструмент для анонимизации персональных данных в документах кредитной организации: договоры, письма, тикеты, заявки, медицинские записи. Требования:

- **Детекция** всех видов ПДн (имена, телефоны, email, паспорта, карты, адреса, даты рождения, медицинские данные и т.д.)
- **Замена** на реалистичные псевдонимы или маски — не просто `[УДАЛЕНО]`, а консистентные значения, сохраняющие смысл документа
- **Консистентность**: один и тот же человек в документе получает один и тот же псевдоним на всех упоминаниях
- **Сохранение формата**: номера телефонов, карт, документов маскируются с сохранением структуры (последние 4 цифры видны)
- **Двухуровневый экспорт**: финальный артефакт (без исходных ПДн) + аудиторский (с исходными, для проверяющих)

### Модель и датасет

- **Модель**: [OpenMed/privacy-filter-nemotron](https://huggingface.co/OpenMed/privacy-filter-nemotron) — токен-классификатор на базе `openai/privacy-filter`, дообученный на `nvidia/Nemotron-PII`. 55 категорий ПДн, 221 BIOES-класс, macro B-F1 ≈ 0.95.
- **Датасет**: [nvidia/Nemotron-PII](https://huggingface.co/datasets/nvidia/Nemotron-PII) — 100 000 синтетических документов (test-split). 150+ типов документов (visa applications, credit card forms, medical records, rental applications, invoices, contracts...), 30 доменов, форматы structured/unstructured, локаль US.

### Алгоритм решения

Пайплайн состоит из 11 шагов, реализованных в модулях `src/pii/`:

1. **Sliding-window токенизация** (`tokenizer.py`) — текст разбивается на окна по 512 токенов с overlap 64 токена. Каждому токену сопоставляется char-offset для последующего маппинга обратно в текст.

2. **Модельный инференс** (`pipeline.py`) — каждое окно пропускается через `AutoModelForTokenClassification`. Для каждого токена предсказывается BIOES-тег и confidence score.

3. **BIOES-decode** (`bioes.py`) — последовательность тегов конвертируется в span-уровневые сущности: `(start, end, label, score)`. S-тег = одиночная сущность, B-I-E = многотокенная.

4. **Merge на границах чанков** (`chunk_merge.py`) — сущности из перекрывающихся окон дедуплицируются. При частичном перекрытии сохраняется спан с максимальным score.

5. **Regex-fallback** (`regex_fallback.py`) — defense-in-depth слой: regex для email, телефонов, номеров карт (с проверкой Luhn). Не дублирует уже покрытые модельные спаны.

6. **Политика уверенности** (`confidence.py`) — трёхуровневая:
   - score ≥ 0.85 → замена (replace)
   - 0.5 ≤ score < 0.85 + high-risk категория → маскирование + `needs_review=true`
   - score < 0.5 → пропуск

7. **Нормализация** (`normalize.py`) — NFKC + casefold + collapse whitespace. Fuzzy-match имён через `rapidfuzz.token_sort_ratio` для группировки вариантов написания.

8. **Реестр псевдонимов** (`registry.py`) — детерминированный per-document реестр. Ключ: `(normalized_value, category)`. Сид: `SHA256(doc_id + value + category)`. Locale-aware словари (EN/RU): имена, фамилии, города, улицы, организации.

9. **Стратегии замены** (`strategies.py`) — category-aware диспатч для 50+ лейблов модели:
   - Имена → псевдоним из словаря (консистентный в документе)
   - Телефоны/карты → формат-сохраняющая маска (последние N цифр видны)
   - Email → маскирование local-part, домен сохранён
   - Даты → генерализация (MM/DD/YYYY для US, DD.MM.YYYY для RU)
   - Адреса → обобщение из словаря городов/улиц
   - Медданные → метка `[MEDICAL DATA]`
   - Чувствительные атрибуты (occupation, gender, race...) → `[REDACTED]`

10. **Применение замен** (`apply.py`) — замены применяются справа налево по char-offsets, чтобы избежать сдвига позиций.

11. **Экспорт** (`export.py`) — двойной: финальный артефакт (`include_original=False`) + аудиторский (`include_original=True`). Форматы: JSON, JSONL, XLSX. Валидация по JSON-схеме.

### Архитектура кода

```
src/pii/
├── run.py              # CLI точка входа
├── pipeline.py         # Оркестрация пайплайна
├── config.py           # Конфигурация (модель, пороги, high-risk категории)
├── tokenizer.py        # Sliding-window токенизация
├── bioes.py            # BIOES-decode
├── chunk_merge.py      # Слияние спанов на границах чанков
├── regex_fallback.py   # Regex defense-in-depth
├── confidence.py       # Политика уверенности
├── normalize.py        # Нормализация + fuzzy-match
├── registry.py         # Locale-aware реестр псевдонимов
├── strategies.py       # Стратегии замены
├── apply.py            # Применение замен по offsets
├── export.py           # Экспорт JSON/JSONL/XLSX
├── dataset.py          # Загрузка Nemotron-PII, стратификация
├── generate_report.py  # Генерация PDF-отчёта
└── generate_report_docx.py  # Генерация Word-отчёта
```

### Результаты инференса

Стратифицированная выборка 1000 записей из test-split (100k) по домену (domain):

| Метрика | Значение |
|---------|----------|
| Обработано документов | 986 |
| Время выполнения | 367 сек (~6 мин, CPU) |
| Сущностей детектировано | 9 199 |
| Псевдонимы (имена, адреса, даты, организации) | 5 365 (58.3%) |
| Формат-маски (телефон, карта, ID, счёт) | 1 373 (14.9%) |
| [REDACTED] (occupation, url, gender и др.) | 2 461 (26.8%) |
| Документов с needs_review | 15 (1.5%) |
| Ошибок обработки | 0 |
| Уникальных типов документов | 678 |

Топ-5 детектированных категорий: PHONE_NUMBER (1 357), first_name (811), date (730), last_name (534), company_name (472).

### Тестирование

Три уровня тестов на pytest:

- **Unit (121 тест)** — BIOES-decode, chunk merge, regex fallback (Luhn), confidence policy, pseudonym registry (EN + RU), replacement strategies, offset apply. Без загрузки модели.
- **Integration (4 теста)** — экспорт final vs audit, валидация JSON/XLSX, no-PII-leak.
- **E2E (4 теста)** — smoke test, no-PII-leak (безопасность), determinism, XLSX schema.
- **Model (7 тестов)** — pipeline на реальных весах: structured/unstructured документы, консистентность.

Быстрый прогон: `uv run pytest -m "not model"` — 121 тест за ~1.5 сек.

### Запуск

```bash
# Установка зависимостей
uv sync

# Быстрые тесты
uv run pytest -m "not model"

# Инференс на выборке
PYTHONPATH=src uv run python -m pii.run --max-samples 100 --output-dir output/case1-pii-anonymization/run

# Стратифицированная выборка
PYTHONPATH=src uv run python -m pii.run --max-samples 1000 --stratify-by domain --output-dir output/case1-pii-anonymization/stratified_1000

# Генерация отчёта
PYTHONPATH=src uv run python -m pii.generate_report_docx
```

### Артефакты

```
output/
├── case1-pii-anonymization/
│   ├── stratified_1000/
│   │   ├── audit.jsonl    # Аудиторский (с original, для проверяющих)
│   │   ├── final.json     # Финальный (без original)
│   │   ├── final.xlsx     # То же в XLSX
│   │   └── summary.json   # Метаданные прогона
│   ├── report.docx        # Word-отчёт
│   └── report.pdf         # PDF-отчёт
├── case2-prompt-injection/   # (будущий кейс)
└── case3-code-review/        # (будущий кейс)
```

### Ограничения

- Модель покрывает 55 категорий ПДн; редкие категории могут давать ложноотрицательные результаты — компенсируется regex-fallback
- Sliding-window: overlap 64 токена может не покрыть сущности длиннее overlap-зоны
- Fuzzy-match имён — эвристика (token_sort_ratio), не строгий coreference resolution
- Обработка ограничена текстовыми документами (без OCR)
- 26.8% сущностей (occupation, url, gender и др.) заменяются на [REDACTED] — нет словаря псевдонимов
- Полный датасет (100k) требует ~6 часов на CPU; для production рекомендуется GPU
