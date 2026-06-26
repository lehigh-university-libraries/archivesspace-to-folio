import logging
import re

logger = logging.getLogger(__name__)


def parse_final_id_from_uri(uri: str) -> int:
    return int(uri.rstrip("/").split("/")[-1])


def _resolve_aspace_value(field_name: str, value) -> str:
    if isinstance(value, list):
        if len(value) > 1:
            logger.warning(
                "ASpace field %r has %d values; using first: %r",
                field_name,
                len(value),
                value[0],
            )
        return str(value[0]) if value else ""
    return str(value or "")


def render_aspace_format(fmt: str, record: dict) -> str:
    def replace(m):
        field_name = m.group(1)
        return _resolve_aspace_value(field_name, record.get(field_name))

    return re.sub(r"\{(\w+)\}", replace, fmt).strip()


def render_field_value(
    value_spec: str, record: dict, functions: dict | None = None
) -> str:
    if value_spec.startswith("fn:"):
        func_name = value_spec[3:]
        func = (functions or {}).get(func_name)
        if not func:
            raise ValueError(f"Unknown field function: {func_name!r}")
        return func(record)
    return render_aspace_format(value_spec, record)
