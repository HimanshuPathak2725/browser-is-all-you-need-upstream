from pathlib import Path
import base64
import hashlib
import importlib.util

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("artifact_barrier", ROOT / "scripts/verify_cpp_grpo_artifacts.py")
barrier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(barrier)


class Clock:
    value = 0.0
    def now(self): return self.value
    def sleep(self, seconds): self.value += seconds


def local(tmp_path):
    path = tmp_path / "checkpoint.bin"
    path.write_bytes(b"checkpoint weights")
    metadata = {"size": str(path.stat().st_size), "generation": "123456",
                "md5Hash": base64.b64encode(hashlib.md5(path.read_bytes()).digest()).decode()}
    return {path.name: path}, metadata


def test_matching_server_bytes_record_generation(tmp_path):
    paths, metadata = local(tmp_path)
    result = barrier.verify(paths, lambda name, timeout: metadata)
    assert result["status"] == "passed"
    assert result["objects"]["checkpoint.bin"]["generation"] == "123456"


def test_pending_upload_is_polled_until_server_acknowledges(tmp_path):
    paths, metadata = local(tmp_path)
    clock, seen = Clock(), []
    def fetch(name, timeout):
        seen.append((name, timeout))
        return metadata if len(seen) == 3 else None
    result = barrier.verify(paths, fetch, timeout=10, poll=2, clock=clock.now, sleep=clock.sleep)
    assert result["status"] == "passed" and clock.value == 4
    assert len(seen) == 3


@pytest.mark.parametrize("state", ["missing", "wrong_md5", "wrong_size", "no_md5"])
def test_missing_or_wrong_remote_bytes_never_pass_and_timeout_is_bounded(tmp_path, state):
    paths, metadata = local(tmp_path)
    if state == "wrong_md5": metadata["md5Hash"] = "different bytes"
    if state == "wrong_size": metadata["size"] = "1"
    if state == "no_md5": metadata.pop("md5Hash")
    clock = Clock()
    result = barrier.verify(paths, lambda name, timeout: None if state == "missing" else metadata,
                            timeout=5, poll=2, clock=clock.now, sleep=clock.sleep)
    assert result["status"] == "failed" and result["reason"] == "timeout"
    assert clock.value == 5 and not result["objects"]
    assert "checkpoint.bin" in result["pending"]


def test_auth_failure_is_immediate_and_explicit(tmp_path):
    paths, _ = local(tmp_path)
    clock = Clock()
    def denied(name, timeout): raise barrier.MetadataFailure("metadata request failed (HTTP 403)")
    result = barrier.verify(paths, denied, timeout=5, clock=clock.now, sleep=clock.sleep)
    assert result["status"] == "failed" and "403" in result["detail"]
    assert clock.value == 0


def test_local_change_after_snapshot_cannot_be_acknowledged(tmp_path):
    paths, metadata = local(tmp_path)
    def fetch(name, timeout):
        paths[name].write_bytes(b"changed checkpoint")
        return metadata
    result = barrier.verify(paths, fetch)
    assert result["status"] == "failed" and "changed" in result["detail"]


def test_rsync_symlink_exclusions_are_not_followed(tmp_path):
    paths, _ = local(tmp_path)
    (tmp_path / "latest").symlink_to(paths["checkpoint.bin"])
    assert set(barrier.regular_files(tmp_path)) == {"checkpoint.bin"}


def test_launch_waits_for_remote_acknowledgement_on_all_exit_paths():
    import yaml
    config = yaml.safe_load((ROOT / "Reward_GRPO/cpp_grpo_final_skypilot.yaml").read_text())
    run = config["run"]
    cleanup = run[run.index("  cleanup() {"):run.index("  trap cleanup EXIT")] if "  cleanup() {" in run else run[run.index("cleanup() {"):run.index("trap cleanup EXIT")]
    assert cleanup.index('run_status.txt') < cleanup.index('900s rsync')
    assert 'verify_cpp_grpo_artifacts.py' in cleanup
    assert '--root "${run_root}"' in cleanup and '--file "${receipt}"' in cleanup
    assert 'exit 3' in cleanup and 'trap - EXIT' in cleanup
    assert '--file "${MILES_LORA_SOURCE_ADAPTER_PATH}/adapter_config.json"' in config["setup"]
