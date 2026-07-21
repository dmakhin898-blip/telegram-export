# telegram-export

Telethon userbot: экспортирует выбранные Telegram-каналы в markdown (удобно класть в Obsidian) и собирает еженедельный дайджест через агента.

## Setup

1. **Python 3.10+** и venv:

   ```bash
   cd telegram-export
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Telegram API** с [my.telegram.org/apps](https://my.telegram.org/apps):
   - Скопируй `.env.example` → `.env`
   - Заполни `API_ID` и `API_HASH`
   - Заполни `INBOX_DIR` — абсолютный путь к своей папке inbox (например внутри vault). Пустое значение не сработает: скрипты требуют явный путь.

   Нужны оба типа доступа:
   - `API_ID` / `API_HASH` — приложение
   - телефон + код (+ пароль 2FA при включённой двухфакторке) — аккаунт; сессия в `telegram_export.session`

3. **Первый логин** (интерактивно):

   ```bash
   source .venv/bin/activate
   python list_dialogs.py
   ```

   Сессия в git не попадает; локально можно `chmod 600 telegram_export.session`.

4. **Каналы**:

   ```bash
   cp channels.example.yaml channels.yaml
   python list_dialogs.py
   ```

   В `channels.yaml` разнеси id по tier:

   - `captain_alumni` — полный бэкап
   - `tier_2` — приоритетные авторы (дайджест, страница 1 после alumni)
   - `other` — остальные (бэкап 14 дней)

   `channels.example.yaml` — только вымышленный шаблон структуры. Свой каталог держи в `channels.yaml` (gitignore).

### Формат id

Копируй id **точно** из `list_dialogs.py`:

```yaml
channels:
  - -1001111111111       # ✓ peer id с префиксом -100
  - "@example_author"    # ✓ username
```

Ошибки:

```yaml
  - -1111111111          # ✗ нет префикса -100
  - -"@username"         # ✗ невалидный YAML/строка
```

## Еженедельный ритуал

1. **Экспорт** — `python export_channels.py` (или пусть агент запустит сам)
2. **Проверка gate** — `telegram-export/.export_run.json` с `digest_allowed: true`, без активного `.export_in_progress`
3. **Саммари** — агент пишет JSON в `telegram-export/_build/{dd_mm_yyyy}/` (пачками по каналам)
4. **Сборка** — `python assemble_digest.py dd_mm_yyyy` → `{INBOX_DIR}/digests/Telegram Digest dd_mm_yyyy.md`

```bash
source .venv/bin/activate
python export_channels.py
# … после генерации JSON агентом …
python assemble_digest.py 18_07_2026
```

Полная инструкция для агента (настройка `.env` / `channels.yaml` / пайплайн дайджеста): **[AGENTS.md](AGENTS.md)**.

### Артефакты экспорта

В корне `telegram-export/` (gitignore):

| Файл | Назначение |
|------|------------|
| `.export_in_progress` | lock на время экспорта |
| `.export_run.json` | manifest последнего запуска |

Поля manifest: `run_id`, `status` (`complete` \| `complete_with_errors` \| `failed`), `digest_allowed`, `inbox_dir`, счётчики, `failed_channels[]`.

Агент **не** читает inbox для дайджеста, пока `digest_allowed` не `true` и lock не снят.

Первый полный бэкап `captain_alumni` может идти долго — смотри появление файлов в `INBOX_DIR`. Параллельные экспорты запрещены lock-файлом.

## Свободные запросы по истории

```
@{INBOX_DIR}/{channel_slug}/2025-11.md

What did channel discuss about [topic] in November?
```

Повторный экспорт не нужен — читай уже выгруженные month-файлы.

## Файлы

| Файл | Назначение |
|------|------------|
| `list_dialogs.py` | список каналов и peer id |
| `export_channels.py` | инкрементальный экспорт + manifest |
| `assemble_digest.py` | сборка дайджеста из `_build/` JSON |
| `AGENTS.md` | инструкция для агента |
| `channels.yaml` | твои каналы (gitignore) |
| `channels.example.yaml` | вымышленный шаблон |
| `.env` | креды и `INBOX_DIR` (gitignore) |

## Куда пишется экспорт

Путь задаётся только через `INBOX_DIR` в `.env`. Файлы: `{channel_slug}/YYYY-MM.md` с UTC-временем и id сообщений. Дайджесты: `{INBOX_DIR}/digests/`.

## Troubleshooting

| Ошибка | Причина | Что сделать |
|--------|---------|-------------|
| `ModuleNotFoundError: telethon` | venv не активирован | `source .venv/bin/activate` |
| `Missing INBOX_DIR` | пустой `.env` / нет переменной | скопируй `.env.example`, задай `INBOX_DIR` |
| `Invalid object ID for a chat` | id без `-100` | копируй id из `list_dialogs.py` |
| `Cannot find entity ... "@user"` | YAML вида `- "@user"` | пиши `"@user"` без минуса |
| `database is locked` | два процесса на одну session | дождись / убей второй Python; не гоняй экспорт параллельно |
| `Export already in progress` | активный lock | дождись или сними stale lock (мёртвый PID / >120 мин) |
| Validation failed в assemble | тонкий `Подробнее` | допиши `context`/`solution` в JSON и повтори assemble |
