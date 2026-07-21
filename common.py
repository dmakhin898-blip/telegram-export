"""Shared config and helpers for telegram-export scripts."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml
from telethon import TelegramClient
from telethon.tl.types import Channel

PROJECT_DIR = Path(__file__).resolve().parent
SESSION_NAME = "telegram_export"
STATE_FILENAME = ".export_state.json"
LOCK_FILENAME = ".export_in_progress"
MANIFEST_FILENAME = ".export_run.json"
LOCK_TTL = timedelta(minutes=120)


def load_env() -> None:
    env_path = PROJECT_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def get_api_credentials() -> tuple[int, str]:
    load_env()
    api_id = os.environ.get("API_ID")
    api_hash = os.environ.get("API_HASH")
    if not api_id or not api_hash:
        raise SystemExit(
            "Missing API_ID or API_HASH. Copy .env.example to .env and fill credentials."
        )
    return int(api_id), api_hash


def project_root() -> Path:
    return PROJECT_DIR


def export_lock_path() -> Path:
    return PROJECT_DIR / LOCK_FILENAME


def export_manifest_path() -> Path:
    return PROJECT_DIR / MANIFEST_FILENAME


def make_run_id(started_at: datetime) -> str:
    return started_at.replace(microsecond=0).isoformat()


def is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def read_export_lock() -> dict[str, Any] | None:
    path = export_lock_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def is_export_lock_stale(lock: dict[str, Any]) -> bool:
    pid = lock.get("pid")
    if pid is not None and not is_process_alive(int(pid)):
        return True
    started_at_raw = lock.get("started_at")
    if not started_at_raw:
        return True
    started_at = datetime.fromisoformat(str(started_at_raw).replace("Z", "+00:00"))
    return datetime.now(timezone.utc) - started_at.astimezone(timezone.utc) > LOCK_TTL


def remove_export_lock() -> None:
    path = export_lock_path()
    if path.exists():
        path.unlink()


def acquire_export_lock(started_at: datetime) -> None:
    existing = read_export_lock()
    if existing:
        if is_export_lock_stale(existing):
            remove_export_lock()
        else:
            raise SystemExit(
                "Export already in progress "
                f"(pid={existing.get('pid')}, started_at={existing.get('started_at')}). "
                "Wait for it to finish."
            )
    lock = {"pid": os.getpid(), "started_at": make_run_id(started_at)}
    export_lock_path().write_text(
        json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def release_export_lock() -> None:
    remove_export_lock()


def read_export_manifest() -> dict[str, Any] | None:
    path = export_manifest_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_export_manifest(
    *,
    run_id: str,
    status: str,
    started_at: datetime,
    finished_at: datetime,
    inbox_dir: Path,
    channels_ok: int,
    channels_failed: int,
    messages_appended: int,
    failed_channels: list[dict[str, str]],
) -> None:
    digest_allowed = status in ("complete", "complete_with_errors")
    manifest = {
        "run_id": run_id,
        "status": status,
        "started_at": make_run_id(started_at),
        "finished_at": make_run_id(finished_at),
        "digest_allowed": digest_allowed,
        "inbox_dir": str(inbox_dir),
        "channels_ok": channels_ok,
        "channels_failed": channels_failed,
        "messages_appended": messages_appended,
        "failed_channels": failed_channels,
    }
    export_manifest_path().write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def get_inbox_dir() -> Path:
    load_env()
    raw = (os.environ.get("INBOX_DIR") or "").strip()
    if not raw:
        raise SystemExit(
            "Missing INBOX_DIR. Copy .env.example to .env and set INBOX_DIR "
            "to your inbox directory path."
        )
    return Path(raw).expanduser().resolve()


def get_client() -> TelegramClient:
    api_id, api_hash = get_api_credentials()
    return TelegramClient(str(PROJECT_DIR / SESSION_NAME), api_id, api_hash)


def channels_config_path() -> Path:
    path = PROJECT_DIR / "channels.yaml"
    if not path.exists():
        raise SystemExit(
            "channels.yaml not found. Copy channels.example.yaml to channels.yaml "
            "and fill channel ids after running list_dialogs.py."
        )
    return path


def load_channel_tiers() -> list[tuple[str, str, object]]:
    """Return (tier_name, backfill_mode, channel_ref) for each configured channel."""
    data = yaml.safe_load(channels_config_path().read_text(encoding="utf-8"))
    tiers = data.get("tiers") or {}
    result: list[tuple[str, str, object]] = []
    for tier_name, tier_cfg in tiers.items():
        backfill = tier_cfg.get("backfill", "2weeks")
        for channel_ref in tier_cfg.get("channels") or []:
            result.append((tier_name, backfill, channel_ref))
    return result


def slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug or "unknown"


def state_path(inbox_dir: Path | None = None) -> Path:
    return (inbox_dir or get_inbox_dir()) / STATE_FILENAME


def load_state(inbox_dir: Path | None = None) -> dict[str, dict[str, str]]:
    path = state_path(inbox_dir)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(state: dict[str, dict[str, str]], inbox_dir: Path | None = None) -> None:
    path = state_path(inbox_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def channel_state_key(channel_id: int) -> str:
    return str(channel_id)


def parse_backfill_min_date(backfill: str, last_export_at: datetime | None) -> datetime | None:
    if last_export_at is not None:
        return last_export_at
    if backfill == "full":
        return None
    if backfill in ("2weeks", "14days"):
        return datetime.now(timezone.utc) - timedelta(days=14)
    raise ValueError(f"Unknown backfill mode: {backfill}")


def message_link(channel_id: int, message_id: int) -> str:
    internal_id = str(channel_id).replace("-100", "", 1)
    return f"https://t.me/c/{internal_id}/{message_id}"


def media_type_label(message) -> str:
    if message.photo:
        return "photo"
    if message.video:
        return "video"
    if message.document:
        return "document"
    if message.audio:
        return "audio"
    if message.voice:
        return "voice"
    if message.sticker:
        return "sticker"
    if message.poll:
        return "poll"
    return "media"


def format_message_block(channel_key: str, message) -> str:
    ts = message.date.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = f"## {ts} | {channel_key} | msg:{message.id}"
    if message.message:
        body = message.message.strip()
    else:
        label = media_type_label(message)
        link = message_link(message.chat_id, message.id)
        body = f"[media: {label}] {link}"
    return f"{header}\n\n{body}\n\n---\n"


def month_key(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m")


def normalize_channel_ref(channel_ref: object) -> int | str:
    """Convert list_dialogs ids or common YAML mistakes to Telethon entity refs."""
    if isinstance(channel_ref, str):
        cleaned = channel_ref.strip().strip('"').strip("'")
        if cleaned.startswith("-") and cleaned[1:].startswith("@"):
            cleaned = cleaned[1:]
        if cleaned.startswith("@"):
            return cleaned
        if cleaned.lstrip("-").isdigit():
            channel_ref = int(cleaned)
        elif cleaned:
            return f"@{cleaned.lstrip('-')}"
        else:
            raise ValueError(f"Empty channel reference: {channel_ref!r}")

    if isinstance(channel_ref, int):
        ref_str = str(channel_ref)
        if ref_str.startswith("-100"):
            return channel_ref
        if channel_ref < 0:
            return int(f"-100{ref_str[1:]}")
        return int(f"-100{channel_ref}")

    return channel_ref


async def resolve_channel(client: TelegramClient, channel_ref: object) -> Channel:
    normalized = normalize_channel_ref(channel_ref)
    entity = await client.get_entity(normalized)
    if not isinstance(entity, Channel):
        raise ValueError(f"{channel_ref!r} is not a channel")
    return entity
