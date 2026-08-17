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

    def expand(self, node_ids, depth, node_budget, edge_budget, direction="out", edge_types=()):
        snapshot = self._active_snapshot()
        if snapshot is None:
            raise ValidationError("SNAPSHOT_NOT_PUBLISHED", "no published snapshot")
        visited = set(node_ids)
        frontier = set(node_ids)
        edges = []
        truncated = False
        for _ in range(depth):
            if not frontier:
                break
            column, other = ("from_node_id", "to_node_id") if direction == "out" else ("to_node_id", "from_node_id")
            placeholders = ",".join("?" for _ in frontier)
            query = f"SELECT * FROM edges WHERE snapshot_id=? AND {column} IN ({placeholders})"
            params = [snapshot["snapshot_id"], *frontier]
            if edge_types:
                types = ",".join("?" for _ in edge_types)
                query += f" AND edge_type IN ({types})"
                params.extend(edge_types)
            next_frontier = set()
            for row in self.connection.execute(query, params):
                if len(edges) >= edge_budget:
                    truncated = True
                    break
                edges.append(dict(row))
                candidate = row[other]
                if candidate not in visited:
                    if len(visited) >= node_budget:
                        truncated = True
                        break
                    visited.add(candidate)
                    next_frontier.add(candidate)
            if truncated:
                break
            frontier = next_frontier
        return {"ok": True, "edges": edges, "paths": [], "truncated": truncated, "coverage": {"nodes": len(visited), "edges": len(edges)}, "snapshot_ref": self._snapshot_ref(snapshot)}

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
