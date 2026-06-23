# archivesspace-to-folio

Syncs ArchivesSpace containers into FOLIO inventory to make archival materials requestable.

For each published, complete ArchivesSpace collection that has a matching FOLIO instance record, the tool:

- Creates a **holdings record** per unique ASpace permanent location
- Creates an **item record** per top-level container (box, folder, etc.)
- Tags all managed records with a configurable statistical code (`MANAGED_VIA_ARCHIVESSPACE`)
- Optionally suppresses any pre-existing unmanaged holdings and items on the same instance

The tool is designed to run as a cron job (e.g. daily), and is fully idempotent — re-running it updates existing managed records rather than creating duplicates.

## Requirements

- Python 3.10+
- Access to an ArchivesSpace instance (staff API)
- Access to a FOLIO instance (Okapi API)

## Installation

```bash
pip install -e .
```

## Configuration

Copy `config.yaml.example` to `config.yaml` and fill in your credentials and settings:

```bash
cp config.yaml.example config.yaml
```

Key settings:

| Setting | Description |
|---|---|
| `aspace.base_url` | ArchivesSpace base URL |
| `aspace.repository_ids` | List of repo IDs to process; empty = all repos |
| `folio.gateway_url` | FOLIO Okapi gateway URL |
| `filters.published` | Only process published resources (default: `true`) |
| `filters.finding_aid_status` | Only process resources with this status (default: `"Completed"`); set to `null` to skip |
| `settings.statistical_code` | Name of the FOLIO statistical code that marks managed records |
| `settings.location_map` | Maps ASpace location IDs (integers) to FOLIO location names |

## Usage

**Full sync** (all configured repositories):
```bash
python -m archivesspace_to_folio --config config.yaml
```

**Sync a single repository:**
```bash
python -m archivesspace_to_folio --repository 7
```

**Sync a single collection:**
```bash
python -m archivesspace_to_folio --repository 7 --collection 216
```

**Delete all managed records for a collection:**
```bash
python -m archivesspace_to_folio --repository 7 --collection 216 --delete
```

**Adjust log verbosity:**
```bash
python -m archivesspace_to_folio --log-level DEBUG
```

## How matching works

A FOLIO instance is matched to an ASpace collection when the instance has an **electronic access** entry whose URI equals the collection's public ASpace URL, e.g.:

```
https://archivesspace.example.edu/repositories/4/resources/231
```

Instance records must be created separately; this tool does not create or delete instance records.

## Managed record lifecycle

- Records are identified as managed by the configured statistical code.
- On each run, managed records are updated if their source data has changed.
- When a new managed holdings record is added to an instance that has pre-existing unmanaged holdings, the unmanaged holdings (and their items) are suppressed (`discoverySuppressed=true`). This behavior is configurable.
- The `--delete` flag removes all managed holdings and items but does not unsuppress previously suppressed records.
