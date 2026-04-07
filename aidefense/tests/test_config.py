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

import pytest
import logging
from aidefense.config import Config
from requests.adapters import HTTPAdapter


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset Config singleton before each test."""
    # Reset the singleton instances
    Config._instances = {}
    yield
    # Clean up after test
    Config._instances = {}


def test_config_default():
    config = Config()
    assert config.runtime_base_url is not None
    assert config.timeout == 30
    assert config.logger is not None
    assert isinstance(config.retry_config, dict)
    assert hasattr(config, "connection_pool")


def test_config_with_runtime_base_url():
    url = "https://custom.endpoint.com"
    config = Config(runtime_base_url=url)
    assert config.runtime_base_url == url


def test_config_with_logger():
    logger = logging.getLogger("test_logger")
    config = Config(logger=logger)
    assert config.logger is logger


def test_config_with_logger_params():
    config = Config(logger_params={"level": "DEBUG"})
    assert config.logger.level == logging.DEBUG


def test_config_with_retry_config():
    retry_conf = {"total": 7, "backoff_factor": 2.0, "status_forcelist": [500, 502]}
    config = Config(retry_config=retry_conf)
    assert config.retry_config["total"] == 7
    assert config.retry_config["backoff_factor"] == 2.0
    assert 500 in config.retry_config["status_forcelist"]


def test_config_with_connection_pool():
    adapter = HTTPAdapter(pool_connections=5, pool_maxsize=10)
    config = Config(connection_pool=adapter)
    assert config.connection_pool is adapter


def test_config_with_pool_config():
    pool_conf = {"pool_connections": 3, "pool_maxsize": 7}
    config = Config(pool_config=pool_conf)
    assert config.connection_pool._pool_connections == 3
    assert config.connection_pool._pool_maxsize == 7


def test_config_warns_on_different_region(caplog):
    Config(region="us-west-2")
    with caplog.at_level(logging.WARNING, logger="aidefense_sdk.config"):
        Config(region="eu-central-1")
    assert "already initialized" in caplog.text
    assert "region" in caplog.text
    assert "eu-central-1" in caplog.text


def test_config_warns_on_different_timeout(caplog):
    Config(timeout=30)
    with caplog.at_level(logging.WARNING, logger="aidefense_sdk.config"):
        Config(timeout=60)
    assert "already initialized" in caplog.text
    assert "timeout" in caplog.text


def test_config_no_warning_on_same_params(caplog):
    Config(region="us-west-2", timeout=30)
    with caplog.at_level(logging.WARNING, logger="aidefense_sdk.config"):
        Config(region="us-west-2", timeout=30)
    assert "already initialized" not in caplog.text


def test_config_no_warning_on_short_region_alias(caplog):
    """'us' normalizes to 'us-west-2', so no mismatch warning."""
    Config(region="us-west-2")
    with caplog.at_level(logging.WARNING, logger="aidefense_sdk.config"):
        Config(region="us")
    assert "already initialized" not in caplog.text


def test_config_no_warning_when_no_kwargs(caplog):
    Config(region="eu-central-1")
    with caplog.at_level(logging.WARNING, logger="aidefense_sdk.config"):
        Config()
    assert "already initialized" not in caplog.text
