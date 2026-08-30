# Sber AI Hackathon 2026

Решения трёх независимых кейсов AI-хакатона Сбер. Каждый кейс — отдельная capability с собственным пайплайном, тестами и артефактами.

## Кейсы

| # | Название | Описание | Статус |
|---|---------|----------|--------|
| 1 | [Обезличить и сохранить смысл](#кейс-1-обезличить-и-сохранить-смысл) | Batch-анонимизация ПДн в документах | ✅ |
| 2 | [Инъекция на входе](#кейс-2-инъекция-на-входе) | Классификация prompt-injection запросов | ✅ |
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

### Метрики качества

Сравнение с разметкой `nvidia/Nemotron-PII` на 986 документах (document-level label matching):

| Метрика | Значение |
|---------|----------|
| Precision | 0.8635 |
| Recall | 0.4847 |
| F1 | 0.6209 |

Per-label F1 (топ-5): url (0.70), state (0.69), account_number (0.68), first_name (0.67), last_name (0.65). phone_number — over-detection: P=0.25, R=0.91.

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
PYTHONPATH=src uv run python -m pii.run --max-samples 100 --output-dir output/case1-pii/run

# Стратифицированная выборка
PYTHONPATH=src uv run python -m pii.run --max-samples 1000 --stratify-by domain --output-dir output/case1-pii/stratified_1000

# Генерация отчёта
PYTHONPATH=src uv run python -m pii.generate_report_docx
```

### Артефакты

```
output/
├── case1-pii/
│   ├── stratified_1000/
│   │   ├── audit.jsonl    # Аудиторский (с original, для проверяющих)
│   │   ├── final.json     # Финальный (без original)
│   │   ├── final.xlsx     # То же в XLSX
│   │   └── summary.json   # Метаданные прогона
│   ├── report.docx        # Word-отчёт
│   └── report.pdf         # PDF-отчёт
```

### Ограничения

- Модель покрывает 55 категорий ПДн; редкие категории могут давать ложноотрицательные результаты — компенсируется regex-fallback
- Sliding-window: overlap 64 токена может не покрыть сущности длиннее overlap-зоны
- Fuzzy-match имён — эвристика (token_sort_ratio), не строгий coreference resolution
- Обработка ограничена текстовыми документами (без OCR)
- 26.8% сущностей (occupation, url, gender и др.) заменяются на [REDACTED] — нет словаря псевдонимов
- Полный датасет (100k) требует ~6 часов на CPU; для production рекомендуется GPU

---

## Кейс 2: Инъекция на входе

### Суть задачи

Построить AI-стража, классифицирующего поток пользовательских запросов на два класса — **safe** и **injection and malicious** — и для каждого выбирающего решение: пропустить, заблокировать или отправить на ручную проверку, с кратким обоснованием.

- **Batch-классификация** 10 000 запросов из test-сплита
- **Confidence-based маршрутизация**: не пропускать пограничные случаи как безопасные
- **Defense-in-depth**: компенсация блайндспота модели через heuristic-слой jailbreak-детекции
- **Обоснование** решения без обязательной генерации LLM

### Модель и датасет

- **Модель**: [protectai/deberta-v3-base-prompt-injection-v2](https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2) — fine-tune `microsoft/deberta-v3-base` (184M параметров), encoder-only sequence classification. Бинарный выход (benign / injection-detected). Post-training метрики: accuracy 95.25%, precision 91.59%, recall 99.74%, F1 95.49%.
- **Датасет**: [jayavibhav/prompt-injection-safety](https://huggingface.co/datasets/jayavibhav/prompt-injection-safety) — 50 000 train / 10 000 test строк. Разметка: label 0 (benign), 1 (injection), 2 (harmful). Для задания классы 1 и 2 объединяются в *injection and malicious*.

### Алгоритм решения

Пайплайн состоит из 5 шагов, реализованных в модулях `src/injection_guard/`:

1. **Batch-классификация** (`classifier.py`) — все тексты пропускаются через DeBERTa батчами по 32 примера (truncation=True, max_length=512). Для каждого запроса вычисляется вероятность injection-класса `p1`. Инференс логирует прогресс по каждому батчу.

2. **Confidence-политика решений** (`policy.py`) — двухпороговая маршрутизация:
   - `p1 < t_low` (0.05) → safe, пропустить
   - `p1 ≥ t_high` (0.55) → injection and malicious, заблокировать
   - `t_low ≤ p1 < t_high` → пограничный случай, ручная проверка

3. **Heuristic-override** (`heuristic.py`) — независимый regex/keyword-слой на 4 категории jailbreak-паттернов:
   - Смена роли/инструкций (EN + RU)
   - Извлечение системного промпта
   - Обфускация (base64, ROT13, переводы)
   - Код-контейнеры с инструктивным текстом
   
   Если heuristic-хит + решение «пропустить» → принудительная эскалация до `needs_review=true`.

4. **Генерация обоснования** (`policy.py`) — rule-based: перечисление сработавших heuristic-категорий и/или уровень уверенности модели. Пустая строка для чистого safe.

5. **Экспорт** (`export.py`) — итоговая таблица (запрос, класс, решение, обоснование) → `.xlsx` + промежуточный `raw_predictions.jsonl`.

### Калибровка порогов

Пороги калибруются на выборке 10 000 строк из train-сплита (grid search по критерию 0.6×recall_harmful + 0.4×F1). Текущие значения: `t_low=0.05`, `t_high=0.55`. Код калибровки: `calibrate.py`.

### Архитектура кода

```
src/injection_guard/
├── pipeline.py         # Оркестрация полного пайплайна
├── config.py           # Конфигурация (пороги, маппинг классов)
├── classifier.py       # Загрузка модели, batch-инференс с логированием
├── heuristic.py        # Словарь regex-паттернов, detect_heuristic_flags()
├── policy.py           # decide() + generate_rationale()
├── export.py           # Сборка таблицы, валидация, экспорт XLSX
├── calibrate.py        # Калибровка порогов на train-сплите
├── evaluate.py         # Evaluator: метрики на test-split
└── generate_report.py  # Генерация Word-отчёта
```

### Результаты инференса

Полный прогон test-сплита (10 000 строк) на CPU:

| Метрика | Значение |
|---------|----------|
| Время выполнения | 752 сек (~12.5 мин, CPU) |
| Скорость инференса | 13 rows/s |
| Пропустить (safe) | 1 905 (19.1%) |
| Заблокировать (injection) | 7 862 (78.6%) |
| Ручная проверка | 233 (2.3%) |
| Heuristic-хиты | 161 (1.6%) |

### Метрики качества

Сравнение с разметкой test-сплита (10 000 строк):

| Метрика | Значение |
|---------|----------|
| Accuracy | 0.5447 |
| Precision (injection) | 0.5565 |
| Recall (injection) | 0.8053 |
| F1 (injection) | 0.6582 |

**Важное ограничение**: 100% harmful-запросов (label=2) модель классифицирует с p1 < 0.05 — считает безопасными. Это известный блайндспот модели DeBERTa. Heuristic-слой перехватывает 16.1% из них.

### Тестирование

Три уровня тестов на pytest:

- **Unit (163 теста)** — маппинг классов, политика решений (все ветки t_low/t_high), heuristic-паттерны (срабатывание/несрабатывание), генератор обоснования. Без загрузки модели.
- **Integration** — pipeline на фикстурных промптах с реальной моделью.
- **E2E** — полный прогон test-сплита, детерминированность повторного запуска.

Быстрый прогон: `uv run pytest -m "not model"` — 163 теста за ~2 сек.

### Запуск

```bash
# Установка зависимостей
uv sync

# Быстрые тесты
uv run pytest -m "not model"

# Полный пайплайн (инференс + экспорт)
PYTHONPATH=src uv run python -c "from injection_guard.pipeline import run_pipeline; run_pipeline()"

# Калибровка порогов
PYTHONPATH=src uv run python -c "from injection_guard.calibrate import calibrate_thresholds; ..."

# Evaluator (метрики на test-split)
PYTHONPATH=src uv run python -m injection_guard.evaluate

# Генерация отчёта
PYTHONPATH=src uv run python -m injection_guard.generate_report
```

### Артефакты

```
output/case2-injection/
├── case2_results.xlsx       # Итоговая таблица (запрос, класс, решение, обоснование)
├── raw_predictions.jsonl     # Промежуточные предсказания (text, p1, raw_label)
├── calibration_result.json  # Результат калибровки порогов
└── report.docx              # Word-отчёт
```

### Ограничения

- **Harmful-блайндспот**: модель не детектирует прямые вредоносные команды (label=2), только prompt injection. Heuristic-слой компенсирует частично (16.1%).
- **False positives**: 3 493 безопасных запроса классифицированы как injection — модель даёт высокие scores на длинных инструктивно-подобных текстах.
- **Калибровка не устранила harmful-блайндспот**: все 1 000 harmful-запросов имеют p1 < t_low.
- **English-only**: модель DeBERTa v2 заявлена только для английского. Heuristic-слой содержит русские паттерны, но основной классификатор — EN-only.
- **Открытый список heuristic-паттернов**: словарь покрывает известные категории, но новые формы атак могут быть пропущены.
