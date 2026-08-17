import sqlite3
from pathlib import Path


class Database:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")

    @property
    def connection(self):
        return self._connection

    def migrate(self):
        migration_path = Path(__file__).parents[3] / "migrations" / "001_initial.sql"
        with self._connection:
            self._connection.executescript(migration_path.read_text(encoding="utf-8"))
            self._connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version) VALUES (1)"
            )

    def close(self):
        self._connection.close()
