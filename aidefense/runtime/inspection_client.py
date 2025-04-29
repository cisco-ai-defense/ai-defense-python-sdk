from .models import Metadata, InspectionConfig
from ..exceptions import ValidationError
from typing import Dict, Any

from ..client import BaseClient
from ..config import Config

from .auth import RuntimeAuth
from .models import PII_ENTITIES, PCI_ENTITIES, PHI_ENTITIES, Rule, RuleName
from abc import abstractmethod, ABC


class InspectionClient(BaseClient, ABC):
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
        config (Config, optional): SDK configuration for endpoints, logging, retries, etc. If not provided, a default singleton Config is used.

    Attributes:
        default_enabled_rules (list): List of Rule objects for all RuleNames. Only rules present in DEFAULT_ENTITY_MAP (PII, PCI, PHI)
            will have their associated entity_types set; all others will have entity_types as None.
        auth (RuntimeAuth): The authentication object for API requests.
        config (Config): The runtime configuration object.
        api_key (str): The API key used for authentication.
    """

    # Default entity map for rules that require entity_types (PII, PCI, PHI)
    DEFAULT_ENTITY_MAP = {
        "PII": PII_ENTITIES,
        "PCI": PCI_ENTITIES,
        "PHI": PHI_ENTITIES,
    }

    def __init__(self, api_key: str, config: Config = None):
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
        config = config or Config()
        super().__init__(config)
        self.auth = RuntimeAuth(api_key)
        self.config = config
        self.api_key = api_key
        self.default_enabled_rules = [
            Rule(
                rule_name=rn,
                entity_types=(
                    self.DEFAULT_ENTITY_MAP[rn.name]
                    if rn.name in self.DEFAULT_ENTITY_MAP
                    else None
                ),
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
        raise NotImplementedError("Subclasses must implement _inspect.")

    def _parse_inspect_response(
        self, response_data: Dict[str, Any]
    ) -> "InspectResponse":
        self.config.logger.debug(
            f"_parse_inspect_response called | response_data: {response_data}"
        )
        """
        Parse API response (chat or http inspect) into an InspectResponse object.

        Args:
            response_data (Dict[str, Any]): The response data returned by the API.

        Returns:
            InspectResponse: The parsed inspection response object containing classifications, rules, severity, and other details.
        """
        from .models import Classification, Rule, RuleName, Severity, InspectResponse

        # Convert classifications from strings to enum values
        classifications = []
        if "classifications" in response_data and response_data["classifications"]:
            for cls in response_data["classifications"]:
                try:
                    classifications.append(Classification(cls))
                except ValueError:
                    pass
        # Parse rules if present
        rules = []
        if "rules" in response_data and response_data["rules"]:
            for rule_data in response_data["rules"]:
                rule_name = None
                if "rule_name" in rule_data:
                    try:
                        rule_name = RuleName(rule_data["rule_name"])
                    except ValueError:
                        pass
                classification = None
                if "classification" in rule_data:
                    try:
                        classification = Classification(rule_data["classification"])
                    except ValueError:
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
        if "severity" in response_data and response_data["severity"]:
            try:
                severity = Severity(response_data["severity"])
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
            request_dict["metadata"] = {
                k: v for k, v in metadata.__dict__.items() if v is not None
            }
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
                return {
                    "rule_name": rule.rule_name.value if rule.rule_name else None,
                    "entity_types": rule.entity_types,
                    "rule_id": rule.rule_id,
                    "classification": (
                        rule.classification.value if rule.classification else None
                    ),
                }

            config_dict["enabled_rules"] = [
                rule_to_dict(rule) for rule in config.enabled_rules if rule is not None
            ]

        for key in [
            "integration_profile_id",
            "integration_profile_version",
            "integration_tenant_id",
            "integration_type",
        ]:
            value = getattr(config, key, None)
            if value is not None:
                config_dict[key] = value

        if config_dict:
            request_dict["config"] = config_dict
        return request_dict
