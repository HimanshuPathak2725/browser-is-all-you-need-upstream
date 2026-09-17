"""Regression coverage for the missing fresh-worker bootstrap in CHARM snapshots."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from Reward_GRPO import stack_v2_charm_grpo as base
from glm47_posttraining.integrations import charm_bridge_preflight as check
from glm47_posttraining.integrations import stack_v2_charm_run as run


@pytest.fixture
def snapshot(tmp_path):
    root = tmp_path / "snapshot"
    run.stage_launch(argparse.Namespace(out=root, run_id="worker-regression"))
    return root


def test_corrected_snapshot_contains_verified_bootstrap_and_unchanged_receipt(snapshot):
    result = check.verify_package(snapshot)
    assert result["files_verified"] > 100
    assert (snapshot / "src/sitecustomize.py").read_bytes() == (base.ROOT.parent / "src/sitecustomize.py").read_bytes()
    for relative in ("Reward_GRPO/stack_v2_charm_grpo.py", "Reward_GRPO/stack_v2_charm_integration_receipt.json"):
        assert (snapshot / relative).read_bytes() == (base.ROOT.parent / relative).read_bytes()
    assert {path.name for path in (snapshot / "scripts").iterdir()} == run.RUNTIME_SCRIPTS
    base.check_receipt()
    with pytest.raises(FileExistsError):
        run.stage_launch(argparse.Namespace(out=snapshot, run_id="must-not-overwrite"))


@pytest.mark.parametrize("name", check.CRITICAL_FILES)
def test_missing_worker_dependency_rejected(snapshot, name):
    (snapshot / name).unlink()
    with pytest.raises(RuntimeError, match="missing required worker dependency"):
        check.verify_package(snapshot)


def test_modified_bootstrap_rejected(snapshot):
    (snapshot / "src/sitecustomize.py").write_text("# omitted registration\n")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        check.verify_package(snapshot)


def test_original_packager_omission_reproduces_failure(tmp_path):
    root = tmp_path / "original"
    base.stage_launch(argparse.Namespace(out=root, run_id="negative-control"))
    with pytest.raises(RuntimeError, match="src/sitecustomize.py"):
        check.verify_package(root)


def test_missing_automatic_import_rejected_without_loading_model(monkeypatch, tmp_path):
    monkeypatch.delitem(sys.modules, "sitecustomize", raising=False)
    with pytest.raises(RuntimeError, match="did not load"):
        check.probe(str(tmp_path), "not-a-model")


def test_disabled_registration_rejected(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "sitecustomize", SimpleNamespace(__file__=str(tmp_path / "src/sitecustomize.py")))
    monkeypatch.setenv("GLM47_REGISTER_BRIDGE", "0")
    with pytest.raises(RuntimeError, match="must be 1"):
        check.probe(str(tmp_path), "not-a-model")


def test_probe_children_have_no_credentials_or_gpu_visibility(snapshot, monkeypatch):
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "WANDB_API_KEY"):
        monkeypatch.setenv(key, "test-secret")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        env = kwargs["env"]
        assert not any(key in env for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "WANDB_API_KEY"))
        assert env["CUDA_VISIBLE_DEVICES"] == ""
        assert env["HF_HUB_OFFLINE"] == "1"
        assert env["WANDB_MODE"] == "disabled"
        assert env["GLM47_REGISTER_BRIDGE"] == "1"
        assert str(snapshot / "src") in env["PYTHONPATH"]
        return SimpleNamespace(returncode=0, stdout='CHARM_BRIDGE_RESULT {"status":"passed"}\n')

    monkeypatch.setattr(check.subprocess, "run", fake_run)
    assert check.check(snapshot, Path("/model"), Path("/root/miles"), True)["status"] == "passed"
    assert [call[-1] for call in calls] == ["--probe", "--ray-probe"]


def test_charm_setup_checks_workers_before_training_and_shell_parses():
    config = yaml.safe_load((base.ROOT / "stack_v2_charm_grpo_skypilot.yaml").read_text())
    assert config["envs"]["GLM47_REGISTER_BRIDGE"] == "1"
    assert "charm_bridge_preflight" in config["setup"] and "--with-ray" in config["setup"]
    for phase in ("setup", "run"):
        subprocess.run(["bash", "-n"], input=config[phase], text=True, check=True)
    launcher = (base.ROOT.parent / "launch_stack_v2_charm_grpo.sh").read_text()
    assert "python3 -m glm47_posttraining.integrations.stack_v2_charm_run" in launcher
    subprocess.run(["bash", "-n"], input=launcher, text=True, check=True)
