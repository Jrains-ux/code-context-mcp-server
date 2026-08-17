from code_context.policies.permission import PermissionMatrix


class ToolRegistry:
    def __init__(self, matrix=None):
        self.matrix = matrix or PermissionMatrix()

    def diagnose(self, skill, registered_tools):
        required = self.matrix.allowed(skill)
        missing = sorted(required - set(registered_tools))
        if missing:
            return {"ok": False, "code": "TOOL_CONTRACT_MISSING", "missing": missing}
        return {"ok": True, "missing": []}

    def register_all(self, connection):
        rows = [(tool, skill) for skill in self.matrix._matrix for tool in self.matrix.allowed(skill)]
        connection.executemany(
            "INSERT OR REPLACE INTO tool_registry(tool_name, skill, enabled) VALUES (?,?,1)",
            rows,
        )
        connection.commit()

    def diagnose_all(self, connection):
        registered = {
            row[0]
            for row in connection.execute("SELECT tool_name FROM tool_registry WHERE enabled=1")
        }
        for skill in self.matrix._matrix:
            result = self.diagnose(skill, registered)
            if not result["ok"]:
                result["skill"] = skill
                return result
        return {"ok": True, "missing": []}
