# Copyright 2025 Cisco Systems, Inc. and its affiliates
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

"""
Example: Custom configuration options for AI Defense SDK

This script demonstrates:
- Setting up custom runtime base URL
- Configuring logging
- Setting up retry policies
- Using connection pooling options
"""

import logging
import requests
from aidefense import ChatInspectionClient, HttpInspectionClient, Config
from aidefense.runtime.models import Message, Role

def setup_custom_logger():
    """Set up and return a custom logger."""
    # Create a custom logger
    logger = logging.getLogger("aidefense_custom")
    logger.setLevel(logging.DEBUG)

    # Create a console handler
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)

    # Create a formatter and add it to the handler
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(handler)

    return logger

def custom_api_endpoint():
    """Example of using a custom API endpoint."""
    print("\n=== Custom API Endpoint Example ===")

    # Create a configuration with a custom base URL
    config = Config(
        runtime_base_url="https://custom-aidefense-api.example.com"
    )

    # Initialize the client with the custom configuration
    client = ChatInspectionClient(api_key="YOUR_API_KEY", config=config)

    print(f"Client configured to use endpoint: {client.endpoint}")

    # Note: This example won't actually make a call since the URL is fictional
    print("(This is a demonstration - no actual API call will be made)")

def custom_logging_configuration():
    """Example of custom logging configuration."""
    print("\n=== Custom Logging Example ===")

    # Method 1: Configure logging via parameters
    config1 = Config(
        logger_params={
            "level": "DEBUG",      # Set logging level
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "filename": "aidefense.log",  # Log to a file
            "filemode": "w"        # Overwrite existing log file
        }
    )

    client1 = ChatInspectionClient(api_key="YOUR_API_KEY", config=config1)
    print("Client 1: Configured with custom logging parameters")

    # Method 2: Use a custom logger
    custom_logger = setup_custom_logger()

    config2 = Config(logger=custom_logger)
    client2 = ChatInspectionClient(api_key="YOUR_API_KEY", config=config2)
    print("Client 2: Configured with custom logger instance")

    # Demonstrate logging (no actual API call)
    try:
        # This will log the validation error
        client2.inspect_conversation([])
    except Exception as e:
        print(f"Expected error caught: {e}")

def retry_policy_configuration():
    """Example of retry policy configuration."""
    print("\n=== Retry Policy Example ===")

    # Create a configuration with custom retry settings
    config = Config(
        retry_config={
            "total": 5,             # Total number of retries
            "backoff_factor": 0.5,  # Exponential backoff factor
            "status_forcelist": [500, 502, 503, 504],  # Status codes to retry
            "allowed_methods": ["GET", "POST"]          # Methods to retry
        }
    )

    client = ChatInspectionClient(api_key="YOUR_API_KEY", config=config)
    print("Client configured with custom retry policy")
    print("Will retry 5 times with exponential backoff")

def connection_pooling_example():
    """Example of connection pooling configuration."""
    print("\n=== Connection Pooling Example ===")

    # Method 1: Configure pool using parameters
    config1 = Config(
        pool_config={
            "pool_connections": 10,  # Number of connection pools
            "pool_maxsize": 20,      # Maximum number of connections per pool
            "max_retries": 3,        # Retries for the pool adapter
            "pool_block": True       # Whether to block when a pool is full
        }
    )

    client1 = HttpInspectionClient(api_key="YOUR_API_KEY", config=config1)
    print("Client 1: Configured with custom connection pool parameters")

    # Method 2: Use a custom adapter
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=5,
        pool_maxsize=10,
        max_retries=requests.adapters.Retry(
            total=3,
            backoff_factor=0.5
        )
    )

    config2 = Config(connection_pool=adapter)
    client2 = HttpInspectionClient(api_key="YOUR_API_KEY", config=config2)
    print("Client 2: Configured with custom connection pool adapter")

if __name__ == "__main__":
    print("AI Defense SDK Custom Configuration Examples")
    print("==========================================")
    print("Note: Replace 'YOUR_API_KEY' with an actual API key before running")

    # Run the examples
    custom_api_endpoint()
    custom_logging_configuration()
    retry_policy_configuration()
    connection_pooling_example()
