#!/usr/bin/env python3
"""CHARM-only credential gate and final-adapter publishing; no training imports.

Preflight performs only identity/permission queries, never commits or W&B runs.
No implicit HF cache, git credentials, netrc, or other users' credentials are used.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import shlex
import sys
import urllib.error
import urllib.request
from pathlib import Path

HF_ENDPOINT = "https://huggingface.co"
WANDB_ENDPOINT = "https://api.wandb.ai"
PROJECT = "glm47-stack-v2-charm-grpo"
APPROVED_HF_ACCOUNT = "HimanshuPathak"
APPROVED_HF_MODEL_REPO = "HimanshuPathak/Stackv2grpo"


class GateError(Exception):
    """Contains only a fixed, secret-safe diagnostic."""


def required(env, name):
    value = env.get(name, "").strip()
    if not value:
        raise GateError(f"missing {name}")
    return value


def hf_token(env):
    for name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        if env.get(name, "").strip():
            return env[name].strip()
    # Explicitly selected runtime only: never fall back to ~/.cache or ~/.netrc.
    path = env.get("HF_TOKEN_PATH")
    if not path and env.get("HF_HOME"):
        path = str(Path(env["HF_HOME"]) / "token")
    if path:
        try:
            value = Path(path).read_text().strip()
            if value:
                return value
        except (OSError, UnicodeError):
            pass
    raise GateError("missing HF_TOKEN (or an explicit HF_TOKEN_PATH/HF_HOME token)")


def wandb_key(env):
    if env.get("WANDB_API_KEY", "").strip():
        return env["WANDB_API_KEY"].strip()
    path = env.get("MILES_WANDB_ENV_FILE")
    if not path:
        raise GateError("missing WANDB_API_KEY or explicitly selected MILES_WANDB_ENV_FILE")
    try:
        matches = []
        for line in Path(path).read_text().splitlines():
            match = re.match(r"^\s*(?:export\s+)?WANDB_API_KEY\s*=\s*(.*)$", line)
            if match:
                values = shlex.split(match[1], comments=True, posix=True)
                if len(values) != 1 or not values[0] or "$" in values[0] or "`" in values[0]:
                    raise ValueError("not a literal key")
                matches.append(values[0])
        if len(matches) != 1:
            raise ValueError("missing or ambiguous key")
        return matches[0]
    except (OSError, UnicodeError, ValueError):
        raise GateError("selected Himanshu W&B config has no unambiguous literal credential") from None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(url, authorization, body=None, *, expect_json=True):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": authorization, "Content-Type": "application/json",
        "User-Agent": "charm-grpo-preflight/1",
    })
    # Refuse redirects; credentials must never be forwarded to another host.
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=25) as response:
            payload = response.read()
        return json.loads(payload) if expect_json and payload else {}
    except urllib.error.HTTPError as exc:
        raise GateError(f"authentication/permission request failed (HTTP {exc.code})") from None
    except (OSError, ValueError):
        raise GateError("authentication/permission request failed (network or response error)") from None


def check_hf(env):
    token = hf_token(env)
    expected = required(env, "MILES_HF_EXPECTED_USER")
    repo = required(env, "MILES_HF_MODEL_REPO")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*/[A-Za-z0-9][A-Za-z0-9._-]*", repo) or ".." in repo or "--" in repo:
        raise GateError("MILES_HF_MODEL_REPO must be namespace/model-repository")
    if env.get("HF_ENDPOINT", HF_ENDPOINT).rstrip("/") != HF_ENDPOINT:
        raise GateError("this launcher supports only the official Hugging Face endpoint")
    if expected != APPROVED_HF_ACCOUNT or repo != APPROVED_HF_MODEL_REPO:
        raise GateError("HF account/model repository is not the approved publication target")
    identity = request_json(HF_ENDPOINT + "/api/whoami-v2", "Bearer " + token)
    if identity.get("name") != expected:
        raise GateError("HF authenticated account does not match MILES_HF_EXPECTED_USER")
    # Official auth_check(write=True) endpoint; older installed SDK lacks write=.
    # A read-only token or a nonexistent repository must fail, not pass via GET repo.
    request_json(f"{HF_ENDPOINT}/api/models/{repo}/auth-check/write", "Bearer " + token, expect_json=False)
    return {"status": "passed", "account": expected, "model_repo": repo,
            "write_access": True, "repository_created": False}


def check_wandb(env):
    key = wandb_key(env)
    expected = required(env, "MILES_WANDB_EXPECTED_USER")
    entity = required(env, "WANDB_ENTITY")
    if env.get("WANDB_BASE_URL", WANDB_ENDPOINT).rstrip("/") != WANDB_ENDPOINT:
        raise GateError("this launcher supports only the official W&B cloud endpoint")
    auth = "Basic " + base64.b64encode(("api:" + key).encode()).decode()
    # Same read-only Viewer query as the W&B SDK; never wandb.init/login.
    payload = request_json(WANDB_ENDPOINT + "/graphql", auth, {"query": """
      query Viewer { viewer { username entity teams { edges { node { name } } } } }
    """})
    viewer = (payload.get("data") or {}).get("viewer")
    if payload.get("errors") or not viewer or not viewer.get("username"):
        raise GateError("W&B credential verification failed")
    if viewer["username"] != expected:
        raise GateError("W&B authenticated account does not match MILES_WANDB_EXPECTED_USER")
    entities = {viewer.get("entity"), viewer.get("username")}
    entities.update(edge["node"]["name"] for edge in (viewer.get("teams") or {}).get("edges", []))
    if entity not in entities:
        raise GateError("WANDB_ENTITY is not among the authenticated account's entities")
    project = request_json(WANDB_ENDPOINT + "/graphql", auth, {
        "query": "query ProjectDetails($entity: String, $project: String) { model(name: $project, entityName: $entity) { name } }",
        "variables": {"entity": entity, "project": PROJECT},
    })
    if project.get("errors") or ((project.get("data") or {}).get("model") or {}).get("name") != PROJECT:
        raise GateError("configured W&B project does not exist or is not accessible")
    return {"status": "passed", "account": viewer["username"], "entity": entity,
            "project": PROJECT, "entity_membership_verified": True,
            "project_read_access_verified": True, "project_write_tested": False, "run_created": False}


def preflight(env):
    result = {"status": "passed", "cloud_launched": False,
              "missing_configuration": [k for k in ("MILES_HF_MODEL_REPO", "MILES_HF_EXPECTED_USER",
                                                    "MILES_WANDB_EXPECTED_USER", "WANDB_ENTITY") if not env.get(k, "").strip()]}
    for name, check in (("hugging_face", check_hf), ("wandb", check_wandb)):
        try:
            result[name] = check(env)
        except GateError as exc:
            result[name] = {"status": "failed", "reason": str(exc)}
            result["status"] = "failed"
        except Exception:
            result[name] = {"status": "failed", "reason": "unexpected credential response; details suppressed"}
            result["status"] = "failed"
    return result


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def adapter_files(run_root, env):
    run_id = required(env, "MILES_RUN_ID")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}", run_id):
        raise GateError("invalid MILES_RUN_ID")
    if run_root.name != run_id or run_root.is_symlink():
        raise GateError("run root does not match the isolated run ID")
    iteration = int(env.get("MILES_NUM_ROLLOUT", "20")) - 1
    checkpoint = f"iter_{iteration:07d}"
    adapter = run_root / "checkpoints/grpo_lora_r16" / checkpoint / "adapter"
    gate = run_root / "grpo_lora_r16/grpo_training_gate.json"
    finite = adapter / "finiteness_receipt.json"
    if not gate.is_file() or not finite.is_file():
        raise GateError("missing completed-training or finiteness receipt")
    training = json.loads(gate.read_text())
    if (gate.is_symlink() or training.get("status") != "passed"
            or training.get("kind") != "glm47-aider-grpo-training-gate"
            or training.get("run_id") != run_id
            or training.get("num_rollout") != iteration + 1
            or training.get("latest_checkpoint", {}).get("iteration") != iteration):
        raise GateError("training gate does not bind this completed run/checkpoint")
    if (run_root / "hf_publish_receipt.json").exists():
        raise GateError("a publishing receipt already exists; refusing duplicate upload")
    receipt = json.loads(finite.read_text())
    if receipt.get("status") != "passed" or receipt.get("nonfinite_tensors") != 0:
        raise GateError("final adapter finiteness receipt did not pass")
    files = {name: adapter / name for name in ("adapter_model.bin", "adapter_config.json", "finiteness_receipt.json")}
    shards = sorted(adapter.glob("adapter_megatron_*.pt"))
    if len(shards) != int(env.get("MILES_EXPECTED_NATIVE_SHARDS", "4")):
        raise GateError("final adapter is missing native LoRA shards")
    files.update({p.name: p for p in shards})
    for path in files.values():
        if not path.is_file() or path.is_symlink() or path.stat().st_size == 0 or not path.resolve().is_relative_to(run_root.resolve()):
            raise GateError("unsafe or missing final adapter file")
    if digest(files["adapter_model.bin"]) != receipt.get("adapter_model_sha256"):
        raise GateError("final adapter digest does not match finiteness receipt")
    latest = training["latest_checkpoint"]
    expected_hashes = {"adapter_model.bin": latest.get("adapter_model_sha256"),
                       "adapter_config.json": latest.get("adapter_config_sha256"),
                       **latest.get("native_shards", {})}
    if set(expected_hashes) != set(files) - {"finiteness_receipt.json"} or any(
            digest(files[name]) != value for name, value in expected_hashes.items()):
        raise GateError("final adapter files do not match completed-training gate hashes")
    return checkpoint, files


def publish(run_root, env, api=None):
    """Only called after training + durable local/GCS preservation succeed."""
    # Bind the exact validated token even if a shared login file changes later.
    env = dict(env, HF_TOKEN=hf_token(env))
    identity = check_hf(env)
    checkpoint, files = adapter_files(run_root, env)
    # Suppress SDK HTTP debug/progress output even if inherited from the runtime.
    os.environ["HF_DEBUG"] = "0"
    os.environ["HF_HUB_VERBOSITY"] = "error"
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    from huggingface_hub import HfApi, CommitOperationAdd
    from huggingface_hub.utils import logging as hub_logging, disable_progress_bars
    hub_logging.set_verbosity_error()
    disable_progress_bars()
    if api is None:
        api = HfApi(endpoint=HF_ENDPOINT, token=hf_token(env))
    repo = identity["model_repo"]
    prefix = f"runs/{env['MILES_RUN_ID']}/{checkpoint}/adapter"
    # Pin parent to avoid racing another publisher. Never replace previous runs.
    info = api.model_info(repo_id=repo, revision="main")
    if not info.sha:
        raise GateError("HF model repository must have an initialized main branch")
    existing = api.list_repo_files(repo_id=repo, repo_type="model", revision=info.sha)
    if any(p == prefix or p.startswith(prefix + "/") for p in existing):
        raise GateError("HF destination already contains this checkpoint; refusing overwrite")
    hashes = {name: digest(path) for name, path in files.items()}
    operations = [CommitOperationAdd(path_in_repo=f"{prefix}/{name}", path_or_fileobj=str(path))
                  for name, path in sorted(files.items())]
    commit = api.create_commit(repo_id=repo, repo_type="model", revision="main", parent_commit=info.sha,
                               operations=operations, commit_message=f"Publish CHARM GRPO {env['MILES_RUN_ID']} {checkpoint}")
    # Verify the remote file list at the immutable returned commit, not moving main.
    actual = set(api.list_repo_files(repo_id=repo, repo_type="model", revision=commit.oid))
    if not all(f"{prefix}/{name}" in actual for name in files):
        raise GateError("HF commit returned but checkpoint file verification failed")
    receipt = {"status": "passed", "account": identity["account"], "repo_id": repo,
               "commit": commit.oid, "path_in_repo": prefix, "file_sha256s": hashes,
               "remote_file_list_verified": True}
    destination = run_root / "hf_publish_receipt.json"
    with destination.open("x") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight")
    launch = sub.add_parser("exec-launch")
    launch.add_argument("args", nargs=argparse.REMAINDER)
    upload = sub.add_parser("publish")
    upload.add_argument("--run-root", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "publish":
            result = publish(args.run_root, os.environ)
        else:
            selected_env = dict(os.environ)
            if args.command == "exec-launch":
                # Read each source once; forward exactly the credentials verified below.
                selected_env.update(HF_TOKEN=hf_token(selected_env), WANDB_API_KEY=wandb_key(selected_env))
            result = preflight(selected_env)
            print(json.dumps(result, indent=2), flush=True)
            if result["status"] != "passed":
                return 2
            if args.command == "exec-launch":
                command = args.args[1:] if args.args[:1] == ["--"] else args.args
                if command[:2] != ["sky", "launch"]:
                    raise GateError("exec-launch accepts only the isolated Sky launch command")
                os.execvpe(command[0], command, selected_env)
            return 0
        print(json.dumps(result, indent=2))
        return 0
    except GateError as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}))
        return 2
    except Exception:
        # SDK HTTP exceptions can include request headers; never print them.
        print(json.dumps({"status": "failed", "reason": "operation failed; sensitive exception details suppressed"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
