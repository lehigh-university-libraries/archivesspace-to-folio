import re


def parse_final_id_from_uri(uri: str) -> int:
    return int(uri.rstrip("/").split("/")[-1])


def render_aspace_format(fmt: str, record: dict) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(record.get(m.group(1)) or ""), fmt).strip()


def render_field_value(value_spec: str, record: dict, functions: dict | None = None) -> str:
    if value_spec.startswith("fn:"):
        func_name = value_spec[3:]
        func = (functions or {}).get(func_name)
        if not func:
            raise ValueError(f"Unknown field function: {func_name!r}")
        return func(record)
    return render_aspace_format(value_spec, record)
