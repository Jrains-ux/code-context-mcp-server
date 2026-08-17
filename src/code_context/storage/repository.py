import json


class SnapshotRepository:
    def __init__(self, connection):
        self.connection = connection

    def create_snapshot(self, source_revision, index_revision, config_version, status):
        cursor = self.connection.execute(
            "INSERT INTO snapshots(source_revision,index_revision,config_version,status) VALUES (?,?,?,?)",
            (source_revision, index_revision, config_version, status),
        )
        self.connection.commit()
        return cursor.lastrowid

    def add_manifest(self, source_root, source_revision, scope, exclude, parser_version, config_version):
        manifest_id = f"{source_root}:{source_revision}"
        self.connection.execute(
            "INSERT INTO manifests(manifest_id,source_root,source_revision,scope_json,exclude_json,parser_version,config_version,workspace_clean,status) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (manifest_id, source_root, source_revision, json.dumps(scope, sort_keys=True), json.dumps(exclude, sort_keys=True), parser_version, config_version, 1, "accepted"),
        )
        self.connection.commit()
        return manifest_id

    def set_active_snapshot(self, snapshot_id):
        with self.connection:
            self.connection.execute(
                "INSERT INTO active_snapshot(singleton,snapshot_id) VALUES (1,?) "
                "ON CONFLICT(singleton) DO UPDATE SET snapshot_id=excluded.snapshot_id",
                (snapshot_id,),
            )

    def get_active_snapshot_id(self):
        row = self.connection.execute(
            "SELECT snapshot_id FROM active_snapshot WHERE singleton=1"
        ).fetchone()
        return None if row is None else row[0]

    def get_snapshot(self, snapshot_id):
        row = self.connection.execute(
            "SELECT * FROM snapshots WHERE snapshot_id=?", (snapshot_id,)
        ).fetchone()
        return None if row is None else dict(row)

    def add_node(self, snapshot_id, kind, sub_kind, source_revision, index_revision, config_version, payload):
        cursor = self.connection.execute(
            "INSERT INTO nodes(snapshot_id,kind,sub_kind,source_revision,index_revision,config_version,payload_json) "
            "VALUES (?,?,?,?,?,?,?)",
            (snapshot_id, kind, sub_kind, source_revision, index_revision, config_version, json.dumps(payload, sort_keys=True)),
        )
        self.connection.commit()
        return cursor.lastrowid

    def get_node(self, node_id):
        row = self.connection.execute("SELECT * FROM nodes WHERE node_id=?", (node_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result

    def add_edge(self, snapshot_id, from_node_id, to_node_id, edge_type, source_revision, index_revision, config_version, payload):
        cursor = self.connection.execute(
            "INSERT INTO edges(snapshot_id,from_node_id,to_node_id,edge_type,source_revision,index_revision,config_version,payload_json) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (snapshot_id, from_node_id, to_node_id, edge_type, source_revision, index_revision, config_version, json.dumps(payload, sort_keys=True)),
        )
        self.connection.commit()
        return cursor.lastrowid

    def add_evidence(self, source_revision, index_revision, config_version, file_path, start_line, end_line, snippet_hash):
        cursor = self.connection.execute(
            "INSERT INTO evidence(source_revision,index_revision,config_version,file_path,start_line,end_line,snippet_hash) "
            "VALUES (?,?,?,?,?,?,?)",
            (source_revision, index_revision, config_version, file_path, start_line, end_line, snippet_hash),
        )
        self.connection.commit()
        return cursor.lastrowid

    def update_evidence(self, evidence_id, snippet_hash):
        with self.connection:
            self.connection.execute("UPDATE evidence SET snippet_hash=? WHERE evidence_id=?", (snippet_hash, evidence_id))

    def add_mapping(self, biz_id, snapshot_id, status, evidence_id):
        cursor = self.connection.execute(
            "INSERT INTO mappings(biz_id,snapshot_id,status,evidence_id) VALUES (?,?,?,?)",
            (biz_id, snapshot_id, status, evidence_id),
        )
        self.connection.commit()
        return cursor.lastrowid

    def get_mapping(self, mapping_id):
        row = self.connection.execute("SELECT * FROM mappings WHERE mapping_id=?", (mapping_id,)).fetchone()
        return None if row is None else dict(row)

    def replace_mapping_evidence(self, mapping_id, evidence_id):
        with self.connection:
            self.connection.execute(
                "UPDATE mappings SET replacement_evidence_id=?, status='candidate' WHERE mapping_id=?",
                (evidence_id, mapping_id),
            )
