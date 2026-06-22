import sqlite3

from telethon.sessions import SQLiteSession

_BUSY_TIMEOUT_MS = 30_000


class ResilientSQLiteSession(SQLiteSession):
    """SQLite session with busy_timeout to avoid 'database is locked' on shutdown."""

    def _cursor(self):
        if self._conn is None:
            self._conn = sqlite3.connect(
                self.filename,
                check_same_thread=False,
                timeout=_BUSY_TIMEOUT_MS / 1000,
            )
            self._conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
        return self._conn.cursor()
