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

"""Base configuration classes for SDK."""

from abc import ABC, abstractmethod
import logging
import threading

import aiohttp
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from aidefense.exceptions import ValidationError


class BaseConfig(ABC):
    """Base configuration class for all AI Defense SDK clients."""

    _instances = {}
    _lock = threading.Lock()

    DEFAULT_STATUS_FORCELIST = (429, 500, 502, 503, 504)
    DEFAULT_BACKOFF_FACTOR = 0.5
    DEFAULT_TOTAL = 3
    DEFAULT_POOL_CONNECTIONS = 10
    DEFAULT_POOL_MAXSIZE = 20
    DEFAULT_LOG_LEVEL = logging.INFO
    DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    DEFAULT_NAME = "aidefense_sdk"
    DEFAULT_REGION = "us-west-2"
    DEFAULT_TIMEOUT = 30

    RUNTIME_REGION_ENDPOINTS = {
        "us": "https://us.api.inspect.aidefense.security.cisco.com",
        "eu": "https://eu.api.inspect.aidefense.security.cisco.com",
        "apj": "https://apj.api.inspect.aidefense.security.cisco.com",
        "us-west-2": "https://us.api.inspect.aidefense.security.cisco.com",
        "eu-central-1": "https://eu.api.inspect.aidefense.security.cisco.com",
        "ap-northeast-1": "https://apj.api.inspect.aidefense.security.cisco.com",
        "me-central-1": "https://uae.api.inspect.aidefense.security.cisco.com",
    }

    MANAGEMENT_REGION_ENDPOINTS = {
        "us-west-2": "https://us.api.aidefense.security.cisco.com",
        "eu-central-1": "https://eu.api.aidefense.security.cisco.com",
        "ap-northeast-1": "https://ap.api.aidefense.security.cisco.com",
    }

    def __new__(cls, *args, **kwargs):
        if cls is BaseConfig:
            raise TypeError("BaseConfig is abstract and cannot be instantiated directly")

        # Singleton constructor for Config. Ensures only one instance is created per subclass.
        # Acquiring a lock is expensive, so we only do it if we need to. Future initializations will be fast.
        # Once the lock is acquired, we check again to ensure no other thread has created an instance.
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__new__(cls)

        return cls._instances[cls]

    def __init__(self, *args, **kwargs):
        # On the first call, _initialized doesn't exist yet. Direct access would raise AttributeError
        if not getattr(self, "_initialized", False):
            self._initialized = True
            self._initialize(*args, **kwargs)

    def _set_region(self, region: str):
        if not isinstance(region, str):
            region = self.DEFAULT_REGION

        if region not in self.RUNTIME_REGION_ENDPOINTS or region not in self.MANAGEMENT_REGION_ENDPOINTS:
            raise ValueError(f"Invalid region: {region}")

        self.region = region

    def _set_timeout(self, timeout: int):
        # bool is a subclass of int in Python
        if not (isinstance(timeout, int) and not isinstance(timeout, bool)):
            timeout = self.DEFAULT_TIMEOUT

        self.timeout = timeout

    def _set_runtime_base_url(self, runtime_base_url: str):
        if runtime_base_url and isinstance(runtime_base_url, str):
            if not runtime_base_url.startswith(("http://", "https://")):
                raise ValidationError(f"Invalid URL: {runtime_base_url}")

            self.runtime_base_url = runtime_base_url
        else:
            self.runtime_base_url = self.RUNTIME_REGION_ENDPOINTS.get(self.region)

        self.runtime_base_url.rstrip("/")

    def _set_management_base_url(self, management_base_url: str):
        if management_base_url and isinstance(management_base_url, str):
            if not management_base_url.startswith(("http://", "https://")):
                raise ValidationError(f"Invalid URL: {management_base_url}")

            self.management_base_url = management_base_url
        else:
            self.management_base_url = self.MANAGEMENT_REGION_ENDPOINTS.get(self.region)

        self.management_base_url.rstrip("/")

    def _set_logger(self, logger, logger_params: dict):
        if logger:
            self.logger = logger
        else:
            if not isinstance(logger_params, dict):
                logger_params = {}

            log_name = logger_params.get("name", self.DEFAULT_NAME)
            log_level = logger_params.get("level", self.DEFAULT_LOG_LEVEL)
            log_format = logger_params.get("format", self.DEFAULT_LOG_FORMAT)

            self.logger = logging.getLogger(log_name)
            self.logger.setLevel(log_level)

            if not self.logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter(log_format))
                self.logger.addHandler(handler)

    def _set_retry_config(self, retry_config: dict):
        if not isinstance(retry_config, dict):
            retry_config = {}

        self.retry_config = {
            "total": retry_config.get("total", self.DEFAULT_TOTAL),
            "backoff_factor": retry_config.get("backoff_factor", self.DEFAULT_BACKOFF_FACTOR),
            "status_forcelist": retry_config.get("status_forcelist", list(self.DEFAULT_STATUS_FORCELIST)),
            "allowed_methods": retry_config.get("allowed_methods", None),
            "raise_on_status": retry_config.get("raise_on_status", False),
            "respect_retry_after_header": retry_config.get("respect_retry_after_header", True),
        }

    def _set_pool_config(self, pool_config: dict):
        if not isinstance(pool_config, dict):
            pool_config = {}

        self.pool_config = {
            "pool_connections": pool_config.get("pool_connections", self.DEFAULT_POOL_CONNECTIONS),
            "pool_maxsize": pool_config.get("pool_maxsize", self.DEFAULT_POOL_MAXSIZE),
        }

    @abstractmethod
    def _initialize(self, *args, **kwargs):
        pass


class Config(BaseConfig):
    """
    SDK configuration object for managing connection, logging, retry, and endpoint settings for synchronous API calls.

    The Config class centralizes all runtime options for AI Defense SDK clients. It enables you to control API endpoints (region or custom),
    HTTP timeouts, logging behavior, retry logic, and HTTP connection pooling.

    Pass a Config instance to any synchronous client (e.g., ChatInspectionClient, HttpInspectionClient) to apply consistent
    settings across all SDK operations.

    Typical usage:
        config = Config(region='us', timeout=60, logger=my_logger)
        client = ChatInspectionClient(api_key=..., config=config)

    Args:
        region (str, optional): Region for API endpoint selection. One of 'us', 'eu', or 'apj'. Default is 'us'.
        runtime_base_url (str, optional): Custom base URL for runtime API endpoint. If provided, takes precedence over region.
        management_base_url (str, optional): Custom base URL for management API endpoint. If provided, takes precedence over region.
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
        management_base_url (str): Base API URL for the selected region.
        logger (logging.Logger): Logger instance.
        retry_config (dict): Retry configuration.
        connection_pool (requests.adapters.HTTPAdapter): HTTP connection pool adapter.
        pool_config (dict): Parameters for connection pool.
    """

    def _initialize(
        self,
        region: str = None,
        runtime_base_url: str = None,
        management_base_url: str = None,
        timeout: int = None,
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
            runtime_base_url (str, optional): Custom base URL for runtime API endpoint.
            management_base_url (str, optional): Custom base URL for management API endpoint.
            timeout (int, optional): Timeout for HTTP requests in seconds. Default is 30.
            logger (logging.Logger, optional): Optional custom logger instance.
            logger_params (dict, optional): Parameters for logger creation.
            retry_config (dict, optional): Retry configuration dict.
            connection_pool (HTTPAdapter, optional): Custom HTTPAdapter for connection pooling.
            pool_config (dict, optional): Parameters for connection pool.
        """
        self._set_region(region)
        self._set_timeout(timeout)
        self._set_runtime_base_url(runtime_base_url)
        self._set_management_base_url(management_base_url)
        self._set_logger(logger, logger_params)
        self._set_retry_config(retry_config)
        self._set_pool_config(pool_config)

        # Build a urllib3 Retry object from retry_config
        self._retry_obj = Retry(
            total=self.retry_config.get("total"),
            backoff_factor=self.retry_config.get("backoff_factor"),
            status_forcelist=self.retry_config.get("status_forcelist"),
            allowed_methods=self.retry_config.get("allowed_methods"),
            raise_on_status=self.retry_config.get("raise_on_status"),
            respect_retry_after_header=self.retry_config.get("respect_retry_after_header"),
        )

        # --- Connection Pool ---
        if connection_pool:
            if not isinstance(connection_pool, HTTPAdapter):
                raise TypeError("connection_pool must be an instance of requests.adapters.HTTPAdapter")

            self.connection_pool = connection_pool
        else:
            self.connection_pool = HTTPAdapter(
                pool_connections=self.pool_config.get("pool_connections"),
                pool_maxsize=self.pool_config.get("pool_maxsize"),
                max_retries=self._retry_obj,
            )


class AsyncConfig(BaseConfig):
    """
    SDK configuration object for managing connection, logging, retry, and endpoint settings for asynchronous API calls.

    The AsyncConfig class centralizes all runtime options for AI Defense SDK clients. It enables you to control API endpoints (region or custom),
    HTTP timeouts, logging behavior, retry logic, and HTTP connection pooling.

    Pass an AsyncConfig instance to any asynchronous client (e.g., AsyncChatInspectionClient) to apply consistent
    settings across all SDK operations.

    Typical usage:

    config = AsyncConfig(region='us-west-2', timeout=60, logger=my_logger)
    client = AsyncChatInspectionClient(api_key=..., config=config)

    Args:
        region (str, optional): Region for API endpoint selection. Default is 'us'.
        runtime_base_url (str, optional): Custom base URL for runtime API endpoint.
        management_base_url (str, optional): Custom base URL for management API endpoint.
        timeout (int, optional): Timeout for HTTP requests in seconds. Default is 30.
        logger (logging.Logger, optional): Optional custom logger instance.
        logger_params (dict, optional): Parameters for logger creation.
        retry_config (dict, optional): Retry configuration dict.
        connection_pool (aiohttp.TCPConnector, optional): Custom TCPConnector for connection pooling. Takes precedence over pool_config and defaults.
        pool_config (dict, optional): Parameters for connection pool.

    Attributes:
        region (str): Selected region.
        timeout (int): HTTP timeout.
        runtime_base_url (str): Base API URL for the selected region.
        management_base_url (str): Base API URL for the selected region.
        logger (logging.Logger): Logger instance.
        retry_config (dict): Retry configuration.
        connection_pool (requests.adapters.HTTPAdapter): HTTP connection pool adapter.
        pool_config (dict): Parameters for connection pool.
    """

    def _initialize(
        self,
        region: str = None,
        runtime_base_url: str = None,
        management_base_url: str = None,
        timeout: int = None,
        logger: logging.Logger = None,
        logger_params: dict = None,
        retry_config: dict = None,
        connection_pool: aiohttp.TCPConnector = None,
        pool_config: dict = None,
    ):
        self._set_region(region)
        self._set_timeout(timeout)
        self._set_runtime_base_url(runtime_base_url)
        self._set_management_base_url(management_base_url)
        self._set_logger(logger, logger_params)
        self._set_retry_config(retry_config)
        self._set_pool_config(pool_config)

        # --- Connection Pool ---
        if connection_pool:
            if not isinstance(connection_pool, aiohttp.TCPConnector):
                raise TypeError("connection_pool must be an instance of aiohttp.TCPConnector")

            self.connection_pool = connection_pool
        else:
            self.connection_pool = aiohttp.TCPConnector(
                limit=self.pool_config.get("pool_connections"),
                limit_per_host=self.pool_config.get("pool_maxsize"),
                ttl_dns_cache=300,
            )
