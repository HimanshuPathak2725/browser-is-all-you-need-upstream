#!/usr/bin/env python3
"""Read-only, bounded GCS acknowledgement of files copied through a cached mount."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import quote


class MetadataFailure(RuntimeError):
    pass


def fingerprint(path):
    value = path.stat()
    return value.st_size, value.st_mtime_ns, value.st_ino


def snapshot(paths, deadline, clock):
    result = {}
    for relative, path in sorted(paths.items()):
        before = fingerprint(path)
        md5, sha256 = hashlib.md5(), hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                if clock() >= deadline:
                    raise TimeoutError("deadline reached while hashing local artifacts")
                md5.update(block)
                sha256.update(block)
        if fingerprint(path) != before:
            raise MetadataFailure("local artifact changed while hashing: " + relative)
        result[relative] = {"size": before[0], "md5": base64.b64encode(md5.digest()).decode(),
                            "sha256": sha256.hexdigest(), "fingerprint": before}
    return result


def verify(paths, fetch, *, timeout=600, poll=2, clock=time.monotonic, sleep=time.sleep,
           membership=None):
    """fetch(relative, timeout) returns GCS metadata, None while absent, or raises.

    Source files must be stable; a server MD5 is mandatory, including for large
    checkpoints. Composite objects without MD5 do not count as verified uploads.
    """
    started = clock()
    deadline = started + timeout
    record = {"status": "failed", "reason": "pending", "objects": {}, "pending": {}}
    try:
        expected = snapshot(paths, deadline, clock)
        if not expected:
            raise MetadataFailure("no regular local artifacts to acknowledge")
        pending = {name: "not_checked" for name in expected}
        record["pending"] = dict(pending)
        while pending:
            for name in list(pending):
                remaining = deadline - clock()
                if remaining <= 0:
                    raise TimeoutError("object-store acknowledgement deadline exceeded")
                metadata = fetch(name, min(30.0, remaining))
                wanted = expected[name]
                if metadata is None:
                    pending[name] = "not_uploaded"
                elif str(metadata.get("size")) != str(wanted["size"]):
                    pending[name] = "size_mismatch"
                elif metadata.get("md5Hash") != wanted["md5"]:
                    pending[name] = "md5_mismatch_or_missing"
                elif not str(metadata.get("generation", "")).isdigit():
                    raise MetadataFailure("object generation missing: " + name)
                else:
                    record["objects"][name] = {"size": wanted["size"], "md5": wanted["md5"],
                        "sha256": wanted["sha256"], "generation": str(metadata["generation"])}
                    del pending[name]
            record["pending"] = dict(pending)
            if pending:
                remaining = deadline - clock()
                if remaining <= 0:
                    raise TimeoutError("object-store acknowledgement deadline exceeded")
                sleep(min(poll, remaining))
        if membership is not None and set(membership()) != set(paths):
            raise MetadataFailure("local artifact membership changed during verification")
        # Timestamps can have coarse resolution; rehash before admitting success
        # so an equal-size rewrite cannot hide behind an unchanged stat result.
        final = snapshot(paths, deadline, clock)
        if any(final[name] != expected[name] for name in paths):
            raise MetadataFailure("local artifact changed after its snapshot")
        record.update(status="passed", reason="server_size_and_md5_match")
    except (OSError, MetadataFailure, TimeoutError) as error:
        record.update(reason="timeout" if isinstance(error, TimeoutError) else "verification_error",
                      detail=str(error))
    record["elapsed_seconds"] = round(clock() - started, 6)
    return record


def metadata_reader(bucket, prefix):
    import google.auth
    from google.auth.transport.requests import AuthorizedSession, Request

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/devstorage.read_only"], request=Request())
    session = AuthorizedSession(credentials, refresh_timeout=15, max_refresh_attempts=1)

    def fetch(relative, timeout):
        name = "/".join(part.strip("/") for part in (prefix, relative) if part)
        url = f"https://storage.googleapis.com/storage/v1/b/{quote(bucket, safe='')}/o/{quote(name, safe='')}"
        try:
            response = session.get(url, params={"fields": "size,md5Hash,generation"},
                                   timeout=timeout, max_allowed_time=timeout)
        except Exception as error:
            # No credentials, request headers or credential payloads enter receipts.
            raise MetadataFailure("metadata transport failed: " + type(error).__name__) from error
        if response.status_code == 404 or response.status_code in {429, 500, 502, 503, 504}:
            return None
        if response.status_code != 200:
            raise MetadataFailure(f"metadata request failed (HTTP {response.status_code})")
        try:
            return response.json()
        except ValueError as error:
            raise MetadataFailure("metadata response is not JSON") from error
    return fetch


def regular_files(root):
    # Matches rsync --no-links. W&B convenience symlinks are not payload files;
    # their real targets beneath the run directory are authenticated separately.
    return {path.relative_to(root).as_posix(): path for path in root.rglob("*")
            if path.is_file() and not path.is_symlink()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--root", type=Path)
    inputs.add_argument("--file", type=Path)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", default="")
    parser.add_argument("--object", help="Exact object name for --file")
    parser.add_argument("--receipt", type=Path, help="New receipt path outside --root")
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--poll", type=float, default=2)
    args = parser.parse_args(argv)
    if not 0 < args.timeout <= 900 or not 0 < args.poll <= 30:
        parser.error("timeout must be in (0,900] and poll in (0,30]")
    if args.root:
        root = args.root.resolve()
        if not root.is_dir() or args.object:
            parser.error("--root must be a directory and cannot use --object")
        paths, prefix = regular_files(root), args.prefix
        membership = lambda: regular_files(root)
        skipped = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_symlink()]
    else:
        if not args.file.is_file() or args.file.is_symlink() or not args.object:
            parser.error("--file requires a regular file and --object")
        paths, prefix, membership, skipped = {args.object: args.file}, "", None, []
    if args.receipt and (args.receipt.exists() or (args.root and root in args.receipt.resolve().parents)):
        parser.error("receipt must be a new path outside the verified run directory")
    try:
        result = verify(paths, metadata_reader(args.bucket, prefix), timeout=args.timeout,
                        poll=args.poll, membership=membership)
    except Exception as error:
        result = {"status": "failed", "reason": "credential_or_transport_setup_failed",
                  "detail": type(error).__name__, "objects": {}, "pending": {}}
    result.update(bucket=args.bucket, prefix=prefix, skipped_symlinks=skipped)
    if args.receipt:
        args.receipt.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    # Metadata only: retain object generations/checksums in SkyPilot logs even if
    # the receipt itself cannot be uploaded. No object contents are printed.
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
