#!/usr/bin/env python3
"""Freeze an authenticated C++ cohort launch; dry-run unless --launch is explicit."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
RUNTIME_IMAGE = "docker:ghcr.io/tokenbender/glm47-runtime@sha256:b4f67ba1519bf276fe1dcb6fcb457600e4a256bc0d5c3011fcbd9cc05f240d43"
SOURCE_CHECKPOINT = "generalized-cpp-kernel-grpo20-spot-20260829-083214-retry1/iter_0000014"
SOURCE_ADAPTER_SHA256 = "b4bb3a250e28696c597d84db459caa75978e160996818dbfce22b8896b2c794b"
# Full project-level launch set shared with w8-biayn doctor --cloud. Checking only
# compute.instances.create misses the permissions needed by SkyPilot bootstrap.
GCP_PERMISSIONS = (
    "compute.disks.create", "compute.disks.list", "compute.firewalls.create",
    "compute.firewalls.delete", "compute.firewalls.get", "compute.globalOperations.get",
    "compute.instances.create", "compute.instances.delete", "compute.instances.get",
    "compute.instances.list", "compute.instances.setLabels", "compute.instances.setServiceAccount",
    "compute.instances.start", "compute.instances.stop", "compute.networks.get",
    "compute.networks.getEffectiveFirewalls", "compute.networks.list", "compute.projects.get",
    "compute.reservations.list", "compute.subnetworks.list", "compute.subnetworks.use",
    "compute.subnetworks.useExternalIp", "compute.zoneOperations.get", "iam.roles.get",
    "iam.serviceAccounts.create", "iam.serviceAccounts.get", "resourcemanager.projects.get",
    "resourcemanager.projects.getIamPolicy", "resourcemanager.projects.setIamPolicy",
    "serviceusage.services.enable", "serviceusage.services.list", "serviceusage.services.use",
    "storage.buckets.create", "storage.buckets.delete",
)
EXTRA_SOURCE_FILES = (
    "pyproject.toml", "examples/grpo.sh", "scripts/train_grpo.sh",
    "src/sitecustomize.py",
    "scripts/check_runtime.py", "scripts/prepare_grpo_adapter.py",
    "scripts/create_grpo_training_gate.py", "scripts/publish_results.py",
    "scripts/verify_cpp_grpo_artifacts.py",
    "scripts/launch_cpp_grpo_final.py", "scripts/evaluate_cpp_grpo_final.py", "scripts/evaluate.py",
    "Reward_GRPO/cpp_grpo_final_skypilot.yaml",
)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def safe_file(root, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise RuntimeError("unsafe artifact path")
    result = Path(root) / path
    if not result.is_file() or result.is_symlink() or Path(root).resolve() not in result.resolve().parents:
        raise RuntimeError(f"missing or unsafe artifact: {relative}")
    return result


def expected_control_catalog(reward, cohort):
    from Reward_GRPO.topic_coverage.controls import controls, enum_controls
    registry = reward.base._registry()
    selected = set(cohort["train"] + cohort["validation"])
    expected = Counter((task, "reference", "reference") for task in selected)
    for sample in reward.base._mutation_control_samples(registry):
        metadata = sample["metadata"]
        if metadata["problem_id"] in cohort["train"]:
            expected[(metadata["problem_id"], "generalized_control", metadata["mutation_case"])] += 1
    for task in sorted(selected & set(reward.TOPICS)):
        for control in controls(task, reward.control_sources(registry.resolve(task), task)):
            if control.kind != "diagnostic":
                expected[(task, "topic_" + control.kind, control.name)] += 1
    if "kindergarten-garden" in selected:
        task = "kindergarten-garden"
        for control in enum_controls(task, reward.reference_sources(registry.resolve(task))):
            kind = "official_positive" if control.expected == "pass" else "official_semantic"
            expected[(task, kind, control.name)] += 1
    for sample in reward.base._heldout_negative_samples(registry):
        task = sample["metadata"]["problem_id"]
        if task in cohort["validation"]:
            expected[(task, "heldout_negative", "starter")] += 1
    return expected


def validate_preflight(path, reward, cohort, expected=None):
    receipt = json.loads(path.read_text())
    expected = expected if expected is not None else expected_control_catalog(reward, cohort)
    count, digest = sum(expected.values()), reward.contract_digest()
    if (receipt.get("status") != "passed" or count == 0
            or receipt.get("cases") != count or receipt.get("matched") != count
            or receipt.get("combined_reward_sha256") != digest
            or receipt.get("train") != cohort["train"]
            or receipt.get("validation") != cohort["validation"]
            or receipt.get("sandbox_image_id") != reward.image_identity()):
        raise RuntimeError("complete passing preflight for the exact cohort, contract and image is required")
    observed = Counter()
    for case_file in sorted(path.parent.glob("case-*.json")):
        case = json.loads(case_file.read_text())
        result = case.get("result", {})
        if (case.get("matched") is not True or result.get("infrastructure_error") is not False
                or result.get("combined_reward_sha256") != digest
                or result.get("sandbox_image_id") != receipt["sandbox_image_id"]
                or result.get("problem_id") != case.get("task")):
            raise RuntimeError("invalid, stale or unauthenticated preflight case: " + case_file.name)
        observed[(case.get("task"), case.get("kind"), case.get("control"))] += 1
    if observed != expected:
        raise RuntimeError("preflight catalog contains missing, duplicate or unexpected controls")
    return receipt


def validate_dataset(directory, cohort, digest, registry=None):
    directory = Path(directory)
    manifest = json.loads(safe_file(directory, "manifest.json").read_text())
    if manifest.get("combined_reward_sha256") != digest:
        raise RuntimeError("dataset uses a different reward contract")
    for relative, expected in manifest.get("file_sha256s", {}).items():
        if sha256(safe_file(directory, relative)) != expected:
            raise RuntimeError("dataset file hash mismatch: " + relative)
    if not manifest.get("file_sha256s"):
        raise RuntimeError("dataset manifest must authenticate its files")
    for relative, split in (("grpo/train.jsonl", "train"), ("eval/validation.jsonl", "validation")):
        rows = [json.loads(line) for line in safe_file(directory, relative).read_text().splitlines() if line]
        ids = []
        for row in rows:
            metadata = row.get("metadata", {})
            task = metadata.get("problem_id")
            if metadata.get("combined_reward_sha256") != digest:
                raise RuntimeError("dataset row has stale verifier binding")
            if registry is not None and metadata.get("generalized_verifier_manifest_sha256") != registry.resolve(task).manifest_sha256:
                raise RuntimeError("dataset row has stale task binding")
            ids.append(task)
        if Counter(ids) != Counter(cohort[split]):
            raise RuntimeError("dataset task IDs or row count differ from cohort: " + split)
    return {path.relative_to(directory).as_posix(): sha256(path)
            for path in sorted(directory.rglob("*")) if path.is_file()
            and ".cache" not in path.relative_to(directory).parts
            and ".git" not in path.relative_to(directory).parts}


def validate_launch_config(config, reward):
    resources, env = config["resources"], config["envs"]
    if (config.get("num_nodes") != 1 or resources.get("infra") != "gcp"
            or resources.get("use_spot") is not True or resources.get("accelerators") != "H100:8"
            or resources.get("instance_type") != "a3-highgpu-8g"
            or resources.get("image_id") != RUNTIME_IMAGE or "any_of" in resources or "ordered" in resources):
        raise RuntimeError("launch requires the pinned runtime on one Spot eight-H100 host")
    if (env.get("GLM47_CPP_SANDBOX_IMAGE") != reward.IMAGE
            or env.get("MILES_DATA_CURRICULUM") != reward.CURRICULUM
            or env.get("MILES_EXPECTED_SOURCE_ADAPTER_SHA256") != SOURCE_ADAPTER_SHA256
            or env.get("MILES_NUM_ROLLOUT") != "20"
            or "charm_bridge" in config.get("setup", "")
            or "build-data" in config.get("run", "")):
        raise RuntimeError("launch configuration drifted from the validated final experiment")
    return config


def verify_stage(root):
    root = Path(root)
    record = json.loads((root / "launch-manifest.json").read_text())
    for relative, expected in record["files"].items():
        if sha256(safe_file(root, relative)) != expected:
            raise RuntimeError("staged source or evidence hash mismatch: " + relative)
    return record


def stage(root, output, reward, cohort, preflight_path, dataset):
    if output.resolve() == root.resolve() or root.resolve() in output.resolve().parents:
        raise RuntimeError("launch staging must be outside the repository")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip():
        raise RuntimeError("commit the intentional changes and use a clean worktree before staging")
    tracked = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0"))
    reward_hashes = reward.file_hashes()
    fresh_digest = hashlib.sha256(json.dumps(reward_hashes, sort_keys=True).encode()).hexdigest()
    if fresh_digest != reward.contract_digest():
        raise RuntimeError("reward files changed after preflight validation")
    # The combined distribution declares both Python packages. Include only
    # tracked browser-package files so the staged editable install remains valid
    # without adding unrelated checkout state to the reward/image identity.
    browser_package = {name for name in tracked if name.startswith("src/w8_biayn/")}
    names = set(reward_hashes) | set(EXTRA_SOURCE_FILES) | browser_package
    if not names <= tracked:
        raise RuntimeError("launch allowlist contains untracked files: " + ", ".join(sorted(names - tracked)))
    output.mkdir(parents=True, exist_ok=False)
    snapshot = output / "source"
    snapshot.mkdir()
    for relative in sorted(names):
        source = safe_file(root, relative)
        if "charm" in relative.lower() or any(part in {"results", "checkpoints", ".env"} for part in Path(relative).parts):
            raise RuntimeError("unrelated artifact in source allowlist: " + relative)
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        if relative in reward_hashes and sha256(destination) != reward_hashes[relative]:
            raise RuntimeError("reward source changed during staging: " + relative)
    evidence = snapshot / "preflight"
    evidence.mkdir()
    for source in [preflight_path, *sorted(preflight_path.parent.glob("case-*.json"))]:
        shutil.copyfile(source, evidence / source.name)
    record = {
        "schema_version": 1, "kind": "cpp-grpo-final-launch", "cohort": cohort,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "combined_reward_sha256": reward.contract_digest(), "sandbox_image_id": reward.image_identity(),
        "source_checkpoint": SOURCE_CHECKPOINT, "source_adapter_sha256": SOURCE_ADAPTER_SHA256,
        "dataset": dataset, "runtime_image": RUNTIME_IMAGE,
        "files": {p.relative_to(snapshot).as_posix(): sha256(p) for p in sorted(snapshot.rglob("*")) if p.is_file()},
    }
    write_json(snapshot / "launch-manifest.json", record)
    verify_stage(snapshot)
    return snapshot, record


def scoped_cloud_env(credentials, environment):
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account
    info = json.loads(credentials.read_text())
    if info.get("type") != "service_account" or not re.fullmatch(r"[a-z][a-z0-9-]+", info.get("project_id", "")):
        raise RuntimeError("an explicit GCP service-account credential is required")
    project = info["project_id"]
    creds = service_account.Credentials.from_service_account_file(str(credentials), scopes=["https://www.googleapis.com/auth/cloud-platform"])
    response = AuthorizedSession(creds).post(
        f"https://cloudresourcemanager.googleapis.com/v1/projects/{project}:testIamPermissions",
        json={"permissions": list(GCP_PERMISSIONS)}, timeout=30)
    response.raise_for_status()
    missing = sorted(set(GCP_PERMISSIONS) - set(response.json().get("permissions", [])))
    if missing:
        raise RuntimeError("GCP project launch permissions missing: " + ", ".join(missing))
    env = dict(environment)
    env.update(GOOGLE_APPLICATION_CREDENTIALS=str(credentials.resolve()),
               CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE=str(credentials.resolve()),
               CLOUDSDK_CORE_PROJECT=project, GOOGLE_CLOUD_PROJECT=project,
               GCLOUD_PROJECT=project, CLOUDSDK_CORE_DISABLE_PROMPTS="1")
    return env, {"project": project, "permissions": list(GCP_PERMISSIONS), "status": "passed"}


def online_gates(args, dataset_files):
    import requests
    from huggingface_hub import HfApi, hf_hub_download
    token, wandb_key = os.environ.get("HF_TOKEN"), os.environ.get("WANDB_API_KEY")
    if not token or not wandb_key or not args.hf_user or not args.wandb_user:
        raise RuntimeError("launch requires explicit HF_TOKEN/WANDB_API_KEY and --hf-user/--wandb-user")
    api = HfApi(token=token)
    if api.whoami()["name"] != args.hf_user:
        raise RuntimeError("HF authentication belongs to a different account")
    if api.dataset_info(args.dataset_repo, revision=args.dataset_revision).sha != args.dataset_revision:
        raise RuntimeError("dataset revision did not resolve to the requested immutable commit")
    for relative, expected in dataset_files.items():
        downloaded = hf_hub_download(args.dataset_repo, relative, repo_type="dataset", revision=args.dataset_revision, token=token)
        if sha256(downloaded) != expected:
            raise RuntimeError("published dataset differs from validated local bytes: " + relative)
    response = requests.post("https://api.wandb.ai/graphql", auth=("api", wandb_key),
        json={"query": "query($entity:String!){viewer{username} entity(name:$entity){name}}",
              "variables": {"entity": args.wandb_entity}}, timeout=30)
    response.raise_for_status()
    data = response.json().get("data", {})
    if data.get("viewer", {}).get("username") != args.wandb_user or data.get("entity", {}).get("name") != args.wandb_entity:
        raise RuntimeError("W&B account/entity does not match the requested run identity")
    if args.credentials is None:
        raise RuntimeError("--credentials or GOOGLE_APPLICATION_CREDENTIALS must name the scoped service account")
    env, iam = scoped_cloud_env(args.credentials, os.environ)
    return env, {"hf_user": args.hf_user, "wandb_user": args.wandb_user, "wandb_entity": args.wandb_entity, "gcp": iam}



def authenticate_model_catalog(directory, model, revision, source, model_info):
    """Authenticate cached model payloads against the immutable HF tree."""
    if model_info.sha != revision:
        raise RuntimeError("HF model metadata resolved to a different revision")
    siblings = {item.rfilename: item for item in model_info.siblings}
    files = {}
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(directory).as_posix()
        safe_file(directory, relative)
        digest = sha256(path)
        if relative == "MODEL_REVISION":
            if path.read_text().strip() != revision:
                raise RuntimeError("cached model revision marker differs from pin")
        else:
            sibling = siblings.get(relative)
            if sibling is None:
                raise RuntimeError("cached model contains a file absent from pinned HF tree: " + relative)
            lfs = sibling.lfs
            expected = (lfs.get("sha256") if isinstance(lfs, dict) else getattr(lfs, "sha256", None)) if lfs else None
            if expected:
                valid = digest == expected
            else:
                git_blob = hashlib.sha1(("blob " + str(path.stat().st_size) + "\0").encode())
                with path.open("rb") as handle:
                    for block in iter(lambda: handle.read(1024 * 1024), b""):
                        git_blob.update(block)
                valid = git_blob.hexdigest() == sibling.blob_id
            if not valid:
                raise RuntimeError("cached model bytes differ from pinned HF tree: " + relative)
        files[relative] = digest
    if "config.json" not in files or not any(name.endswith(".safetensors") for name in files):
        raise RuntimeError("cached model is missing configuration or weights")
    return {"model": model, "revision": revision, "hf_revision": model_info.sha,
            "authentication": "huggingface-pinned-revision", "source": source, "files": files}


def fetch_data(record_path, output):
    from huggingface_hub import hf_hub_download
    record = verify_stage(record_path.parent)
    pin = record["dataset"]
    if output.exists():
        raise RuntimeError("dataset destination must be new; refusing to reuse stale run data")
    output.mkdir(parents=True)
    for relative, expected in pin["files"].items():
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise RuntimeError("unsafe dataset path")
        downloaded = hf_hub_download(pin["repo"], relative, repo_type="dataset", revision=pin["revision"], token=os.environ.get("HF_TOKEN"))
        if sha256(downloaded) != expected:
            raise RuntimeError("downloaded pinned dataset hash mismatch: " + relative)
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(downloaded, destination)
    from Reward_GRPO import generalized_cpp_topic_grpo as reward
    if reward.contract_digest() != record["combined_reward_sha256"] or reward.image_identity() != record["sandbox_image_id"]:
        raise RuntimeError("remote reward code/image differs from the validated launch")
    validate_dataset(output, record["cohort"], record["combined_reward_sha256"], reward.base._registry())
    return {"status": "passed", "repo": pin["repo"], "revision": pin["revision"], "files": len(pin["files"])}


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "model-catalog":
        from huggingface_hub import HfApi
        sub = argparse.ArgumentParser()
        sub.add_argument("command")
        sub.add_argument("--directory", type=Path, required=True)
        sub.add_argument("--output", type=Path, required=True)
        sub.add_argument("--model", required=True)
        sub.add_argument("--revision", required=True)
        sub.add_argument("--source", required=True)
        args = sub.parse_args()
        if args.output.exists() or args.directory.resolve() in args.output.resolve().parents:
            sub.error("model catalog must be a new file outside the model directory")
        info = HfApi(token=os.environ.get("HF_TOKEN")).model_info(args.model, revision=args.revision, files_metadata=True)
        record = authenticate_model_catalog(args.directory, args.model, args.revision, args.source, info)
        write_json(args.output, record)
        print(json.dumps({"status": "passed", "model": args.model, "revision": args.revision,
                          "files": len(record["files"]), "catalog_sha256": sha256(args.output)}))
        return 0
    if len(sys.argv) > 1 and sys.argv[1] in {"verify-stage", "fetch-data"}:
        sub = argparse.ArgumentParser()
        sub.add_argument("command")
        sub.add_argument("--record", type=Path, default=ROOT / "launch-manifest.json")
        sub.add_argument("--out", type=Path)
        args = sub.parse_args()
        if args.command == "fetch-data" and args.out is None:
            sub.error("fetch-data requires --out")
        result = (fetch_data(args.record, args.out) if args.command == "fetch-data"
                  else {"status": "passed", "source_commit": verify_stage(args.record.parent)["source_commit"]})
        print(json.dumps(result, sort_keys=True))
        return 0
    import yaml
    from Reward_GRPO import generalized_cpp_topic_grpo as reward
    from Reward_GRPO.generalized_cpp_cohort import load_cohort
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--preflight-receipt", required=True, type=Path)
    parser.add_argument("--dataset-dir", required=True, type=Path)
    parser.add_argument("--dataset-repo", required=True)
    parser.add_argument("--dataset-revision", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--credentials", type=Path, default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
    parser.add_argument("--hf-user")
    parser.add_argument("--wandb-user")
    parser.add_argument("--wandb-entity", default="himanshu2725pathak-wootzapp")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.dataset_revision):
        raise RuntimeError("--dataset-revision must be the immutable 40-character HF commit")
    cohort = load_cohort()
    preflight = validate_preflight(args.preflight_receipt, reward, cohort)
    files = validate_dataset(args.dataset_dir, cohort, reward.contract_digest(), reward.base._registry())
    config = validate_launch_config(yaml.safe_load((ROOT / "Reward_GRPO/cpp_grpo_final_skypilot.yaml").read_text()), reward)
    env, identities = dict(os.environ), {"status": "not_checked_dry_run"}
    if args.launch:
        missing = [tool for tool in ("sky", "docker") if shutil.which(tool) is None]
        if missing:
            raise RuntimeError("missing launch tools: " + ", ".join(missing) +
                               "; install the documented launch dependencies before --launch")
        env, identities = online_gates(args, files)
    snapshot, record = stage(ROOT, args.out, reward, cohort, args.preflight_receipt,
                             {"repo": args.dataset_repo, "revision": args.dataset_revision, "files": files})
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id, cluster = "cpp-grpo-final-v1-" + stamp, "cpp-grpo-final-" + stamp
    image_tar = args.out.resolve() / "reward-image.tar"
    if args.launch:
        subprocess.run(["docker", "save", "-o", str(image_tar), preflight["sandbox_image_id"]], check=True)
    config["workdir"] = str(snapshot.resolve())
    config["envs"].update(MILES_RUN_ID=run_id, GLM47_SOURCE_COMMIT=record["source_commit"],
        WANDB_ENTITY=args.wandb_entity, MILES_EXPECTED_TRAIN_COUNT=str(len(cohort["train"])),
        FINAL_REWARD_IMAGE_ID=preflight["sandbox_image_id"], FINAL_REWARD_CONTRACT=reward.contract_digest())
    config["file_mounts"]["/workspace/final-verifier-image.tar"] = str(image_tar)
    rendered = args.out / "launch.yaml"
    rendered.write_text(yaml.safe_dump(config, sort_keys=False))
    command = ["sky", "launch", "-y", "--down", "--detach-run", "-c", cluster, str(rendered),
               "--secret", "WANDB_API_KEY", "--secret", "HF_TOKEN"]
    receipt = {"run_id": run_id, "cluster": cluster, "launch_requested": args.launch,
               "command": command, "source_commit": record["source_commit"], "dataset": record["dataset"],
               "cohort": cohort, "combined_reward_sha256": record["combined_reward_sha256"],
               "sandbox_image_id": record["sandbox_image_id"], "identities": identities,
               "runtime_image": RUNTIME_IMAGE, "preflight_sha256": sha256(args.preflight_receipt),
               "image_archive_sha256": sha256(image_tar) if args.launch else None,
               "operations": {"status": ["sky", "status", cluster],
                              "logs": ["sky", "logs", cluster],
                              "teardown": ["sky", "down", "-y", cluster]},
               "operation_auth": "reuse the same scoped GCP credential environment; no global auth changes"}
    write_json(args.out / "launch-receipt.json", receipt)
    print(json.dumps(receipt, indent=2), flush=True)
    if args.launch:
        result = subprocess.run(command, env=env, cwd=snapshot)
        write_json(args.out / "launch-result.json", {"exit_code": result.returncode})
        return result.returncode
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
