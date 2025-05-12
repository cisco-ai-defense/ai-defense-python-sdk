Contributing
============

Thank you for your interest in contributing to the AI Defense Python SDK! This document provides guidelines for contributions to the project.

Getting Started
--------------

1. **Fork the Repository**: Start by forking the repository on GitHub.

2. **Clone Your Fork**: Clone your fork to your local machine.

   .. code-block:: bash

      git clone https://github.com/YOUR-USERNAME/ai-defense-python-sdk.git
      cd ai-defense-python-sdk

      .. TODO: Update repository URL and cd command when package name changes

3. **Set Up Development Environment**: The project uses Poetry for dependency management.

   .. code-block:: bash

      # Install Poetry if you don't have it
      pip install poetry

      # Install dependencies
      poetry install

      # Activate the virtual environment
      poetry shell

4. **Create a Branch**: Create a branch for your feature or bug fix.

   .. code-block:: bash

      git checkout -b feature/your-feature-name

Development Guidelines
--------------------

- **Follow PEP 8**: Adhere to Python's PEP 8 style guide.
- **Add Tests**: Include tests for new features and bug fixes.
- **Update Documentation**: Keep documentation up-to-date with changes.
- **Use Type Hints**: Add type hints to function definitions for better IDE support and code clarity.

Pre-commit Hooks
--------------

The repository includes pre-commit hooks for code formatting and linting. Install them with:

.. code-block:: bash

   pre-commit install

Running Tests
-----------

Tests can be run using pytest:

.. code-block:: bash

   pytest

Pull Request Process
------------------

1. **Create a Pull Request**: Once your changes are ready, push your branch to your fork and create a pull request.
2. **CI Checks**: Ensure all CI checks pass.
3. **Code Review**: Address any feedback from the review process.
4. **Merge**: Once approved, your pull request will be merged.

Examples Structure
----------------

The SDK maintains a well-organized examples directory structure:

- ``/examples/chat/`` - Basic chat inspection examples
- ``/examples/chat/providers/`` - Provider-specific chat inspection examples
- ``/examples/http/`` - Basic HTTP inspection examples
- ``/examples/http/providers/`` - Provider-specific HTTP inspection examples
- ``/examples/advanced/`` - Advanced usage examples

If adding new examples, please maintain this organization.

License
------

By contributing to this project, you agree that your contributions will be licensed under the project's Apache 2.0 license.
