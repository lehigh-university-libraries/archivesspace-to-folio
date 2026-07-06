import logging
from typing import Optional

from asnake.client import ASnakeClient

from .config import ASpaceConfig, FiltersConfig
from .utils import parse_final_id_from_uri

logger = logging.getLogger(__name__)


def make_client(config: ASpaceConfig) -> ASnakeClient:
    client = ASnakeClient(
        baseurl=config.base_url,
        username=config.username,
        password=config.password,
    )
    client.authorize()
    return client


def get_repositories(client: ASnakeClient, repo_ids: list[int]) -> list[dict]:
    all_repos = client.get("repositories").json()
    if not repo_ids:
        return all_repos
    id_set = set(repo_ids)
    return [r for r in all_repos if parse_final_id_from_uri(r["uri"]) in id_set]


def get_collections(
    client: ASnakeClient,
    repo_id: int,
    filters: FiltersConfig,
    resource_id: Optional[int] = None,
) -> list[dict]:
    if resource_id is not None:
        resource = client.get(f"repositories/{repo_id}/resources/{resource_id}").json()
        if _matches_filters(resource, filters):
            return [resource]
        return []

    page = 1
    results = []
    while True:
        resp = client.get(
            f"repositories/{repo_id}/resources",
            params={"page": page, "page_size": 100},
        ).json()
        for resource in resp.get("results", []):
            if _matches_filters(resource, filters):
                results.append(resource)
        if resp.get("last_page", 1) <= page:
            break
        page += 1
    return results


def _matches_filters(resource: dict, filters: FiltersConfig) -> bool:
    if filters.published is not None and resource.get("publish") != filters.published:
        return False
    if filters.finding_aid_status is not None:
        if resource.get("finding_aid_status") != filters.finding_aid_status:
            return False
    return True


def get_top_containers(
    client: ASnakeClient, repo_id: int, resource_id: int
) -> list[dict]:
    resource_uri = f"/repositories/{repo_id}/resources/{resource_id}"
    resp = client.get(
        f"repositories/{repo_id}/top_containers/search",
        params={"q": f'collection_uri_u_sstr:"{resource_uri}"', "page_size": 250},
    ).json()
    return resp.get("response", {}).get("docs", [])


def get_locations(client: ASnakeClient) -> dict[str, dict]:
    page = 1
    locations = {}
    while True:
        resp = client.get("locations", params={"page": page, "page_size": 100}).json()
        for loc in resp.get("results", []):
            locations[loc["uri"]] = loc
        if resp.get("last_page", 1) <= page:
            break
        page += 1
    return locations


def get_tlc_location_id(tlc: dict) -> Optional[int]:
    uris = tlc.get("location_uris", [])
    if not uris:
        return None
    if len(uris) > 1:
        logger.warning(
            "TLC %s has %d location URIs; using first",
            tlc.get("uri"),
            len(uris),
        )
    try:
        return parse_final_id_from_uri(uris[0])
    except (ValueError, IndexError):
        return None


def get_tlc_location_key(
    tlc: dict, locations: dict[str, dict], key_field: str = "classification"
) -> Optional[str]:
    loc_id = get_tlc_location_id(tlc)
    if loc_id is None:
        return None
    location = locations.get(f"/locations/{loc_id}")
    if location is None:
        logger.warning("ASpace location ID %d not found in loaded locations", loc_id)
        return None
    return location.get(key_field)
