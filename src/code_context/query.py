import json

from code_context.validators.schema_validator import ValidationError


class TechnicalQueryService:
    def __init__(self, connection):
        self.connection = connection

    def search(self, query, limit):
        snapshot = self._active_snapshot()
        if snapshot is None:
            raise ValidationError("SNAPSHOT_NOT_PUBLISHED", "no published snapshot")
        rows = self.connection.execute(
            "SELECT nodes.* FROM node_fts JOIN nodes ON nodes.node_id=node_fts.node_id "
            "WHERE node_fts.snapshot_id=? AND node_fts MATCH ? LIMIT ?",
            (str(snapshot["snapshot_id"]), query, limit),
        ).fetchall()
        if not rows:
            indexed = self.connection.execute(
                "SELECT count(*) FROM node_fts WHERE snapshot_id=?", (str(snapshot["snapshot_id"]),)
            ).fetchone()[0]
            if not indexed:
                raise ValidationError("INDEX_UNAVAILABLE", "published snapshot is not indexed")
        return {
            "ok": True,
            "nodes": [self._node_result(row, snapshot) for row in rows],
            "snapshot_ref": self._snapshot_ref(snapshot),
            "degraded": False,
        }

    def expand(self, node_ids, depth, node_budget, edge_budget, direction="out", edge_types=(), node_scope=None):
        if direction not in {"out", "in", "both"}:
            raise ValidationError("INVALID_DIRECTION", "direction must be out, in, or both")
        snapshot = self._active_snapshot()
        if snapshot is None:
            raise ValidationError("SNAPSHOT_NOT_PUBLISHED", "no published snapshot")
        visited = set(node_ids)
        frontier = list(dict.fromkeys(node_ids))
        predecessor = {}
        edges = []
        truncated = False
        for _ in range(depth):
            if not frontier:
                break
            conditions = []
            params = [snapshot["snapshot_id"]]
            if direction == "out":
                conditions.append("from_node_id IN ({})".format(",".join("?" for _ in frontier)))
                params.extend(frontier)
            elif direction == "in":
                conditions.append("to_node_id IN ({})".format(",".join("?" for _ in frontier)))
                params.extend(frontier)
            else:
                placeholders = ",".join("?" for _ in frontier)
                conditions.append(f"(from_node_id IN ({placeholders}) OR to_node_id IN ({placeholders}))")
                params.extend(frontier)
                params.extend(frontier)
            query = "SELECT * FROM edges WHERE snapshot_id=? AND " + " AND ".join(conditions)
            if edge_types:
                types = ",".join("?" for _ in edge_types)
                query += f" AND edge_type IN ({types})"
                params.extend(edge_types)
            query += " ORDER BY edge_id"
            next_frontier = set()
            for row in self.connection.execute(query, params):
                if len(edges) >= edge_budget:
                    truncated = True
                    break
                current = self._current_endpoint(row, frontier, direction)
                candidate = self._other_endpoint(row, current)
                if candidate not in visited:
                    if not self._node_matches_scope(candidate, snapshot["snapshot_id"], node_scope):
                        continue
                    if len(visited) >= node_budget:
                        truncated = True
                        break
                    visited.add(candidate)
                    predecessor[candidate] = current
                    next_frontier.add(candidate)
                edges.append(dict(row))
            if truncated:
                break
            frontier = [node_id for node_id in next_frontier]
        paths = [self._path_to(node_id, predecessor) for node_id in predecessor]
        return {"ok": True, "edges": edges, "paths": paths, "truncated": truncated, "coverage": {"nodes": len(visited), "edges": len(edges)}, "snapshot_ref": self._snapshot_ref(snapshot)}

    @staticmethod
    def _current_endpoint(row, frontier, direction):
        if direction == "out":
            return row["from_node_id"]
        if direction == "in":
            return row["to_node_id"]
        if row["from_node_id"] in frontier:
            return row["from_node_id"]
        return row["to_node_id"]

    @staticmethod
    def _other_endpoint(row, current):
        return row["to_node_id"] if row["from_node_id"] == current else row["from_node_id"]

    def _node_matches_scope(self, node_id, snapshot_id, node_scope):
        if not node_scope:
            return True
        row = self.connection.execute(
            "SELECT canonical_key, payload_json FROM nodes WHERE snapshot_id=? AND node_id=?",
            (snapshot_id, node_id),
        ).fetchone()
        if row is None:
            return False
        payload = json.loads(row["payload_json"])
        canonical_keys = node_scope.get("canonical_keys")
        if canonical_keys and row["canonical_key"] not in set(canonical_keys):
            return False
        file_paths = node_scope.get("file_paths")
        if file_paths and payload.get("file_path") not in set(file_paths):
            return False
        return True

    @staticmethod
    def _path_to(node_id, predecessor):
        path = [node_id]
        while path[-1] in predecessor:
            path.append(predecessor[path[-1]])
        path.reverse()
        return path

    def _active_snapshot(self):
        row = self.connection.execute(
            "SELECT snapshots.* FROM active_snapshot JOIN snapshots ON snapshots.snapshot_id=active_snapshot.snapshot_id WHERE active_snapshot.singleton=1 AND snapshots.status='published'"
        ).fetchone()
        return None if row is None else dict(row)

    def _node_result(self, row, snapshot):
        result = dict(row)
        payload = json.loads(result.pop("payload_json"))
        evidence_id = payload.get("evidence_id")
        result["payload"] = payload
        result["matched_fields"] = ["name", "qualified_name"]
        result["score"] = 1.0
        result["evidence_refs"] = [] if evidence_id is None else [evidence_id]
        result["snapshot_ref"] = self._snapshot_ref(snapshot)
        return result

    def _snapshot_ref(self, snapshot):
        return {key: snapshot[key] for key in ("source_revision", "index_revision", "config_version")}
