import argparse
import json
from pathlib import Path

from code_context.bootstrap.first_build import BootstrapService
from code_context.consumer import DistributionService
from code_context.consumer import EvaluationService
from code_context.consumer import KnowledgeService
from code_context.query import TechnicalQueryService
from code_context.sync import SyncService
from code_context.storage.repository import InitializationRepository
from code_context.storage.repository import SnapshotRepository
from code_context.storage.schema import Database
from code_context.tools.registry import ToolRegistry
from code_context.validators.schema_validator import ValidationError


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


def run(command, database_path, manifest=None, source_root=None, scope=(), exclude=(), expected_parent=None, query=None, limit=20, node_ids=(), depth=1, node_budget=100, edge_budget=100, operation_id=None, baseline_ref=None, target_source_revision=None, dataset_id=None, golden_set_version=None, samples=(), minimum_samples=1, tool_versions=None, document_kind=None, document_scope=None, template_version=None, generator_version=None, manifest_id=None, target=None, idempotency_key=None):
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
        if command == "bootstrap":
            if InitializationRepository(db.connection).get_manifest() is None:
                return {"ok": False, "code": "SERVICE_NOT_READY"}
            try:
                return BootstrapService(SnapshotRepository(db.connection)).build(
                    source_root, manifest["source_revision"], manifest["config_version"], scope,
                    exclude=exclude, expected_parent=expected_parent,
                )
            except ValidationError as error:
                return {"ok": False, "code": error.code}
        if command in ("search", "expand"):
            service = TechnicalQueryService(db.connection)
            try:
                if command == "search":
                    return service.search(query, limit)
                return service.expand(node_ids, depth, node_budget, edge_budget)
            except ValidationError as error:
                return {"ok": False, "code": error.code}
        if command == "sync":
            try:
                return SyncService(SnapshotRepository(db.connection)).update(operation_id or "default", baseline_ref, source_root, target_source_revision or "", manifest["config_version"] if manifest else "1", scope)
            except ValidationError as error:
                return {"ok": False, "code": error.code}
        if command == "evaluate":
            try:
                return EvaluationService(db.connection).evaluate(dataset_id, golden_set_version, samples, tool_versions, minimum_samples)
            except ValidationError as error:
                return {"ok": False, "code": error.code}
        if command == "knowledge-generate":
            try:
                return KnowledgeService(db.connection).generate(document_kind, document_scope, template_version, generator_version)
            except ValidationError as error:
                return {"ok": False, "code": error.code}
        if command == "knowledge-push":
            try:
                return DistributionService(db.connection).push(manifest_id, target, idempotency_key)
            except ValidationError as error:
                return {"ok": False, "code": error.code}
        return {"ok": False, "code": "UNKNOWN_COMMAND", "command": command}
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="code-context")
    parser.add_argument("command", choices=("init", "migrate", "doctor", "health", "bootstrap", "search", "expand", "sync", "evaluate", "knowledge-generate", "knowledge-push"))
    parser.add_argument("--database", default=".code-context/context.db")
    parser.add_argument("--project", default="local")
    parser.add_argument("--workspace")
    parser.add_argument("--source-revision", default="unversioned")
    parser.add_argument("--config-version", default="1")
    parser.add_argument("--source-root")
    parser.add_argument("--scope", action="append", default=[])
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--expected-parent", type=int)
    parser.add_argument("--query")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--node-id", action="append", default=[], type=int)
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--node-budget", type=int, default=100)
    parser.add_argument("--edge-budget", type=int, default=100)
    parser.add_argument("--operation-id")
    parser.add_argument("--baseline-ref", type=int)
    parser.add_argument("--target-source-revision")
    parser.add_argument("--dataset-id")
    parser.add_argument("--golden-set-version")
    parser.add_argument("--samples-json", default="[]")
    parser.add_argument("--minimum-samples", type=int, default=1)
    parser.add_argument("--tool-versions-json", default="{}")
    parser.add_argument("--document-kind")
    parser.add_argument("--document-scope")
    parser.add_argument("--template-version")
    parser.add_argument("--generator-version")
    parser.add_argument("--manifest-id")
    parser.add_argument("--target")
    parser.add_argument("--idempotency-key")
    args = parser.parse_args(argv)
    manifest = None
    if args.command in ("init", "bootstrap"):
        manifest = default_manifest(
            args.database,
            project=args.project,
            workspace=args.workspace,
            source_revision=args.source_revision,
            config_version=args.config_version,
        )
    result = run(
        args.command, args.database, manifest=manifest, source_root=args.source_root,
        scope=args.scope, exclude=args.exclude, expected_parent=args.expected_parent,
        query=args.query, limit=args.limit, node_ids=args.node_id, depth=args.depth,
        node_budget=args.node_budget, edge_budget=args.edge_budget,
        operation_id=args.operation_id, baseline_ref=args.baseline_ref, target_source_revision=args.target_source_revision,
        dataset_id=args.dataset_id, golden_set_version=args.golden_set_version,
        samples=json.loads(args.samples_json), minimum_samples=args.minimum_samples,
        tool_versions=json.loads(args.tool_versions_json), document_kind=args.document_kind,
        document_scope=args.document_scope, template_version=args.template_version,
        generator_version=args.generator_version, manifest_id=args.manifest_id,
        target=args.target, idempotency_key=args.idempotency_key,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
