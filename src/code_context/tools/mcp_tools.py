import argparse
import json

from code_context.storage.schema import Database
from code_context.tools.registry import ToolRegistry


def run(command, database_path):
    db = Database(database_path)
    try:
        db.migrate()
        registry = ToolRegistry()
        if command == "init":
            registry.register_all(db.connection)
            return {"ok": True, "command": "init", "status": "initialized"}
        if command == "migrate":
            return {"ok": True, "command": "migrate", "status": "migrated"}
        if command == "doctor":
            required = {"schema_migrations", "snapshots", "nodes", "edges", "evidence", "tool_registry"}
            actual = {
                row[0]
                for row in db.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            missing_tables = sorted(required - actual)
            if missing_tables:
                return {"ok": False, "code": "SCHEMA_MISSING", "missing": missing_tables}
            result = registry.diagnose_all(db.connection)
            if not result["ok"]:
                return result
            return {"ok": True, "status": "healthy"}
        return {"ok": False, "code": "UNKNOWN_COMMAND", "command": command}
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="code-context")
    parser.add_argument("command", choices=("init", "migrate", "doctor"))
    parser.add_argument("--database", default=".code-context/context.db")
    args = parser.parse_args(argv)
    result = run(args.command, args.database)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
