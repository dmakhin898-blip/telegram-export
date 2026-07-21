# Инструкция для агента: telegram-export

Этот файл — для агента пользователя. Здесь нет личных каналов и путей владельца репозитория. Помоги пользователю настроить проект и собрать еженедельный дайджест.

## 1. Первичная настройка

### 1.1 Окружение Python

```bash
cd telegram-export
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 1.2 Файл `.env`

1. Скопируй `.env.example` → `.env`.
2. Возьми `API_ID` и `API_HASH` на [my.telegram.org/apps](https://my.telegram.org/apps).
3. Заполни `INBOX_DIR` — **абсолютный** путь к папке inbox (обычно внутри Obsidian vault), куда писать экспорт. Пример структуры значения: `/Users/<user>/Documents/<vault>/telegram-inbox`.
4. Пустое `INBOX_DIR` недопустимо: скрипты завершатся с ошибкой и отсылкой к `.env.example`.

Агент **не** подставляет чужой путь из примеров — только спрашивает у пользователя или читает уже заполненный `.env`.

### 1.3 Первый логин

```bash
source .venv/bin/activate
python list_dialogs.py
```

Пользователь вводит телефон, код из Telegram и при необходимости облачный пароль 2FA. Создаётся `telegram_export.session` (уже в `.gitignore`).

### 1.4 Каналы

```bash
cp channels.example.yaml channels.yaml
python list_dialogs.py
```

1. `channels.example.yaml` — только **вымышленная** структура. Реальные id пользователя туда не коммить.
2. Помоги заполнить `channels.yaml`:
   - `tiers.captain_alumni.channels` — каналы с полным бэкапом (`backfill: full`)
   - `tiers.tier_2.channels` — приоритетные авторы (страница 1 дайджеста после alumni)
   - `tiers.other.channels` — остальные (`backfill: 2weeks`)
3. Id копировать **точно** с `-100…` из вывода `list_dialogs.py`. Юзернеймы — `"@username"` без ведущего минуса.
4. `channels.yaml` в git не попадает.

### 1.5 Поведение `INBOX_DIR` / `common.py`

- Путь inbox берётся **только** из переменной окружения `INBOX_DIR` (обычно из `.env`).
- Хардкодного пути владельца в коде нет.
- Если `INBOX_DIR` пуст или не задан → `SystemExit` с текстом про копирование `.env.example` и установку `INBOX_DIR`.
- Экспорт пишет в `{INBOX_DIR}/{channel_slug}/YYYY-MM.md`.

Проверка после настройки: убедись, что `INBOX_DIR` в `.env` указывает на существующую (или создаваемую) директорию, куда пользователю можно писать.

## 2. Еженедельный ритуал

### Шаг A — экспорт

```bash
source .venv/bin/activate
python export_channels.py
```

Жди завершения (первый полный бэкап alumni может быть долгим). Параллельные экспорты блокируются lock-файлом.

### Шаг B — gate

Перед чтением inbox проверь:

| Условие | Действие |
|---------|----------|
| Есть `.export_in_progress` и lock не stale (PID жив, <120 мин) | ждать / сообщить пользователю |
| Нет `.export_run.json` или `digest_allowed: false` | **стоп**, дайджест не собирать |
| `digest_allowed: true`, `status` ∈ `{complete, complete_with_errors}` | можно читать inbox |

Артефакты лежат в корне `telegram-export/` (gitignored): `.export_in_progress`, `.export_run.json`.

### Шаг C — JSON-чанки саммари

Не пиши финальный `Telegram Digest ….md` вручную.

1. Определи период: от `created_at` последнего дайджеста в `{INBOX_DIR}/digests/` (или 14 дней назад, если дайджестов нет) до сейчас (UTC).
2. Создай папку `telegram-export/_build/{dd_mm_yyyy}/` (дата генерации).
3. Порядок генерации:
   1. Alumni → `alumni.json` (тематические кластеры, ~20 полных тем + overflow)
   2. tier_2 → `tier_2.json` (до 5 полных тем на канал + overflow)
   3. other → пачками **не больше 5 каналов** → `other_batch_01.json`, `other_batch_02.json`, …
   4. `meta.json` со списком всех `other_batches`
4. Экспорт между batch-ами **не** перезапускать.

#### Схема полной темы (tier_2 / other)

Поля: `teaser`, `url`, `problem`, `context`, `solution`.  
`context` должен быть плотным (≥2 предложения **или** ≥200 символов), `solution` — ≥1 предложение **или** ≥80 символов. Нельзя копировать тизер в `context` и нельзя оставлять link-only.

#### Overflow (tier_2 / other)

- До 5 полных тем; меньше — нормально, без пустых заглушек.
- До 10 строк в `more_topics`: `{"summary": "…", "url": "…"}`.
- Остальное → `omitted_count`.
- В markdown: `### Ещё темы`, затем `_Ещё N не вошло в подборку._`.
- Разворачивать эти one-liners в полные блоки по запросу **не нужно**.

#### Alumni overflow

- `more_topics`: `theme`, `post_count`, `url`.
- По запросу пользователя можно дописать полные 3-слойные блоки (только alumni).

#### meta.json (минимум)

```json
{
  "date": "18_07_2026",
  "created_at": "<ISO8601 UTC>",
  "period_from": "<ISO8601 UTC>",
  "period_to": "<ISO8601 UTC>",
  "export_run_id": "<run_id из .export_run.json>",
  "export_status": "complete",
  "other_batches": ["other_batch_01.json"],
  "inactive_channels": [],
  "failed_channels": []
}
```

### Шаг D — сборка

```bash
source .venv/bin/activate
python assemble_digest.py dd_mm_yyyy
```

Скрипт:

- читает `_build/{dd_mm_yyyy}/`
- валидирует полные темы
- при ошибке печатает id тем, exit ≠ 0, **файл дайджеста не пишет**
- при успехе пишет `{INBOX_DIR}/digests/Telegram Digest dd_mm_yyyy.md`

Если валидация упала — допиши плотный `context`/`solution` в JSON и повтори assemble.

Папка `_build/` техническая (gitignore). После успеха можно оставить для отладки.

## 3. Чего не делать

1. Не коммитить `.env`, `channels.yaml`, `*.session`, `_build/`, `openspec/`.
2. Не подставлять чужие реальные каталоги каналов в example-файлы.
3. Не писать финальный дайджест в обход `assemble_digest.py`.
4. Не класть в этот файл личные интересы / списки каналов владельца репозитория — только нейтральный пайплайн.

## 4. Полезные команды

| Команда | Зачем |
|---------|--------|
| `python list_dialogs.py` | список каналов и peer id |
| `python export_channels.py` | инкрементальный экспорт |
| `python assemble_digest.py dd_mm_yyyy` | сборка дайджеста из JSON |
| `python assemble_digest.py dd_mm_yyyy --dry-run` | только валидация |
| `python -m unittest tests/test_assemble_digest.py` | проверка gate на фикстурах |

## 5. Человеческий README

Для ручной установки без агента см. [README.md](README.md). Детали дайджест-пайплайна для агента — этот файл.
