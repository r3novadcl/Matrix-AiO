"""
Shared in-memory cached JSON config store.

Every antinuke/automod check used to open, read, and json.load() the ENTIRE
config file from disk on every single Discord event (channel create, role
delete, message sent, ...). That synchronous disk I/O on the hot path was
the real cause of "slow" antinuke/automod reactions.

FastConfig loads the file into memory once, serves get()/set() from memory
(instant, no I/O on the hot path), and writes changes to disk in the
background so nothing is ever blocked waiting on a file write.
"""

import json
import os
import asyncio


def _safe_write_json(filepath: str, data: dict):
    dirname = os.path.dirname(filepath)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    tmp = f"{filepath}.tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, filepath)
    except OSError:
        pass


class FastConfig:
    def __init__(self, filepath: str, default_factory):
        self.filepath = filepath
        self.default_factory = default_factory
        self._data = self._load_from_disk()
        self._save_pending = False

    def _load_from_disk(self) -> dict:
        if not os.path.exists(self.filepath):
            return {}
        try:
            with open(self.filepath) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def get(self, guild_id) -> dict:
        gid = str(guild_id)
        if gid not in self._data:
            self._data[gid] = self.default_factory()
            self._schedule_save()
        return self._data[gid]

    def set(self, guild_id, cfg: dict):
        self._data[str(guild_id)] = cfg
        self._schedule_save()

    def _schedule_save(self):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            self._save_sync()
            return
        if loop.is_running():
            loop.create_task(self._save_async())
        else:
            self._save_sync()

    async def _save_async(self):
        await asyncio.get_event_loop().run_in_executor(None, self._save_sync)

    def _save_sync(self):
        _safe_write_json(self.filepath, self._data)


class CachedFile:
    """
    Drop-in replacement for the old whole-file `load_x()` / `save_x(d)`
    pattern used across the cogs. `load()` always returns the SAME
    in-memory dict (no disk read after the first call), and `save(d)`
    just triggers a non-blocking background write — so every cog that
    does `data = load_x(); data[...] = ...; save_x(data)` keeps working
    exactly as before, it's just no longer doing disk I/O on every call.
    """
    def __init__(self, filepath: str, default=dict):
        self.filepath = filepath
        self._data = self._load_from_disk(default)

    def _load_from_disk(self, default):
        if not os.path.exists(self.filepath):
            return default()
        try:
            with open(self.filepath) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return default()

    def load(self) -> dict:
        return self._data

    def save(self, data: dict = None):
        if data is not None:
            self._data = data
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            self._save_sync()
            return
        if loop.is_running():
            loop.create_task(self._save_async())
        else:
            self._save_sync()

    async def _save_async(self):
        await asyncio.get_event_loop().run_in_executor(None, self._save_sync)

    def _save_sync(self):
        _safe_write_json(self.filepath, self._data)
