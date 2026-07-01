# Populated at startup via configure() before any sync runs.
context: dict = {}


def configure(**kwargs) -> None:
    context.update(kwargs)


def electronic_access_from_uri(record: dict) -> list:
    uri = record.get("uri", "")
    public_domain = context.get("public_domain", "")
    entry = {"uri": f"https://{public_domain}{uri}"}
    relationship_id = context.get("electronic_access_relationship_id")
    if relationship_id:
        entry["relationshipId"] = relationship_id
    return [entry]
