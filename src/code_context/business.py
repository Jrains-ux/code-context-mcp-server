import json
import time
import uuid

from code_context.validators.schema_validator import ValidationError


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

    def confirm(self, mapping_id, expected_version, decision, evidence_refs, reason):
        if decision not in ("confirmed", "rejected") or not evidence_refs: raise ValidationError("EVIDENCE_REQUIRED", "evidence is required")
        mapping = self.connection.execute("SELECT * FROM mappings WHERE mapping_id=?", (mapping_id,)).fetchone()
        if mapping is None or mapping[4] != expected_version: raise ValidationError("CAS_VERSION_MISMATCH", "mapping version mismatch")
        if mapping[3] == "stale" and decision == "confirmed": raise ValidationError("CAS_VERSION_MISMATCH", "stale mapping cannot be restored")
        with self.connection:
            self.connection.execute("UPDATE mappings SET status=?,expected_version=? WHERE mapping_id=?", (decision, expected_version + 1, mapping_id))
            self.connection.execute("INSERT INTO confirmation_audit(mapping_id,decision,evidence_id,reason) VALUES (?,?,?,?)", (mapping_id, decision, evidence_refs[0], reason))
        return {"ok": True, "status": decision}

    def _active(self):
        row = self.connection.execute("SELECT snapshot_id FROM active_snapshot WHERE singleton=1").fetchone()
        if row is None: raise ValidationError("SNAPSHOT_NOT_PUBLISHED", "no published snapshot")
        return row[0]
