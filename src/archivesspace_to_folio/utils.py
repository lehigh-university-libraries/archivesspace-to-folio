import re


def parse_final_id_from_uri(uri: str) -> int:
    return int(uri.rstrip("/").split("/")[-1])


def render_aspace_format(fmt: str, record: dict) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(record.get(m.group(1)) or ""), fmt).strip()
