# AI Defense ModelScan Module

The AI Defense ModelScan module provides comprehensive security scanning capabilities for AI/ML model files and repositories. It offers both high-level convenience methods and granular step-by-step control for scanning operations.

## Features

- **File Scanning**: Scan individual model files for security threats and malicious code
- **Repository Scanning**: Scan entire model repositories from platforms like HuggingFace
- **Multiple Scan Approaches**: High-level client for convenience or granular control for custom workflows
- **Comprehensive Results**: Detailed threat detection and analysis results

## Installation

```bash
pip install cisco-aidefense-sdk
```

## Quick Start

### Basic File Scanning with ModelScanClient

```python
from aidefense.modelscan import ModelScanClient
from aidefense.modelscan.models import ScanStatus
from aidefense import Config

# Initialize the client
client = ModelScanClient(
    api_key="YOUR_MANAGEMENT_API_KEY",
    config=Config(management_base_url="https://api.security.cisco.com")
)

# Scan a local file
result = client.scan_file("/path/to/model.pkl")

# Check the results
if result.status == ScanStatus.COMPLETED:
    print("✅ Scan completed successfully")
    
    # Check for threats in analysis results
    for file_info in result.analysis_results.items:
        if file_info.threats.items:
            print(f"⚠️  Threats found in {file_info.name}:")
        elif file_info.status == ScanStatus.COMPLETED:
            print(f"✅ {file_info.name} is clean")
        else:
            print(f"ℹ️  {file_info.name} status: {file_info.status}")
elif result.status == ScanStatus.FAILED:
    print("❌ Scan failed")
```

### Repository Scanning with ModelScanClient

```python
from aidefense.modelscan import ModelScanClient
from aidefense.modelscan.models import (
    ModelRepoConfig, Auth, HuggingFaceAuth, URLType, ScanStatus
)
from aidefense import Config

# Initialize the client
client = ModelScanClient(
    api_key="YOUR_MANAGEMENT_API_KEY",
    config=Config(management_base_url="https://api.security.cisco.com")
)

# Configure repository scan with authentication
repo_config = ModelRepoConfig(
    url="https://huggingface.co/username/model-name",
    type=URLType.HUGGING_FACE,
    auth=Auth(huggingface=HuggingFaceAuth(access_token="hf_your_token_here"))
)

# Scan the repository
result = client.scan_repo(repo_config)

# Process results
if result.status == ScanStatus.COMPLETED:
    print("✅ Repository scan completed successfully")
    print(f"Repository: {result.repository.url}")
    print(f"Files scanned: {result.repository.files_scanned}")
    
    # Check analysis results
    for file_info in result.analysis_results.items:
        if file_info.threats.items:
            print(f"⚠️  Threats found in {file_info.name}:")
        elif file_info.status == ScanStatus.COMPLETED:
            print(f"✅ {file_info.name} is clean")
        else:
            print(f"ℹ️  {file_info.name} was {file_info.status}")
elif result.status == ScanStatus.FAILED:
    print("❌ Repository scan failed")
```

### Public Repository Scanning (No Authentication)

```python
from aidefense.modelscan import ModelScanClient
from aidefense.modelscan.models import ModelRepoConfig, URLType
from aidefense import Config

client = ModelScanClient(
    api_key="YOUR_MANAGEMENT_API_KEY",
    config=Config(management_base_url="https://api.security.cisco.com")
)

# Scan a public repository without authentication
public_repo_config = ModelRepoConfig(
    url="https://huggingface.co/username/public-model",
    type=URLType.HUGGING_FACE
)

result = client.scan_repo(public_repo_config)
print(f"Public repository scan status: {result.status}")
```

## Granular File Scanning with ModelScan

For more control over the scanning process, you can use the base `ModelScan` class to perform step-by-step operations:

### Step-by-Step File Scanning

```python
from pathlib import Path
from time import sleep
from aidefense.modelscan import ModelScan
from aidefense.modelscan.models import ScanStatus, GetScanStatusRequest
from aidefense import Config

# Initialize the base client
client = ModelScan(
    api_key="YOUR_MANAGEMENT_API_KEY",
    config=Config(management_base_url="https://api.security.cisco.com")
)

# Step 1: Register a new scan
response = client.register_scan()
scan_id = response.scan_id
print(f"📝 Registered scan with ID: {scan_id}")

try:
    # Step 2: Upload the file
    file_path = Path("/path/to/model.pkl")
    success = client.upload_file(scan_id, file_path)
    if success:
        print(f"📤 Successfully uploaded {file_path.name}")
    
    # Step 3: Trigger the scan
    client.trigger_scan(scan_id)
    print("🚀 Scan triggered, processing...")
    
    # Step 4: Monitor scan progress
    max_retries = 30
    wait_time = 2
    
    for attempt in range(max_retries):
        request = GetScanStatusRequest(file_limit=50, file_offset=0)
        response = client.get_scan(scan_id, request)
        scan_info = response.scan_status_info
        
        print(f"📊 Scan status: {scan_info.status}")
        
        if scan_info.status == ScanStatus.COMPLETED:
            print("✅ Scan completed successfully!")
            
            # Process results
            for file_info in scan_info.analysis_results.items:
                if file_info.threats.items:
                    print(f"⚠️  Threats detected in {file_info.name}")
                elif file_info.status == ScanStatus.COMPLETED:
                    print(f"✅ {file_info.name} is clean")
                else:
                    print(f"ℹ️  {file_info.name} status: {file_info.status}")
            break
            
        elif scan_info.status == ScanStatus.FAILED:
            print("❌ Scan failed")
            break
            
        elif scan_info.status == ScanStatus.CANCELED:
            print("🚫 Scan was canceled")
            break
            
        elif scan_info.status in [ScanStatus.PENDING, ScanStatus.IN_PROGRESS]:
            print(f"⏳ Scan in progress... (attempt {attempt + 1}/{max_retries})")
            sleep(wait_time)
        else:
            print(f"❓ Unknown status: {scan_info.status}")
            sleep(wait_time)
    else:
        print("⏰ Scan timed out")
        # Cancel the scan if it times out
        client.cancel_scan(scan_id)

except Exception as e:
    print(f"❌ Error during scan: {e}")
    # Clean up on error
    try:
        client.cancel_scan(scan_id)
        print("🧹 Scan canceled due to error")
    except:
        pass

finally:
    # Optional: Clean up the scan data
    try:
        client.delete_scan(scan_id)
        print("🗑️  Scan data cleaned up")
    except Exception as e:
        print(f"⚠️  Could not delete scan: {e}")
```

## Scan Management Operations

### List All Scans

```python
from aidefense import Config
from aidefense.modelscan import ModelScanClient
from aidefense.modelscan.models import ListScansRequest

client = ModelScanClient(
    api_key="YOUR_MANAGEMENT_API_KEY",
    config=Config(management_base_url="https://api.security.cisco.com")
)

# Get first 10 scans
request = ListScansRequest(limit=10, offset=0)
response = client.list_scans(request)

scans = response.scans.items
paging = response.scans.paging

print(f"📋 Found {len(scans)} scans (total: {paging.total}):")
for scan in scans:
    # Create issue summary
    issue_summary = []
    for severity, count in scan.issues_by_severity.items():
        if count > 0:
            issue_summary.append(f"{severity}: {count}")
    issue_text = ", ".join(issue_summary) if issue_summary else "No issues"
    
    print(f"  • {scan.scan_id}")
    print(f"    Name: {scan.name} | Type: {scan.type} | Status: {scan.status}")
    print(f"    Files: {scan.files_scanned} | Issues: {issue_text}")
    print(f"    Created: {scan.created_at}")
    print()

# Get next page of scans
next_request = ListScansRequest(limit=10, offset=10)
more_scans = client.list_scans(next_request)
```

### Get Detailed Scan Information

```python
from aidefense import Config
from aidefense.modelscan import ModelScanClient
from aidefense.modelscan.models import GetScanStatusRequest

client = ModelScanClient(
    api_key="YOUR_MANAGEMENT_API_KEY",
    config=Config(management_base_url="https://api.security.cisco.com")
)

# Get detailed information about a specific scan
scan_id = "your_scan_id_here"
request = GetScanStatusRequest(file_limit=10, file_offset=0)
response = client.get_scan(scan_id, request)

# Extract scan status info
scan_info = response.scan_status_info
print(f"📊 Scan Details for {scan_id}:")
print(f"  Status: {scan_info.status}")
print(f"  Type: {scan_info.type}")
print(f"  Created: {scan_info.created_at}")
print(f"  Completed: {scan_info.completed_at}")

# Repository info (if applicable)
if scan_info.repository:
    print(f"  Repository: {scan_info.repository.url}")
    print(f"  Files Scanned: {scan_info.repository.files_scanned}")

# Check analysis results with pagination
analysis_results = scan_info.analysis_results
print(f"  Results: {len(analysis_results.items)} items (total: {analysis_results.paging.total})")
print()

for item in analysis_results.items:
    # Determine status icon
    if item.status == "SKIPPED":
        status_icon = "⏭️"
    elif item.threats.items:
        status_icon = "⚠️"
    else:
        status_icon = "✅"
    
    print(f"    {status_icon} {item.name} ({item.size} bytes)")
    print(f"       Status: {item.status}")
    
    if item.reason:
        print(f"       Reason: {item.reason}")
    
    if item.threats.items:
        threat_counts = {}
        for threat in item.threats.items:
            severity = threat.severity
            threat_counts[severity] = threat_counts.get(severity, 0) + 1
        
        threat_summary = ", ".join([f"{severity}: {count}" for severity, count in threat_counts.items()])
        print(f"       Threats: {threat_summary}")
    
    print()
```

### Cancel and Delete Scans

```python
from aidefense import Config
from aidefense.modelscan import ModelScanClient

client = ModelScanClient(
    api_key="YOUR_MANAGEMENT_API_KEY",
    config=Config(management_base_url="https://api.security.cisco.com")
)

scan_id = "your_scan_id_here"

# Cancel a running scan
try:
    client.cancel_scan(scan_id)
    print(f"🚫 Canceled scan {scan_id}")
    
    # Wait a moment for cancellation to process
    import time
    time.sleep(2)
    
    # Delete the scan data
    client.delete_scan(scan_id)
    print(f"🗑️  Deleted scan {scan_id}")
    
except Exception as e:
    print(f"❌ Error managing scan: {e}")
```

## Configuration and Authentication

### Repository Authentication

Currently supported repository types and their authentication methods:

#### HuggingFace Repositories

```python
from aidefense.modelscan.models import ModelRepoConfig, Auth, HuggingFaceAuth, URLType

# Create HuggingFace authentication
auth = Auth(huggingface=HuggingFaceAuth(access_token="hf_your_access_token_here"))

# Use with repository configuration
repo_config = ModelRepoConfig(
    url="https://huggingface.co/username/model-name",
    type=URLType.HUGGING_FACE,
    auth=auth
)

print(f"Repository type: {repo_config.type}")  # URLType.HUGGING_FACE
print(f"Repository URL: {repo_config.url}")
```

## Scan Status Reference

The `ScanStatus` enum provides the following status values:

- `NONE_SCAN_STATUS`: Default/uninitialized status
- `PENDING`: Scan registered but not yet started
- `IN_PROGRESS`: Scan is currently running
- `COMPLETED`: Scan finished successfully
- `FAILED`: Scan encountered an error
- `CANCELED`: Scan was manually canceled

## Best Practices

### 1. Resource Management

Always clean up scan resources, especially when using the granular `ModelScan` class:

```python
scan_id = None
try:
    response = client.register_scan()
    scan_id = response.scan_id
    # ... perform scan operations
except Exception as e:
    if scan_id:
        client.cancel_scan(scan_id)
        # wait for cancel task to complete, get the scan info to check the status
        sleep(10)
        client.delete_scan(scan_id)
    raise e
```

### 2. Timeout Handling

Implement appropriate timeouts for long-running scans:

```python
import time
from aidefense.modelscan.models import ScanStatus, GetScanStatusRequest

def wait_for_scan_completion(client, scan_id, max_wait_time=300, check_interval=5):
    """Wait for scan completion with timeout."""
    start_time = time.time()
    
    while time.time() - start_time < max_wait_time:
        request = GetScanStatusRequest(file_limit=10, file_offset=0)
        response = client.get_scan(scan_id, request)
        status = response.scan_status_info.status
        
        if status in [ScanStatus.COMPLETED, ScanStatus.FAILED, ScanStatus.CANCELED]:
            return response.scan_status_info
            
        time.sleep(check_interval)
    
    # Timeout reached
    client.cancel_scan(scan_id)
    raise TimeoutError(f"Scan {scan_id} timed out after {max_wait_time} seconds")
```

### 3. Batch Processing

For multiple files, use the high-level client for simplicity:

```python
import os
from pathlib import Path

def scan_directory(client, directory_path):
    """Scan all model files in a directory."""
    directory = Path(directory_path)
    model_extensions = ['.pkl', '.joblib', '.h5', '.pb', '.onnx', '.pt', '.pth']
    
    results = {}
    
    for file_path in directory.rglob('*'):
        if file_path.suffix.lower() in model_extensions:
            try:
                print(f"Scanning {file_path.name}...")
                result = client.scan_file(file_path)
                results[str(file_path)] = result
            except Exception as e:
                print(f"Failed to scan {file_path.name}: {e}")
                results[str(file_path)] = {"error": str(e)}
    
    return results

# Usage
results = scan_directory(client, "/path/to/models/")
```
