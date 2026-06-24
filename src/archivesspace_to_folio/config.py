from dataclasses import dataclass, field
from typing import Optional
import yaml


@dataclass
class ASpaceConfig:
    base_url: str
    username: str
    password: str
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
class SettingsConfig:
    aspace_domain: str
    material_type: str
    permanent_loan_type: str
    holdings_type: str
    managed_statistical_code: str
    holdings_call_number_aspace_format: str
    holdings_source: str = "FOLIO"
    suppressed_statistical_code: Optional[str] = None
    item_call_number_aspace_format: Optional[str] = None
    suppress_non_managed_holdings: bool = True
    location_map: dict[int, str] = field(default_factory=dict)
    default_location: Optional[str] = None


@dataclass
class Config:
    aspace: ASpaceConfig
    folio: FolioConfig
    filters: FiltersConfig
    settings: SettingsConfig


def load_config(path: str) -> Config:
    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    aspace_raw = raw.get("aspace", {})
    folio_raw = raw.get("folio", {})
    filters_raw = raw.get("filters", {})
    settings_raw = raw.get("settings", {})

    location_map_raw = settings_raw.get("location_map") or {}
    location_map = {int(k): v for k, v in location_map_raw.items()}

    return Config(
        aspace=ASpaceConfig(
            base_url=aspace_raw["base_url"],
            username=aspace_raw["username"],
            password=aspace_raw["password"],
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
        settings=SettingsConfig(
            aspace_domain=settings_raw["aspace_domain"],
            material_type=settings_raw["material_type"],
            permanent_loan_type=settings_raw["permanent_loan_type"],
            holdings_type=settings_raw["holdings_type"],
            managed_statistical_code=settings_raw["managed_statistical_code"],
            holdings_source=settings_raw.get("holdings_source", "FOLIO"),
            suppressed_statistical_code=settings_raw.get("suppressed_statistical_code", None),
            item_call_number_aspace_format=settings_raw.get("item_call_number_aspace_format", None),
            holdings_call_number_aspace_format=settings_raw["holdings_call_number_aspace_format"],
            suppress_non_managed_holdings=settings_raw.get(
                "suppress_non_managed_holdings", True
            ),
            location_map=location_map,
            default_location=settings_raw.get("default_location", None),
        ),
    )
