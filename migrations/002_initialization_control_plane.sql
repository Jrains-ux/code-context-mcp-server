CREATE TABLE IF NOT EXISTS initialization_manifest (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    project TEXT NOT NULL,
    workspace TEXT NOT NULL,
    source_revision TEXT NOT NULL,
    config_version TEXT NOT NULL,
    skills_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS manifest_tool_permissions (
    skill TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    PRIMARY KEY (skill, tool_name)
);
