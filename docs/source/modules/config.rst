Configuration
=============

.. automodule:: aidefense.config
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The Config module provides a centralized framework for configuring global settings for the AI Defense SDK. It uses a singleton pattern to ensure consistent configuration across all inspection clients, while allowing customization of endpoints, logging, retry behavior, and connection pooling.

Configuration Options
--------------------

**Endpoint Configuration**

- ``region``: Select region for API endpoint (``'us'``, ``'eu'``, or ``'apj'``). Default: ``'us'``
- ``runtime_base_url``: Custom base URL for API endpoint (takes precedence over region)

**HTTP Configuration**

- ``timeout``: HTTP request timeout in seconds. Default: ``30``
- ``retry_config``: Dictionary with retry settings (``total``, ``backoff_factor``, ``status_forcelist``, etc.)
- ``connection_pool``: Custom HTTPAdapter for connection pooling
- ``pool_config``: Dictionary with connection pool settings (``pool_connections``, ``pool_maxsize``)

**Logging Configuration**

- ``logger``: Custom logger instance
- ``logger_params``: Dictionary with logger settings (``name``, ``level``, ``format``)

Usage Examples
-------------

Basic Configuration
^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense import Config

    # Create a custom configuration
    config = Config(
        runtime_base_url="https://custom-endpoint.example.com/api",
        logger_params={"level": "DEBUG"},
        retry_config={"total": 5, "backoff_factor": 1.0}
    )

    # Use this config when initializing clients
    from aidefense import ChatInspectionClient, HttpInspectionClient

    chat_client = ChatInspectionClient(api_key="YOUR_INSPECTION_API_KEY", config=config)
    http_client = HttpInspectionClient(api_key="YOUR_INSPECTION_API_KEY", config=config)

Custom Logging
^^^^^^^^^^^^^

.. code-block:: python

    import logging
    from aidefense import Config

    # Set up a custom logger
    logger = logging.getLogger("my-aidefense-logger")
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    # Pass the logger to the config
    config = Config(logger=logger)

Advanced Retry Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense import Config

    # Create a config with custom retry settings
    config = Config(
        retry_config={
            "total": 3,  # Total number of retries
            "backoff_factor": 0.5,  # Exponential backoff factor
            "status_forcelist": [500, 502, 503, 504],  # Only retry on these status codes
            "allowed_methods": ["GET", "POST"]  # Only retry these methods
        }
    )

Customizing API Endpoints
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense import Config, ChatInspectionClient, HttpInspectionClient

    # Create a config with a custom endpoint
    config = Config(
        runtime_base_url="https://private-deployment.example.com/v1"
    )

    # Both clients will use the custom endpoint
    chat_client = ChatInspectionClient(api_key="YOUR_INSPECTION_API_KEY", config=config)
    http_client = HttpInspectionClient(api_key="YOUR_INSPECTION_API_KEY", config=config)

Configuration for Multiple Environments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    import os
    from aidefense import Config, ChatInspectionClient

    # Helper function to get environment-specific configuration
    def get_config(environment):
        if environment == "production":
            return Config(
                runtime_base_url="https://api.aidefense.example.com/v1",
                logger_params={"level": "INFO"},
                retry_config={"total": 5, "backoff_factor": 1.0}
            )
        elif environment == "staging":
            return Config(
                runtime_base_url="https://staging-api.aidefense.example.com/v1",
                logger_params={"level": "DEBUG"},
                retry_config={"total": 3, "backoff_factor": 0.5}
            )
        else:  # development
            return Config(
                runtime_base_url="https://dev-api.aidefense.example.com/v1",
                logger_params={"level": "DEBUG"},
                retry_config={"total": 2, "backoff_factor": 0.1}
            )

    # Get configuration based on environment variable
    env = os.environ.get("ENVIRONMENT", "development")
    config = get_config(env)

    # Initialize client with the environment-specific config
    client = ChatInspectionClient(api_key="YOUR_INSPECTION_API_KEY", config=config)

See the `/examples/advanced/custom_configuration.py` example in the SDK's well-organized examples directory for more advanced configuration scenarios.

Connection Pooling Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from aidefense import Config
    from requests.adapters import HTTPAdapter

    # Option 1: Use pool_config dictionary
    config = Config(
        pool_config={
            "pool_connections": 10,  # Number of connection pools to cache
            "pool_maxsize": 20      # Maximum number of connections to save in the pool
        }
    )

    # Option 2: Provide a custom HTTPAdapter
    adapter = HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=3
    )

    config = Config(connection_pool=adapter)

Default Values
^^^^^^^^^^^^^

The Config class provides sensible defaults for all parameters:

.. code-block:: python

    # These are the effective defaults if no parameters are provided
    config = Config(
        region="us",                          # US region endpoint
        timeout=30,                         # 30 second timeout
        logger_params={                     # Default logger settings
            "name": "aidefense",
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        retry_config={                      # Default retry settings
            "total": 3,
            "backoff_factor": 0.5,
            "status_forcelist": [429, 500, 502, 503, 504]
        },
        pool_config={                       # Default connection pool
            "pool_connections": 10,
            "pool_maxsize": 10
        }
    )
