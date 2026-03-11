"""Exclude agent-framework example tests from root-level pytest collection.

These tests have their own dependencies and virtual environments and are
meant to be run inside each example directory, not from the repo root.
"""
collect_ignore_glob = ["*"]
