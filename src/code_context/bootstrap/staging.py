from code_context.validators.schema_validator import ValidationError, require_same_revisions

_UNSET = object()


class SnapshotPublisher:
    def __init__(self, repository):
        self.repository = repository

    def publish(self, snapshot_id, expected_parent=_UNSET):
        snapshot = self.repository.get_snapshot(snapshot_id)
        if snapshot is None:
            raise ValidationError("SNAPSHOT_NOT_FOUND", "snapshot does not exist")
        if snapshot["status"] != "staging":
            raise ValidationError("SNAPSHOT_NOT_STAGING", "only staging snapshots can be published")
        rows = self.repository.connection.execute(
            "SELECT source_revision,index_revision,config_version FROM nodes WHERE snapshot_id=?",
            (snapshot_id,),
        ).fetchall()
        for row in rows:
            require_same_revisions(snapshot, dict(row))
        edge_rows = self.repository.connection.execute(
            "SELECT source_revision,index_revision,config_version FROM edges WHERE snapshot_id=?", (snapshot_id,)
        ).fetchall()
        for row in edge_rows:
            require_same_revisions(snapshot, dict(row))
        if self.repository.connection.execute(
            "SELECT count(*) FROM nodes WHERE snapshot_id=? AND kind='Graph' AND canonical_key IS NULL", (snapshot_id,)
        ).fetchone()[0]:
            raise ValidationError("CANONICAL_KEY_REQUIRED", "graph nodes require canonical keys")
        with self.repository.connection:
            status_update = self.repository.connection.execute(
                "UPDATE snapshots SET status='published' WHERE snapshot_id=? AND status='staging'",
                (snapshot_id,),
            )
            if status_update.rowcount != 1:
                raise ValidationError("SNAPSHOT_NOT_STAGING", "only staging snapshots can be published")
            if expected_parent is _UNSET:
                active_update = self.repository.connection.execute(
                    "INSERT INTO active_snapshot(singleton,snapshot_id) VALUES (1,?) "
                    "ON CONFLICT(singleton) DO UPDATE SET snapshot_id=excluded.snapshot_id",
                    (snapshot_id,),
                )
            else:
                active_update = self.repository.connection.execute(
                    "INSERT INTO active_snapshot(singleton,snapshot_id) VALUES (1,?) "
                    "ON CONFLICT(singleton) DO UPDATE SET snapshot_id=excluded.snapshot_id "
                    "WHERE active_snapshot.snapshot_id IS ?",
                    (snapshot_id, expected_parent),
                )
            if active_update.rowcount != 1:
                raise ValidationError("PUBLISH_PARENT_MISMATCH", "active snapshot differs from expected parent")
