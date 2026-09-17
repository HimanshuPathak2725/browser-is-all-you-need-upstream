"""Frozen Stack-v2 CHARM data and reward adapter for the existing Miles GRPO runner."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import secrets
import shlex
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any, Mapping

from glm47_posttraining.aider_polyglot.dataset import DATASET_KIND, build_aider_messages, write_jsonl
from glm47_posttraining.aider_polyglot.harness import CandidatePolicyError, _validate_candidate_source
from glm47_posttraining.aider_polyglot.parser import AiderResponseError, parse_whole_file_response
from glm47_posttraining.cpp_perf.sandbox import docker_base_args
from glm47_posttraining.integrations.miles_aider_polyglot import neutralize_infrastructure_scores

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "stack_v2_charm_grpo_assets"
DEFAULT_REGISTRY = ASSETS / "registry.json"
REGISTRY_SHA256 = "1c9621f22674e0478bb9f4962210d3b560dcedb0ea69471a048c003aee5a2cdb"
CURRICULUM = "stack-v2-charm-v1"
PROFILE = "charm-native-cpp17-v1"
IMAGE = "glm47-stack-v2-charm-cpp:v1"
SOURCE_JSONL_SHA256 = "aeb8fc0d28cfb709e66df8ca0eae5ce3c6bfc733caaaba6cf474db5fbddc31ff"
MATERIALIZATION_SHA256 = "961b2cc1f9b47c57fc5c93473751c5835482b64afc582d9f48d2bd21d1c494aa"
CERTIFICATION_SHA256 = "f7cc3c96668537604f02be7494c3fd728769a75f4cc0927348a87a3dabd1b951"
PREFIX = "charm-stack-29003-"
VALIDATION = frozenset(PREFIX + n for n in (
    "mode-string-canonicalizer", "layered-box-layout", "cyclic-lease-ring",
    "hex-image-reassembler", "quaternion-path-sampler",
))
CALIBRATION = PREFIX + "planar-motion-lock"
FLAGS = ["-std=c++17", "-Wall", "-Wextra", "-Wpedantic", "-Werror"]
FENCE = chr(96) * 3
# Test helper symbols, macros and paths must not be controlled by a response.
RESERVED = re.compile(
    r"\b(?:charm_\w*|CHECK(?:_THROWS)?|glm47_hidden_main|glm47_charm_\w*)\b"
    r"|#\s*include\s*[<\"][^>\"]*(?:\.\./|/work|test_support|hidden_test|\.meta|\.reference)"
    r"|__attribute__\s*\(\(\s*(?:constructor|destructor)"
)

def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))

def read_json(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path.name}")
    return value

def regular(root: Path, name: str) -> Path:
    rel = PurePosixPath(name)
    if not name or rel.is_absolute() or ".." in rel.parts:
        raise ValueError("unsafe binding path")
    path = root.joinpath(*rel.parts)
    if not path.is_file() or any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError(f"missing or unsafe binding: {name}")
    if root.resolve() not in path.resolve().parents:
        raise ValueError("binding escaped root")
    return path

def tree_hashes(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("symlink in frozen task")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha(path)
    return result

def whole_file(files: Mapping[str, str]) -> str:
    return "\n\n".join(f"{n}\n{FENCE}cpp\n{s.rstrip()}\n{FENCE}" for n, s in files.items()) + "\n"

def prepare(args: argparse.Namespace) -> dict:
    """Transport certified bytes unchanged; author only integration bindings."""
    if args.out.exists():
        raise FileExistsError(f"refusing to replace bindings: {args.out}")
    for path, digest in ((args.input_jsonl, SOURCE_JSONL_SHA256),
                         (args.materialization, MATERIALIZATION_SHA256),
                         (args.certification, CERTIFICATION_SHA256)):
        if sha(path) != digest:
            raise ValueError(f"frozen input digest mismatch: {path.name}")
    rows = [json.loads(line) for line in args.input_jsonl.read_text().splitlines()]
    materialization, certifications = read_json(args.materialization), read_json(args.certification)
    records = {r["task_id"]: r for r in certifications["task_receipts"]}
    proposals = {r["task_id"]: r for r in materialization["tasks"]}
    ids = {r["task_id"] for r in rows}
    if len(rows) != 20 or len(ids) != 20 or ids != set(proposals) or ids != set(records):
        raise ValueError("input task identities disagree")
    if certifications["decision"] != "PASS" or not VALIDATION < ids or CALIBRATION not in ids:
        raise ValueError("invalid frozen certification/split")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="charm-bindings-", dir=args.out.parent) as temp:
        stage = Path(temp)
        entries = {}
        for row in rows:
            task_id = row["task_id"]
            spec = proposals[task_id]
            source = args.tasks_root / spec["family"] / spec["release"] / task_id
            if tree_hashes(source) != spec["file_sha256s"]:
                raise ValueError(f"frozen task changed: {task_id}")
            dest = stage / "tasks" / task_id
            shutil.copytree(source, dest)
            rubric = read_json(dest / ".rubric.json")
            editable = rubric["editable_files"]
            if editable != row["metadata"]["editable_files"]:
                raise ValueError("editable metadata mismatch")
            root_files = sorted(n for n in spec["file_sha256s"]
                                if "/" not in n and n.endswith((".h", ".cpp", ".hpp", ".cc")))
            split = "calibration" if task_id == CALIBRATION else "validation" if task_id in VALIDATION else "train"
            proof = records[task_id]
            bound_proofs = {}
            for kind in ("oracle", "negative_control"):
                original = Path(proof[f"{kind}_proof_path"])
                if sha(original) != proof[f"{kind}_receipt_sha256"]:
                    raise ValueError("certified proof digest mismatch")
                name = f"evidence/{task_id}/{kind}.json"
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, target)
                bound_proofs[name] = sha(target)
            manifest = {
                "schema_version": 1, "task_id": task_id, "profile": PROFILE,
                "task_dir": f"tasks/{task_id}", "files": spec["file_sha256s"],
                "editable_files": editable, "root_files": root_files,
                "sources": [n for n in root_files if n.endswith((".cpp", ".cc"))],
                "fixed_files": [n for n in root_files if n not in editable],
                "tests": [".meta/example.cpp", ".meta/hidden_test.cpp"],
                "support_files": [".meta/test_support.h"],
                "family": spec["family"], "split": split, "lineage_id": f"stack-v2/{task_id}",
                "certification": proof, "proof_files": bound_proofs,
            }
            manifest_name = f"manifests/{task_id}.json"
            write_json(stage / manifest_name, manifest)
            entries[task_id] = {"manifest": manifest_name, "manifest_sha256": sha(stage / manifest_name),
                                "split": split, "family": spec["family"]}
        registry = {
            "schema_version": 1, "curriculum": CURRICULUM, "profile": PROFILE,
            "input_jsonl_sha256": SOURCE_JSONL_SHA256, "materialization_sha256": MATERIALIZATION_SHA256,
            "certification_sha256": CERTIFICATION_SHA256,
            "expert_approval": "confirmed by task owner in integration request",
            "source_tasks_modified": False, "tasks": entries,
        }
        write_json(stage / "registry.json", registry)
        shutil.copy2(args.input_jsonl, stage / "source.jsonl")
        shutil.copy2(args.materialization, stage / "materialization.json")
        shutil.copy2(args.certification, stage / "certification.json")
        os.rename(stage, args.out)
    return {"registry": str(args.out / "registry.json"), "tasks": 20,
            "counts": {"train": 14, "validation": 5, "calibration": 1},
            "registry_sha256": sha(args.out / "registry.json")}

class Registry:
    def __init__(self, path: Path = DEFAULT_REGISTRY):
        self.path = path.resolve()
        self.root = self.path.parent
        self.payload = read_json(regular(self.root, self.path.name))
        self.digest = sha(self.path)
        if self.digest != REGISTRY_SHA256:
            raise ValueError("unrecognized frozen registry digest")
        self.entries = self.payload["tasks"]
        if self.payload.get("curriculum") != CURRICULUM or len(self.entries) != 20:
            raise ValueError("incorrect CHARM registry")

    def resolve(self, task_id: str) -> tuple[dict, Path]:
        entry = self.entries[task_id]
        manifest_path = regular(self.root, entry["manifest"])
        if sha(manifest_path) != entry["manifest_sha256"]:
            raise ValueError("manifest digest mismatch")
        manifest = read_json(manifest_path)
        if manifest["task_id"] != task_id or manifest["split"] != entry["split"]:
            raise ValueError("task identity/split mismatch")
        task_root = self.root / manifest["task_dir"]
        if not task_root.is_dir() or self.root not in task_root.resolve().parents:
            raise ValueError("unsafe task root")
        for name, digest in manifest["files"].items():
            if sha(regular(task_root, name)) != digest:
                raise ValueError(f"task asset digest mismatch: {task_id}/{name}")
        for name, digest in manifest["proof_files"].items():
            if sha(regular(self.root, name)) != digest:
                raise ValueError("certification proof changed")
        return manifest, task_root

    def row(self, task_id: str) -> dict:
        manifest, root = self.resolve(task_id)
        prompt = build_aider_messages(root, manifest["editable_files"])
        fixed = "\n\n".join(f"Read-only file: {n}\n{FENCE}cpp\n{(root / n).read_text()}\n{FENCE}"
                           for n in manifest["fixed_files"] if n.endswith((".h", ".hpp")))
        if fixed:
            prompt[-1]["content"] += "\n\nPublic API context (do not edit these files):\n" + fixed
        split = manifest["split"]
        metadata = {
            "data_source": DATASET_KIND, "task_id": f"aider-shadow-cpp/{task_id}",
            "problem_id": task_id, "split": split, "harness_kind": PROFILE,
            "task_path": f"tasks/{split}/{task_id}.json",
            "editable_files": manifest["editable_files"], "fixed_files": manifest["fixed_files"],
            "hidden_test_sha256": manifest["files"][".meta/hidden_test.cpp"],
            "source_prompt_sha256": manifest["files"][".docs/instructions.md"],
            "verification_gate": PROFILE, "family": manifest["family"], "lineage_id": manifest["lineage_id"],
            "charm_registry_sha256": self.digest,
            "charm_manifest_sha256": self.entries[task_id]["manifest_sha256"],
        }
        return {"prompt": prompt, "label": metadata["task_id"], "task_id": metadata["task_id"],
                "problem_id": task_id, "split": split, "metadata": metadata}

def build_data(args: argparse.Namespace) -> dict:
    if args.curriculum != CURRICULUM:
        raise ValueError("incorrect CHARM curriculum")
    if args.train_limit is not None or args.eval_limit is not None:
        raise ValueError("the approved experiment split must not be silently truncated")
    registry = Registry()
    if Path(getattr(args, "tasks_dir", ROOT)).resolve() != ROOT:
        raise ValueError("--tasks-dir must identify this experiment's Reward_GRPO package")
    output = args.out.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to replace run data: {output}")
    if registry.root == output or registry.root in output.parents or output in registry.root.parents:
        raise ValueError("data output overlaps frozen assets")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="charm-data-", dir=output.parent) as temp:
        stage = Path(temp)
        rows = [registry.row(t) for t in sorted(registry.entries)]
        groups = {s: [r for r in rows if r["split"] == s] for s in ("train", "validation", "calibration")}
        if getattr(args, "sort_by_size", False):
            for group in groups.values():
                group.sort(key=lambda r: (len(str(r["prompt"])), r["problem_id"]))
        for row in rows:
            write_json(stage / row["metadata"]["task_path"],
                       {"schema_version": 1, "kind": PROFILE, **row["metadata"], "prompt": row["prompt"]})
        for path, split in (("grpo/train.jsonl", "train"), ("eval/validation.jsonl", "validation"),
                            ("eval/train_monitor.jsonl", "train"), ("eval/calibration.jsonl", "calibration")):
            write_jsonl(stage / path, groups[split])
        manifest = {
            "kind": DATASET_KIND, "schema_version": 5, "profile": args.profile, "run_id": args.run_id,
            "source_root": "bigcode/the-stack-v2", "source_manifest_kind": "charm-frozen-grpo-bindings-v1",
            "source_manifest_sha256": registry.digest,
            "source_tree_sha256": hashlib.sha256(canonical(registry.payload["tasks"])).hexdigest(),
            "input_jsonl_sha256": SOURCE_JSONL_SHA256, "charm_registry_sha256": registry.digest,
            "runtime_assets": "Reward_GRPO/stack_v2_charm_grpo_assets",
            "reward_function": "Reward_GRPO.stack_v2_charm_grpo.reward_func",
            "split_contract": {
                "train": "14 frozen tasks", "validation": "5 task-disjoint lineages",
                "calibration": "1 already-correct starter, not optimized",
                "monitor": "training trend only", "official_26": "external fixed evaluation only",
                "official_task_id_overlap": [], "source_reference_answers_packaged": False,
                "reference_answers_packaged": False, "imitation_role": "none",
            },
            "counts": {"available_shadow": 20, "train": len(groups["train"]), "validation": len(groups["validation"]),
                       "calibration": len(groups["calibration"]), "monitor": len(groups["train"])},
            "task_ids_by_split": {s: [r["problem_id"] for r in g] for s, g in groups.items()},
            "prompt_sha256": [hashlib.sha256(canonical(r["prompt"])).hexdigest() for r in rows],
            "files": {"grpo_train": "grpo/train.jsonl", "validation": "eval/validation.jsonl",
                      "train_monitor": "eval/train_monitor.jsonl", "calibration": "eval/calibration.jsonl"},
            "file_sha256s": tree_hashes(stage),
        }
        write_json(stage / "manifest.json", manifest)
        os.rename(stage, output)
    return {"grpo_train": str(output / "grpo/train.jsonl"), "eval": str(output / "eval/validation.jsonl"),
            "manifest": str(output / "manifest.json"), "counts": manifest["counts"]}

def value(sample: Any, key: str, default: Any = None) -> Any:
    return sample.get(key, default) if isinstance(sample, Mapping) else getattr(sample, key, default)

def check_source(name: str, source: str) -> None:
    if len(source.encode()) > 256 * 1024:
        raise CandidatePolicyError("candidate file exceeds byte limit")
    _validate_candidate_source(name, source)
    if RESERVED.search(source) or re.search(r'#\s*(?:include\s*[<"]\s*/|line\b)', source):
        raise CandidatePolicyError("candidate references private harness primitives or paths")

def sandbox_identity() -> dict:
    result = subprocess.run(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"],
                            capture_output=True, text=True, timeout=20)
    if result.returncode or not result.stdout.strip().startswith("sha256:"):
        raise RuntimeError(f"missing CHARM sandbox image: {IMAGE}")
    return {"backend": "docker", "image": IMAGE, "image_id": result.stdout.strip(),
            "network": "none", "profile": PROFILE}

def execute(manifest: dict, root: Path, files: Mapping[str, str]) -> dict:
    """Execute both immutable suites with all TUs. Docker is mandatory.

    Only scratch is mounted, never the registry, references, host credentials
    or Docker socket. A trusted driver authenticates normal test completion.
    """
    with tempfile.TemporaryDirectory(prefix="stack-v2-charm-") as temp:
        scratch = Path(temp)
        src, private = scratch / "src", scratch / "private"
        src.mkdir()
        private.mkdir()
        for name in manifest["root_files"]:
            shutil.copy2(root / name, src / name)
        for name, contents in files.items():
            (src / name).write_text(contents)
        for name in manifest["support_files"]:
            shutil.copy2(root / name, private / Path(name).name)
        for suite, test in zip(("example", "hidden"), manifest["tests"]):
            shutil.copy2(root / test, private / f"{suite}.cpp")
        marker = "CHARM_PASS_" + secrets.token_hex(24)
        (private / "driver.cpp").write_text(
            '#include <cstdio>\nint glm47_hidden_main();\nint main(){int r=glm47_hidden_main();'
            f'if(r==0) std::puts("{marker}"); return r;}}\n'
        )
        flags = " ".join(FLAGS) + " -Isrc -Iprivate"
        script = ["set -eu", "ulimit -c 0", "ulimit -f 8192", "mkdir obj"]
        objects = []
        for index, name in enumerate(manifest["sources"]):
            obj = f"obj/source{index}.o"
            objects.append(obj)
            script.append(f"timeout 90s g++ {flags} -c {shlex.quote('src/' + name)} -o {obj} >compile.log 2>&1 || exit 11")
        script.append(f"timeout 90s g++ {' '.join(FLAGS)} -c private/driver.cpp -o obj/driver.o >compile.log 2>&1 || exit 70")
        for suite in ("example", "hidden"):
            script.append(f"timeout 90s g++ {flags} -Dmain=glm47_hidden_main -c private/{suite}.cpp -o obj/{suite}.o >compile.log 2>&1 || exit 12")
            script.append(f"timeout 90s g++ {' '.join(objects)} obj/{suite}.o obj/driver.o -o {suite} >compile.log 2>&1 || exit 13")
        script += ["rm -r -- private obj src", "set +e"]
        for suite in ("example", "hidden"):
            script.append(f"CHARM_NONCE=29003 timeout 20s ./{suite} >{suite}.log 2>&1")
            script.append("status=$?; test $status -eq 0 || exit 15")
        container_name = "stack-v2-charm-" + secrets.token_hex(12)
        command = docker_base_args(scratch, image=IMAGE, memory="2g", pids_limit=128)
        command[2:2] = ["--name", container_name]
        command += ["bash", "-c", "\n".join(script)]
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=20)
            return {"status": "infrastructure_error", "reason": "sandbox_deadline"}
        if proc.returncode not in (0, 11, 12, 13, 15):
            return {"status": "infrastructure_error", "reason": "sandbox_execution",
                    "returncode": proc.returncode, "diagnostic": proc.stderr[-1500:]}
        log_hashes = {p.name: sha(p) for p in scratch.glob("*.log")}
        if proc.returncode in (11, 12, 13):
            diagnostic = (scratch / "compile.log").read_text(errors="replace")[-2000:]
            if any(s in diagnostic.lower() for s in ("no space left", "cannot allocate memory",
                                                     "resource temporarily unavailable", "internal compiler error")):
                return {"status": "infrastructure_error", "reason": "compiler_infrastructure", "diagnostic": diagnostic}
            return {"status": "compile_failed", "stage": {11: "translation_unit", 12: "test_api", 13: "link"}[proc.returncode],
                    "diagnostic": diagnostic, "log_sha256s": log_hashes}
        successes = {s: (scratch / f"{s}.log").is_file() and marker in (scratch / f"{s}.log").read_text(errors="replace")
                     for s in ("example", "hidden")}
        passed = proc.returncode == 0 and all(successes.values())
        return {"status": "passed" if passed else "tests_failed", "suite_passes": successes,
                "returncode": proc.returncode, "log_sha256s": log_hashes}

def score_sample(sample: Any, registry: Registry | None = None) -> dict:
    metadata = value(sample, "metadata", {}) or {}
    metadata = metadata if isinstance(metadata, Mapping) else {}
    response = value(sample, "response", "") or ""
    task_id = metadata.get("problem_id")
    result = {"task_id": metadata.get("task_id"), "problem_id": task_id, "split": metadata.get("split"),
              "rollout_id": value(sample, "rollout_id"), "sample_index": value(sample, "index"), "response": response,
              "score": 0.0, "reward": 0.0, "infrastructure_error": False,
              "profile": PROFILE, "format_valid": False, "all_tests_pass": False}
    try:
        registry = registry or Registry()
        manifest, root = registry.resolve(task_id)
        expected = registry.row(task_id)["metadata"]
        for key in ("task_id", "problem_id", "split", "charm_registry_sha256", "charm_manifest_sha256",
                    "hidden_test_sha256", "editable_files"):
            if metadata.get(key) != expected[key]:
                raise ValueError(f"sample binding mismatch: {key}")
        try:
            if not isinstance(response, str):
                raise AiderResponseError("invalid_format", "response is not text")
            parsed = parse_whole_file_response(response, manifest["editable_files"])
            for name, contents in parsed.files.items():
                check_source(name, contents)
        except (AiderResponseError, CandidatePolicyError) as error:
            return {**result, "score": -1.0, "reward": -1.0,
                    "reason": getattr(error, "reason", "candidate_policy"), "boundary_valid": False}
        execution = execute(manifest, root, parsed.files)
        result.update({"format_valid": parsed.format_valid, "boundary_valid": True,
                       "modified_files": sorted(parsed.files), "execution": execution,
                       "charm_manifest_sha256": expected["charm_manifest_sha256"]})
        status = execution["status"]
        if status == "infrastructure_error":
            return {**result, "infrastructure_error": True, "reason": execution["reason"]}
        # Native CHARM outcomes are binary; never invent Catch assertion counts.
        # API compatibility is established by compilation against both tests.
        score = {"passed": 1.0 if parsed.format_valid else 0.975, "tests_failed": -0.45,
                 "compile_failed": -0.95 if execution.get("stage") == "translation_unit" else -0.75}[status]
        return {**result, "score": score, "reward": score, "reason": status, "all_tests_pass": status == "passed",
                "compile_error": status == "compile_failed",
                "tests_passed": 2 if status == "passed" else sum(execution.get("suite_passes", {}).values()),
                "tests_total": 2, "test_count_unit": "suite", "candidate_semantic_fraction": None}
    except Exception as error:
        return {**result, "infrastructure_error": True, "reason": "binding_or_runner_error",
                "error": f"{type(error).__name__}: {error}"}

async def reward_func(_args: Any, sample: Any, **_kwargs: Any) -> dict | list[dict]:
    try:
        registry = Registry()
    except Exception:
        if isinstance(sample, list):
            return [score_sample(s) for s in sample]
        return score_sample(sample)
    if not isinstance(sample, list):
        return await asyncio.to_thread(score_sample, sample, registry)
    workers = max(1, min(int(os.environ.get("GLM47_CPP_REWARD_WORKERS", "4")), 24))
    semaphore = asyncio.Semaphore(workers)
    async def score(item: Any) -> dict:
        async with semaphore:
            return await asyncio.to_thread(score_sample, item, registry)
    records = neutralize_infrastructure_scores(list(await asyncio.gather(*(score(s) for s in sample))))
    for record in records:
        record["reward"] = record["score"]
    return records

def control_response(manifest: dict, root: Path, kind: str) -> str:
    editable = manifest["editable_files"]
    if kind == "starter":
        return whole_file({n: (root / n).read_text() for n in editable})
    files = {n: (root / ".reference" / n).read_text() for n in editable}
    if kind in ("negative", "mutation2"):
        source = root / (".meta/negative.cpp" if kind == "negative" else ".meta/mutations/semantic_2.cpp")
        includes = source.parent / ("negative_include" if kind == "negative" else "mutation2_include")
        cpp = [n for n in editable if n.endswith(".cpp")]
        if cpp:
            files[cpp[0]] = source.read_text()
            for companion in cpp[1:]:
                files[companion] = "// Mutation control consolidates implementations in the primary file.\n"
        for name in editable:
            if (includes / name).is_file():
                files[name] = (includes / name).read_text()
        if not cpp and not any((includes / n).is_file() for n in editable):
            # Hilbert controls are .cpp, while the solver's action is header-only.
            # Keep their bodies; inline declarations make this transport ODR-safe.
            header = editable[0]
            declarations = (root / header).read_text()
            declarations = re.sub(r"^(std::.*\);)$", r"inline \1", declarations, flags=re.MULTILINE)
            files[header] = declarations + "\n" + source.read_text().replace(f'#include "{header}"', "")
    elif kind == "compile_failure":
        files[editable[0]] += "\n#error intentional_integration_compile_failure\n"
    elif kind == "forbidden":
        return whole_file(files) + f"CMakeLists.txt\n{FENCE}cmake\nproject(forbidden)\n{FENCE}\n"
    elif kind == "early_exit":
        files[editable[0]] += "\nvoid evade(){ std::exit(0); }\n"
    elif kind not in ("reference", "decorated"):
        raise ValueError(kind)
    response = whole_file(files)
    if kind == "decorated":
        for name in editable:
            response = response.replace(name + "\n" + FENCE, "**" + name + "**\n" + FENCE, 1)
    return response

def integration_check(args: argparse.Namespace) -> dict:
    if not 1 <= args.workers <= 24:
        raise ValueError("integration workers must be between 1 and 24")
    if args.output and args.output.exists():
        raise FileExistsError("refusing to replace integration receipt")
    code_before = integration_code_hashes()
    registry = Registry()
    identity = sandbox_identity()
    kinds = ("reference", "starter", "negative", "mutation2", "compile_failure", "forbidden", "early_exit", "decorated")
    controls = []
    for task_id in sorted(registry.entries):
        manifest, root = registry.resolve(task_id)
        for kind in kinds:
            controls.append((task_id, kind, {"metadata": registry.row(task_id)["metadata"], "rollout_id": "integration",
                                            "response": control_response(manifest, root, kind)}))
    records = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = [pool.submit(score_sample, sample, registry) for _, _, sample in controls]
        for (task_id, kind, sample), future in zip(controls, pending):
            record = future.result()
            positive = kind in ("reference", "decorated") or (kind == "starter" and task_id == CALIBRATION)
            ok = not record["infrastructure_error"] and ((record["score"] > 0) == positive)
            if kind in ("negative", "mutation2"):
                ok = ok and record.get("reason") == "tests_failed"
            if kind == "compile_failure":
                ok = ok and record.get("reason") == "compile_failed"
            records.append({"task_id": task_id, "control": kind, "passed": ok,
                            "sample_sha256": hashlib.sha256(canonical(sample)).hexdigest(),
                            "reward_record": {k: v for k, v in record.items() if k != "response"}})
            print(f"{task_id} {kind}: {'PASS' if ok else 'FAIL'} score={record['score']} reason={record.get('reason')}", flush=True)
    with tempfile.TemporaryDirectory(prefix="charm-data-check-") as temp:
        built = build_data(argparse.Namespace(curriculum=CURRICULUM, out=Path(temp) / "data", train_limit=None,
                                             eval_limit=None, profile=PROFILE, run_id="integration-check"))
        data_manifest = read_json(Path(built["manifest"]))
        actual_rows = []
        for rel in ("grpo/train.jsonl", "eval/validation.jsonl", "eval/calibration.jsonl"):
            actual_rows.extend(json.loads(line) for line in (Path(temp) / "data" / rel).read_text().splitlines())
        if {r["problem_id"] for r in actual_rows} != set(registry.entries):
            raise ValueError("data projection dropped tasks")
        for row in actual_rows:
            if row["prompt"][-1]["role"] != "user" or row != registry.row(row["problem_id"]):
                raise ValueError("prompt/data mismatch")
    # Deserialize the actual built JSONLs, then exercise Miles' object/list API.
    batch = []
    for row in actual_rows:
        manifest, root = registry.resolve(row["problem_id"])
        batch.append(SimpleNamespace(**row, response=control_response(manifest, root, "reference")))
    batch_records = asyncio.run(reward_func(None, batch))
    batch_ok = len(batch_records) == 20 and all(r["score"] == 1.0 and not r["infrastructure_error"] for r in batch_records)
    if integration_code_hashes() != code_before:
        raise ValueError("integration code changed while checks were running")
    result = {"schema_version": 1, "kind": "charm-miles-grpo-integration",
              "status": "passed" if all(r["passed"] for r in records) and batch_ok else "failed",
              "registry_sha256": registry.digest, "adapter_sha256": sha(Path(__file__)),
              "code_sha256s": integration_code_hashes(), "sandbox": identity,
              "tasks": 20, "controls": len(records), "passed_controls": sum(r["passed"] for r in records),
              "async_reference_batch_passed": batch_ok, "data_counts": data_manifest["counts"],
              "source_tasks_modified": False, "training_started": False, "results": records}
    if args.output:
        if args.output.exists():
            raise FileExistsError("refusing to replace integration receipt")
        write_json(args.output, result)
    return result

def integration_code_hashes() -> dict:
    repo = ROOT.parent
    names = [
        "Reward_GRPO/stack_v2_charm_grpo.py",
        "Reward_GRPO/stack_v2_charm_sandbox.Dockerfile",
        "src/glm47_posttraining/aider_polyglot/dataset.py",
        "src/glm47_posttraining/aider_polyglot/parser.py",
        "src/glm47_posttraining/aider_polyglot/harness.py",
        "src/glm47_posttraining/cpp_perf/sandbox.py",
        "src/glm47_posttraining/integrations/miles_aider_polyglot.py",
    ]
    return {n: sha(repo / n) for n in names}

def check_receipt() -> dict:
    receipt = read_json(ROOT / "stack_v2_charm_integration_receipt.json")
    if (receipt.get("status") != "passed" or receipt.get("passed_controls") != 160
            or receipt.get("tasks") != 20 or not receipt.get("async_reference_batch_passed")
            or receipt.get("registry_sha256") != REGISTRY_SHA256
            or receipt.get("code_sha256s") != integration_code_hashes()):
        raise ValueError("missing, stale or unsuccessful integration receipt")
    return receipt

def preflight() -> dict:
    check_receipt()
    registry = Registry()
    identity = sandbox_identity()
    samples = []
    for task_id in sorted(registry.entries):
        manifest, root = registry.resolve(task_id)
        samples.append({"metadata": registry.row(task_id)["metadata"],
                        "response": control_response(manifest, root, "reference")})
    records = asyncio.run(reward_func(None, samples))
    if len(records) != 20 or any(r["score"] != 1.0 or r["infrastructure_error"] for r in records):
        raise RuntimeError("CHARM reward-worker preflight failed")
    return {"status": "passed", "tasks": 20, "registry_sha256": registry.digest, "sandbox": identity}


def check_prompts(args: argparse.Namespace) -> dict:
    """Count actual GRPO generation prompts with the selected model tokenizer."""
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer_dir), local_files_only=True)
    registry = Registry()
    rows = []
    for task_id in sorted(registry.entries):
        prompt = registry.row(task_id)["prompt"]
        tokens = tokenizer.apply_chat_template(prompt, tokenize=True, add_generation_prompt=True, enable_thinking=True)
        ids = tokens if isinstance(tokens, list) else tokens["input_ids"]
        if ids and isinstance(ids[0], list):
            ids = ids[0]
        rows.append({"task_id": task_id, "prompt_tokens": len(ids),
                     "prompt_token_ids_sha256": hashlib.sha256(canonical(ids)).hexdigest()})
    maximum = max(r["prompt_tokens"] for r in rows)
    result = {"status": "passed" if maximum + 8192 <= 12288 else "failed",
              "registry_sha256": registry.digest, "tasks": len(rows), "max_prompt_tokens": maximum,
              "response_budget": 8192, "sequence_length": 12288, "thinking": True,
              "tokenizer_files": {p.name: sha(p) for p in args.tokenizer_dir.iterdir()
                                  if p.name in ("tokenizer.json", "tokenizer_config.json", "chat_template.jinja")},
              "rows": rows}
    if args.output:
        if args.output.exists():
            raise FileExistsError(args.output)
        write_json(args.output, result)
    return result

def stage_launch(args: argparse.Namespace) -> dict:
    """Freeze only required runtime code and this experiment's assets."""
    check_receipt()
    registry = Registry()
    for task_id in registry.entries:
        registry.resolve(task_id)
    output = args.out.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite launch snapshot: {output}")
    repo = ROOT.parent
    if output == repo or output in repo.parents or output == ASSETS or ASSETS in output.parents or (repo / "src") in output.parents or (repo / "scripts") in output.parents:
        raise ValueError("unsafe launch snapshot destination")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="charm-launch-", dir=output.parent) as temp:
        stage = Path(temp)
        for directory in ("src/glm47_posttraining", "scripts"):
            shutil.copytree(repo / directory, stage / directory, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for name in ("pyproject.toml", "examples/grpo.sh", "Reward_GRPO/stack_v2_charm_grpo.py",
                     "Reward_GRPO/stack_v2_charm_sandbox.Dockerfile",
                     "Reward_GRPO/stack_v2_charm_grpo_skypilot.yaml",
                     "Reward_GRPO/stack_v2_charm_integration_receipt.json"):
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / name, target)
        shutil.copytree(ASSETS, stage / ASSETS.relative_to(repo))
        write_json(stage / "launch-manifest.json", {
            "schema_version": 1, "kind": "stack-v2-charm-grpo-launch-snapshot",
            "run_id": args.run_id, "registry_sha256": registry.digest,
            "files": tree_hashes(stage), "training_started": False,
        })
        os.rename(stage, output)
    return {"workdir": str(output), "launch_manifest_sha256": sha(output / "launch-manifest.json")}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare-bindings")
    prep.add_argument("--input-jsonl", type=Path, required=True)
    prep.add_argument("--tasks-root", type=Path, required=True)
    prep.add_argument("--materialization", type=Path, required=True)
    prep.add_argument("--certification", type=Path, required=True)
    prep.add_argument("--out", type=Path, default=ASSETS)
    build = sub.add_parser("build-data")
    build.add_argument("--tasks-dir", required=True)
    build.add_argument("--out", type=Path, required=True)
    build.add_argument("--curriculum", default=CURRICULUM, choices=[CURRICULUM])
    build.add_argument("--profile", default=PROFILE)
    build.add_argument("--run-id")
    build.add_argument("--eval-splits", default="validation,test")
    build.add_argument("--sort-by-size", action="store_true")
    build.add_argument("--train-limit", type=int)
    build.add_argument("--eval-limit", type=int)
    check = sub.add_parser("check-integration")
    check.add_argument("--workers", type=int, default=4)
    check.add_argument("--output", type=Path)
    sub.add_parser("preflight")
    prompts = sub.add_parser("check-prompts")
    prompts.add_argument("--tokenizer-dir", type=Path, required=True)
    prompts.add_argument("--output", type=Path)
    stage = sub.add_parser("stage-launch")
    stage.add_argument("--out", type=Path, required=True)
    stage.add_argument("--run-id", required=True)
    args = parser.parse_args()
    result = (prepare(args) if args.command == "prepare-bindings" else
              build_data(args) if args.command == "build-data" else
              integration_check(args) if args.command == "check-integration" else
              check_prompts(args) if args.command == "check-prompts" else
              stage_launch(args) if args.command == "stage-launch" else preflight())
    print(json.dumps({k: v for k, v in result.items() if k != "results"}, indent=2))
    if result.get("status") == "failed":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
