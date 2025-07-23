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

The ``cisco-aidefense-sdk`` provides a developer-friendly interface for inspecting chat conversations and HTTP
requests/responses using Cisco's AI Defense API.
It enables you to detect security, privacy, and safety risks in real time, with flexible configuration and robust validation.

Features
--------

- **Chat Inspection**: Analyze chat prompts, responses, or full conversations for risks.
- **HTTP Inspection**: Inspect HTTP requests and responses, including support for ``requests.Request``, ``requests.PreparedRequest``, and ``requests.Response`` objects as well as dictionary body types.
- **Strong Input Validation**: Prevent malformed requests and catch errors early.
- **Flexible Configuration**: Easily customize logging, retry policies, and connection pooling.
- **Extensible Models**: Typed data models for all API request/response structures.
- **Customizable Entities**: Override default PII/PCI/PHI entity lists for granular control.
- **Robust Error Handling**: Typed exceptions for all error scenarios.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
