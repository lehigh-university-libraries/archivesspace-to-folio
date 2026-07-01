# archivesspace-to-folio

Syncs ArchivesSpace containers into FOLIO inventory to make archival materials requestable.

For each published, complete ArchivesSpace collection that has a matching FOLIO instance record, the tool:

- Creates a **holdings record** per unique ASpace permanent location
- Creates an **item record** per top-level container (box, folder, etc.)
- Tags all managed records with configurable statistical codes
- Optionally suppresses any pre-existing unmanaged holdings and items on the same instance

The tool is designed to run as a cron job (e.g. daily), and is fully idempotent — re-running it updates existing managed records rather than creating duplicates.

## Requirements

- Python 3.10+
- Access to an ArchivesSpace instance (staff API)
- Access to a FOLIO instance (Okapi API)

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Copy `config.yaml.example` to `config.yaml` and fill in your credentials and settings:

```bash
cp config.yaml.example config.yaml
```

See [`config.yaml.example`](config.yaml.example) for all available options and documentation.

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

Records created by this tool are identified by two configurable statistical codes:

- **`managed_statistical_code`** — applied to all holdings and items touched by the tool (including pre-existing holdings that the tool adopts)
- **`owned_statistical_code`** — applied only to holdings records that the tool itself created

On each run, managed records are updated if their source data has changed.

When a new managed holdings record is added to an instance that already has unmanaged holdings, the unmanaged holdings (and their items) are optionally suppressed (`discoverySuppress=true`). This behavior is configurable.

The `--delete` flag removes all managed items and any holdings the tool created. Holdings that were adopted (pre-existing when the tool first ran) are instead released: the managed statistical code is removed and they are unsuppressed if the tool had suppressed them.
