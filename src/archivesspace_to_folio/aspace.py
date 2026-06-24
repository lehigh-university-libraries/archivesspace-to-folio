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


def filter_child_tlcs(tlcs: list[dict]) -> list[dict]:
    # TODO: Need test case for child container filtering.
    logger.warning("Child container filtering is not yet tested.")
    tlc_uris = {t.get("uri") for t in tlcs}
    roots = []
    for tlc in tlcs:
        parent_ref = tlc.get("parent", {})
        if isinstance(parent_ref, dict):
            parent_uri = parent_ref.get("ref")
        else:
            parent_uri = None
        if parent_uri and parent_uri in tlc_uris:
            logger.warning(
                "Top container %s is a child of %s — skipping",
                tlc.get("uri"),
                parent_uri,
            )
        else:
            roots.append(tlc)
    return roots


def get_tlc_location_id(tlc: dict) -> Optional[int]:
    # TODO: See if this field is ever actually used.
    for loc in tlc.get("container_locations", []):
        if loc.get("status") == "current":
            ref = loc.get("ref", "")
            if ref:
                try:
                    return parse_final_id_from_uri(ref)
                except (ValueError, IndexError):
                    pass
    return None
