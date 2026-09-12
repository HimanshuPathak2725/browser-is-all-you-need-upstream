"""CPU-only, offline bootstrap checks for the frozen CHARM launch package.

Never loads model weights, creates GPU actors, trains, or contacts HF/W&B.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

MODULE = "glm47_posttraining.integrations.charm_bridge_preflight"
CRITICAL_FILES = (
    "src/sitecustomize.py",
    "src/glm47_posttraining/integrations/miles_glm47_bridge.py",
    "src/glm47_posttraining/integrations/miles_train_with_glm47_bridge.py",
    "src/glm47_posttraining/integrations/charm_bridge_preflight.py",
    "scripts/train_grpo.sh",
    "examples/grpo.sh",
)


def verify_package(root: Path) -> dict:
    manifest = json.loads((root / "launch-manifest.json").read_text())
    for name in CRITICAL_FILES:
        path = root / name
        if not path.is_file() or name not in manifest["files"]:
            raise RuntimeError(f"launch package missing required worker dependency: {name}")
    for name, digest in manifest["files"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise RuntimeError(f"invalid launch manifest path: {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"launch package hash mismatch: {name}")
    return {"files_verified": len(manifest["files"]),
            "launch_manifest_sha256": hashlib.sha256((root / "launch-manifest.json").read_bytes()).hexdigest()}


def probe(root: str, checkpoint: str) -> dict:
    # Do not register explicitly here: that would hide the startup bug.
    bootstrap = sys.modules.get("sitecustomize")
    expected = Path(root).resolve() / "src/sitecustomize.py"
    if bootstrap is None or Path(getattr(bootstrap, "__file__", "")).resolve() != expected:
        raise RuntimeError("fresh worker did not load the packaged sitecustomize.py")
    if os.environ.get("GLM47_REGISTER_BRIDGE") != "1":
        raise RuntimeError("GLM47_REGISTER_BRIDGE must be 1 in workers")
    from transformers import AutoConfig
    from megatron.bridge import AutoBridge

    config = AutoConfig.from_pretrained(checkpoint, local_files_only=True, trust_remote_code=False)
    if config.architectures != ["Glm4MoeLiteForCausalLM"]:
        raise RuntimeError("unexpected model architecture")
    # Same architecture validation as from_hf_pretrained, without loading weights.
    bridge = AutoBridge.from_hf_config(config)
    provider = bridge.to_megatron_provider(load_weights=False)
    return {"status": "passed", "pid": os.getpid(), "architecture": config.architectures[0],
            "bootstrap": str(expected), "provider": type(provider).__name__,
            "model_weights_loaded": False, "training_started": False}


def ray_probe(root: str, checkpoint: str) -> dict:
    import ray

    # A new, explicitly CPU-only local Ray instance; never attach to a training cluster.
    with tempfile.TemporaryDirectory(prefix="charm-bridge-ray-") as temp:
        ray.init(address="local", num_cpus=2, num_gpus=0, include_dashboard=False,
                 _node_ip_address="127.0.0.1", _temp_dir=temp, log_to_driver=False)
        try:
            @ray.remote(num_cpus=1, num_gpus=0)
            class Worker:
                def check(self):
                    return probe(root, checkpoint)

            workers = [Worker.remote() for _ in range(2)]
            records = ray.get([worker.check.remote() for worker in workers], timeout=180)
            if len({r["pid"] for r in records}) != 2 or any(r["pid"] == os.getpid() for r in records):
                raise RuntimeError("expected two independent Ray worker processes")
            return {"status": "passed", "ray_workers": records, "gpus_allocated": 0}
        finally:
            ray.shutdown()


def check(root: Path, checkpoint: Path, miles_root: Path, with_ray: bool) -> dict:
    package = verify_package(root)
    env = dict(os.environ)
    # Diagnostic children need no credentials or GPU visibility.
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "WANDB_API_KEY"):
        env.pop(key, None)
    env.update(GLM47_REGISTER_BRIDGE="1", CUDA_VISIBLE_DEVICES="", HF_HUB_OFFLINE="1",
               TRANSFORMERS_OFFLINE="1", WANDB_MODE="disabled", PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=f"/root/Megatron-LM/:{root / 'src'}:{miles_root}")
    records = {}
    for mode in (["--probe", "--ray-probe"] if with_ray else ["--probe"]):
        command = [sys.executable, "-m", MODULE, "--root", str(root),
                   "--checkpoint", str(checkpoint), mode]
        completed = subprocess.run(command, env=env, cwd=root, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
        if completed.returncode:
            # No environment or credential values are emitted.
            raise RuntimeError(f"{mode} failed:\n{completed.stderr[-6000:]}")
        lines = [line for line in completed.stdout.splitlines() if line.startswith("CHARM_BRIDGE_RESULT ")]
        if len(lines) != 1:
            raise RuntimeError(f"{mode} returned no unique result")
        records[mode.removeprefix("--")] = json.loads(lines[0].split(" ", 1)[1])
    return {"status": "passed", **package, **records, "training_started": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--miles-root", type=Path, default=Path("/root/miles"))
    parser.add_argument("--with-ray", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--ray-probe", action="store_true")
    args = parser.parse_args()
    root, checkpoint = args.root.resolve(), args.checkpoint.resolve()
    result = (probe(str(root), str(checkpoint)) if args.probe else
              ray_probe(str(root), str(checkpoint)) if args.ray_probe else
              check(root, checkpoint, args.miles_root.resolve(), args.with_ray))
    print("CHARM_BRIDGE_RESULT " + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
