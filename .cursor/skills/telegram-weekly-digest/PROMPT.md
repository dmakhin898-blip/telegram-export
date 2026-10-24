# Digest generation prompt

Copy into Cursor with:
- `@telegram-inbox/`
- `@AI tasks/telegram-export/channels.yaml`

---

Сгенерируй еженедельный дайджест Telegram-каналов **на русском**.

**Важно (v3):** не сохраняй финальный `Telegram Digest ….md` напрямую. Сначала пиши JSON-чанки в `telegram-export/_build/{dd_mm_yyyy}/`, затем запускай `python assemble_digest.py {dd_mm_yyyy}`.

## Export gate (обязательно — до чтения inbox)

**По умолчанию** (первый дайджест за запуск): агент **сам** запускает экспорт в этой сессии:

```bash
cd "/Users/daniilmakhin/Documents/AI tasks/telegram-export" && source .venv/bin/activate && python export_channels.py
```

Жди завершения (до ~120 мин). **Не читай `@telegram-inbox/` для дайджеста**, пока gate не пройден.

Проверь `telegram-export/.export_run.json`:

| Условие | Действие |
|---------|----------|
| `.export_in_progress` существует и lock **не stale** (PID жив, <120 мин) | жди или остановись с сообщением |
| manifest отсутствует или `digest_allowed: false` | **стоп**, дайджест не писать |
| `digest_allowed: true`, `status` ∈ `{complete, complete_with_errors}` | можно читать inbox |

**Дополнение в тот же день (append-only):** если пользователь явно просит supplement / догрузку и manifest `finished_at` попадает на **сегодня по Europe/Moscow**, `status` = `complete` или `complete_with_errors` — **не запускай экспорт**, сразу append `## Дополнение · HH:MM`.

## Период

1. Найди последний дайджест в `telegram-inbox/digests/` (макс. `created_at` в YAML frontmatter любого файла).
2. Нет дайджестов → `period_from` = 14 дней назад (UTC).
3. Иначе `period_from` = `created_at` последнего дайджеста (или последней `## Дополнение · HH:MM` в файле за сегодня).
4. `period_to` = сейчас (UTC).
5. Только сообщения в интервале; даты в заголовках экспорта UTC.

## Pipeline: JSON → assemble

Дата папки и файла: `dd_mm_yyyy` (например `18_07_2026`).

```
telegram-export/_build/dd_mm_yyyy/
  meta.json
  alumni.json
  tier_2.json
  other_batch_01.json
  other_batch_02.json
  …
```

После всех чанков:

```bash
cd "/Users/daniilmakhin/Documents/AI tasks/telegram-export"
source .venv/bin/activate
python assemble_digest.py dd_mm_yyyy
```

Финальный файл пишет только скрипт: `{INBOX_DIR}/digests/Telegram Digest dd_mm_yyyy.md`.

Сборщик сам ставит счёт полезного на заголовок канала (`### {имя} · {счёт}`, в том числе `· 0`) и упорядочивает каналы внутри `tier_2` и внутри `other` по этому счёту. При равенстве остаётся порядок `channels.yaml`. Не вписывай счёт в финальный дайджест вручную. Порядок каналов в JSON — не финальный порядок внутри tier.

### meta.json

```json
{
  "date": "18_07_2026",
  "created_at": "<ISO8601 UTC>",
  "period_from": "<ISO8601 UTC>",
  "period_to": "<ISO8601 UTC>",
  "export_run_id": "<из manifest run_id>",
  "export_status": "complete",
  "other_batches": ["other_batch_01.json", "other_batch_02.json"],
  "inactive_channels": ["@alias1"],
  "failed_channels": []
}
```

`other_batches` обязан перечислять все ожидаемые batch-файлы. Отсутствующий файл = ошибка assemble.

### alumni.json

```json
{
  "channels": [
    {
      "name": "Captain Alumni – Комьюнити выпускников",
      "short_name": "Captain Alumni",
      "topics": [
        {
          "theme": "Название темы",
          "teaser": "одно предложение",
          "url": "https://t.me/…",
          "problem": "…",
          "context": "плотный абзац (gate: ≥2 предложения или ≥200 символов)",
          "solution": "плотный абзац (gate: ≥1 предложение или ≥80 символов)"
        }
      ],
      "more_topics": [
        {"theme": "Другая тема", "post_count": 3, "url": "https://t.me/…"}
      ],
      "omitted_count": 4
    }
  ]
}
```

### tier_2.json / other_batch_NN.json

```json
{
  "channels": [
    {
      "name": "Полное имя канала",
      "short_name": "Короткое",
      "topics": [
        {
          "teaser": "одно предложение",
          "url": "https://t.me/…",
          "problem": "…",
          "context": "…",
          "solution": "…"
        }
      ],
      "more_topics": [
        {"summary": "Суть в одном предложении", "url": "https://t.me/…"}
      ],
      "omitted_count": 3
    }
  ]
}
```

Лимиты на канал (tier_2 / other): `topics` ≤ 5, `more_topics` ≤ 10. Меньше — OK, **без placeholder-тем**. Если qualifying posts ≤ 5 — `more_topics` пустой, секцию overflow не создавать (`omitted_count: 0`).

### Validation gate (assemble_digest.py)

Полная тема отклоняется, если:

- нет `problem` / `context` / `solution`
- `context` < 2 предложений **и** < 200 символов
- `solution` < 1 предложения **и** < 80 символов
- `context` равен тизеру или link-only

Компактные `more_topics` длиной не проверяются. При ошибке скрипт печатает id тем, exit ≠ 0, **финальный файл не пишет**.

## Разбивка по tier (`channels.yaml`)

| Tier | Страница | Каналы |
|------|----------|--------|
| `captain_alumni` | **Страница 1** (начало) | все из `tiers.captain_alumni.channels` |
| `tier_2` | **Страница 1** (после alumni) | все из `tiers.tier_2.channels` — **не дублировать на странице 2** |
| `other` (backfill 2weeks) | **Страница 3+** | все из `tiers.other.channels` с активностью |
| Служебное | **Хвост** | только «Без активности» |

Сопоставляй slug папки в `telegram-inbox/` с каналом по `channels.yaml` / catalog.

## AI-синтез (обязательно)

**Не копируй текст из экспорта.** Анализируй тематику, формулируй своими словами.

- Тизер (слой 1) и callout (слой 2) — **оригинальные саммари**, не цитаты.
- Запрещено копировать >15 подряд идущих слов из поста (кроме имён, URL, цифр).
- Для tier_2 и `other`: обычно 1 пост = 1 тема, но текст всё равно перефразируй.
- Для `captain-alumni-комьюнити-выпускников`: **группируй по теме** — несколько постов → одна тема; ссылка `[пост]` на **самый релевантный** пост.
- Callout — **обычная русская проза**, не ультра-сжатый стиль чата. Контекст должен объяснять пост, а не повторять тизер одним предложением.

## Структура темы (3 слоя в финальном markdown)

Сборщик рендерит JSON в такой вид:

### Слой 1 — тизер

```markdown
**{короткое имя канала}** — [пост](https://t.me/…/msg_id): суть в одном предложении (синтез, не цитата).
- [ ] Почитать в телеграмме
```

### Слой 2 — dropdown с деталями

Раскрывающийся **Obsidian callout** (`> [!abstract]- Подробнее`). Не использовать `<details>`.

1. **Проблема** — что болит / какой вопрос поднят.
2. **Контекст** — факты, цифры, кто что пробовал (синтез; плотность как у Alumni).
3. **Решение** — выводы, actionable-шаги.

URL из постов — **гиперссылки внутри текста**, не отдельным списком.

### Слой 3 — ссылка на пост

В конце callout, после чекбокса `Полезно`: `→ [Читать в Telegram](url)`.

---

## Порядок генерации

1. Alumni → `alumni.json`
2. Tier_2 → `tier_2.json`
3. Other → пачками по **≤5 каналов** → `other_batch_01.json`, …
4. `meta.json`
5. `assemble_digest.py`

Экспорт **не** перезапускать между batch-ами other.

---

## Страница 1 — Captain Alumni + Tier 2

### `captain-alumni-комьюнити-выпускников`

1. Прочитай все посты за период (кроме рекламы — см. ниже).
2. **Сгруппируй по темам** (CWS, Google/Yandex Ads, баны, монетизация, paywall, партнёрки, фишинг и т.д.).
3. **Ранжируй темы**: важность (AI) → число постов в теме → свежесть. Самая главная — первая.
4. **~20 полных блоков** для топ-тем.
5. Остальные релевантные темы → `more_topics` + `omitted_count`.
6. Минимума нет — если тем мало, выведи все релевантные.

Остальные captain-каналы (App-Database, Билдеры и др.) — все значимые темы за период.

### Tier 2 (`tiers.tier_2.channels`)

Сразу после alumni, **без общего заголовка секции**.

- До **5 полных тем** на канал (меньше OK, без placeholders).
- Ранжирование: важность → реакции/реплаи (если есть) → свежесть.
- Реклама и media-only stubs — вне `topics`, `more_topics` и `omitted_count`.
- Остаток → до 10 строк в `more_topics` (`summary` + `url`), затем `omitted_count`.
- Expand-on-request для tier_2 **нет**.

### Overflow alumni

В JSON: `more_topics` с `theme`, `post_count`, `url` + `omitted_count`.  
В markdown сборщик рисует `### Ещё темы Alumni`.

По запросу пользователя («разверни тему X из overflow» / «догрузи остальные темы alumni») — сгенерируй полные 3-слойные блоки для названных тем из того же периода (можно дописать в digest вручную после assemble). **Только Alumni.**

---

## Страница 3+ — Каналы other

Для **каждого** канала tier `other` **с активностью** (tier_2 исключены):

- До **5 полных тем** + overflow как у tier_2.
- Генерация **пачками ≤5 каналов** → отдельный `other_batch_NN.json`.
- Каналы без постов — в `meta.inactive_channels`.

### События · Скоро

Если в каналах есть ближайшие события — добавь в последний other-batch отдельный канал-объект или поле в `meta` не требуется: можно вставить таблицу в `meta` позже; пока клади события как обычные topics канала мероприятий (макс. 8 строк смысла в периоде ≤14 дней от `period_to`).

---

## Хвост

`inactive_channels` и `failed_channels` — в `meta.json`. Сборщик рендерит `## Каналы без активности` и при необходимости `## Экспорт неполный`.

**Секции `## Полезные ссылки` не создавай.**

---

## Рекламные посты — исключить

**Пропускай** посты, которые рекламируют продукт/услугу/партнёрство. **Оставляй** посты про механизмы и стратегию рекламы без спонсорской пометки.

Эвристики (начало/конец поста): `* * реклама * *`, `#реклама`, `Реклама.` / `Реклама`, `erid:`, `Рекламодатель`. Плюс **контекстный анализ** — при сомнении решай по смыслу (продаёт vs обсуждает).

---

## Критерии отбора тем

- пересечение с интересами **ИЛИ**
- тред ≥3 сообщений **ИЛИ**
- actionable-пост (инструмент, вакансия, анонс, кейс с цифрами)

Для tier_2 и other: топ до 5 полных на канал, остальное в overflow.

## Ссылки на посты

1. `alias` из конфига → `https://t.me/{alias}/{msg_id}`
2. URL из `[media: ...]` stub
3. `msg:N` + `(channel_id)` → `https://t.me/c/{channel_id}/{msg_id}`

## Интересы

**Общие:** Chrome/CWS/монетизация/реклама; Captain/alumni/билдеры; PM/стартапы/вакансии; App Database; Ростов; путешествия/лыжи; инструменты и actionable-анонсы.

**Фокус:**
- `captain-alumni-*` — тематические кластеры, ~20 полных + overflow
- `tier_2` — топ до 5 на канал (Антонов, Мараховский, Кримсон) + overflow
- `мероприятия-ростов-*` — события
- прочие `other` — топ до 5 + overflow, батчами по 5 каналов

## Исключить

- Media-only `[media: ...]` без контекста
- Рекламные посты (см. выше)
- Дубли tier_2 на странице 2+
- Дублирование одной темы на разных страницах
- Копипаст текста экспорта в саммари
- Placeholder-темы «пустой слот»
- Прямую запись финального digest в обход `assemble_digest.py`
- Отдельный список «Полезные ссылки»

## Обратная связь (не автоматически)

Читать `- [x] Почитать в телеграмме` / `- [x] Полезно` в прошлых дайджестах → предлагать правки интересов.
