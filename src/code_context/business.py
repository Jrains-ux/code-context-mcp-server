import json
import time
import uuid

from code_context.validators.schema_validator import ValidationError


class BusinessMiningService:
    def __init__(self, connection): self.connection = connection

    def mine(self, mode, snapshot_id, candidates):
        if mode not in ("initial", "incremental"):
            raise ValidationError("MINING_MODE_INVALID", "mode must be initial or incremental")
        snapshot = self.connection.execute(
            "SELECT * FROM snapshots WHERE snapshot_id=?", (snapshot_id,)
        ).fetchone()
        if snapshot is None:
            raise ValidationError("SNAPSHOT_NOT_FOUND", "snapshot does not exist")
        if not isinstance(candidates, list):
            raise ValidationError("MINING_CANDIDATES_INVALID", "candidates must be a list")

        run_id = uuid.uuid4().hex
        try:
            with self.connection:
                for candidate in candidates:
                    self._validate_candidate(candidate)
                    evidence_refs = list(candidate["evidence_refs"])
                    self.connection.execute(
                        "INSERT INTO business_nodes(snapshot_id,node_type,canonical_key,payload_json,status,source_revision,index_revision,config_version) VALUES (?,?,?,?,?,?,?,?)",
                        (snapshot_id, candidate["node_type"], candidate["canonical_key"], json.dumps(candidate["payload"], sort_keys=True), "candidate", snapshot["source_revision"], snapshot["index_revision"], snapshot["config_version"]),
                    )
                    mapping_cursor = self.connection.execute(
                        "INSERT INTO mappings(biz_id,snapshot_id,status,evidence_id,requirement_id,anchor_node_ids_json,evidence_refs_json,review_required,review_mode,risk_level,confidence,review_batch_id,updated_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (candidate["biz_id"], snapshot_id, "candidate", evidence_refs[0], candidate.get("requirement_id"), json.dumps(candidate.get("anchor_node_ids", [])), json.dumps(evidence_refs), 1, candidate.get("review_mode", "manual_review_required"), candidate.get("risk_level"), candidate.get("confidence"), candidate.get("review_batch_id"), candidate.get("updated_by", "mining")),
                    )
                    mapping_id = mapping_cursor.lastrowid
                    self.connection.executemany(
                        "INSERT INTO mapping_evidence(mapping_id,evidence_id,created_by) VALUES (?,?,?)",
                        [(mapping_id, evidence_id, candidate.get("updated_by", "mining")) for evidence_id in evidence_refs],
                    )
                    self.connection.execute(
                        "INSERT OR REPLACE INTO business_routes(term,biz_id,context_id,summary,node_scope_json,snapshot_id) VALUES (?,?,?,?,?,?)",
                        (candidate["term"], candidate["biz_id"], candidate["context_id"], candidate["summary"], json.dumps(candidate["node_scope"], sort_keys=True), snapshot_id),
                    )
                self.connection.execute(
                    "INSERT INTO mining_runs(run_id,mode,snapshot_id,candidate_count,status) VALUES (?,?,?,?,?)",
                    (run_id, mode, snapshot_id, len(candidates), "candidate"),
                )
        except Exception:
            with self.connection:
                self.connection.execute(
                    "INSERT OR REPLACE INTO mining_runs(run_id,mode,snapshot_id,candidate_count,status) VALUES (?,?,?,?,?)",
                    (run_id, mode, snapshot_id, len(candidates), "rejected"),
                )
            raise
        return {"ok": True, "run_id": run_id, "mode": mode, "snapshot_id": snapshot_id, "candidate_count": len(candidates), "status": "candidate"}

    @staticmethod
    def _validate_candidate(candidate):
        required = ("biz_id", "term", "context_id", "summary", "node_scope", "node_type", "canonical_key", "payload", "evidence_refs")
        if not isinstance(candidate, dict) or any(field not in candidate for field in required):
            raise ValidationError("MINING_CANDIDATE_INVALID", "candidate is missing required fields")
        if not candidate["evidence_refs"]:
            raise ValidationError("EVIDENCE_REQUIRED", "candidate requires evidence")


class BusinessRouter:
    def __init__(self, connection): self.connection = connection

    def add_candidate(self, term, biz_id, context_id, summary, node_scope, snapshot_id):
        with self.connection:
            self.connection.execute("INSERT OR REPLACE INTO business_routes(term,biz_id,context_id,summary,node_scope_json,snapshot_id) VALUES (?,?,?,?,?,?)", (term, biz_id, context_id, summary, json.dumps(node_scope), snapshot_id))

    def resolve(self, query, ttl_seconds=300):
        snapshot_id = self._active()
        rows = self.connection.execute("SELECT * FROM business_routes WHERE term=? AND snapshot_id=?", (query, snapshot_id)).fetchall()
        candidates = [{"biz_id": r[2], "context_id": r[3], "summary": r[4], "node_scope": json.loads(r[5])} for r in rows]
        if not candidates: return {"ok": True, "status": "not_found", "candidates": []}
        token = uuid.uuid4().hex
        with self.connection: self.connection.execute("INSERT INTO route_tokens(token,snapshot_id,candidates_json,expires_at) VALUES (?,?,?,?)", (token, snapshot_id, json.dumps(candidates), int(time.time()) + ttl_seconds))
        return {"ok": True, "status": "selected" if len(candidates) == 1 else "needs_user_selection", "candidates": candidates, "route_token": token}

    def select(self, token, context_id):
        row = self.connection.execute("SELECT * FROM route_tokens WHERE token=?", (token,)).fetchone()
        if row is None or row[3] < int(time.time()): raise ValidationError("ROUTE_TOKEN_EXPIRED", "route token expired")
        if row[1] != self._active(): raise ValidationError("SCOPE_MISMATCH", "snapshot changed")
        candidates = json.loads(row[2])
        for candidate in candidates:
            if candidate["context_id"] == context_id: return {"ok": True, "status": "selected", **candidate, "route_token": token}
        raise ValidationError("CONTEXT_SELECTION_REQUIRED", "context is not a token candidate")

    def confirm(self, mapping_id, expected_version, decision, evidence_refs, reason,
                review_mode=None, updated_by=None):
        if decision not in ("confirmed", "rejected") or not evidence_refs: raise ValidationError("EVIDENCE_REQUIRED", "evidence is required")
        mapping = self.connection.execute("SELECT * FROM mappings WHERE mapping_id=?", (mapping_id,)).fetchone()
        if mapping is None or mapping[4] != expected_version: raise ValidationError("CAS_VERSION_MISMATCH", "mapping version mismatch")
        if mapping[3] == "stale" and decision == "confirmed": raise ValidationError("CAS_VERSION_MISMATCH", "stale mapping cannot be restored")
        with self.connection:
            self.connection.execute(
                "UPDATE mappings SET status=?,expected_version=?,evidence_id=?,evidence_refs_json=?,review_mode=COALESCE(?,review_mode),updated_by=?,updated_at=CURRENT_TIMESTAMP WHERE mapping_id=?",
                (decision, expected_version + 1, evidence_refs[0], json.dumps(list(evidence_refs)), review_mode, updated_by, mapping_id),
            )
            self.connection.execute(
                "INSERT INTO confirmation_audit(mapping_id,decision,evidence_id,reason,evidence_refs_json,review_mode,updated_by) VALUES (?,?,?,?,?,?,?)",
                (mapping_id, decision, evidence_refs[0], reason, json.dumps(list(evidence_refs)), review_mode, updated_by),
            )
        return {"ok": True, "status": decision}

    def _active(self):
        row = self.connection.execute("SELECT snapshot_id FROM active_snapshot WHERE singleton=1").fetchone()
        if row is None: raise ValidationError("SNAPSHOT_NOT_PUBLISHED", "no published snapshot")
        return row[0]
