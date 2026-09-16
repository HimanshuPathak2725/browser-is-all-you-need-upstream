"""Authenticate and export an explicit training cohort without changing old admission evidence."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import tempfile

from Reward_GRPO import generalized_cpp_grpo as base

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COHORT = ROOT / 'Reward_GRPO/cohorts/cpp-grpo-final-v1.json'
VERIFIER_PATHS = (
    'generalized_verifier_docs', 'Reward_GRPO/Generalized Cpp Verifiers',
    'Reward_GRPO/topic_coverage',
)
VERIFIER_FILES = (
    'Reward_GRPO/generalized_cpp_grpo.py', 'Reward_GRPO/global_cpp_verifier_runner.py',
    'Reward_GRPO/generalized_cpp_topic_grpo.py', 'Reward_GRPO/generalized_cpp_cohort.py',
    'Reward_GRPO/generalized_cpp_topic_sandbox.Dockerfile',
)


def verifier_hashes():
    paths = [ROOT / p for p in VERIFIER_FILES]
    for directory in VERIFIER_PATHS:
        paths.extend(p for p in (ROOT / directory).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix != '.pyc')
    return {p.relative_to(ROOT).as_posix(): base._sha256(p) for p in sorted(paths)}


def task_identity(binding):
    return {'manifest_sha256': binding.manifest_sha256,
            'fixture_files': {p: base._sha256(binding.fixture_dir / p)
                              for p in binding.manifest['protected_files']}}


def load_cohort(path=DEFAULT_COHORT, registry=None):
    registry = registry or base._registry()
    data = json.loads(Path(path).read_text())
    if data.get('schema_version') != 1 or not data.get('version'):
        raise ValueError('unsupported cohort schema')
    train, validation = data.get('train', []), data.get('validation', [])
    selected = train + validation
    if not train or not validation or len(set(selected)) != len(selected):
        raise ValueError('cohort must have unique, disjoint train and validation tasks')
    if set(data['tasks']) != set(selected):
        raise ValueError('cohort task identity catalog mismatch')
    if data['registry_sha256'] != base._sha256(registry.path):
        raise ValueError('cohort registry hash mismatch')
    if data['verifier_files'] != verifier_hashes():
        raise ValueError('cohort verifier hash mismatch')
    for task in selected:
        binding = registry.resolve(task)
        if data['tasks'][task] != task_identity(binding):
            raise ValueError(f'cohort fixture identity mismatch: {task}')
    return data


def selected_registry(data, registry):
    """An explicit export view; never rewrite historical registry/admission receipts."""
    view = copy.copy(registry)
    view.entries = {task: {**entry, 'train': task in data['train'],
                          'validation': task in data['validation']}
                    for task, entry in registry.entries.items()}
    view.dataset = {**registry.dataset, 'dataset_tag': data['version'],
                    'official_task_id_overlap': data['train'],
                    'midband_admission': None}
    return view


def build_data(args):
    from Reward_GRPO import generalized_cpp_topic_grpo as topic
    registry = base._registry()
    data = load_cohort(registry=registry)
    if args.train_limit is not None or args.eval_limit is not None:
        raise ValueError('a frozen cohort cannot be silently truncated')
    with tempfile.TemporaryDirectory(prefix='final-cpp-cohort-') as temp:
        source = base._write_task_source(selected_registry(data, registry), Path(temp))
        paths = base.build_aider_polyglot_datasets(source, args.out,
            train_limit=None, monitor_limit=len(data['train']), profile=args.profile,
            run_id=args.run_id, sort_by_size=args.sort_by_size, force=args.force)
    for path in args.out.rglob('*.jsonl'):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows:
            metadata = row['metadata']; task = metadata['problem_id']
            metadata.update(cohort_version=data['version'],
                cohort_sha256=base._sha256(DEFAULT_COHORT),
                combined_reward_sha256=topic.contract_digest(),
                generalized_verifier_manifest_sha256=data['tasks'][task]['manifest_sha256'],
                topic_coverage_required=task in topic.TOPICS)
        path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    manifest_path = Path(paths['manifest'])
    manifest = json.loads(manifest_path.read_text())
    manifest.update(cohort_version=data['version'], cohort_sha256=base._sha256(DEFAULT_COHORT),
        combined_reward_sha256=topic.contract_digest(), reward_function=topic.MODULE+'.reward_func',
        reward_scoring_version=topic.SCORING_VERSION, train_tasks=data['train'],
        validation_tasks=data['validation'], source_versions=data['source_versions'],
        task_identities=data['tasks'], reference_answers_packaged=False,
        official_training_overlap=True)
    # Export paths are locators, not provenance; omit temporary/local paths.
    for key in ('source_root', 'source_dir', 'tasks_dir', 'output_dir'):
        manifest.pop(key, None)
    manifest['file_sha256s'] = {p.relative_to(args.out).as_posix(): base._sha256(p)
                              for p in args.out.rglob('*') if p.is_file() and p != manifest_path}
    topic.write_json(manifest_path, manifest)
    return {k: str(v) for k,v in paths.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['validate'])
    args = parser.parse_args()
    data = load_cohort()
    print(json.dumps({'status':'passed','version':data['version'],
                      'train':data['train'],'validation':data['validation']}, indent=2))


if __name__ == '__main__':
    main()
