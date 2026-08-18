import hashlib
import json
import time
import uuid

from code_context.query import TechnicalQueryService
from code_context.business import BusinessRouter
from code_context.validators.schema_validator import ValidationError


class EvaluationService:
    def __init__(self, connection):
        self.connection = connection

    def evaluate(self, dataset_id, golden_set_version, samples, tool_versions=None, minimum_samples=1, snapshot_ref=None, mode="technical"):
        if len(samples) < minimum_samples:
            raise ValidationError("EVALUATION_INSUFFICIENT", "not enough evaluation samples")
        snapshot = _active_snapshot(self.connection, snapshot_ref)
        started = time.perf_counter()
        failures = []
        passed = 0
        query = TechnicalQueryService(self.connection)
        router = BusinessRouter(self.connection)
        route_passed = 0
        retrieved = relevant = 0
        for sample in samples:
            if mode == "business":
                result = router.resolve(sample["query"])
                actual = []
                if result["status"] == sample.get("expected_status"):
                    route_passed += 1
                if result["status"] == "selected" and sample.get("context_id"):
                    selected = router.select(result["route_token"], sample["context_id"])
                    actual = [int(node_id) for node_id in selected["node_scope"]]
            else:
                result = query.search(sample["query"], sample.get("limit", 20))
                actual = [node["node_id"] for node in result["nodes"]]
            expected = sample["expected_node_ids"]
            relevant += len(set(expected)); retrieved += len(set(actual) & set(expected))
            if actual == expected:
                passed += 1
            else:
                failures.append((sample, expected, actual))
        metrics = {
            "total": len(samples),
            "passed": passed,
            "failed": len(failures),
            "accuracy": passed / len(samples),
            "freshness": True,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "token_cost": 0,
        }
        if mode == "business":
            metrics.update({"route_accuracy": route_passed / len(samples), "precision": retrieved / sum(len(set(sample["expected_node_ids"])) or 1 for sample in samples), "recall": retrieved / relevant if relevant else 1.0})
        run_id = uuid.uuid4().hex
        with self.connection:
            self.connection.execute(
                "INSERT INTO evaluation_runs(run_id,dataset_id,golden_set_version,metrics_json,threshold_status,snapshot_id,source_revision,index_revision,config_version,tool_versions_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (run_id, dataset_id, golden_set_version, json.dumps(metrics, sort_keys=True), "passed" if not failures else "failed", snapshot["snapshot_id"], snapshot["source_revision"], snapshot["index_revision"], snapshot["config_version"], json.dumps(tool_versions or {}, sort_keys=True)),
            )
            self.connection.executemany(
                "INSERT INTO failure_cases(run_id,sample_json,expected_json,actual_json,code) VALUES (?,?,?,?,?)",
                [(run_id, json.dumps(sample, sort_keys=True), json.dumps(expected), json.dumps(actual), "GOLDEN_MISMATCH") for sample, expected, actual in failures],
            )
        return {"ok": True, "run_id": run_id, "metrics": metrics, "failure_cases": len(failures), "snapshot_ref": _snapshot_ref(snapshot)}

    def acceptance_gate(self, metrics, thresholds):
        failed = {key: {"actual": metrics.get(key), "required": value} for key, value in thresholds.items() if metrics.get(key, 0) < value}
        if failed:
            raise ValidationError("ACCEPTANCE_GATE_FAILED", json.dumps(failed, sort_keys=True))
        return {"ok": True, "status": "passed"}


class KnowledgeService:
    def __init__(self, connection):
        self.connection = connection

    def generate(self, kind, document_scope, template_version, generator_version, snapshot_ref=None, impact_node_ids=None):
        snapshot = _active_snapshot(self.connection, snapshot_ref)
        if kind == "technical":
            if impact_node_ids:
                placeholders = ",".join("?" for _ in impact_node_ids)
                rows = self.connection.execute(f"SELECT node_id,kind,sub_kind,payload_json FROM nodes WHERE snapshot_id=? AND node_id IN ({placeholders}) ORDER BY node_id", (snapshot["snapshot_id"], *impact_node_ids)).fetchall()
            else:
                rows = self.connection.execute("SELECT node_id,kind,sub_kind,payload_json FROM nodes WHERE snapshot_id=? ORDER BY node_id", (snapshot["snapshot_id"],)).fetchall()
            evidence_refs = sorted({json.loads(row[3]).get("evidence_id") for row in rows if json.loads(row[3]).get("evidence_id") is not None})
            body = [f"# Technical knowledge: {document_scope}", "", *[f"- {row[0]} {row[1]}/{row[2]} {json.loads(row[3]).get('name', '')}" for row in rows]]
        elif kind == "business":
            row = self.connection.execute("SELECT * FROM mappings WHERE mapping_id=? AND snapshot_id=? AND status='confirmed'", (int(document_scope), snapshot["snapshot_id"])).fetchone()
            if row is None:
                raise ValidationError("CONFIRMED_MAPPING_REQUIRED", "business document requires a confirmed mapping")
            evidence_refs = [row[6]] if row[6] is not None else []
            body = [f"# Business knowledge: {row[1]}", "", f"- mapping_id: {row[0]}", f"- snapshot_id: {snapshot['snapshot_id']}"]
        else:
            raise ValidationError("DOCUMENT_KIND_INVALID", "document kind must be technical or business")
        metadata = {"snapshot_ref": _snapshot_ref(snapshot), "evidence_refs": evidence_refs, "generator_version": generator_version, "template_version": template_version}
        content = "\n".join(["---", json.dumps(metadata, sort_keys=True), "---", "", *body, ""])
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        artifact_id = uuid.uuid4().hex
        manifest_id = uuid.uuid4().hex
        document_id = f"{kind}:{document_scope}:{snapshot['snapshot_id']}"
        document_version = snapshot["index_revision"]
        with self.connection:
            self.connection.execute("INSERT INTO document_artifacts(artifact_id,document_id,document_version,snapshot_id,kind,content,content_hash) VALUES (?,?,?,?,?,?,?)", (artifact_id, document_id, document_version, snapshot["snapshot_id"], kind, content, content_hash))
            self.connection.execute("INSERT INTO document_manifests(manifest_id,artifact_id,document_id,document_version,snapshot_id,source_revision,index_revision,config_version,evidence_refs_json,generator_version,template_version,content_hash,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (manifest_id, artifact_id, document_id, document_version, snapshot["snapshot_id"], snapshot["source_revision"], snapshot["index_revision"], snapshot["config_version"], json.dumps(evidence_refs), generator_version, template_version, content_hash, "generated"))
        return {"ok": True, "artifact_id": artifact_id, "manifest_id": manifest_id, "content_hash": content_hash, "snapshot_ref": _snapshot_ref(snapshot)}


class DistributionService:
    def __init__(self, connection):
        self.connection = connection

    def configure_target(self, target, endpoint, options=None):
        if not target or target == "local" or not endpoint.startswith("https://"):
            raise ValidationError("DISTRIBUTION_TARGET_INVALID", "external targets require HTTPS")
        with self.connection:
            self.connection.execute("INSERT OR REPLACE INTO distribution_targets(target,endpoint,options_json,enabled) VALUES (?,?,?,1)", (target, endpoint, json.dumps(options or {}, sort_keys=True)))
        return {"ok": True, "target": target}

    def push(self, manifest_id, target, idempotency_key):
        existing = self.connection.execute("SELECT result_json FROM distribution_attempts WHERE idempotency_key=?", (idempotency_key,)).fetchone()
        if existing is not None:
            return json.loads(existing[0])
        if self.connection.execute("SELECT 1 FROM document_manifests WHERE manifest_id=?", (manifest_id,)).fetchone() is None:
            raise ValidationError("DOCUMENT_MANIFEST_NOT_FOUND", "document manifest does not exist")
        configured = self.connection.execute("SELECT 1 FROM distribution_targets WHERE target=? AND enabled=1", (target,)).fetchone()
        supported = target == "local" or configured is not None
        result = {"ok": supported, "manifest_id": manifest_id, "target": target, "status": "pushed" if supported else "failed", "retryable": not supported}
        if not supported:
            result["code"] = "DISTRIBUTION_TARGET_UNSUPPORTED"
        with self.connection:
            self.connection.execute("INSERT INTO distribution_attempts(attempt_id,manifest_id,target,idempotency_key,status,retryable,result_json) VALUES (?,?,?,?,?,?,?)", (uuid.uuid4().hex, manifest_id, target, idempotency_key, result["status"], int(result["retryable"]), json.dumps(result, sort_keys=True)))
        return result


def _active_snapshot(connection, snapshot_ref=None):
    row = connection.execute("SELECT snapshots.* FROM active_snapshot JOIN snapshots ON snapshots.snapshot_id=active_snapshot.snapshot_id WHERE active_snapshot.singleton=1 AND snapshots.status='published'").fetchone()
    if row is None:
        raise ValidationError("SNAPSHOT_NOT_PUBLISHED", "no published snapshot")
    snapshot = dict(row)
    if snapshot_ref and any(snapshot.get(key) != snapshot_ref.get(key) for key in ("source_revision", "index_revision", "config_version")):
        raise ValidationError("SNAPSHOT_VERSION_MISMATCH", "snapshot reference differs from active publication")
    return snapshot


def _snapshot_ref(snapshot):
    return {key: snapshot[key] for key in ("source_revision", "index_revision", "config_version")}
