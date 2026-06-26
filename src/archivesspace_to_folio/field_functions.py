from typing import Callable

# Registry for field value functions.
# Key: name used after "fn:" in config values (e.g. "fn:my_func" → key "my_func").
# Value: callable (record: dict) -> str, where record is the source ASpace object
#        (collection dict for holdings fields, TLC dict for item fields).
REGISTRY: dict[str, Callable[[dict], str]] = {}
