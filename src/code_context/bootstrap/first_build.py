import ast
import hashlib
import json
from pathlib import Path

from code_context.bootstrap.staging import SnapshotPublisher
from code_context.validators.schema_validator import ValidationError


class BootstrapService:
    def __init__(self, repository):
        self.repository = repository

    def build(self, source_root, source_revision, config_version, scope, exclude=(), expected_parent=None):
        if not source_revision:
            raise ValidationError("SOURCE_REVISION_REQUIRED", "source revision is required")
        if not scope:
            raise ValidationError("SOURCE_SCOPE_REQUIRED", "source scope is required")
        source_root = Path(source_root)
        files = self._scoped_files(source_root, scope, exclude)
        manifest_id = self.repository.add_manifest(
            str(source_root), source_revision, {"include": list(scope)},
            {"exclude": list(exclude)}, "python-ast-1", config_version,
        )
        snapshot_id = self.repository.create_snapshot(
            source_revision, f"bootstrap-{source_revision}", config_version, "staging"
        )
        for file_path in files:
            self.repository.add_task_run(
                f"{snapshot_id}:{file_path.relative_to(source_root).as_posix()}",
                snapshot_id,
                file_path.relative_to(source_root).as_posix(),
                source_revision,
                "running",
            )
        artifacts = []
        for file_path in files:
            artifacts.extend(self._extract_file(source_root, file_path))
        if not artifacts:
            return self._reject(snapshot_id, "COVERAGE_GATE_FAILED", {"scope": list(scope)})
        seen = set()
        for artifact in artifacts:
            if artifact["canonical_key"] in seen:
                return self._reject(snapshot_id, "ARTIFACT_CONFLICT", artifact)
            seen.add(artifact["canonical_key"])
            evidence_id = self.repository.add_evidence(
                source_revision,
                f"bootstrap-{source_revision}",
                config_version,
                artifact["file_path"],
                artifact["start_line"],
                artifact["end_line"],
                artifact["content_hash"],
            )
            artifact["payload"]["evidence_id"] = evidence_id
            self.repository.add_artifact(
                snapshot_id, artifact["canonical_key"], artifact["kind"],
                artifact["content_hash"], evidence_id, artifact["payload"],
            )
            self.repository.add_node(
                snapshot_id, "Behavior", artifact["kind"], source_revision,
                f"bootstrap-{source_revision}", config_version, artifact["payload"],
            )
        active_snapshot_id = self.repository.get_active_snapshot_id()
        if active_snapshot_id != expected_parent:
            return self._reject(
                snapshot_id, "PUBLISH_PARENT_MISMATCH",
                {"expected_parent": expected_parent, "active_snapshot": active_snapshot_id},
            )
        SnapshotPublisher(self.repository).publish(snapshot_id)
        self.repository.complete_tasks(snapshot_id)
        return {
            "ok": True,
            "status": "published",
            "snapshot_id": snapshot_id,
            "manifest_id": manifest_id,
            "node_count": len(artifacts),
        }

    def _reject(self, snapshot_id, code, detail):
        self.repository.add_conflict(snapshot_id, code, detail)
        return {"ok": False, "status": "staging", "code": code, "snapshot_id": snapshot_id}

    def _scoped_files(self, source_root, scope, exclude):
        if not source_root.is_dir():
            return []
        include = tuple(
            "" if Path(item).as_posix() == "." else Path(item).as_posix().strip("/")
            for item in scope
        )
        excluded = tuple(Path(item).as_posix().strip("/") for item in exclude)
        files = []
        for file_path in source_root.rglob("*.py"):
            relative = file_path.relative_to(source_root).as_posix()
            if not any(not item or relative == item or relative.startswith(f"{item}/") for item in include):
                continue
            if any(relative == item or relative.startswith(f"{item}/") for item in excluded):
                continue
            files.append(file_path)
        return sorted(files)

    def _extract_file(self, source_root, file_path):
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
        relative = file_path.relative_to(source_root).as_posix()
        module_name = relative[:-3].replace("/", ".")
        artifacts = [self._artifact(relative, module_name, "module", tree, source)]
        visitor = _ArtifactVisitor(relative, module_name, source)
        visitor.visit(tree)
        return artifacts + visitor.artifacts

    def _artifact(self, relative, qualified_name, kind, node, source):
        content = ast.get_source_segment(source, node) or source
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return {
            "canonical_key": f"{relative}:{qualified_name}:{kind}",
            "kind": kind,
            "file_path": relative,
            "start_line": getattr(node, "lineno", 1),
            "end_line": getattr(node, "end_lineno", source.count("\n") + 1),
            "content_hash": content_hash,
            "payload": {"name": qualified_name.rsplit(".", 1)[-1], "qualified_name": qualified_name, "file_path": relative, "content_hash": content_hash},
        }


class _ArtifactVisitor(ast.NodeVisitor):
    def __init__(self, relative, module_name, source):
        self.relative = relative
        self.names = [module_name]
        self.source = source
        self.artifacts = []

    def visit_ClassDef(self, node):
        self._visit_named(node, "class")

    def visit_FunctionDef(self, node):
        self._visit_named(node, "function")

    def visit_AsyncFunctionDef(self, node):
        self._visit_named(node, "function")

    def _visit_named(self, node, kind):
        self.names.append(node.name)
        qualified_name = ".".join(self.names)
        content = ast.get_source_segment(self.source, node) or ""
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self.artifacts.append({
            "canonical_key": f"{self.relative}:{qualified_name}:{kind}",
            "kind": kind,
            "file_path": self.relative,
            "start_line": node.lineno,
            "end_line": node.end_lineno,
            "content_hash": content_hash,
            "payload": {"name": node.name, "qualified_name": qualified_name, "file_path": self.relative, "content_hash": content_hash},
        })
        self.generic_visit(node)
        self.names.pop()
