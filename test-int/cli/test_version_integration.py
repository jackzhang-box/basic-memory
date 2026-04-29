"""Integration tests for version command."""

from typer.testing import CliRunner

from agent_brain.cli.main import app
import agent_brain


def test_version_command():
    """Test 'bm --version' command shows version."""
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert agent_brain.__version__ in result.stdout
