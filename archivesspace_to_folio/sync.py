import logging
from collections import defaultdict
from typing import Optional

from . import aspace as aspace
from . import field_functions
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

    folio_ref, aspace_locations = _resolve_reference_data(
        aspace_client, folio_client, config
    )

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
                folio_ref,
                aspace_locations,
                delete_mode,
            )


def _resolve_reference_data(
    aspace_client, folio_client, config: Config
) -> tuple[folio.FolioReferenceData, dict[str, dict]]:
    ea_relationship_id = None
    if config.mapping.items.electronic_access_relationship:
        ea_relationship_id = folio.lookup_ref(
            folio_client,
            "/electronic-access-relationships",
            "electronicAccessRelationships",
            "name",
            config.mapping.items.electronic_access_relationship,
        )
    field_functions.configure(
        public_domain=config.aspace.public_domain,
        electronic_access_relationship_id=ea_relationship_id,
    )
    logger.info("Resolving FOLIO reference data...")
    folio_ref = folio.resolve_reference_data(folio_client, config.mapping)
    logger.info("Loading ASpace location data...")
    aspace_locations = aspace.get_locations(aspace_client)
    logger.info("Loaded %d ASpace location(s)", len(aspace_locations))
    return folio_ref, aspace_locations


def _sync_collection(
    collection: dict,
    repo_id: int,
    config: Config,
    aspace_client,
    folio_client,
    folio_ref: folio.FolioReferenceData,
    aspace_locations: dict[str, dict],
    delete_mode: bool,
) -> None:
    coll_id = parse_final_id_from_uri(collection["uri"])
    aspace_url = f"https://{config.aspace.public_domain}/repositories/{repo_id}/resources/{coll_id}"
    title = collection.get("title", collection["uri"])

    instance = folio.find_instance_by_aspace_url(folio_client, aspace_url)
    if not instance:
        logger.info(
            "No FOLIO instance found for collection '%s' (%s)", title, aspace_url
        )
        return

    if delete_mode:
        logger.info("Deleting managed records for '%s'", title)
        folio.delete_managed_records(folio_client, instance["id"], folio_ref)
        return

    tlcs = aspace.get_top_containers(aspace_client, repo_id, coll_id)
    tlcs = aspace.filter_child_tlcs(tlcs)
    logger.info(
        "Collection '%s': %d top-level container(s) after filtering", title, len(tlcs)
    )

    location_groups: dict[Optional[str], list[dict]] = defaultdict(list)
    for tlc in tlcs:
        loc_key = aspace.get_tlc_location_key(
            tlc, aspace_locations, config.mapping.location_key_field
        )
        if loc_key is None:
            logger.warning("TLC %s has no location", tlc.get("uri"))
        location_groups[loc_key].append(tlc)

    for loc_key, tlc_group in location_groups.items():
        if loc_key is not None and loc_key not in config.mapping.location_map:
            if config.mapping.skip_unmapped_location:
                logger.warning(
                    "ASpace location key %r not in location_map (config problem); skipping %d TLC(s)",
                    loc_key,
                    len(tlc_group),
                )
                continue

        folio_location_code = (
            config.mapping.location_map.get(loc_key) if loc_key is not None else None
        )
        folio_location_code = folio_location_code or config.mapping.default_location
        if not folio_location_code:
            logger.warning(
                "No FOLIO location for ASpace location key %r; skipping %d TLC(s)",
                loc_key,
                len(tlc_group),
            )
            continue

        folio_location_id = folio_ref.location_code_to_id.get(folio_location_code)
        if not folio_location_id:
            logger.warning(
                "FOLIO location '%s' not found; skipping %d TLC(s)",
                folio_location_code,
                len(tlc_group),
            )
            continue

        holdings, holdings_created = folio.create_or_update_holdings(
            folio_client,
            instance["id"],
            folio_location_id,
            collection,
            folio_ref,
            config.mapping,
        )
        if holdings_created:
            if config.mapping.suppress_non_managed_holdings:
                folio.suppress_non_managed_holdings(
                    folio_client,
                    instance["id"],
                    holdings["id"],
                    folio_ref.managed_stat_code_id,
                    folio_ref.suppressed_stat_code_id,
                )
        for tlc in tlc_group:
            folio.create_or_update_item(
                folio_client,
                holdings["id"],
                tlc,
                repo_id,
                folio_ref,
                config.mapping,
            )
