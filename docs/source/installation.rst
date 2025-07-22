Installation
============

Requirements
-----------

The AI Defense Python SDK requires Python 3.8 or later.

Installing from PyPI
-------------------

The recommended way to install the AI Defense Python SDK is via pip:

.. code-block:: bash

    pip install cisco-aidefense-sdk

Installing from Source
---------------------

You can also install the SDK directly from the source code:

.. code-block:: bash

    git clone https://github.com/cisco-ai-defense/ai-defense-python-sdk
    cd ai-defense-python-sdk
    pip install .


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
