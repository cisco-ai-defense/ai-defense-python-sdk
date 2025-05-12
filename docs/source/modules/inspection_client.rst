Inspection Client
================

.. automodule:: aidefense.runtime.inspection_client
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The InspectionClient is an abstract base class that serves as the intermediate layer between the low-level BaseClient and the concrete inspection clients (ChatInspectionClient and HttpInspectionClient). It adds AI Defense-specific functionality on top of the HTTP capabilities provided by BaseClient.

Class Hierarchy
--------------

.. code-block:: text

    BaseClient (Abstract Base Class)
        └── InspectionClient (Abstract Base Class)
                ├── ChatInspectionClient
                └── HttpInspectionClient

Core Functionality
-----------------

**Common Inspection Logic**

- Default rule handling and configuration
- Integration profile management
- Response parsing and interpretation
- InspectResponse object creation

**Shared Utilities**

- Entity type handling (PII, PCI, PHI entities)
- Metadata management
- Severity and classification interpretation

Implementation Details
---------------------

The InspectionClient serves as a bridge between the generic HTTP capabilities of BaseClient and the endpoint-specific functionality of the concrete clients:

.. code-block:: python

    # InspectionClient abstract method that derived classes must implement
    @abstractmethod
    def _inspect(
        self,
        # parameters vary by concrete implementation
        metadata: Optional[Metadata] = None,
        config: Optional[InspectionConfig] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> InspectResponse:
        """
        Implement the specific inspection logic for each endpoint.

        This must be implemented by each concrete client (Chat, HTTP)
        """
        pass

Rule Configuration
----------------

The InspectionClient provides common rule configuration functionality used by all derived clients:

.. code-block:: python

    # Rule configuration with entity types
    enabled_rules = [
        # PII rule with entity types
        Rule(
            rule_name=RuleName.PII,
            entity_types=PII_ENTITIES
        ),
        # PCI rule with entity types
        Rule(
            rule_name=RuleName.PCI,
            entity_types=PCI_ENTITIES
        ),
        # PHI rule with entity types
        Rule(
            rule_name=RuleName.PHI,
            entity_types=PHI_ENTITIES
        ),
        # Other rules without entity types
        Rule(rule_name=RuleName.PROMPT_INJECTION),
        Rule(rule_name=RuleName.JAILBREAK),
        # etc.
    ]

    # Config with enabled rules
    config = InspectionConfig(enabled_rules=enabled_rules)

This standardized rule configuration ensures consistent behavior across all inspection types.
