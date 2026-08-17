from code_context.validators.schema_validator import ValidationError, require_same_revisions


class SnapshotPublisher:
    def __init__(self, repository):
        self.repository = repository

    def publish(self, snapshot_id):
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
        with self.repository.connection:
            self.repository.connection.execute(
                "UPDATE snapshots SET status='published' WHERE snapshot_id=?", (snapshot_id,)
            )
            self.repository.connection.execute(
                "INSERT INTO active_snapshot(singleton,snapshot_id) VALUES (1,?) "
                "ON CONFLICT(singleton) DO UPDATE SET snapshot_id=excluded.snapshot_id",
                (snapshot_id,),
            )
