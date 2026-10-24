---
name: telegram-weekly-digest
description: >-
  Generates Russian weekly Telegram digest from telegram-inbox exports.
  AI thematic summaries (no copy-paste). 3-layer topics (teaser + callout + t.me).
  Page 1: Captain Alumni (thematic clusters, ~20 full + overflow) + tier_2 (≤5/channel + overflow).
  Page 3+: other tier (≤5 topics/channel + overflow), batched JSON → assemble_digest.py.
  Use when user asks for telegram digest, дайджест, weekly inbox summary,
  or @telegram-inbox review after export.
---

# Telegram Weekly Digest

## Prerequisites

1. **Export gate (обязательно):** дайджест только после успешного экспорта. См. раздел «Export gate» ниже.
2. Read tier membership from `channels.yaml` (`captain_alumni`, `tier_2`, `other`)

## Export gate

**По умолчанию** (`/telegram-weekly-digest`): агент **сам** запускает экспорт в этой же сессии, ждёт завершения (~35 мин), проверяет manifest, потом читает inbox.

```bash
cd "/Users/daniilmakhin/Documents/AI tasks/telegram-export"
source .venv/bin/activate
python export_channels.py
```

Артефакты в `telegram-export/` (не в inbox):

| Файл | Назначение |
|------|------------|
| `.export_in_progress` | lock: `pid`, `started_at` — экспорт идёт |
| `.export_run.json` | manifest: `run_id`, `status`, `digest_allowed`, stats |

**Перед чтением inbox для дайджеста:**

1. Нет `.export_in_progress` (или lock stale: PID мёртв / >120 мин)
2. `.export_run.json` с `digest_allowed: true` от **этого** запуска экспорта
3. `status` ∈ `{complete, complete_with_errors}`

Если lock активен или manifest не готов — **стоп**, не писать дайджест.

**Дополнение в тот же день (MSK):** если пользователь просит supplement и manifest `finished_at` — сегодня по `Europe/Moscow`, `status` = `complete*` — **без повторного экспорта**, append `## Дополнение · HH:MM`.

## Quick start

```
@telegram-inbox/
@AI tasks/telegram-export/channels.yaml

Сгенерируй дайджест по skill telegram-weekly-digest
```

Follow [PROMPT.md](PROMPT.md). **Не пиши финальный markdown напрямую** — сначала JSON в `_build/`, затем `assemble_digest.py`.

## Topic structure (обязательно для каждой полной темы)

Три слоя — см. [PROMPT.md](PROMPT.md) и [EXAMPLES.md](EXAMPLES.md). **AI пишет саммари**, не копирует экспорт.

| Слой | Содержание | Чекбокс |
|------|------------|---------|
| 1 | `**Канал** — [пост](url): синтез в одном предложении` | `- [ ] Почитать в телеграмме` |
| 2 | Obsidian callout `> [!abstract]- Подробнее`: Проблема + Контекст + Решение (плотный русский прозы, проходит gate) | `- [ ] Полезно` |
| 3 | `→ [Читать в Telegram](url)` в конце callout | — |

Отдельной секции `## Полезные ссылки` **нет**.

## Layout

| Page | Content |
|------|---------|
| 1a | `captain_alumni` — alumni комьюнити: **тематические кластеры**, ~20 полных + overflow |
| 1b | `tier_2` — **≤5 полных тем/канал** + `### Ещё темы` (до 10 one-liners) |
| 3+ | `other` — **≤5 полных тем/канал** + overflow; tier_2 **исключены** |
| tail | `## Каналы без активности` |

`<!-- page-break -->` после alumni, после tier_2, перед `other`.

`assemble_digest.py` пишет заголовок каждого канала как `### {name} · {count}`: счёт отметок «Полезно» за всё время, включая `· 0`. Внутри `tier_2` и внутри `other` каналы идут по этому счёту, больше — выше; при равенстве остаётся порядок `channels.yaml`. Alumni остаётся одним блоком, без перестановки. Не вписывай счёт в финальный дайджест вручную. Порядок каналов в JSON — не финальный порядок внутри tier.

## Workflow (v3)

0. **Export gate** — default: run `export_channels.py` synchronously (timeout ≥120 min), verify manifest; append-only: skip if today's MSK manifest is `complete*`.
1. Period from last digest `created_at` (see PROMPT.md).
2. Split channels by `channels.yaml` tiers.
3. **Alumni pass** → write `telegram-export/_build/{dd_mm_yyyy}/alumni.json` (cluster by theme, ~20 full + overflow).
4. **Tier_2 pass** → write `tier_2.json` (≤5 full/channel + overflow; no placeholders).
5. **Other passes** → batches of **≤5 channels**; each batch writes `other_batch_NN.json` only (no final markdown).
6. Write `meta.json` listing expected `other_batches`, inactive channels, export ids.
7. Run assemble:

```bash
cd "/Users/daniilmakhin/Documents/AI tasks/telegram-export"
source .venv/bin/activate
python assemble_digest.py dd_mm_yyyy
```

8. If assemble exits non-zero — thicken failing JSON topics and re-run assemble. **Do not** hand-write the final digest to bypass the gate.
9. Skip sponsored posts; keep educational posts about advertising.

## Overflow

| Tier | Overflow | Expand on request |
|------|----------|-------------------|
| Alumni | `### Ещё темы Alumni` + omitted count | **Yes** — full 3-layer blocks |
| tier_2 / other | `### Ещё темы` (≤10 one-liners) + `_Ещё N не вошло в подборку._` | **No** |

## Exclude

No `[media: ...]` section; skip media-only stubs; skip sponsored posts; no empty placeholder topics.

## Example

[EXAMPLES.md](EXAMPLES.md).
