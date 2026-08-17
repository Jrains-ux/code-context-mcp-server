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
        migration_root = Path(__file__).parents[3] / "migrations"
        with self._connection:
            for migration_path in sorted(migration_root.glob("[0-9][0-9][0-9]_*.sql")):
                version = int(migration_path.name.split("_", 1)[0])
                migration_table = self._connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
                ).fetchone()
                applied = None if migration_table is None else self._connection.execute(
                    "SELECT 1 FROM schema_migrations WHERE version=?", (version,)
                ).fetchone()
                if applied is not None:
                    continue
                self._connection.executescript(migration_path.read_text(encoding="utf-8"))
                self._connection.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))

    def close(self):
        self._connection.close()
