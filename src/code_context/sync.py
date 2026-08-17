import json

from code_context.bootstrap.first_build import BootstrapService
from code_context.validators.schema_validator import ValidationError


class SyncService:
    def __init__(self, repository): self.repository = repository

    def update(self, operation_id, baseline_ref, source_root, target_source_revision, config_version, scope):
        existing = self.repository.connection.execute("SELECT result_json FROM sync_operations WHERE operation_id=?", (operation_id,)).fetchone()
        if existing: return json.loads(existing[0])
        active = self.repository.get_active_snapshot_id()
        if active is None or baseline_ref != active: raise ValidationError("BASELINE_REF_NOT_FOUND", "baseline is not active")
        mappings = self.repository.connection.execute("SELECT mapping_id FROM mappings WHERE snapshot_id=? AND status!='stale'", (baseline_ref,)).fetchall()
        with self.repository.connection:
            for row in mappings:
                self.repository.connection.execute("UPDATE mappings SET status='stale' WHERE mapping_id=?", (row[0],))
                self.repository.connection.execute("INSERT INTO stale_events(mapping_id,dependency_type,old_revision,new_revision,reason,status) VALUES (?,?,?,?,?,?)", (row[0], "snapshot", str(baseline_ref), target_source_revision, "incremental sync", "stale"))
        result = BootstrapService(self.repository).build(source_root, target_source_revision, config_version, scope, expected_parent=baseline_ref)
        result["operation_id"] = operation_id
        with self.repository.connection: self.repository.connection.execute("INSERT INTO sync_operations(operation_id,baseline_ref,target_source_revision,result_json) VALUES (?,?,?,?)", (operation_id, baseline_ref, target_source_revision, json.dumps(result)))
        return result
