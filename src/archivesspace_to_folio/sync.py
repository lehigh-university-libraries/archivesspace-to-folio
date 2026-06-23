import logging
from collections import defaultdict
from typing import Optional

from . import aspace as aspace
from . import folio as folio
from .config import Config
from .utils import parse_final_id_from_uri

logger = logging.getLogger(__name__)


def sync(
    config: Config,
    repository_id: Optional[int] = None,
    resource_id: Optional[int] = None,
    delete_mode: bool = False,
) -> None:
    aspace_client = aspace.make_client(config.aspace)
    folio_client = folio.make_client(config.folio)

    logger.info("Resolving FOLIO reference data...")
    ref = folio.resolve_reference_data(folio_client, config.settings)

    repo_ids = [repository_id] if repository_id else config.aspace.repository_ids
    repos = aspace.get_repositories(aspace_client, repo_ids)
    logger.info("Processing %d repository/repositories", len(repos))

    for repo in repos:
        repo_id = parse_final_id_from_uri(repo["uri"])
        collections = aspace.get_collections(
            aspace_client,
            repo_id,
            config.filters,
            resource_id=resource_id,
        )
        logger.info(
            "Repository %d: %d collection(s) in scope", repo_id, len(collections)
        )

        for collection in collections:
            _sync_collection(
                collection,
                repo_id,
                config,
                aspace_client,
                folio_client,
                ref,
                delete_mode,
            )


def _sync_collection(
    collection: dict,
    repo_id: int,
    config: Config,
    aspace_client,
    folio_client,
    ref: folio.FolioReferenceData,
    delete_mode: bool,
) -> None:
    coll_id = parse_final_id_from_uri(collection["uri"])
    aspace_url = f"https://{config.settings.aspace_domain}/repositories/{repo_id}/resources/{coll_id}"
    title = collection.get("title", collection["uri"])

    instance = folio.find_instance_by_aspace_url(folio_client, aspace_url)
    if not instance:
        logger.info(
            "No FOLIO instance found for collection '%s' (%s)", title, aspace_url
        )
        return

    if delete_mode:
        logger.info("Deleting managed records for '%s'", title)
        folio.delete_managed_records(
            folio_client, instance["id"], ref.managed_stat_code_id
        )
        return

    tlcs = aspace.get_top_containers(aspace_client, repo_id, coll_id)
    tlcs = aspace.filter_child_tlcs(tlcs)
    logger.info(
        "Collection '%s': %d top-level container(s) after filtering", title, len(tlcs)
    )

    location_groups: dict[Optional[int], list[dict]] = defaultdict(list)
    for tlc in tlcs:
        loc_id = aspace.get_tlc_location_id(tlc)
        if loc_id is None:
            logger.warning("TLC %s has no current location", tlc.get("uri"))
        location_groups[loc_id].append(tlc)

    for aspace_loc_id, tlc_group in location_groups.items():
        folio_location_name = (
            config.settings.location_map.get(aspace_loc_id)
            if aspace_loc_id is not None
            else None
        )
        folio_location_name = folio_location_name or config.settings.default_location
        if not folio_location_name:
            logger.warning(
                "No FOLIO location mapping for ASpace location ID %s; skipping %d TLC(s)",
                aspace_loc_id,
                len(tlc_group),
            )
            continue

        folio_location_id = ref.location_name_to_id.get(folio_location_name)
        if not folio_location_id:
            logger.warning(
                "FOLIO location '%s' not found; skipping %d TLC(s)",
                folio_location_name,
                len(tlc_group),
            )
            continue

        holdings, holdings_created = folio.create_or_update_holdings(
            folio_client,
            instance["id"],
            folio_location_id,
            collection,
            ref,
            config.settings,
        )
        if holdings_created:
            if config.settings.suppress_non_managed_holdings:
                folio.suppress_non_managed_holdings(
                    folio_client,
                    instance["id"],
                    holdings["id"],
                    ref.managed_stat_code_id,
                    ref.suppressed_stat_code_id,
                )
        for tlc in tlc_group:
            folio.create_or_update_item(
                folio_client,
                holdings["id"],
                tlc,
                repo_id,
                ref,
                config.settings,
            )
