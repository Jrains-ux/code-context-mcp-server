import argparse
import json
from pathlib import Path

from code_context.storage.repository import InitializationRepository
from code_context.storage.schema import Database
from code_context.tools.registry import ToolRegistry


def default_manifest(
    database_path,
    project="local",
    workspace=None,
    source_revision="unversioned",
    config_version="1",
):
    matrix = ToolRegistry().matrix
    return {
        "project": project,
        "workspace": workspace or str(Path(database_path).parent),
        "source_revision": source_revision,
        "config_version": config_version,
        "skills": {skill: sorted(matrix.allowed(skill)) for skill in matrix._matrix},
    }


def validate_manifest(manifest, matrix):
    required = ("project", "workspace", "source_revision", "config_version", "skills")
    if not isinstance(manifest, dict) or any(not manifest.get(field) for field in required):
        return {"ok": False, "code": "SKILL_MANIFEST_INVALID"}
    if not isinstance(manifest["skills"], dict):
        return {"ok": False, "code": "SKILL_MANIFEST_INVALID"}
    for skill, tools in manifest["skills"].items():
        if skill not in matrix._matrix or not isinstance(tools, list):
            return {"ok": False, "code": "SKILL_MANIFEST_INVALID"}
        if not set(tools) <= matrix.allowed(skill):
            return {"ok": False, "code": "SKILL_MANIFEST_INVALID"}
    return {"ok": True}


def health_result(connection, registry):
    required = {
        "schema_migrations",
        "snapshots",
        "nodes",
        "edges",
        "evidence",
        "tool_registry",
        "initialization_manifest",
        "manifest_tool_permissions",
    }
    actual = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    schema_ok = required <= actual
    manifest = InitializationRepository(connection).get_manifest() if schema_ok else None
    manifest_ok = validate_manifest(manifest, registry.matrix)["ok"] if manifest else False
    registry_result = (
        registry.diagnose_manifest(connection, manifest["skills"])
        if manifest_ok
        else {"ok": False, "code": "SKILL_MANIFEST_INVALID"}
    )
    active = connection.execute(
        "SELECT snapshots.status FROM active_snapshot "
        "JOIN snapshots ON snapshots.snapshot_id=active_snapshot.snapshot_id "
        "WHERE active_snapshot.singleton=1"
    ).fetchone()
    store_ok = active is not None and active[0] == "published"
    runtime_ready = schema_ok and manifest_ok and registry_result["ok"] and store_ok
    checks = {
        "schema": schema_ok,
        "manifest": manifest_ok,
        "registry": registry_result["ok"],
        "store": store_ok,
    }
    if runtime_ready:
        return {"ok": True, "status": "healthy", "runtime_ready": True, "checks": checks}
    if not schema_ok:
        code = "SCHEMA_MISSING"
    elif not manifest_ok:
        code = "SKILL_MANIFEST_INVALID"
    elif not registry_result["ok"]:
        code = registry_result["code"]
    else:
        code = "SERVICE_NOT_READY"
    return {
        "ok": False,
        "status": "not_ready",
        "code": code,
        "runtime_ready": False,
        "checks": checks,
    }


def run(command, database_path, manifest=None):
    db = Database(database_path)
    try:
        db.migrate()
        registry = ToolRegistry()
        if command == "init":
            manifest = manifest or default_manifest(database_path)
            validation = validate_manifest(manifest, registry.matrix)
            if not validation["ok"]:
                return validation
            InitializationRepository(db.connection).save_manifest(manifest)
            registry.register_all(db.connection, manifest["skills"])
            return {"ok": True, "command": "init", "status": "initialized", "manifest": manifest}
        if command == "migrate":
            return {"ok": True, "command": "migrate", "status": "migrated"}
        if command == "doctor":
            return health_result(db.connection, registry)
        if command == "health":
            return health_result(db.connection, registry)
        return {"ok": False, "code": "UNKNOWN_COMMAND", "command": command}
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="code-context")
    parser.add_argument("command", choices=("init", "migrate", "doctor", "health"))
    parser.add_argument("--database", default=".code-context/context.db")
    parser.add_argument("--project", default="local")
    parser.add_argument("--workspace")
    parser.add_argument("--source-revision", default="unversioned")
    parser.add_argument("--config-version", default="1")
    args = parser.parse_args(argv)
    manifest = None
    if args.command == "init":
        manifest = default_manifest(
            args.database,
            project=args.project,
            workspace=args.workspace,
            source_revision=args.source_revision,
            config_version=args.config_version,
        )
    result = run(args.command, args.database, manifest=manifest)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
