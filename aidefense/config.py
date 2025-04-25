"""Base configuration classes for SDK."""

import logging
import requests
import threading
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class Config:
    """
    SDK configuration object for managing connection, logging, retry, and endpoint settings.

    The Config class centralizes all runtime options for AI Defense SDK clients. It enables you to control API endpoints (region or custom), HTTP timeouts, logging behavior, retry logic, and HTTP connection pooling. Pass a Config instance to any client (e.g., ChatInspectionClient, HttpInspectionClient) to apply consistent settings across all SDK operations.

    Typical usage:
        config = Config(region='us', timeout=60, logger=my_logger)
        client = ChatInspectionClient(api_key=..., config=config)

    Args:
        region (str, optional): Region for API endpoint selection. One of 'us', 'eu', or 'apj'. Default is 'us'.
        runtime_base_url (str, optional): Custom base URL for API endpoint. If provided, takes precedence over region.
        timeout (int, optional): Timeout for HTTP requests in seconds. Default is 30.
        logger (logging.Logger, optional): Optional custom logger instance. If not provided, one is created.
        logger_params (dict, optional): Parameters for logger creation (`name`, `level`, `format`).
        retry_config (dict, optional): Retry configuration dict (e.g., {"total": 3, "backoff_factor": 0.5, "status_forcelist": [...]}).
        connection_pool (requests.adapters.HTTPAdapter, optional): Optional custom HTTPAdapter for connection pooling. Takes precedence over pool_config and defaults.
        pool_config (dict, optional): Parameters for connection pool (`pool_connections`, `pool_maxsize`, `max_retries`). Used if connection_pool is not provided.

    Attributes:
        region (str): Selected region.
        timeout (int): HTTP timeout.
        runtime_base_url (str): Base API URL for the selected region.
        logger (logging.Logger): Logger instance.
        retry_config (dict): Retry configuration.
        connection_pool (requests.adapters.HTTPAdapter): HTTP connection pool adapter.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        # Singleton constructor for Config. Ensures only one instance is created.
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialize(*args, **kwargs)
        return cls._instance

    def _initialize(
        self,
        region: str = "us",
        runtime_base_url: str = None,
        timeout: int = 30,
        logger: logging.Logger = None,
        logger_params: dict = None,
        retry_config: dict = None,
        connection_pool: HTTPAdapter = None,
        pool_config: dict = None,
    ):
        """
        Initialize the configuration with the provided parameters.

        Args:
            region (str, optional): Region for API endpoint selection. Default is 'us'.
            runtime_base_url (str, optional): Custom base URL for API endpoint.
            timeout (int, optional): Timeout for HTTP requests in seconds. Default is 30.
            logger (logging.Logger, optional): Optional custom logger instance.
            logger_params (dict, optional): Parameters for logger creation.
            retry_config (dict, optional): Retry configuration dict.
            connection_pool (HTTPAdapter, optional): Custom HTTPAdapter for connection pooling.
            pool_config (dict, optional): Parameters for connection pool.
        """
        self.region = region
        self.timeout = timeout
        self.runtime_region_endpoints = {
            "us": "https://us.api.inspect.aidefense.security.cisco.com",
            "eu": "https://eu.api.inspect.aidefense.security.cisco.com",
            "apj": "https://apj.api.inspect.aidefense.security.cisco.com",
        }
        if runtime_base_url:
            self.runtime_base_url = runtime_base_url
        else:
            self.runtime_base_url = self.runtime_region_endpoints.get(region)

        # --- Logger ---
        if logger:
            self.logger = logger
        else:
            if logger_params is None:
                logger_params = {}
            log_name = logger_params.get("name", "aidefense_sdk")
            log_level = logger_params.get("level", logging.DEBUG)
            log_format = logger_params.get("format", "%(asctime)s %(levelname)s %(name)s: %(message)s")
            self.logger = logging.getLogger(log_name)
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter(log_format))
                self.logger.addHandler(handler)
            self.logger.setLevel(log_level)

        # --- Retry Config ---
        self.retry_config = retry_config or {
            "total": 3,
            "backoff_factor": 0.5,
            "status_forcelist": [429, 500, 502, 503, 504],
        }
        # Build a urllib3 Retry object from retry_config
        self._retry_obj = Retry(
            total=self.retry_config.get("total", 3),
            backoff_factor=self.retry_config.get("backoff_factor", 0.5),
            status_forcelist=self.retry_config.get("status_forcelist", [429, 500, 502, 503, 504]),
            allowed_methods=self.retry_config.get("allowed_methods", None),
            raise_on_status=self.retry_config.get("raise_on_status", False),
            respect_retry_after_header=self.retry_config.get("respect_retry_after_header", True),
        )

        # --- Connection Pool ---
        if connection_pool:
            if not isinstance(connection_pool, HTTPAdapter):
                raise TypeError("connection_pool must be an instance of requests.adapters.HTTPAdapter")
            self.connection_pool = connection_pool
        elif pool_config:
            self.connection_pool = HTTPAdapter(
                pool_connections=pool_config.get("pool_connections", 10),
                pool_maxsize=pool_config.get("pool_maxsize", 20),
                max_retries=self._retry_obj
            )
        else:
            self.connection_pool = HTTPAdapter(
                pool_connections=10,
                pool_maxsize=20,
                max_retries=self._retry_obj
            )

    def get_runtime_endpoint_url(self, region: str) -> str:
        """
        Get the runtime endpoint URL for a given region.

        Args:
            region (str): The region key (e.g., 'us', 'eu', 'apj').

        Returns:
            str: The runtime base URL for the selected region.

        Raises:
            ValueError: If the region is invalid.
        """
        if region not in self.runtime_region_endpoints:
            raise ValueError(f"Invalid region: {region}")
        self.runtime_base_url = self.runtime_region_endpoints[region]
        return self.runtime_base_url
