import pytest
import logging
from aidefense.config import Config
from requests.adapters import HTTPAdapter


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset Config singleton before each test."""
    # Reset the singleton instance
    Config._instance = None
    yield
    # Clean up after test
    Config._instance = None


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
