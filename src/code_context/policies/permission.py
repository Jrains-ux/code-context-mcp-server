class PermissionMatrix:
    _matrix = {
        "Bootstrap": {"ingest", "detect_conflicts", "check_coverage", "publish", "job", "status"},
        "Sync": {"detect_conflicts", "check_coverage", "publish", "job", "status", "update"},
        "Query": {"lexical_search", "search", "query", "relation_expand", "search_paths", "resolve_business_context", "dict_read", "biz_mapping"},
        "Mining": {"lexical_search", "search", "query", "relation_expand", "search_paths", "confirm", "dict_read", "biz_mapping", "dict_write", "annotate_path"},
        "Knowledge": {"lexical_search", "search", "query", "relation_expand", "dict_read", "biz_mapping"},
        "Evaluation": {"lexical_search", "search", "query", "relation_expand", "search_paths", "confirm", "resolve_business_context"},
        "Admin": {"dict_read", "biz_mapping", "push", "health_check"},
    }

    def allowed(self, skill):
        return set(self._matrix.get(skill, set()))

    def can_call(self, skill, tool):
        return tool in self.allowed(skill)
