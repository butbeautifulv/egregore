"""Sub-containers backing bootstrap.container.Container.

Each module below owns construction logic for one responsibility cluster
(catalog/registry access, persistence/queue connectors, engagement/bus
orchestration, tool execution, auth, observability, policy resolution).
The top-level ``Container`` in ``bootstrap/container.py`` remains the sole
public entry point: it holds one instance of each sub-container and every
``get_*()`` method on ``Container`` delegates to the matching sub-container
method, preserving the pre-split public API exactly.
"""
