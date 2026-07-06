import argparse
import logging
import sys

from .config import load_config
from .sync import sync


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="archivesspace-to-folio",
        description="Sync ArchivesSpace containers into FOLIO inventory as requestable items.",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        metavar="CONFIG",
        help="Path to config YAML file (default: ./config.yaml)",
    )
    parser.add_argument(
        "--repository",
        type=int,
        default=None,
        metavar="REPO_ID",
        help="Restrict to a specific ASpace repository ID",
    )
    parser.add_argument(
        "--collection",
        type=int,
        default=None,
        metavar="RESOURCE_ID",
        help="Restrict to a specific ASpace resource ID (requires --repository)",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete all managed holdings and items instead of syncing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Log actions but make no API writes",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    if args.collection is not None and args.repository is None:
        parser.error("--collection requires --repository")

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    if args.log_level != "DEBUG":
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

    config = load_config(args.config)

    sync(
        config,
        repository_id=args.repository,
        resource_id=args.collection,
        delete_mode=args.delete,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
