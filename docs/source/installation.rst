Installation
============

Requirements
-----------

The AI Defense Python SDK requires Python 3.8 or later.

Installing from PyPI
-------------------

The recommended way to install the AI Defense Python SDK is via pip:

.. code-block:: bash

    pip install aidefense-sdk

Installing from Source
---------------------

You can also install the SDK directly from the source code:

.. code-block:: bash

    git clone https://github.com/cisco-sbg/ai-defense-python-sdk.git
    cd ai-defense-python-sdk
    pip install .

.. TODO: Update repository URL when package name changes

Using Poetry
-----------

For development, the project uses Poetry for dependency management:

.. code-block:: bash

    # Install Poetry if you don't have it already
    pip install poetry

    # Install dependencies
    poetry install

    # Activate the virtual environment
    poetry shell
