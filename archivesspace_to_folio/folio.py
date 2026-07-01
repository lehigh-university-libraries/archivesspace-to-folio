import logging
from dataclasses import dataclass
from typing import Optional

from folioclient import FolioClient

from .config import FolioConfig, MappingConfig
from .utils import parse_final_id_from_uri, render_field_value

logger = logging.getLogger(__name__)

_HOLDINGS_PUT_EXCLUDE_FIELDS = ["holdingsItems", "bareHoldingsItems"]


@dataclass
class FolioReferenceData:
    material_type_id: str
    permanent_loan_type_id: str
    holdings_type_id: str
    holdings_source_id: str
    managed_stat_code_id: str
    owned_stat_code_id: str
    suppressed_stat_code_id: Optional[str]
    location_code_to_id: dict[str, str]


def make_client(config: FolioConfig) -> FolioClient:
    return FolioClient(
        config.gateway_url,
        config.tenant_id,
        config.username,
        config.password,
    )


def resolve_reference_data(
    fc: FolioClient, settings: MappingConfig
) -> FolioReferenceData:
    material_type_id = lookup_ref(
        fc, "/material-types", "mtypes", "name", settings.items.material_type
    )
    loan_type_id = lookup_ref(
        fc, "/loan-types", "loantypes", "name", settings.items.permanent_loan_type
    )
    holdings_type_id = lookup_ref(
        fc, "/holdings-types", "holdingsTypes", "name", settings.holdings.type
    )
    holdings_source_id = lookup_ref(
        fc,
        "/holdings-sources",
        "holdingsRecordsSources",
        "name",
        settings.holdings.source,
    )
    managed_stat_code_id = lookup_ref(
        fc,
        "/statistical-codes",
        "statisticalCodes",
        "code",
        settings.managed_statistical_code,
    )
    owned_stat_code_id = lookup_ref(
        fc,
        "/statistical-codes",
        "statisticalCodes",
        "code",
        settings.owned_statistical_code,
    )
    suppressed_stat_code_id = (
        lookup_ref(
            fc,
            "/statistical-codes",
            "statisticalCodes",
            "code",
            settings.suppressed_statistical_code,
        )
        if settings.suppressed_statistical_code
        else None
    )

    locations = list(
        fc.folio_get_all("/locations", key="locations", query="cql.allRecords=1")
    )
    location_code_to_id = {loc["code"]: loc["id"] for loc in locations}

    return FolioReferenceData(
        material_type_id=material_type_id,
        permanent_loan_type_id=loan_type_id,
        holdings_type_id=holdings_type_id,
        holdings_source_id=holdings_source_id,
        managed_stat_code_id=managed_stat_code_id,
        owned_stat_code_id=owned_stat_code_id,
        suppressed_stat_code_id=suppressed_stat_code_id,
        location_code_to_id=location_code_to_id,
    )


def lookup_ref(fc: FolioClient, path: str, key: str, field: str, value: str) -> str:
    records = list(fc.folio_get_all(path, key=key, query=f'{field}=="{value}"'))
    if not records:
        raise ValueError(f"No FOLIO record found at {path} where {field}={value!r}")
    return records[0]["id"]


def find_instance_by_aspace_url(fc: FolioClient, url: str) -> Optional[dict]:
    results = list(
        fc.folio_get_all(
            "/search/instances",
            key="instances",
            query=f'electronicAccess.uri=="{url}"',
            query_params={"expandAll": True},
        )
    )
    if not results:
        return None
    if len(results) > 1:
        logger.error("Multiple FOLIO instances match URL %s; skipping collection", url)
        return None
    return results[0]


def find_item_by_barcode(fc: FolioClient, barcode: str) -> Optional[dict]:
    results = list(
        fc.folio_get_all(
            "/item-storage/items",
            key="items",
            query=f'barcode=="{barcode}"',
        )
    )
    return results[0] if results else None


def get_managed_holdings(
    fc: FolioClient, instance_id: str, managed_stat_code_id: str
) -> list[dict]:
    return list(
        fc.folio_get_all(
            "/holdings-storage/holdings",
            key="holdingsRecords",
            query=f'instanceId=="{instance_id}" and statisticalCodeIds="{managed_stat_code_id}"',
        )
    )


def get_managed_items(
    fc: FolioClient, holdings_id: str, managed_stat_code_id: str
) -> list[dict]:
    return list(
        fc.folio_get_all(
            "/item-storage/items",
            key="items",
            query=f'holdingsRecordId=="{holdings_id}" and statisticalCodeIds="{managed_stat_code_id}"',
        )
    )


def create_or_update_holdings(
    fc: FolioClient,
    instance_id: str,
    folio_location_id: str,
    collection: dict,
    ref: FolioReferenceData,
    settings: MappingConfig,
) -> tuple[dict, bool]:
    existing = list(
        fc.folio_get_all(
            "/holdings-storage/holdings",
            key="holdingsRecords",
            query=(
                f'instanceId=="{instance_id}"'
                f' and permanentLocationId=="{folio_location_id}"'
            ),
        )
    )
    desired = {
        "instanceId": instance_id,
        "permanentLocationId": folio_location_id,
        "holdingsTypeId": ref.holdings_type_id,
        "sourceId": ref.holdings_source_id,
    }
    for folio_field, value_spec in settings.holdings.fields.items():
        desired[folio_field] = render_field_value(value_spec, collection)

    if existing:
        holdings = existing[0]
        updated = dict(holdings)
        code_missing = ref.managed_stat_code_id not in updated.get(
            "statisticalCodeIds", []
        )
        updated = _ensure_stat_code(updated, ref.managed_stat_code_id)
        for folio_field, value_spec in settings.holdings.fields.items():
            updated[folio_field] = render_field_value(value_spec, collection)
        if _record_differs(holdings, desired) or code_missing:
            fc.folio_put(
                f"/holdings-storage/holdings/{updated['id']}",
                payload=_strip_fields(updated, _HOLDINGS_PUT_EXCLUDE_FIELDS),
            )
            logger.info("Updated holdings %s", updated["id"])
        return updated, False

    result = fc.folio_post(
        "/holdings-storage/holdings",
        payload={
            **desired,
            "statisticalCodeIds": [ref.managed_stat_code_id, ref.owned_stat_code_id],
        },
    )
    logger.info("Created holdings %s", result["id"])
    return result, True


def create_or_update_item(
    fc: FolioClient,
    holdings_id: str,
    tlc: dict,
    repo_id: int,
    ref: FolioReferenceData,
    settings: MappingConfig,
) -> tuple[dict, bool]:
    tlc_id = parse_final_id_from_uri(tlc.get("uri", ""))
    barcode = f"AS_TEMP_{repo_id}_{tlc_id}"
    desired = {
        "holdingsRecordId": holdings_id,
        "barcode": barcode,
        "materialTypeId": ref.material_type_id,
        "permanentLoanTypeId": ref.permanent_loan_type_id,
        "status": {"name": "Available"},
        "statisticalCodeIds": [ref.managed_stat_code_id],
    }
    for folio_field, value_spec in settings.items.fields.items():
        desired[folio_field] = render_field_value(value_spec, tlc)

    existing = find_item_by_barcode(fc, barcode)
    if existing:
        updated = dict(existing)
        updated = _ensure_stat_code(updated, ref.managed_stat_code_id)
        for folio_field, value_spec in settings.items.fields.items():
            updated[folio_field] = render_field_value(value_spec, tlc)
        if _record_differs(existing, desired):
            fc.folio_put(f"/item-storage/items/{updated['id']}", payload=updated)
            logger.info("Updated item %s (barcode %s)", updated["id"], barcode)
        return updated, False

    result = fc.folio_post("/item-storage/items", payload=desired)
    logger.info("Created item %s (barcode %s)", result["id"], barcode)
    return result, True


def suppress_non_managed_holdings(
    fc: FolioClient,
    instance_id: str,
    except_id: str,
    managed_stat_code_id: str,
    suppressed_stat_code_id: Optional[str] = None,
) -> None:
    all_holdings = list(
        fc.folio_get_all(
            "/holdings-storage/holdings",
            key="holdingsRecords",
            query=f'instanceId=="{instance_id}"',
        )
    )
    for holdings in all_holdings:
        if holdings["id"] == except_id:
            continue
        if managed_stat_code_id in holdings.get("statisticalCodeIds", []):
            continue
        already_suppressed = holdings.get("discoverySuppress")
        if not already_suppressed or (
            suppressed_stat_code_id
            and suppressed_stat_code_id not in holdings.get("statisticalCodeIds", [])
        ):
            holdings["discoverySuppress"] = True
            if suppressed_stat_code_id:
                holdings = _ensure_stat_code(holdings, suppressed_stat_code_id)
            if not already_suppressed or _record_differs(
                holdings, {"statisticalCodeIds": [suppressed_stat_code_id]}
            ):
                fc.folio_put(
                    f"/holdings-storage/holdings/{holdings['id']}",
                    payload=_strip_fields(holdings, _HOLDINGS_PUT_EXCLUDE_FIELDS),
                )
                logger.info("Suppressed non-managed holdings %s", holdings["id"])

        items = list(
            fc.folio_get_all(
                "/item-storage/items",
                key="items",
                query=f'holdingsRecordId=="{holdings["id"]}"',
            )
        )
        for item in items:
            already_suppressed_item = item.get("discoverySuppress")
            if not already_suppressed_item or (
                suppressed_stat_code_id
                and suppressed_stat_code_id not in item.get("statisticalCodeIds", [])
            ):
                item["discoverySuppress"] = True
                if suppressed_stat_code_id:
                    item = _ensure_stat_code(item, suppressed_stat_code_id)
                if not already_suppressed_item or _record_differs(
                    item, {"statisticalCodeIds": [suppressed_stat_code_id]}
                ):
                    fc.folio_put(f"/item-storage/items/{item['id']}", payload=item)
                    logger.info(
                        "Suppressed item %s on non-managed holdings", item["id"]
                    )


def delete_managed_records(
    fc: FolioClient, instance_id: str, ref: FolioReferenceData
) -> None:
    holdings_list = get_managed_holdings(fc, instance_id, ref.managed_stat_code_id)
    for holdings in holdings_list:
        items = get_managed_items(fc, holdings["id"], ref.managed_stat_code_id)
        for item in items:
            fc.folio_delete(f"/item-storage/items/{item['id']}")
            logger.info("Deleted owned item %s", item["id"])
        if ref.owned_stat_code_id in holdings.get("statisticalCodeIds", []):
            fc.folio_delete(f"/holdings-storage/holdings/{holdings['id']}")
            logger.info("Deleted owned holdings %s", holdings["id"])
        else:
            _release_adopted_holdings(fc, holdings, ref)


def _release_adopted_holdings(
    fc: FolioClient, holdings: dict, ref: FolioReferenceData
) -> None:
    updated = dict(holdings)
    codes_to_remove = {ref.managed_stat_code_id}
    if ref.suppressed_stat_code_id:
        codes_to_remove.add(ref.suppressed_stat_code_id)
    was_app_suppressed = (
        ref.suppressed_stat_code_id
        and ref.suppressed_stat_code_id in holdings.get("statisticalCodeIds", [])
    )
    updated["statisticalCodeIds"] = [
        c for c in updated.get("statisticalCodeIds", []) if c not in codes_to_remove
    ]
    if was_app_suppressed:
        updated["discoverySuppress"] = False
    fc.folio_put(
        f"/holdings-storage/holdings/{updated['id']}",
        payload=_strip_fields(updated, _HOLDINGS_PUT_EXCLUDE_FIELDS),
    )
    logger.info("Released adopted holdings %s", holdings["id"])


def _record_differs(existing: dict, desired: dict) -> bool:
    for key, value in desired.items():
        if not _values_match(existing.get(key), value):
            return True
    return False


def _values_match(existing_value, desired_value) -> bool:
    if isinstance(desired_value, list):
        return all(item in (existing_value or []) for item in desired_value)
    if isinstance(desired_value, dict):
        if not isinstance(existing_value, dict):
            return False
        return all(existing_value.get(k) == v for k, v in desired_value.items())
    return existing_value == desired_value


def _strip_fields(record: dict, fields: list[str]) -> dict:
    return {k: v for k, v in record.items() if k not in fields}


def _ensure_stat_code(record: dict, stat_code_id: str) -> dict:
    codes = record.setdefault("statisticalCodeIds", [])
    if stat_code_id not in codes:
        codes.append(stat_code_id)
    return record
