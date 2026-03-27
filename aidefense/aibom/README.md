# AI Defense AIBOM Module

The AI Defense AIBOM module provides APIs for creating, storing, and querying AI Bill of Materials (AIBOM) analyses. It supports both:

- High-level workflows through `AiBomClient` (analyze sources and submit reports)
- Low-level API access through `AiBom` (direct CRUD/query operations)

## Features

- **Analyze and Submit**: Run local AIBOM analysis and submit results to AI Defense
- **Report Submission**: Submit already-generated AIBOM JSON reports
- **BOM Query APIs**: List BOMs, fetch BOM details, and list BOM components
- **Summary Statistics**: Retrieve aggregate AIBOM summary metrics
- **Delete Support**: Remove BOMs by `analysis_id`

## Installation

```bash
pip install cisco-aidefense-sdk
```

If you want to use `AiBomClient.analyze(...)`, install the optional AIBOM extra:

```bash
pip install "cisco-aidefense-sdk[aibom]"
```

## Quick Start

### High-Level Client: Analyze and Submit

```python
from aidefense import Config
from aidefense.aibom.aibom_client import AiBomClient

client = AiBomClient(
    api_key="YOUR_MANAGEMENT_API_KEY",
    config=Config(management_base_url="https://api.security.cisco.com"),
)

# Analyze one or more local sources
report = client.analyze(sources=["/path/to/project"])

# Submit the generated report
response = client.submit_report_file(raw_data=report)
print(response.analysis_id, response.status)
```

### Submit an Existing Report File

```python
from pathlib import Path
from aidefense import Config
from aidefense.aibom.aibom_client import AiBomClient

client = AiBomClient(
    api_key="YOUR_MANAGEMENT_API_KEY",
    config=Config(management_base_url="https://api.security.cisco.com"),
)

response = client.submit_report_file(file_path=Path("./aibom-report.json"))
print(response.model_dump_json(indent=2))
```

### Low-Level Client: Direct AIBOM API Methods

```python
from aidefense import Config
from aidefense.aibom.aibom_base import AiBom
from aidefense.aibom.models import (
    BomsSummaryRequest,
    ListBomComponentsRequest,
    ListBomsRequest,
)

client = AiBom(
    api_key="YOUR_MANAGEMENT_API_KEY",
    config=Config(management_base_url="https://api.security.cisco.com"),
)

# List BOMs
boms = client.list_boms(ListBomsRequest(limit=10, offset=0))
print(f"Found {len(boms.items)} BOMs")

if boms.items:
    analysis_id = boms.items[0].analysis_id

    # Get one BOM
    bom = client.get_bom(analysis_id)
    print(bom.model_dump_json(indent=2))

    # List components
    components = client.list_bom_components(
        analysis_id,
        ListBomComponentsRequest(limit=20, offset=0),
    )
    print(f"Components: {len(components.items)}")

# Get summary
summary = client.get_bom_summary(BomsSummaryRequest())
print(summary.model_dump_json(indent=2))
```

## API Surface

### `AiBomClient` Methods

- `analyze(sources, output_file=None, **kwargs) -> dict`
- `submit_report_file(raw_data=None, file_path=None) -> CreateAnalysisResponse`
- `analyze_and_submit(sources, output_file=None, **kwargs) -> CreateAnalysisResponse`

### `AiBom` Methods

- `create_analysis(req: CreateAnalysisRequest) -> CreateAnalysisResponse`
- `list_boms(req: ListBomsRequest) -> ListBomsResponse`
- `get_bom(analysis_id: str) -> BomDetail`
- `delete_bom(analysis_id: str) -> None`
- `list_bom_components(analysis_id: str, req: ListBomComponentsRequest) -> ListBomComponentsResponse`
- `get_bom_summary(req: BomsSummaryRequest) -> GetBomSummaryResponse`

## BOM Status Reference

| Status                               | Description                    |
| ------------------------------------ | ------------------------------ |
| `BOM_STATUS_UNSPECIFIED`             | Status unknown or unspecified  |
| `BOM_STATUS_COMPLETED`               | Analysis completed successfully |
| `BOM_STATUS_COMPLETED_WITH_ERRORS`   | Completed, with non-fatal errors |
| `BOM_STATUS_FAILED`                  | Analysis failed                |
| `BOM_STATUS_SKIPPED`                 | Analysis was skipped           |

## Source Kind Reference

| Source Kind                  | Description                          |
| ---------------------------- | ------------------------------------ |
| `SOURCE_KIND_LOCAL_PATH`     | Local file system source             |
| `SOURCE_KIND_CONTAINER`      | Container image/source               |
| `SOURCE_KIND_OTHER`          | Mixed or unknown source type         |
| `SOURCE_KIND_UNSPECIFIED`    | Unspecified source type              |

## Error Handling

```python
from aidefense.exceptions import ApiError, ValidationError, SDKError

try:
    report = client.analyze(sources=["/path/to/project"])
    response = client.submit_report_file(raw_data=report)
except ValidationError as e:
    print(f"Invalid request: {e}")
except ApiError as e:
    print(f"API error: {e}")
except SDKError as e:
    print(f"SDK error: {e}")
```

## Related Examples

- `examples/aibom/aibom_client.py`
- `examples/aibom/aibom_base.py`
