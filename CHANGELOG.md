# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.3] - 2026-07-30

- Proxy stream attributes in OpenAI streaming wrapper
- Add policy ID, profile response, and policy-with-profiles SDK support
- Add validation SDK with standard and adaptive validation support

[2.1.3]: https://github.com/cisco-ai-defense/ai-defense-python-sdk/compare/v2.1.2...v2.1.3

## [2.1.2] - 2026-07-10

### Added

- **AIBOM high-level client** (`AiBomClient`) for analyze-and-submit workflows, with
  optional `cisco-aidefense-sdk[aibom]` extra for local analysis support
  ([#86](https://github.com/cisco-ai-defense/ai-defense-python-sdk/pull/86)).
- **MCP registry endpoints** for MCP server management
  ([#81](https://github.com/cisco-ai-defense/ai-defense-python-sdk/pull/81)).
- **MCPScan model alignment** with the service proto definitions
  ([#72](https://github.com/cisco-ai-defense/ai-defense-python-sdk/pull/72),
  re-landed in [#90](https://github.com/cisco-ai-defense/ai-defense-python-sdk/pull/90)).
- **`detected_pii` field** on inspection responses
  ([#104](https://github.com/cisco-ai-defense/ai-defense-python-sdk/pull/104)).
- **Google ADK agentsec example** under `examples/agentsec/2-agent-frameworks/google-adk-agent/`
  ([#103](https://github.com/cisco-ai-defense/ai-defense-python-sdk/pull/103)).
- **`UNSPECIFIED` connection status** handling in the connection event model enum
  ([#106](https://github.com/cisco-ai-defense/ai-defense-python-sdk/pull/106)).

### Changed

- `Config` singleton now logs a warning when re-requested with different parameters
  ([#102](https://github.com/cisco-ai-defense/ai-defense-python-sdk/pull/102)).
- Runtime version metadata (`aidefense/version.py`) and Sphinx docs (`docs/source/conf.py`)
  are synced to the package version for accurate `User-Agent` reporting.
- Updated `CONTRIBUTING.md`
  ([#93](https://github.com/cisco-ai-defense/ai-defense-python-sdk/pull/93)).
- Agentsec example `requirements.txt` files no longer list the PyPI `uuid` package
  ([#105](https://github.com/cisco-ai-defense/ai-defense-python-sdk/pull/105)).

### Fixed

- `ValidateMCPServersRequest` now enforces required fields
  ([#98](https://github.com/cisco-ai-defense/ai-defense-python-sdk/pull/98)).
- `GetMCPServerScanReportRequest` now enforces `filter_options` as required
  ([#100](https://github.com/cisco-ai-defense/ai-defense-python-sdk/pull/100)).
- AIBOM module is optional at import time with regression coverage when `cisco-aibom` is not installed.
- AIBOM example and client handling for checksum validation and BOM status values.

### Removed

- **Obsolete PyPI `uuid` dependency** — the SDK no longer declares a dependency on the
  PyPI `uuid==1.30` package
  ([#105](https://github.com/cisco-ai-defense/ai-defense-python-sdk/pull/105)).
  That package is a Python 2-era shim with no wheel; installing it shadows Python 3's
  stdlib `uuid` module. All SDK code uses only stdlib `uuid` APIs.

### Upgrade guidance

- Downstream packages should pin **`cisco-aidefense-sdk>=2.1.2`** to avoid transitively
  installing PyPI `uuid` via older SDK releases.
- After upgrading, verify `pip show uuid` returns nothing and
  `python -c "import uuid; print(uuid.__file__)"` points to the stdlib module.

[2.1.2]: https://github.com/cisco-ai-defense/ai-defense-python-sdk/compare/v2.1.1...v2.1.2
