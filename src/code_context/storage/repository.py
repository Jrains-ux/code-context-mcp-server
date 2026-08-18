import json

from code_context.validators.schema_validator import require_same_revisions, ValidationError


class InitializationRepository:
    def __init__(self, connection):
        self.connection = connection

    def save_manifest(self, manifest):
        skills_json = json.dumps(manifest["skills"], sort_keys=True)
        with self.connection:
            self.connection.execute(
                "INSERT INTO initialization_manifest(singleton,project,workspace,source_revision,config_version,skills_json) "
                "VALUES (1,?,?,?,?,?) "
                "ON CONFLICT(singleton) DO UPDATE SET project=excluded.project,workspace=excluded.workspace,"
                "source_revision=excluded.source_revision,config_version=excluded.config_version,skills_json=excluded.skills_json",
                (
                    manifest["project"],
                    manifest["workspace"],
                    manifest["source_revision"],
                    manifest["config_version"],
                    skills_json,
                ),
            )
            self.connection.execute("DELETE FROM manifest_tool_permissions")
            self.connection.executemany(
                "INSERT INTO manifest_tool_permissions(skill,tool_name) VALUES (?,?)",
                [
                    (skill, tool)
                    for skill, tools in manifest["skills"].items()
                    for tool in tools
                ],
            )

    def get_manifest(self):
        row = self.connection.execute(
            "SELECT project,workspace,source_revision,config_version,skills_json "
            "FROM initialization_manifest WHERE singleton=1"
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["skills"] = json.loads(result.pop("skills_json"))
        return result


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

    def get_node_by_canonical_key(self, snapshot_id, canonical_key):
        row = self.connection.execute(
            "SELECT * FROM nodes WHERE snapshot_id=? AND canonical_key=?",
            (snapshot_id, canonical_key),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result

    def persist_graph_artifacts(self, snapshot_id, graph):
        """Persist one parser result without intermediate commits."""
        snapshot = self.get_snapshot(snapshot_id)
        if snapshot is None:
            raise ValidationError("SNAPSHOT_NOT_FOUND", "snapshot does not exist")
        if snapshot["status"] != "staging":
            raise ValidationError("SNAPSHOT_NOT_STAGING", "graph requires a staging snapshot")
        if graph.source_revision != snapshot["source_revision"] or graph.snapshot_revision != snapshot["index_revision"]:
            raise ValidationError("REVISION_MISMATCH", "graph revisions do not match snapshot")
        keys = [node.canonical_key for node in graph.nodes]
        if len(keys) != len(set(keys)):
            raise ValidationError("ARTIFACT_CONFLICT", "duplicate node canonical key")
        if any(not key for key in keys):
            raise ValidationError("ARTIFACT_CONFLICT", "canonical key is required")
        existing = self.connection.execute(
            "SELECT canonical_key FROM nodes WHERE snapshot_id=? AND canonical_key IS NOT NULL",
            (snapshot_id,),
        ).fetchall()
        if set(keys) & {row[0] for row in existing}:
            raise ValidationError("ARTIFACT_CONFLICT", "canonical key already exists")

        node_ids = {}
        edge_keys = set()
        with self.connection:
            for node in graph.nodes:
                require_same_revisions(snapshot, {
                    "source_revision": node.evidence.source_revision,
                    "index_revision": node.snapshot_revision,
                    "config_version": node.evidence.config_revision or snapshot["config_version"],
                })
                evidence_id = self._insert_evidence(node.evidence, node.location, node.payload)
                payload = self._artifact_payload(node.canonical_key, node.name, node.location, node.evidence, node.payload, evidence_id)
                cursor = self.connection.execute(
                    "INSERT INTO nodes(snapshot_id,kind,sub_kind,source_revision,index_revision,config_version,payload_json,canonical_key,evidence_id) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (snapshot_id, "Graph", node.kind, snapshot["source_revision"], snapshot["index_revision"], snapshot["config_version"], json.dumps(payload, sort_keys=True), node.canonical_key, evidence_id),
                )
                node_ids[node.canonical_key] = cursor.lastrowid
                self.connection.execute(
                    "INSERT INTO artifact_manifests(snapshot_id,canonical_key,kind,content_hash,evidence_id,payload_json) VALUES (?,?,?,?,?,?)",
                    (snapshot_id, node.canonical_key, node.kind, self._content_hash(payload), evidence_id, json.dumps(payload, sort_keys=True)),
                )

            for edge in graph.edges:
                require_same_revisions(snapshot, {
                    "source_revision": edge.evidence.source_revision,
                    "index_revision": edge.snapshot_revision,
                    "config_version": edge.evidence.config_revision,
                })
                require_same_revisions(snapshot, {
                    "source_revision": edge.evidence.source_revision,
                    "index_revision": edge.evidence.snapshot_revision,
                    "config_version": edge.evidence.config_revision,
                })
                edge_identity = (edge.edge_type, edge.source_key, edge.target_key, edge.location.path, edge.location.start_line)
                if edge_identity in edge_keys:
                    continue
                edge_keys.add(edge_identity)
                source_id = node_ids.get(edge.source_key) or self._ensure_external_node(snapshot_id, snapshot, edge.source_key, edge)
                target_id = node_ids.get(edge.target_key) or self._ensure_external_node(snapshot_id, snapshot, edge.target_key, edge)
                evidence_id = self._insert_evidence(edge.evidence, edge.location, edge.payload)
                payload = self._artifact_payload(edge.edge_type, edge.edge_type, edge.location, edge.evidence, {**edge.payload, "source_key": edge.source_key, "target_key": edge.target_key}, evidence_id)
                self.connection.execute(
                    "INSERT INTO edges(snapshot_id,from_node_id,to_node_id,edge_type,source_revision,index_revision,config_version,payload_json,evidence_id) VALUES (?,?,?,?,?,?,?,?,?)",
                    (snapshot_id, source_id, target_id, edge.edge_type, snapshot["source_revision"], snapshot["index_revision"], snapshot["config_version"], json.dumps(payload, sort_keys=True), evidence_id),
                )

            self._rebuild_node_index_in_transaction(snapshot_id)
        node_count = self.connection.execute(
            "SELECT count(*) FROM nodes WHERE snapshot_id=?", (snapshot_id,)
        ).fetchone()[0]
        return {"node_count": node_count, "edge_count": len(edge_keys)}

    @staticmethod
    def _content_hash(payload):
        import hashlib
        return hashlib.sha256(json.dumps(dict(payload), sort_keys=True, default=str).encode("utf-8")).hexdigest()

    @staticmethod
    def _artifact_payload(canonical_key, name, location, evidence, payload, evidence_id):
        result = dict(payload)
        result.update({
            "canonical_key": canonical_key,
            "name": name,
            "file_path": location.path,
            "start_line": location.start_line,
            "end_line": location.end_line,
            "evidence_id": evidence_id,
            "source_revision": evidence.source_revision,
            "index_revision": evidence.snapshot_revision,
            "config_version": evidence.config_revision,
        })
        return result

    def _insert_evidence(self, evidence, location, payload):
        cursor = self.connection.execute(
            "INSERT INTO evidence(source_revision,index_revision,config_version,file_path,start_line,end_line,snippet_hash,parser,confidence,metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (evidence.source_revision, evidence.snapshot_revision, evidence.config_revision, location.path, location.start_line, location.end_line or location.start_line, self._content_hash(payload), evidence.parser, evidence.confidence, json.dumps(dict(evidence.metadata), sort_keys=True, default=str)),
        )
        return cursor.lastrowid

    def _ensure_external_node(self, snapshot_id, snapshot, canonical_key, edge):
        existing = self.get_node_by_canonical_key(snapshot_id, f"external:{canonical_key}")
        if existing:
            return existing["node_id"]
        external_key = f"external:{canonical_key}"
        evidence_id = self._insert_evidence(edge.evidence, edge.location, edge.payload)
        payload = self._artifact_payload(external_key, canonical_key, edge.location, edge.evidence, {"external": True}, evidence_id)
        cursor = self.connection.execute(
            "INSERT INTO nodes(snapshot_id,kind,sub_kind,source_revision,index_revision,config_version,payload_json,canonical_key,evidence_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (snapshot_id, "Graph", "external", snapshot["source_revision"], snapshot["index_revision"], snapshot["config_version"], json.dumps(payload, sort_keys=True), external_key, evidence_id),
        )
        self.connection.execute(
            "INSERT INTO artifact_manifests(snapshot_id,canonical_key,kind,content_hash,evidence_id,payload_json) VALUES (?,?,?,?,?,?)",
            (snapshot_id, external_key, "external", self._content_hash(payload), evidence_id, json.dumps(payload, sort_keys=True)),
        )
        return cursor.lastrowid

    def _rebuild_node_index_in_transaction(self, snapshot_id):
        rows = self.connection.execute("SELECT node_id,payload_json FROM nodes WHERE snapshot_id=?", (snapshot_id,)).fetchall()
        self.connection.execute("DELETE FROM node_fts WHERE snapshot_id=?", (str(snapshot_id),))
        self.connection.executemany(
            "INSERT INTO node_fts(node_id,snapshot_id,name,qualified_name,file_path,content_hash) VALUES (?,?,?,?,?,?)",
            [(str(row[0]), str(snapshot_id), *(lambda payload: (payload.get("name", ""), payload.get("qualified_name", ""), payload.get("file_path", ""), payload.get("content_hash", "")))(json.loads(row[1]))) for row in rows],
        )

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

    def add_task_run(self, task_id, snapshot_id, scope, source_revision, status):
        with self.connection:
            self.connection.execute(
                "INSERT INTO task_runs(task_id,snapshot_id,scope,source_revision,status) VALUES (?,?,?,?,?)",
                (task_id, snapshot_id, scope, source_revision, status),
            )

    def complete_tasks(self, snapshot_id):
        with self.connection:
            self.connection.execute("UPDATE task_runs SET status='completed' WHERE snapshot_id=?", (snapshot_id,))

    def add_artifact(self, snapshot_id, canonical_key, kind, content_hash, evidence_id, payload):
        with self.connection:
            self.connection.execute(
                "INSERT INTO artifact_manifests(snapshot_id,canonical_key,kind,content_hash,evidence_id,payload_json) VALUES (?,?,?,?,?,?)",
                (snapshot_id, canonical_key, kind, content_hash, evidence_id, json.dumps(payload, sort_keys=True)),
            )

    def add_conflict(self, snapshot_id, code, detail):
        with self.connection:
            self.connection.execute(
                "INSERT INTO conflict_reports(snapshot_id,code,detail_json) VALUES (?,?,?)",
                (snapshot_id, code, json.dumps(detail, sort_keys=True)),
            )

    def rebuild_node_index(self, snapshot_id):
        rows = self.connection.execute(
            "SELECT node_id,payload_json FROM nodes WHERE snapshot_id=?", (snapshot_id,)
        ).fetchall()
        with self.connection:
            self.connection.execute("DELETE FROM node_fts WHERE snapshot_id=?", (str(snapshot_id),))
            self.connection.executemany(
                "INSERT INTO node_fts(node_id,snapshot_id,name,qualified_name,file_path,content_hash) VALUES (?,?,?,?,?,?)",
                [
                    (str(row[0]), str(snapshot_id), *(lambda payload: (payload.get("name", ""), payload.get("qualified_name", ""), payload.get("file_path", ""), payload.get("content_hash", "")))(json.loads(row[1])))
                    for row in rows
                ],
            )
