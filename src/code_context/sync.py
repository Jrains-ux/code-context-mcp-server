import json
import subprocess

from code_context.bootstrap.first_build import BootstrapService
from code_context.validators.schema_validator import ValidationError


class SyncService:
    def __init__(self, repository): self.repository = repository

    def update(self, operation_id, baseline_ref, source_root, target_source_revision, config_version, scope):
        existing = self.repository.connection.execute("SELECT result_json FROM sync_operations WHERE operation_id=?", (operation_id,)).fetchone()
        if existing: return json.loads(existing[0])
        active = self.repository.get_active_snapshot_id()
        if active is None or baseline_ref != active: raise ValidationError("BASELINE_REF_NOT_FOUND", "baseline is not active")
        baseline = self.repository.get_snapshot(baseline_ref)
        changes = self._git_diff(source_root, baseline["source_revision"], target_source_revision, scope)
        affected_node_ids = self._affected_nodes(baseline_ref, changes)
        closure_node_ids = self._dependency_closure(baseline_ref, affected_node_ids)
        stale_mapping_ids = self._affected_mappings(baseline_ref, closure_node_ids)
        result = BootstrapService(self.repository).build(source_root, target_source_revision, config_version, scope, expected_parent=baseline_ref)
        with self.repository.connection:
            for mapping_id in stale_mapping_ids:
                self.repository.connection.execute("UPDATE mappings SET status='stale',updated_at=CURRENT_TIMESTAMP WHERE mapping_id=?", (mapping_id,))
                self.repository.connection.execute("INSERT INTO stale_events(mapping_id,dependency_type,old_revision,new_revision,reason,status) VALUES (?,?,?,?,?,?)", (mapping_id, "dependency_closure", baseline["source_revision"], target_source_revision, "affected by incremental sync", "stale"))
        result.update({
            "operation_id": operation_id,
            "changes": changes,
            "affected_node_ids": affected_node_ids,
            "closure_node_ids": closure_node_ids,
            "stale_mapping_ids": stale_mapping_ids,
        })
        with self.repository.connection:
            self.repository.connection.execute(
                "INSERT INTO sync_operations(operation_id,baseline_ref,target_source_revision,result_json,changes_json,affected_node_ids_json,closure_node_ids_json,stale_mapping_ids_json) VALUES (?,?,?,?,?,?,?,?)",
                (operation_id, baseline_ref, target_source_revision, json.dumps(result), json.dumps(changes), json.dumps(affected_node_ids), json.dumps(closure_node_ids), json.dumps(stale_mapping_ids)),
            )
        return result

    def _git_diff(self, source_root, baseline_revision, target_revision, scope):
        command = ["git", "-C", str(source_root), "diff", "--name-status", baseline_revision, target_revision, "--", *scope]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode:
            raise ValidationError("GIT_DIFF_FAILED", completed.stderr.strip() or "git diff failed")
        return self._parse_diff(completed.stdout)

    def _affected_nodes(self, snapshot_id, changes):
        paths = {
            path.replace("\\", "/")
            for change in changes
            for path in (change["path"], change["old_path"])
            if path
        }
        rows = self.repository.connection.execute(
            "SELECT node_id,payload_json FROM nodes WHERE snapshot_id=?", (snapshot_id,)
        ).fetchall()
        return sorted(
            row[0] for row in rows
            if json.loads(row[1]).get("file_path", "").replace("\\", "/") in paths
        )

    def _dependency_closure(self, snapshot_id, seed_node_ids):
        closure = set(seed_node_ids)
        frontier = set(seed_node_ids)
        while frontier:
            placeholders = ",".join("?" for _ in frontier)
            rows = self.repository.connection.execute(
                f"SELECT from_node_id,to_node_id FROM edges WHERE snapshot_id=? AND (from_node_id IN ({placeholders}) OR to_node_id IN ({placeholders}))",
                [snapshot_id, *frontier, *frontier],
            ).fetchall()
            next_frontier = {node_id for row in rows for node_id in row if node_id not in closure}
            closure.update(next_frontier)
            frontier = next_frontier
        return sorted(closure)

    def _affected_mappings(self, snapshot_id, closure_node_ids):
        closure = set(closure_node_ids)
        rows = self.repository.connection.execute(
            "SELECT mapping_id,anchor_node_ids_json FROM mappings WHERE snapshot_id=? AND status!='stale'", (snapshot_id,)
        ).fetchall()
        return sorted(
            row[0] for row in rows
            if closure.intersection(json.loads(row[1]))
        )

    @staticmethod
    def _parse_diff(output):
        changes = []
        for line in output.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            status = parts[0][0]
            if status in {"R", "C"} and len(parts) >= 3:
                changes.append({"status": status, "path": parts[2], "old_path": parts[1]})
            else:
                changes.append({"status": status, "path": parts[1], "old_path": None})
        return changes
