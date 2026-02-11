# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

from aidefense.mcpscan.mcp_scan_base import MCPScan
from aidefense.mcpscan.models import (
    StartMCPServerScanRequest,
    MCPScanStatus,
)


class MCPScanClient(MCPScan):
    """
    High-level client for AI Defense MCP server scanning operations.

    MCPScanClient extends the base MCPScan class to provide convenient methods
    for scanning MCP servers. It handles the complete scan workflow including
    starting scans, monitoring progress, and waiting for completion.

    This client automatically manages scan lifecycle with built-in polling
    and timeout handling for scan completion.

    Typical Usage:
        ```python
        from aidefense.mcpscan import MCPScanClient
        from aidefense.mcpscan.models import (
            StartMCPServerScanRequest, TransportType, MCPScanStatus,
            ServerType, RemoteServerInput
        )
        from aidefense import Config
        import time

        # Initialize the client
        client = MCPScanClient(
            api_key="YOUR_MANAGEMENT_API_KEY",
            config=Config(management_base_url="https://api.security.cisco.com")
        )

        # Scan an MCP server asynchronously
        request = StartMCPServerScanRequest(
            name="My MCP Server",
            server_type=ServerType.REMOTE,
            remote=RemoteServerInput(
                url="https://mcp-server.example.com/sse",
                connection_type=TransportType.SSE
            )
        )
        scan_id = client.scan_mcp_server_async(request)

        # Poll for completion
        while True:
            status = client.get_scan_status(scan_id)
            if status.status == MCPScanStatus.COMPLETED:
                print("Scan completed!")
                if status.result and status.result.is_safe:
                    print("✅ MCP server is safe")
                else:
                    print("⚠️ Security issues detected")
                break
            elif status.status == MCPScanStatus.FAILED:
                print(f"Scan failed: {status.error_info}")
                break
            time.sleep(5)
        ```

    Attributes:
        Inherits all attributes from the base MCPScan class including:
        - api_key: The API key for authentication
        - config: Configuration object with service settings
        - auth: Authentication handler
    """

    def scan_mcp_server_async(
            self,
            request: StartMCPServerScanRequest
    ) -> str:
        """
        Start an MCP server scan and return immediately without waiting.

        This method starts a scan and returns the scan ID immediately, allowing
        you to poll for status separately. Useful for non-blocking operations
        or when integrating with async frameworks.

        Args:
            request (StartMCPServerScanRequest): Request object containing MCP server details.

        Returns:
            str: The scan ID that can be used to check status later.

        Example:
            ```python
            from aidefense.mcpscan import MCPScanClient
            from aidefense.mcpscan.models import (
                StartMCPServerScanRequest, TransportType, MCPScanStatus,
                ServerType, RemoteServerInput
            )
            import time

            client = MCPScanClient(api_key="YOUR_MANAGEMENT_API_KEY")

            # Start scan without waiting
            request = StartMCPServerScanRequest(
                name="My MCP Server",
                server_type=ServerType.REMOTE,
                remote=RemoteServerInput(
                    url="https://mcp-server.example.com/sse",
                    connection_type=TransportType.SSE
                )
            )
            scan_id = client.scan_mcp_server_async(request)
            print(f"Scan started: {scan_id}")

            # Do other work...

            # Check status later
            while True:
                status = client.get_scan_status(scan_id)
                print(f"Status: {status.status}")

                if status.status == MCPScanStatus.COMPLETED:
                    print("Scan completed!")
                    break
                elif status.status == MCPScanStatus.FAILED:
                    print(f"Scan failed: {status.error_message}")
                    break

                time.sleep(5)
            ```
        """
        response = self.start_scan(request)
        return response.scan_id

