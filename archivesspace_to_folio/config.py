from dataclasses import dataclass, field
from typing import Optional
import yaml


@dataclass
class ASpaceConfig:
    base_url: str
    username: str
    password: str
    public_domain: str = ""
    repository_ids: list[int] = field(default_factory=list)


@dataclass
class FolioConfig:
    gateway_url: str
    tenant_id: str
    username: str
    password: str


@dataclass
class FiltersConfig:
    published: Optional[bool] = True
    finding_aid_status: Optional[str] = "Completed"


@dataclass
class HoldingsMappingConfig:
    type: str
    source: str = "FOLIO"
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class ItemsMappingConfig:
    material_type: str
    permanent_loan_type: str
    electronic_access_relationship: Optional[str] = None
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class MappingConfig:
    holdings: HoldingsMappingConfig
    items: ItemsMappingConfig
    managed_statistical_code: str
    owned_statistical_code: str
    location_key_field: str
    skip_unmapped_location: bool
    suppressed_statistical_code: Optional[str] = None
    suppress_non_managed: bool = True
    location_map: dict[str, str] = field(default_factory=dict)
    default_location: Optional[str] = None


@dataclass
class Config:
    aspace: ASpaceConfig
    folio: FolioConfig
    filters: FiltersConfig
    mapping: MappingConfig
    state_file: Optional[str] = None


def load_config(path: str) -> Config:
    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    aspace_raw = raw.get("aspace", {})
    folio_raw = raw.get("folio", {})
    filters_raw = raw.get("filters", {})
    mapping_raw = raw.get("mapping", {})
    holdings_raw = mapping_raw.get("holdings", {})
    items_raw = mapping_raw.get("items", {})

    location_map_raw = mapping_raw.get("location_map") or {}
    location_map = {str(k): v for k, v in location_map_raw.items()}

    return Config(
        state_file=raw.get("state_file", None),
        aspace=ASpaceConfig(
            base_url=aspace_raw["base_url"],
            username=aspace_raw["username"],
            password=aspace_raw["password"],
            public_domain=aspace_raw.get("public_domain", ""),
            repository_ids=[int(r) for r in aspace_raw.get("repository_ids", [])],
        ),
        folio=FolioConfig(
            gateway_url=folio_raw["gateway_url"],
            tenant_id=folio_raw["tenant_id"],
            username=folio_raw["username"],
            password=folio_raw["password"],
        ),
        filters=FiltersConfig(
            published=filters_raw.get("published", None),
            finding_aid_status=filters_raw.get("finding_aid_status", None),
        ),
        mapping=MappingConfig(
            holdings=HoldingsMappingConfig(
                type=holdings_raw["type"],
                source=holdings_raw.get("source", "FOLIO"),
                fields=holdings_raw.get("fields") or {},
            ),
            items=ItemsMappingConfig(
                material_type=items_raw["material_type"],
                permanent_loan_type=items_raw["permanent_loan_type"],
                electronic_access_relationship=items_raw.get("electronic_access_relationship", None),
                fields=items_raw.get("fields") or {},
            ),
            managed_statistical_code=mapping_raw["managed_statistical_code"],
            owned_statistical_code=mapping_raw["owned_statistical_code"],
            suppressed_statistical_code=mapping_raw.get("suppressed_statistical_code", None),
            suppress_non_managed=mapping_raw.get("suppress_non_managed", True),
            location_map=location_map,
            location_key_field=mapping_raw["location_key_field"],
            skip_unmapped_location=mapping_raw["skip_unmapped_location"],
            default_location=mapping_raw.get("default_location", None),
        ),
    )
