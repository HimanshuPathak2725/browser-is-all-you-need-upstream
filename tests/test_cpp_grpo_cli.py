"""The CLI delegates unchanged arguments to the validated launcher."""
import subprocess
from pathlib import Path

from typer.testing import CliRunner

import w8_biayn.cli as cli


def test_cpp_grpo_delegates_without_enabling_launch(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "run_command", lambda args, **kw: calls.append((args, kw)))
    result = CliRunner().invoke(cli.app, ["cpp-grpo", "--dataset-dir", "/tmp/a dataset",
                                         "--out", "/tmp/receipt"])
    assert result.exit_code == 0, result.output
    args, options = calls.pop()
    assert Path(args[1]).name == "launch_cpp_grpo_final.py"
    assert args[2:] == ["--dataset-dir", "/tmp/a dataset", "--out", "/tmp/receipt"]
    assert "--launch" not in args and not options


def test_cpp_grpo_help_reaches_launcher(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "run_command", lambda args, **kw: calls.append(args))
    result = CliRunner().invoke(cli.app, ["cpp-grpo", "--help"])
    assert result.exit_code == 0 and calls[0][-1] == "--help"


def test_cpp_grpo_preserves_explicit_launch_and_failure(monkeypatch):
    def failed(args, **kwargs):
        assert args[-1] == "--launch"
        raise subprocess.CalledProcessError(2, args)
    monkeypatch.setattr(cli, "run_command", failed)
    result = CliRunner().invoke(cli.app, ["cpp-grpo", "--launch"])
    assert result.exit_code == 2
