# AI Defense AI-BOM Module

The AI-BOM (AI Bill of Materials) module provides client support for managing AI-BOM analyses with Cisco AI Defense. It allows you to list BOMs, create analyses, retrieve BOM details, list components, and delete BOMs.

## Features

- **List BOMs**: Paginated listing with filters (status, source kind, date range, search)
- **BOM Summary**: Aggregated statistics across BOMs
- **Create Analysis**: Submit AI-BOM analysis reports
- **Get BOM**: Retrieve full BOM detail by analysis ID
- **List Components**: List components with filters (category, framework, search)
- **Delete BOM**: Soft delete with optional reason

## Installation

```bash
pip install cisco-aidefense-sdk
```

## Quick Start

```python
from aidefense import AIBom, Config
from aidefense.aibom.models import ListBomsRequest, SortBy, BomSortOrder

# Initialize the client
client = AIBom(
    api_key="YOUR_MANAGEMENT_API_KEY",
    config=Config(management_base_url="https://api.security.cisco.com")
)

# List BOMs
request = ListBomsRequest(
    limit=10,
    offset=0,
    sort_by=SortBy.SORT_BY_LAST_GENERATED_AT,
    order=BomSortOrder.DESC
)
response = client.list_boms(request)
for item in response.items:
    print(f"{item.analysis_id}: {item.source_name} ({item.assets_discovered} assets)")

# Get BOM detail
bom = client.get_bom(analysis_id="analysis-uuid")
print(f"Source: {bom.source_name}, Status: {bom.status}")
if bom.summary:
    print(f"Total assets: {bom.summary.total_assets}")

# Get BOM summary stats
from aidefense.aibom.models import GetBomSummaryRequest

summary_req = GetBomSummaryRequest()
summary_resp = client.get_bom_summary(summary_req)
if summary_resp.summary:
    print(f"Total BOMs: {summary_resp.summary.total_boms}")
    print(f"Total assets: {summary_resp.summary.total_assets}")

# Create analysis
from aidefense.aibom.models import CreateAnalysisRequest, SourceInput, SourceKind

create_req = CreateAnalysisRequest(
    run_id="run-123",
    source_kind=SourceKind.SOURCE_KIND_LOCAL_PATH,
    sources=[SourceInput(name="my-app", path="/path/to/source")],
    report={"assets": []}  # Raw report JSON
)
create_resp = client.create_analysis(create_req)
print(f"Analysis ID: {create_resp.analysis_id}")

# List components
from aidefense.aibom.models import ListBomComponentsRequest

comp_req = ListBomComponentsRequest(
    analysis_id="analysis-uuid",
    limit=25,
    offset=0
)
comp_resp = client.list_bom_components("analysis-uuid", comp_req)
for comp in comp_resp.items:
    print(f"  {comp.name} ({comp.category})")

# Delete BOM
client.delete_bom(analysis_id="analysis-uuid", reason="Obsolete analysis")
```

## Enums

| Enum               | Values                                                                 |
|--------------------|------------------------------------------------------------------------|
| `BomStatus`        | BOM_STATUS_UNSPECIFIED, BOM_STATUS_COMPLETED, BOM_STATUS_COMPLETED_WITH_ERRORS, BOM_STATUS_FAILED, BOM_STATUS_SKIPPED |
| `SourceKind`       | SOURCE_KIND_LOCAL_PATH, SOURCE_KIND_CONTAINER, SOURCE_KIND_OTHER       |
| `ComponentCategory`| COMPONENT_CATEGORY_MODEL, COMPONENT_CATEGORY_AGENT, COMPONENT_CATEGORY_PROMPT, COMPONENT_CATEGORY_TOOL, etc. |
| `SortBy`           | SORT_BY_SUBMITTED_AT, SORT_BY_LAST_GENERATED_AT, SORT_BY_ASSETS_DISCOVERED |
