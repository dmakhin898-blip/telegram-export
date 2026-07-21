#!/usr/bin/env python3
"""List Telegram channel dialogs with names and ids for channels.yaml setup."""

from __future__ import annotations

import asyncio

from telethon.tl.types import Channel

from common import get_client


async def main() -> None:
    client = get_client()
    async with client:
        print("Channel dialogs (copy ids into channels.yaml):\n")
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            if not isinstance(entity, Channel):
                continue
            peer_id = int(f"-100{entity.id}")
            username = f" @{entity.username}" if entity.username else ""
            print(f"{dialog.name}{username}\t{peer_id}")


if __name__ == "__main__":
    asyncio.run(main())
