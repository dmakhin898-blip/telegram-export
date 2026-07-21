#!/usr/bin/env python3
"""Export configured Telegram channels to Obsidian monthly markdown files."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone

from common import (
    acquire_export_lock,
    channel_state_key,
    format_message_block,
    get_client,
    get_inbox_dir,
    load_channel_tiers,
    load_state,
    make_run_id,
    month_key,
    parse_backfill_min_date,
    release_export_lock,
    resolve_channel,
    save_state,
    slugify,
    write_export_manifest,
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
    channel_key = f"{slugify(entity.title)} ({key})"
    slug = slugify(entity.title)

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
