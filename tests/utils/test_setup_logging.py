"""Tests for logging setup helpers."""

import os
import sys

from agent_brain import utils


def test_setup_logging_uses_shared_log_file_off_windows(monkeypatch, tmp_path) -> None:
    """Non-Windows platforms should keep the shared log filename."""
    added_sinks: list[str] = []

    monkeypatch.setenv("AGENT_BRAIN_ENV", "dev")
    monkeypatch.setattr(utils.os, "name", "posix")
    monkeypatch.setattr(utils.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(utils.logger, "remove", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        utils.logger,
        "add",
        lambda sink, **kwargs: added_sinks.append(str(sink)),
    )

    utils.setup_logging(log_to_file=True)

    assert added_sinks == [str(tmp_path / ".agent-brain" / "agent-brain.log")]


def test_setup_logging_uses_per_process_log_file_on_windows(monkeypatch, tmp_path) -> None:
    """Windows uses per-process logs so rotation never contends across processes."""
    added_sinks: list[str] = []

    monkeypatch.setenv("AGENT_BRAIN_ENV", "dev")
    monkeypatch.setattr(utils.os, "name", "nt")
    monkeypatch.setattr(utils.os, "getpid", lambda: 4242)
    monkeypatch.setattr(utils.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(utils.logger, "remove", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        utils.logger,
        "add",
        lambda sink, **kwargs: added_sinks.append(str(sink)),
    )

    utils.setup_logging(log_to_file=True)

    assert added_sinks == [str(tmp_path / ".agent-brain" / "agent-brain-4242.log")]


def test_setup_logging_trims_stale_windows_pid_logs(monkeypatch, tmp_path) -> None:
    """Windows cleanup should bound stale PID-specific log files across runs."""
    log_dir = tmp_path / ".agent-brain"
    log_dir.mkdir()

    stale_logs = []
    for index in range(6):
        log_path = log_dir / f"agent-brain-{1000 + index}.log"
        log_path.write_text("old log", encoding="utf-8")
        mtime = 1_000 + index
        os.utime(log_path, (mtime, mtime))
        stale_logs.append(log_path)

    monkeypatch.setenv("AGENT_BRAIN_ENV", "dev")
    monkeypatch.setattr(utils.os, "name", "nt")
    monkeypatch.setattr(utils.os, "getpid", lambda: 4242)
    monkeypatch.setattr(utils.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(utils.logger, "remove", lambda *args, **kwargs: None)
    monkeypatch.setattr(utils.logger, "add", lambda *args, **kwargs: None)

    utils.setup_logging(log_to_file=True)

    remaining = sorted(path.name for path in log_dir.glob("agent-brain-*.log*"))
    assert remaining == [
        "agent-brain-1002.log",
        "agent-brain-1003.log",
        "agent-brain-1004.log",
        "agent-brain-1005.log",
    ]


def test_setup_logging_test_env_uses_stderr_only(monkeypatch) -> None:
    """Test mode should add one stderr sink and return before other branches run."""
    added_sinks: list[object] = []
    configured_calls: list[dict] = []

    monkeypatch.setenv("AGENT_BRAIN_ENV", "test")
    monkeypatch.setattr(utils.logger, "remove", lambda *args, **kwargs: None)
    monkeypatch.setattr(utils.logger, "add", lambda sink, **kwargs: added_sinks.append(sink))
    monkeypatch.setattr(
        utils.logger,
        "configure",
        lambda **kwargs: configured_calls.append(kwargs),
    )

    utils.setup_logging(log_to_file=True, log_to_stdout=True, structured_context=True)

    assert added_sinks == [sys.stderr]
    assert configured_calls == []


def test_setup_logging_log_to_stdout(monkeypatch) -> None:
    """stdout logging should attach a stderr sink outside test mode."""
    added_sinks: list[object] = []

    monkeypatch.setenv("AGENT_BRAIN_ENV", "dev")
    monkeypatch.setattr(utils.logger, "remove", lambda *args, **kwargs: None)
    monkeypatch.setattr(utils.logger, "add", lambda sink, **kwargs: added_sinks.append(sink))

    utils.setup_logging(log_to_stdout=True)

    assert added_sinks == [sys.stderr]


def test_setup_logging_suppresses_noisy_loggers(monkeypatch) -> None:
    """Third-party HTTP/file-watch loggers should be raised to WARNING."""
    monkeypatch.setenv("AGENT_BRAIN_ENV", "dev")
    monkeypatch.setattr(utils.logger, "remove", lambda *args, **kwargs: None)
    monkeypatch.setattr(utils.logger, "add", lambda *args, **kwargs: None)

    httpx_logger = utils.logging.getLogger("httpx")
    watchfiles_logger = utils.logging.getLogger("watchfiles.main")
    original_httpx_level = httpx_logger.level
    original_watchfiles_level = watchfiles_logger.level

    try:
        httpx_logger.setLevel(utils.logging.DEBUG)
        watchfiles_logger.setLevel(utils.logging.INFO)

        utils.setup_logging()

        assert httpx_logger.level == utils.logging.WARNING
        assert watchfiles_logger.level == utils.logging.WARNING
    finally:
        httpx_logger.setLevel(original_httpx_level)
        watchfiles_logger.setLevel(original_watchfiles_level)
