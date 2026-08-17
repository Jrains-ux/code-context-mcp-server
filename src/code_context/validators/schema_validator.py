class ValidationError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def require_same_revisions(expected, actual):
    fields = ("source_revision", "index_revision", "config_version")
    for field in fields:
        if expected[field] != actual[field]:
            raise ValidationError("REVISION_MISMATCH", f"{field} does not match snapshot")
