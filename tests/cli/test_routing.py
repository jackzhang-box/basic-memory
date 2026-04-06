"""Tests for CLI routing utilities."""

import os

import pytest

from basic_memory.cli.commands.routing import force_routing


class TestForceRouting:
    """Tests for force_routing context manager."""

    def test_local_sets_env_var(self):
        """Local flag should set BASIC_MEMORY_FORCE_LOCAL."""
        os.environ.pop("BASIC_MEMORY_FORCE_LOCAL", None)

        with force_routing(local=True):
            assert os.environ.get("BASIC_MEMORY_FORCE_LOCAL") == "true"

        # Should be cleaned up after context exits
        assert os.environ.get("BASIC_MEMORY_FORCE_LOCAL") is None

    def test_neither_flag_no_change(self):
        """Neither flag should not change env vars."""
        os.environ.pop("BASIC_MEMORY_FORCE_LOCAL", None)

        with force_routing():
            assert os.environ.get("BASIC_MEMORY_FORCE_LOCAL") is None

        assert os.environ.get("BASIC_MEMORY_FORCE_LOCAL") is None

    def test_preserves_original_env_var(self):
        """Should restore original env var value after context exits."""
        os.environ["BASIC_MEMORY_FORCE_LOCAL"] = "original"

        with force_routing(local=True):
            assert os.environ.get("BASIC_MEMORY_FORCE_LOCAL") == "true"

        # Should restore original value
        assert os.environ.get("BASIC_MEMORY_FORCE_LOCAL") == "original"

        # Cleanup
        os.environ.pop("BASIC_MEMORY_FORCE_LOCAL", None)

    def test_restores_on_exception(self):
        """Should restore env vars even when exception is raised."""
        os.environ.pop("BASIC_MEMORY_FORCE_LOCAL", None)

        try:
            with force_routing(local=True):
                assert os.environ.get("BASIC_MEMORY_FORCE_LOCAL") == "true"
                raise RuntimeError("Test exception")
        except RuntimeError:
            pass

        # Should be cleaned up even after exception
        assert os.environ.get("BASIC_MEMORY_FORCE_LOCAL") is None
