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

from abc import abstractmethod, ABC
from typing import Dict, Any
from dataclasses import asdict

from .auth import RuntimeAuth, AsyncAuth
from .models import PII_ENTITIES, PCI_ENTITIES, PHI_ENTITIES
from .models import (
    Action,
    Rule,
    RuleName,
    Metadata,
    InspectionConfig,
    Severity,
    Classification,
    InspectResponse,
)
from .constants import INTEGRATION_DETAILS
from ..request_handler import RequestHandler
from ..config import Config, AsyncConfig, BaseConfig
from ..async_request_handler import AsyncRequestHandler


class BaseInspectionClient(ABC):
    """
    Abstract base class for all AI Defense inspection clients (e.g., HTTP and Chat inspection).

    This class provides foundational logic for SDK-level configuration, connection pooling, authentication,
    logging, and retry behavior. It is responsible for initializing the runtime configuration (from aidefense/config.py),
    setting up the HTTP session, and managing authentication for API requests.

    Key Features:
    - Centralizes all runtime options for AI Defense SDK clients, such as API endpoints, HTTP timeouts, logging, retry logic, and connection pooling.
    - Handles the creation and mounting of a configured HTTPAdapter with retry logic, as specified in the Config object.
    - Provides a consistent authentication mechanism using API keys via the RuntimeAuth class.
    - Precomputes a default set of enabled rules for inspection, including entity types only for rules that require them (PII, PCI, PHI).

    Usage:
        Subclass this client to implement specific inspection logic (e.g., HttpInspectionClient, ChatInspectionClient).
        Pass a Config instance to apply consistent settings across all SDK operations.

    Args:
        api_key (str): Your AI Defense API key.

    Attributes:
        default_enabled_rules (list): List of Rule objects for all RuleNames. Only rules present in DEFAULT_ENTITY_MAP (PII, PCI, PHI)
            will have their associated entity_types set; all others will have entity_types as None.
        api_key (str): The API key used for authentication.
    """

    # Default entity map for rules that require entity_types (PII, PCI, PHI)
    DEFAULT_ENTITY_MAP = {
        "PII": PII_ENTITIES,
        "PCI": PCI_ENTITIES,
        "PHI": PHI_ENTITIES,
    }

    def __new__(cls, *args, **kwargs):
        if cls is BaseInspectionClient:
            raise TypeError("BaseInspectionClient cannot be instantiated directly.")

        return super().__new__(cls, *args, **kwargs)

    def __init__(self, api_key: str, config: BaseConfig):
        """
        Initialize the InspectionClient.

        Args:
            api_key (str): Your AI Defense API key for authentication.

        Attributes:
            api_key (str): The API key used for authentication.
            config (BaseConfig): The configuration object.
            default_enabled_rules (list): List of Rule objects for all RuleNames. Only rules present in
                DEFAULT_ENTITY_MAP (PII, PCI, PHI) will have their associated entity_types set; all others will have entity_types as None.
        """
        self.api_key = api_key
        self.config = config
        self.default_enabled_rules = [
            Rule(
                rule_name=rn,
                entity_types=self.DEFAULT_ENTITY_MAP.get(rn.name, None),
            )
            for rn in RuleName
        ]

    @abstractmethod
    def _inspect(self, *args, **kwargs):
        """
        Abstract method for performing an inspection request.

        This method must be implemented by subclasses. It should handle validation and send
        the inspection request to the API endpoint.

        Args:
            *args: Variable length argument list for implementation-specific parameters.
            **kwargs: Arbitrary keyword arguments for implementation-specific parameters.

        Raises:
            NotImplementedError: If the method is not implemented by a subclass.
        """
        pass

    def _parse_inspect_response(self, response_data: Dict[str, Any]) -> "InspectResponse":
        """
        Parse API response (chat or http inspect) into an InspectResponse object.

        Args:
            response_data (Dict[str, Any]): The response data returned by the API.

        Returns:
            InspectResponse: The parsed inspection response object containing classifications, rules, severity, and other details.

        Example:
            Input (response_data):
            ```python
            {
                "classifications": [
                    "SECURITY_VIOLATION"
                ],
                "is_safe": False,
                "severity": "NONE_SEVERITY",
                "rules": [
                    {
                        "rule_name": "Prompt Injection",
                        "rule_id": 0,
                        "entity_types": [
                            ""
                        ],
                        "classification": "SECURITY_VIOLATION"
                    }
                ],
                "attack_technique": "NONE_ATTACK_TECHNIQUE",
                "explanation": "",
                "client_transaction_id": "",
                "event_id": "b403de99-8d19-408f-8184-ec6d7907f508"
                "action": "Allow"
            }
            ```

            Output (InspectResponse):
            ```python
            InspectResponse(
                classifications=[Classification.SECURITY_VIOLATION],
                is_safe=False,
                severity=Severity.NONE_SEVERITY,
                rules=[
                    Rule(
                        rule_name="Prompt Injection",  # Note: This will remain a string since it's not in RuleName enum
                        rule_id=0,
                        entity_types=[""],
                        classification=Classification.SECURITY_VIOLATION
                    )
                ],
                attack_technique="NONE_ATTACK_TECHNIQUE",
                explanation="",
                client_transaction_id="",
                event_id="b403de99-8d19-408f-8184-ec6d7907f508"
                action="Allow"
            )
            ```
        """
        self.config.logger.debug(f"_parse_inspect_response called | response_data: {response_data}")

        # Convert classifications from strings to enum values
        classifications = []
        for cls in response_data.get("classifications", []):
            try:
                # Ensure the classification is added if it's a valid enum value
                classifications.append(Classification(cls))
            except ValueError:
                # Log invalid classification but don't add it
                self.config.logger.warning(f"Invalid classification type: {cls}")
        # Parse rules if present
        rules = []
        for rule_data in response_data.get("rules", []):
            # Try to convert to enum, keep original string if not in enum
            rule_name = rule_data["rule_name"]
            try:
                rule_name = RuleName(rule_data["rule_name"])
            except ValueError:
                # Keep the original string for custom rule names
                pass
            # Try to convert to enum, keep original string if not in enum
            classification = rule_data.get("classification")
            try:
                classification = Classification(rule_data["classification"])
            except ValueError:
                # Keep the original string for custom classifications
                pass
            rules.append(
                Rule(
                    rule_name=rule_name,
                    entity_types=rule_data.get("entity_types"),
                    rule_id=rule_data.get("rule_id"),
                    classification=classification,
                )
            )
        # Parse severity if present
        severity = None
        action = None
        try:
            severity = Severity(response_data.get("severity", None))
        except ValueError:
            pass

        try:
            action = Action(response_data.get("action", None))
        except ValueError:
            pass

        # Create the response object
        return InspectResponse(
            classifications=classifications,
            is_safe=response_data.get("is_safe", True),
            severity=severity,
            rules=rules or None,
            attack_technique=response_data.get("attack_technique"),
            explanation=response_data.get("explanation"),
            client_transaction_id=response_data.get("client_transaction_id"),
            event_id=response_data.get("event_id"),
            action=action,
        )

    def _prepare_inspection_metadata(self, metadata: Metadata) -> Dict:
        """
        Convert a Metadata object to a JSON-serializable dictionary for API requests.

        Args:
            metadata (Metadata): Additional metadata about the request, such as user identity and application identity.

        Returns:
            Dict: A dictionary with non-None metadata fields for inclusion in the API request.
        """
        request_dict = {}
        if metadata:
            request_dict["metadata"] = asdict(metadata)

        return request_dict

    def _prepare_inspection_config(self, config: InspectionConfig) -> Dict:
        """
        Convert an InspectionConfig object to a JSON-serializable dictionary for API requests.

        This includes serializing Rule objects and enums to plain dictionaries and string values.

        Args:
            config (InspectionConfig): The inspection configuration, including enabled rules and integration profile details.

        Returns:
            Dict: A dictionary representation of the inspection configuration for use in API requests.
        """
        request_dict = {}
        if not config:
            return request_dict
        config_dict = {}
        if config.enabled_rules:

            def rule_to_dict(rule):
                d = asdict(rule)
                # Convert Enums to their values
                if d.get("rule_name") is not None:
                    d["rule_name"] = d["rule_name"].value
                if d.get("classification") is not None:
                    d["classification"] = d["classification"].value
                return d

            config_dict["enabled_rules"] = [rule_to_dict(rule) for rule in config.enabled_rules if rule is not None]

        for key in INTEGRATION_DETAILS:
            value = getattr(config, key, None)
            if value is not None:
                config_dict[key] = value

        if config_dict:
            request_dict["config"] = config_dict

        return request_dict


class InspectionClient(BaseInspectionClient):
    """
    Base class for all AI Defense sync inspection clients (e.g., HTTP and Chat inspection).

    This class provides foundational logic for SDK-level configuration, connection pooling, authentication,
    logging, and retry behavior. It is responsible for initializing the runtime configuration (from aidefense/config.py),
    setting up the HTTP session, and managing authentication for API requests.

    Key Features:
    - Centralizes all runtime options for AI Defense SDK clients, such as API endpoints, HTTP timeouts, logging, retry logic, and connection pooling.
    - Handles the creation and mounting of a configured HTTPAdapter with retry logic, as specified in the Config object.
    - Provides a consistent authentication mechanism using API keys via the RuntimeAuth class.
    - Precomputes a default set of enabled rules for inspection, including entity types only for rules that require them (PII, PCI, PHI).

    Usage:
        Subclass this client to implement specific inspection logic (e.g., HttpInspectionClient, ChatInspectionClient).
        Pass a Config instance to apply consistent settings across all SDK operations.

    Args:
        api_key (str): Your AI Defense API key.
        config (Config, optional): SDK configuration for endpoints, logging, retries, etc. If not provided, a default singleton Config is used.

    Attributes:
        auth (RuntimeAuth): The authentication object for API requests.
        config (Config): The runtime configuration object.
    """

    def __new__(cls, *args, **kwargs):
        if cls is InspectionClient:
            raise TypeError("InspectionClient cannot be instantiated directly.")

        return super().__new__(cls)

    def __init__(self, api_key: str, config: Config):
        """
        Initialize the InspectionClient.

        Args:
            api_key (str): Your AI Defense API key for authentication.
            config (Config, optional): SDK configuration for endpoints, logging, retries, etc.
                If not provided, a default singleton Config is used.

        Attributes:
            auth (RuntimeAuth): Authentication object for API requests.
            config (Config): The runtime configuration object.
            api_key (str): The API key used for authentication.
            default_enabled_rules (list): List of Rule objects for all RuleNames. Only rules present in
                DEFAULT_ENTITY_MAP (PII, PCI, PHI) will have their associated entity_types set; all others will have entity_types as None.
        """
        super().__init__(api_key, config)
        self.auth = RuntimeAuth(api_key)
        self._request_handler = RequestHandler(config)

    def _inspect(self, *args, **kwargs):
        """
        Sync method for performing an inspection request.

        This method must be implemented by subclasses. It should handle validation and send
        the inspection request to the API endpoint.

        Args:
            *args: Variable length argument list for implementation-specific parameters.
            **kwargs: Arbitrary keyword arguments for implementation-specific parameters.

        Raises:
            NotImplementedError: If the method is not implemented by a subclass.
        """
        raise NotImplementedError("Subclasses must implement _inspect.")


class AsyncInspectionClient(BaseInspectionClient):
    """
    Base class for all AI Defense async inspection clients (e.g., HTTP and Chat inspection).

    This class provides foundational logic for SDK-level configuration, connection pooling, authentication,
    logging, and retry behavior. It is responsible for initializing the runtime configuration (from aidefense/config.py),
    setting up the HTTP session, and managing authentication for API requests.

    Key Features:
    - Centralizes all runtime options for AI Defense SDK clients, such as API endpoints, HTTP timeouts, logging, retry logic, and connection pooling.
    - Handles the creation and mounting of a configured async auth middleware with retry logic, as specified in the Config object.
    - Provides a consistent authentication mechanism using API keys via the AsyncAuth class.
    - Precomputes a default set of enabled rules for inspection, including entity types only for rules that require them (PII, PCI, PHI).

    Usage:
        Subclass this client to implement specific inspection logic (e.g., HttpInspectionClient, ChatInspectionClient).
        Pass a Config instance to apply consistent settings across all SDK operations.

    Args:
        api_key (str): Your AI Defense API key.
        config (AsyncConfig, optional): SDK configuration for endpoints, logging, retries, etc. If not provided, a default singleton Config is used.

    Attributes:
        auth (AsyncAuth): The authentication object for API requests.
        config (AsyncConfig): The runtime configuration object.
    """

    def __new__(cls, *args, **kwargs):
        if cls is AsyncInspectionClient:
            raise TypeError("AsyncInspectionClient cannot be instantiated directly.")

        return super().__new__(cls)

    def __init__(self, api_key: str, config: AsyncConfig):
        """
        Initialize the async inspection client.

        Args:
            api_key (str): Your AI Defense API key for authentication.
            config (AsyncConfig): Async SDK configuration for endpoints, logging, retries, etc.
        """
        super().__init__(api_key, config)
        self.auth = AsyncAuth(api_key)
        self._request_handler = AsyncRequestHandler(config)

    async def __aenter__(self):
        """
        Enter the async context manager.

        Initializes the HTTP session for making API requests.

        Returns:
            AsyncInspectionClient: The client instance ready for making requests.
        """
        await self._request_handler.ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the async context manager.

        Closes the HTTP session and cleans up resources.

        Args:
            exc_type: Exception type if an exception was raised, None otherwise.
            exc_val: Exception value if an exception was raised, None otherwise.
            exc_tb: Exception traceback if an exception was raised, None otherwise.
        """
        await self._request_handler.close()

    async def _inspect(self, *args, **kwargs):
        """
        Async method for performing an inspection request.

        This method must be implemented by subclasses. It should handle validation and send
        the inspection request to the API endpoint.

        Args:
            *args: Variable length argument list for implementation-specific parameters.
            **kwargs: Arbitrary keyword arguments for implementation-specific parameters.

        Raises:
            NotImplementedError: If the method is not implemented by a subclass.
        """
        raise NotImplementedError("Subclasses must implement _inspect.")
