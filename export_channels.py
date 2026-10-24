#!/usr/bin/env python3
"""Export configured Telegram channels to Obsidian monthly markdown files."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from telethon.errors import (
    AuthKeyError,
    FloodWaitError,
    SessionPasswordNeededError,
    UnauthorizedError,
    UserDeactivatedBanError,
    UserDeactivatedError,
)

from common import (
    acquire_export_lock,
    channel_state_key,
    format_message_block,
    get_client,
    get_inbox_dir,
    heading_channel_key,
    load_channel_tiers,
    load_state,
    make_run_id,
    month_key,
    normalize_channel_ref,
    parse_backfill_min_date,
    parse_export_heading,
    public_username,
    release_export_lock,
    resolve_channel,
    save_state,
    slugify,
    write_export_manifest,
)

_AUTH_ERRORS = (
    AuthKeyError,
    UnauthorizedError,
    UserDeactivatedBanError,
    UserDeactivatedError,
    SessionPasswordNeededError,
)


async def export_channel(
    client,
    tier_name: str,
    backfill: str,
    channel_ref: object,
    inbox_dir,
    state: dict[str, dict[str, str]],
) -> int:
    entity = await resolve_channel(client, channel_ref)
    key = channel_state_key(entity.id)
    slug = slugify(entity.title)
    channel_key = heading_channel_key(slug, key, getattr(entity, "username", None))

    last_export_raw = (state.get(key) or {}).get("last_export_at")
    last_export_at = (
        datetime.fromisoformat(last_export_raw.replace("Z", "+00:00"))
        if last_export_raw
        else None
    )
    min_date = parse_backfill_min_date(backfill, last_export_at)

    print(f"Exporting {entity.title} [{tier_name}, backfill={backfill}]...")
    blocks_by_month: dict[str, list[str]] = defaultdict(list)
    count = 0

    async for message in client.iter_messages(entity, reverse=True):
        msg_dt = message.date.astimezone(timezone.utc)
        if min_date and msg_dt <= min_date.astimezone(timezone.utc):
            continue
        blocks_by_month[month_key(msg_dt)].append(
            format_message_block(channel_key, message)
        )
        count += 1

    if count == 0:
        print(f"  No new messages for {entity.title}")
        return 0

    channel_dir = inbox_dir / slug
    channel_dir.mkdir(parents=True, exist_ok=True)
    for month, blocks in sorted(blocks_by_month.items()):
        out_path = channel_dir / f"{month}.md"
        with out_path.open("a", encoding="utf-8") as fh:
            fh.writelines(blocks)
        print(f"  Appended {len(blocks)} messages to {out_path}")

    state[key] = {
        "last_export_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    }
    print(f"  Exported {count} messages")
    return count


def _export_markdown_files(inbox: Path) -> list[Path]:
    if not inbox.is_dir():
        return []
    digests = inbox / "digests"
    files: list[Path] = []
    for path in sorted(inbox.rglob("*.md")):
        if not path.is_file():
            continue
        if _is_under(digests, path):
            continue
        files.append(path)
    return files


def _is_under(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _bare_channel_ids(path: Path) -> set[str]:
    found: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        heading = parse_export_heading(line)
        if heading is None or heading.username or not heading.channel_id.isdigit():
            continue
        found.add(heading.channel_id)
    return found


def _split_line_ending(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    if line.endswith("\r"):
        return line[:-1], "\r"
    return line, ""


def _rewrite_heading_line(line: str, username_by_id: dict[str, str]) -> str:
    body, ending = _split_line_ending(line)
    heading = parse_export_heading(body)
    if heading is None or heading.username:
        return line
    username = username_by_id.get(heading.channel_id)
    if not username:
        return line
    old_key = heading_channel_key(heading.slug, heading.channel_id, None)
    new_key = heading_channel_key(heading.slug, heading.channel_id, username)
    if old_key not in body:
        return line
    return body.replace(old_key, new_key, 1) + ending


def _rewrite_export_file(path: Path, username_by_id: dict[str, str]) -> int:
    original = path.read_text(encoding="utf-8")
    changed = 0
    lines: list[str] = []
    for line in original.splitlines(keepends=True):
        rewritten = _rewrite_heading_line(line, username_by_id)
        if rewritten != line:
            changed += 1
        lines.append(rewritten)
    if changed == 0:
        return 0
    tmp = path.with_name(path.name + ".stamp-tmp")
    tmp.write_text("".join(lines), encoding="utf-8")
    try:
        tmp.replace(path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return changed


async def _username_for_channel(client, channel_id: str) -> str | None:
    ref = normalize_channel_ref(int(channel_id))
    try:
        entity = await client.get_entity(ref)
    except FloodWaitError as exc:
        await asyncio.sleep(int(exc.seconds) + 1)
        entity = await client.get_entity(ref)
    return public_username(getattr(entity, "username", None))


async def stamp_export_usernames(inbox_dir, client) -> int:
    """Add `@username` to public export headings. Do not append posts or touch state."""
    inbox = Path(inbox_dir)
    files = _export_markdown_files(inbox)
    bare_ids: set[str] = set()
    for path in files:
        bare_ids.update(_bare_channel_ids(path))

    username_by_id: dict[str, str] = {}
    no_username = 0
    resolve_errors = 0
    for channel_id in sorted(bare_ids, key=int):
        try:
            username = await _username_for_channel(client, channel_id)
        except _AUTH_ERRORS:
            raise
        except Exception as exc:
            resolve_errors += 1
            print(f"ERROR resolving {channel_id}: {type(exc).__name__}: {exc}")
            continue
        if username:
            username_by_id[channel_id] = username
        else:
            no_username += 1

    rewritten = 0
    for path in files:
        rewritten += _rewrite_export_file(path, username_by_id)
    print(
        f"Public usernames: {len(username_by_id)}. "
        f"No public username: {no_username}. "
        f"Resolve errors: {resolve_errors}. "
        f"Headings rewritten: {rewritten}."
    )
    return rewritten


async def run_export() -> None:
    started_at = datetime.now(timezone.utc).replace(microsecond=0)
    run_id = make_run_id(started_at)
    inbox_dir = get_inbox_dir()
    inbox_dir.mkdir(parents=True, exist_ok=True)

    acquire_export_lock(started_at)

    channels_ok = 0
    channels_failed = 0
    messages_appended = 0
    failed_channels: list[dict[str, str]] = []
    status = "failed"
    loop_completed = False

    try:
        state = load_state(inbox_dir)
        tiers = load_channel_tiers()
        if not tiers:
            raise SystemExit("No channels configured in channels.yaml")

        client = get_client()
        async with client:
            for tier_name, backfill, channel_ref in tiers:
                try:
                    count = await export_channel(
                        client, tier_name, backfill, channel_ref, inbox_dir, state
                    )
                    save_state(state, inbox_dir)
                    channels_ok += 1
                    messages_appended += count
                except Exception as exc:
                    channels_failed += 1
                    failed_channels.append(
                        {"ref": str(channel_ref), "error": str(exc)}
                    )
                    print(f"ERROR exporting {channel_ref!r}: {exc}")

        loop_completed = True
        status = "complete" if channels_failed == 0 else "complete_with_errors"
    finally:
        finished_at = datetime.now(timezone.utc).replace(microsecond=0)
        if not loop_completed:
            status = "failed"
        write_export_manifest(
            run_id=run_id,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            inbox_dir=inbox_dir,
            channels_ok=channels_ok,
            channels_failed=channels_failed,
            messages_appended=messages_appended,
            failed_channels=failed_channels,
        )
        release_export_lock()
        print(f"Export run complete (status={status}).")


async def main() -> None:
    await run_export()


if __name__ == "__main__":
    asyncio.run(main())
