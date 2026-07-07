import dacite
from dataclasses import dataclass, field
from typing import Optional
import yaml


@dataclass
class ASpaceConfig:
    base_url: str
    username: str
    password: str
    public_domain: str = ""


@dataclass
class FolioConfig:
    gateway_url: str
    tenant_id: str
    username: str
    password: str


@dataclass
class CollectionFiltersConfig:
    published: Optional[bool] = None
    finding_aid_status: Optional[str] = None


@dataclass
class RepositoryFiltersConfig:
    published: Optional[bool] = None
    repository_ids: list[int] = field(default_factory=list)


@dataclass
class FiltersConfig:
    collections: CollectionFiltersConfig = field(default_factory=CollectionFiltersConfig)
    repositories: RepositoryFiltersConfig = field(default_factory=RepositoryFiltersConfig)


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
    return dacite.from_dict(Config, raw)
