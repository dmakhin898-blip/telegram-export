# Digest output example

## Captain Alumni — одна тема (3 слоя, AI-синтез)

Финальный markdown после `assemble_digest.py`:

```markdown
**Captain Alumni** — [пост](https://t.me/c/2210731208/16231): Связка US IP + UK eSIM и Elama даёт рабочий Google Ads из РФ при пополнении ~10k ₽.
- [ ] Почитать в телеграмме

> [!abstract]- Подробнее
> **Проблема:** Запуск Google Ads для расширений из РФ упирается в верификацию и баны при прямой оплате.
>
> **Контекст:** Участники собрали связку: резидентский US IP, UK eSIM, Firefox с [FoxyProxy](https://addons.mozilla.org/firefox/addon/foxyproxy-standard/). [Elama](https://elama.ru/) прошли по UK ВУ; пополнение ~10k ₽ конвертируется в ~$90.
>
> **Решение:** Elama — ядро связки; трекинг установок — через цели на welcome page ([урок Monetize](https://monetize.software/ru/publisher/lessons/e416d0cd-fef5-4fd4-a1a7-6de8cc2dc3c6)).
>
> - [ ] Полезно
>
> → [Читать в Telegram](https://t.me/c/2210731208/16231)
```

Текст **перефразирован** — не копия экспорта. Контекст плотный (не повтор тизера).

---

## Alumni overflow (тем > ~20)

```markdown
### Ещё темы Alumni

- Верификация телефона Google (3 поста) — [пост](https://t.me/c/2210731208/16250)
- Локализация _locales для CWS (2 поста) — [пост](https://t.me/c/2210731208/16280)

_Есть ещё 4 мелких тем, не вошедших в список._
```

По запросу пользователя — развернуть любую тему в полный 3-слойный блок (**только Alumni**).

---

## Tier 2 / other — канал с overflow

```markdown
### Антонов такой Антонов · 4

**Антонов** — [пост](https://t.me/auantonov/1234): Краткий синтез мысли автора в одном предложении.
- [ ] Почитать в телеграмме

> [!abstract]- Подробнее
> **Проблема:** …
>
> **Контекст:** … (плотный абзац: факты, цифры, сравнение; не одно предложение-повтор тизера)
>
> **Решение:** …
>
> - [ ] Полезно
>
> → [Читать в Telegram](https://t.me/auantonov/1234)

… до 5 полных тем …

### Ещё темы

- Одно предложение сути — [пост](https://t.me/auantonov/1240)
- Ещё одна короткая суть — [пост](https://t.me/auantonov/1241)

_Ещё 3 не вошло в подборку._
```

Expand-on-request для этих строк **нет**.

---

## Sample JSON shapes (`_build/dd_mm_yyyy/`)

### other_batch_01.json (фрагмент)

```json
{
  "channels": [
    {
      "name": "Example News Channel",
      "short_name": "Example News",
      "topics": [
        {
          "teaser": "Короткий синтез анонса API-лимита.",
          "url": "https://t.me/example_news/42",
          "problem": "Клиент теряет батчи на новом rate limit.",
          "context": "В анонсе новые квоты на минуту и сутки. Автор сравнивает naive sleep и backoff с jitter. Есть ссылка на changelog и пример очереди.",
          "solution": "Ввести backoff с jitter, уменьшить батч, логировать 429 отдельно."
        }
      ],
      "more_topics": [
        {"summary": "Заметка про миграцию вебхуков", "url": "https://t.me/example_news/43"}
      ],
      "omitted_count": 1
    }
  ]
}
```

### alumni more_topics (фрагмент)

```json
{
  "theme": "Keyword research tooling",
  "post_count": 3,
  "url": "https://t.me/c/2210731208/16250"
}
```

---

## Same-day append

```markdown
## Дополнение · 18:45
…
```
