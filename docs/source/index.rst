AI Defense Python SDK Documentation
===================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   overview
   installation
   modules/index
   examples
   contributing
   license

Overview
--------

The ``cisco-aidefense-sdk`` provides a developer-friendly interface for protecting AI applications
using Cisco's AI Defense platform.
It enables you to detect security, privacy, and safety risks in real time, with flexible configuration and robust validation.

Features
--------

- **Agent Runtime SDK (agentsec)**: Auto-patch LLM and MCP clients with 2 lines of code -- supports API mode and Gateway mode with 10+ LLM providers.
- **Chat Inspection**: Analyze chat prompts, responses, or full conversations for risks.
- **HTTP Inspection**: Inspect HTTP requests and responses, including support for ``requests.Request``, ``requests.PreparedRequest``, and ``requests.Response`` objects as well as dictionary body types.
- **MCP Inspection**: Inspect MCP (Model Context Protocol) JSON-RPC 2.0 messages for security, privacy, and safety violations.
- **MCP Server Scanning**: Scan MCP servers for security threats and manage resource connections, policies, and events.
- **Strong Input Validation**: Prevent malformed requests and catch errors early.
- **Flexible Configuration**: Easily customize logging, retry policies, and connection pooling via YAML, environment variables, or programmatic kwargs.
- **Extensible Models**: Typed data models for all API request/response structures.
- **Customizable Entities**: Override default PII/PCI/PHI entity lists for granular control.
- **Robust Error Handling**: Typed exceptions for all error scenarios.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
