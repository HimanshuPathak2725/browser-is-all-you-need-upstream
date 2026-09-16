#!/usr/bin/env python3
"""Matched whole-file C++ evaluation; fresh generation and replay remain distinct."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import inspect
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
COHORT_VERSION = 'cpp-grpo-final-v1'
# Frozen September v4 launch decoding contract, retained for both new checkpoints.
STOP_TOKEN_IDS = (154820, 154827, 154829)
SHA = re.compile(r'[0-9a-f]{40}')


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def read_jsonl(path):
    with Path(path).open() as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path, value):
    with Path(path).open('x') as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')


def messages(row):
    prompt = row.get('prompt')
    if (not isinstance(prompt, list) or not prompt or
            any(not isinstance(item, dict) or item.get('role') not in {'system', 'user', 'assistant'}
                or not isinstance(item.get('content'), str) for item in prompt)
            or prompt[-1]['role'] != 'user'):
        raise ValueError('whole-file evaluation requires the original chat-message prompt')
    return prompt  # Never stringify a message list or add a second system prompt.


def load_dataset(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest.get('cohort_version') != COHORT_VERSION:
        raise ValueError('dataset does not pin the final cohort')
    hashes = manifest.get('file_sha256s', {})
    if not hashes:
        raise ValueError('dataset has no authenticated file catalog')
    for relative, expected in hashes.items():
        path = directory / relative
        if (Path(relative).is_absolute() or '..' in Path(relative).parts
                or directory not in path.resolve().parents or not path.is_file()
                or digest(path) != expected):
            raise ValueError(f'dataset file hash mismatch: {relative}')
    rows = []
    for split, relative, task_key in (
        ('development', 'grpo/train.jsonl', 'train_tasks'),
        ('held_out', 'eval/validation.jsonl', 'validation_tasks'),
    ):
        if relative not in hashes:
            raise ValueError(f'unbound prompt source: {relative}')
        selected = read_jsonl(directory / relative)
        intended = manifest.get(task_key, [])
        ids = [row.get('problem_id') for row in selected]
        if not intended or len(ids) != len(set(ids)) or set(ids) != set(intended):
            raise ValueError(f'{split} task membership mismatch')
        for row in selected:
            metadata = row.get('metadata', {})
            task = row['problem_id']
            if metadata.get('problem_id') != task:
                raise ValueError('row and reward task identity disagree')
            for key in ('cohort_version', 'cohort_sha256', 'combined_reward_sha256'):
                if metadata.get(key) != manifest.get(key) or not metadata.get(key):
                    raise ValueError(f'row binding mismatch: {task}/{key}')
            if (metadata.get('generalized_verifier_manifest_sha256') !=
                    manifest['task_identities'][task]['manifest_sha256']):
                raise ValueError(f'task manifest mismatch: {task}')
            messages(row)
            rows.append({**row, 'evaluation_split': split, 'prompt_sha256': canonical_hash(row['prompt'])})
    ids = [row['problem_id'] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('development and held-out tasks overlap')
    return manifest, sorted(rows, key=lambda row: (row['evaluation_split'], row['problem_id']))


def adapter_identity(directory):
    if directory is None:
        return None
    root = Path(directory)
    weights = [root / name for name in ('adapter_model.safetensors', 'adapter_model.bin') if (root / name).is_file()]
    if len(weights) != 1 or not (root / 'adapter_config.json').is_file():
        raise ValueError('adapter must contain adapter_config.json and exactly one adapter_model.safetensors or adapter_model.bin')
    paths = [root / 'adapter_config.json', *weights]
    return {p.name: digest(p) for p in paths}


def adapter_settings(directory):
    if directory is None:
        return None
    config = json.loads((Path(directory) / 'adapter_config.json').read_text())
    modules, rank = config.get('target_modules'), config.get('r')
    if (config.get('peft_type') != 'LORA' or type(rank) is not int or rank < 1
            or not isinstance(modules, list) or not modules
            or any(not isinstance(module, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9.]*', module) for module in modules)
            or len(set(modules)) != len(modules)):
        raise ValueError('adapter requires an explicit, unique LoRA target-module list and positive rank')
    if config.get('rank_pattern') or config.get('alpha_pattern') or config.get('use_dora'):
        raise ValueError('adapter uses unsupported per-module rank/alpha overrides or DoRA')
    return {'rank': rank, 'target_modules': modules, 'alpha': config.get('lora_alpha')}


def resolve_model(args):
    """Authenticate a mounted model copy against its pinned source file catalog."""
    if not args.model_path:
        if args.model_file_manifest:
            raise ValueError('model file catalog requires --model-path')
        return args.model, {'kind': 'huggingface_revision', 'model': args.model, 'revision': args.model_revision}
    if not args.model_file_manifest:
        raise ValueError('--model-path requires --model-file-manifest from the pinned source')
    catalog = json.loads(args.model_file_manifest.read_text())
    if (catalog.get('model') != args.model or catalog.get('revision') != args.model_revision
            or not catalog.get('source') or not catalog.get('files')
            or catalog.get('authentication') != 'huggingface-pinned-revision'
            or catalog.get('hf_revision') != args.model_revision):
        raise ValueError('model source catalog identity mismatch')
    root = args.model_path.resolve()
    files = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if files != set(catalog['files']) or 'config.json' not in files:
        raise ValueError('local model file membership differs from source catalog')
    if not any(p.endswith(('.safetensors', '.bin')) for p in files):
        raise ValueError('local model catalog contains no model weights')
    for relative, expected in catalog['files'].items():
        path = root / relative
        if Path(relative).is_absolute() or '..' in Path(relative).parts or digest(path) != expected:
            raise ValueError(f'local model hash mismatch: {relative}')
    return str(root), {'kind': 'source_snapshot_catalog', 'model': args.model,
                       'revision': args.model_revision, 'source': catalog['source'],
                       'authentication': catalog['authentication'], 'hf_revision': catalog['hf_revision'],
                       'file_catalog_sha256': digest(args.model_file_manifest), 'files': catalog['files']}


def trial_seed(seed, task, trial):
    return int(canonical_hash([seed, task, trial])[:8], 16) % (2**31)


def classify(record):
    """Correctness comes from completed official execution, never reward rounding."""
    receipt = record.get('verifier_receipt') or {}
    if record.get('infrastructure_error') or receipt.get('status') == 'invalid':
        return 'INVALID', 'infrastructure'
    policies = receipt.get('policy_results', [])
    kernels = {k.get('kernel_id'): k for p in policies for k in p.get('kernels', [])}
    g03 = kernels.get('G03-2', {})
    facts = g03.get('facts', {})
    run = facts.get('candidate', {}).get('run', {})
    reference = facts.get('reference', {})
    topic = record.get('topic_coverage')
    if any(p.get('status') == 'invalid' for p in policies) or (topic or {}).get('status') == 'invalid':
        return 'INVALID', 'infrastructure'
    if receipt.get('status') == 'pass':
        authenticated = (g03.get('status') == 'pass' and reference.get('status') == 'OK'
                         and run.get('verified_pass') is True and run.get('execution_completed') is True
                         and run.get('harness_returncode') == 0 and run.get('returncode') == 0
                         and not run.get('crashed') and not run.get('timed_out')
                         and not run.get('infrastructure_error'))
        if not authenticated:
            return 'INVALID', 'inconsistent_verifier_receipt'
        if record.get('topic_required') and (not topic or topic.get('reference_status') != 'pass'
                                             or topic.get('status') not in {'pass', 'fail'}):
            return 'INVALID', 'incomplete_topic_receipt'
        if not topic or topic.get('status') == 'pass':
            return 'PASS', None
    if receipt.get('status') not in {'pass', 'fail'}:
        reason = record.get('reason')
        if reason in {'forbidden_file', 'duplicate_file', 'candidate_boundary'}:
            return 'FAIL', 'boundary'
        if record.get('format_valid') is False or reason in {'parse_error', 'missing_file', 'empty_response', 'no_files'}:
            return 'FAIL', 'format'
        return 'INVALID', 'incomplete_verifier_receipt'
    build = facts.get('candidate', {}).get('build', {})
    build_status = build.get('status')
    if build_status in {'CE-1', 'CE-2'}:
        return 'FAIL', 'compile'
    if build_status == 'LE':
        return 'FAIL', 'link'
    if kernels.get('G02-1', {}).get('status') == 'fail':
        return 'FAIL', 'compile'
    if kernels.get('G02-2', {}).get('status') == 'fail':
        return 'FAIL', 'link'
    if run.get('crashed') or run.get('timed_out') or run.get('failure_kind') in {'signal', 'runtime_timeout', 'incomplete_test_execution'}:
        return 'FAIL', 'runtime'
    if topic and topic.get('status') == 'fail':
        runs = [run for group in topic.get('candidate', {}).get('groups', []) for run in group.get('runs', [])]
        if any(run.get('reason') in {'runtime_timeout', 'runtime_signal'} for run in runs):
            return 'FAIL', 'runtime'
        return 'FAIL', 'semantic'
    if g03.get('status') == 'fail':
        return 'FAIL', 'semantic'
    if any(k.get('status') == 'fail' for key, k in kernels.items() if str(key).startswith('G01-')):
        return 'FAIL', 'interface'
    return 'FAIL', 'format_or_policy'


def aggregate(records, rows, trials):
    expected = {(r['problem_id'], trial) for r in rows for trial in range(1, trials + 1)}
    observed = [(r['problem_id'], r['trial']) for r in records]
    if len(observed) != len(set(observed)) or set(observed) != expected:
        raise ValueError('incomplete or duplicate trial grid; refusing an invented score')
    catalog = {r['problem_id']: r['evaluation_split'] for r in rows}
    table = []
    for task in sorted(catalog):
        samples = sorted((r for r in records if r['problem_id'] == task), key=lambda r: r['trial'])
        outcomes = [r['verdict'] for r in samples]
        if any(value not in {'PASS', 'FAIL', 'INVALID'} for value in outcomes):
            raise ValueError('unknown trial verdict')
        passed, invalid = outcomes.count('PASS'), outcomes.count('INVALID')
        table.append({'task': task, 'split': catalog[task], 'outcomes': outcomes,
                      'passed': passed, 'valid_trials': trials - invalid, 'invalid_trials': invalid,
                      'direct_pass_at_k': True if passed else None if invalid else False})
    summaries = {}
    for split in ('development', 'held_out'):
        tasks = [r for r in table if r['split'] == split]
        samples = [r for r in records if catalog[r['problem_id']] == split]
        known = [r for r in tasks if r['direct_pass_at_k'] is not None]
        summaries[split] = {
            'tasks': len(tasks), 'scheduled_trials': len(tasks) * trials,
            'pass_at_1': {'passes': sum(r['passed'] for r in tasks),
                          'valid_trials': sum(r['valid_trials'] for r in tasks)},
            'direct_pass_at_k': {'k': trials, 'passed_tasks': sum(r['direct_pass_at_k'] is True for r in tasks),
                                 'known_tasks': len(known), 'unknown_tasks': len(tasks) - len(known)},
            'invalid_trials': sum(r['invalid_trials'] for r in tasks),
            'trial_pass_at_1': [{
                'trial': trial, 'passes': sum(r['verdict'] == 'PASS' for r in samples if r['trial'] == trial),
                'valid_trials': sum(r['verdict'] != 'INVALID' for r in samples if r['trial'] == trial),
                'invalid_trials': sum(r['verdict'] == 'INVALID' for r in samples if r['trial'] == trial),
            } for trial in range(1, trials + 1)],
            'failure_breakdown': dict(Counter(r['failure_kind'] for r in samples if r['verdict'] != 'PASS')),
            'truncated_generations': sum(r.get('generation', {}).get('truncated') is True for r in samples),
        }
    return {'trials_per_task': trials, 'task_table': table, 'splits': summaries}


def generate(args, rows):
    try:
        from glm47_posttraining.integrations.miles_glm47_bridge import register_glm47_bridge
        register_glm47_bridge()
        from sglang import Engine
        from sglang.srt.sampling.sampling_params import SamplingParams
        from sglang.srt.utils.common import SUPPORTED_LORA_TARGET_MODULES
        from transformers import AutoTokenizer
        from scripts.evaluate import (sglang_engine_kwargs, output_text, output_finish_reason,
                                      output_token_count, output_is_truncated)
    except ImportError as error:
        raise RuntimeError('Generation requires the pinned GLM47 runtime with SGLang, Transformers and the LoRA bridge; nothing was installed') from error
    required_sampling = {'sampling_seed', 'stop_token_ids', 'skip_special_tokens'}
    missing_sampling = required_sampling - set(inspect.signature(SamplingParams.__init__).parameters)
    if missing_sampling:
        raise RuntimeError(f'SGLang runtime lacks required matched sampling settings: {sorted(missing_sampling)}')
    model_path = getattr(args, 'resolved_model', args.model)
    tokenizer = AutoTokenizer.from_pretrained(model_path, revision=args.model_revision, trust_remote_code=True)
    kwargs = dict(model_path=model_path, revision=args.model_revision, trust_remote_code=True,
                  tp_size=args.tp_size, dtype='bfloat16', mem_fraction_static=args.mem_fraction_static,
                  cuda_graph_max_bs=16, moe_runner_backend='triton', log_level='warning', random_seed=args.seed)
    if args.adapter:
        adapter = adapter_settings(args.adapter)
        unsupported = set(adapter['target_modules']) - set(SUPPORTED_LORA_TARGET_MODULES)
        if unsupported:
            raise RuntimeError(f'SGLang does not support adapter target modules: {sorted(unsupported)}')
        kwargs.update(enable_lora=True, max_lora_rank=adapter['rank'], lora_target_modules=adapter['target_modules'],
                      lora_backend='triton', experts_shared_outer_loras=True, lora_use_virtual_experts=True)
    supported = sglang_engine_kwargs(kwargs)
    critical = set(kwargs) - {'cuda_graph_max_bs'}
    if any(key not in supported for key in critical):
        raise RuntimeError('SGLang runtime would discard a required model/LoRA/seed setting')
    engine = Engine(**supported)
    try:
        if args.adapter:
            loaded = engine.load_lora_adapter('evaluation', args.adapter)
            success = loaded.get('success') if isinstance(loaded, dict) else getattr(loaded, 'success', None)
            if success is not True:
                detail = loaded.get('error_message') if isinstance(loaded, dict) else getattr(loaded, 'error_message', None)
                raise RuntimeError(f'SGLang did not authenticate successful adapter loading: {detail}')
        for row in rows:
            prompt = tokenizer.apply_chat_template(messages(row), tokenize=False, add_generation_prompt=True, enable_thinking=True)
            for trial in range(1, args.trials + 1):
                seed = trial_seed(args.seed, row['problem_id'], trial)
                sampling = {'max_new_tokens': args.max_tokens, 'temperature': args.temperature,
                            'top_p': 1.0, 'sampling_seed': seed,
                            'stop_token_ids': list(STOP_TOKEN_IDS), 'skip_special_tokens': True}
                output = engine.generate(prompt, sampling, lora_path='evaluation' if args.adapter else None)
                if isinstance(output, list):
                    if len(output) != 1:
                        raise RuntimeError('unexpected SGLang result count')
                    output = output[0]
                response = output_text(output)
                yield {'problem_id': row['problem_id'], 'trial': trial, 'prompt_sha256': row['prompt_sha256'],
                       'response': response, 'response_sha256': canonical_hash(response), 'sampling_seed': seed,
                       'rendered_prompt_sha256': canonical_hash(prompt),
                       'finish_reason': output_finish_reason(output), 'completion_tokens': output_token_count(output, 'completion'),
                       'prompt_tokens': output_token_count(output, 'prompt'), 'truncated': output_is_truncated(output, args.max_tokens)}
    finally:
        engine.shutdown()


def validate_generations(generations, rows, trials):
    by_task = {r['problem_id']: r for r in rows}
    seen = set()
    for item in generations:
        key = (item.get('problem_id'), item.get('trial'))
        if key in seen or key[0] not in by_task or type(key[1]) is not int or not 1 <= key[1] <= trials:
            raise ValueError('duplicate, unknown or invalid generated trial')
        seen.add(key)
        if (item.get('prompt_sha256') != by_task[key[0]]['prompt_sha256']
                or not isinstance(item.get('response'), str)
                or item.get('response_sha256') != canonical_hash(item['response'])):
            raise ValueError('generated output/prompt hash mismatch')
    if len(seen) != len(rows) * trials:
        raise ValueError('incomplete generated trial grid')


def score_generations(args, generations, rows, reward):
    """Bound physical worker concurrency; preserve each result before sorting."""
    by_task = {row['problem_id']: row for row in rows}
    receipts = args.output_dir / 'receipts'
    receipts.mkdir()
    def score(index, item):
        row = by_task[item['problem_id']]
        sample = {'metadata': dict(row['metadata']), 'response': item['response'],
                  'response_length': item.get('completion_tokens'), 'index': index,
                  'rollout_id': f"{args.label}-trial-{item['trial']}"}
        try:
            result = reward.score_sample(sample)
        except Exception as error:
            result = {'infrastructure_error': True, 'reason': 'evaluation_scoring_exception',
                      'exception': f'{type(error).__name__}: {error}'}
        try:
            verdict, failure = classify(result)
        except (TypeError, ValueError, KeyError, AttributeError) as error:
            verdict, failure = 'INVALID', 'malformed_verifier_receipt'
            result = {'original_result': result, 'infrastructure_error': True,
                      'exception': f'{type(error).__name__}: {error}'}
        return {'problem_id': item['problem_id'], 'trial': item['trial'], 'verdict': verdict,
                'failure_kind': failure, 'response_sha256': item['response_sha256'], 'result': result,
                'generation': {key: item.get(key) for key in ('truncated', 'finish_reason', 'completion_tokens', 'prompt_tokens', 'sampling_seed')}}
    records = {}
    with ThreadPoolExecutor(max_workers=args.score_workers) as pool:
        futures = {pool.submit(score, index, item): index for index, item in enumerate(generations)}
        for future in as_completed(futures):
            index = futures[future]
            record = future.result()
            write_json(receipts / f'{index:04d}.json', record)
            records[index] = record
            print(f"{record['problem_id']} trial {record['trial']}: {record['verdict']} ({record['failure_kind'] or 'verified completion'})", flush=True)
    ordered = [records[index] for index in range(len(generations))]
    with (args.output_dir / 'records.jsonl').open('x') as handle:
        for record in ordered:
            handle.write(json.dumps(record, sort_keys=True, allow_nan=False) + '\n')
    return ordered


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--dataset-repo', required=True)
    parser.add_argument('--dataset-revision', required=True)
    parser.add_argument('--model', required=True, help='Hugging Face base model repository ID')
    parser.add_argument('--model-revision', required=True)
    parser.add_argument('--model-path', type=Path, help='Existing local copy authenticated by --model-file-manifest')
    parser.add_argument('--model-file-manifest', type=Path, help='Model/revision/source identity and relative file SHA-256 catalog')
    parser.add_argument('--adapter', help='Converted PEFT adapter directory; omit only for base-model evaluation')
    parser.add_argument('--checkpoint-id', required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--generated', type=Path, help='Replay this driver\'s preserved generations; never called new evaluation')
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--seed', type=int, default=20260916)
    parser.add_argument('--temperature', type=float, default=0.7)
    parser.add_argument('--max-tokens', type=int, default=8192)
    parser.add_argument('--tp-size', type=int, default=4)
    parser.add_argument('--score-workers', type=int, default=4, help='Concurrent isolated reward workers (1..24)')
    parser.add_argument('--mem-fraction-static', type=float, default=0.7)
    parser.add_argument('--sandbox-image', default='glm47-generalized-cpp-topics:final-v1')
    args = parser.parse_args(argv)
    if not SHA.fullmatch(args.dataset_revision) or not SHA.fullmatch(args.model_revision):
        parser.error('dataset/model revisions must be immutable 40-character commit SHAs')
    if args.trials < 1 or args.max_tokens < 1 or not math.isfinite(args.temperature) or args.temperature < 0 or not 1 <= args.score_workers <= 24:
        parser.error('invalid trial/token/temperature configuration')
    if Path(args.model).exists():
        parser.error('--model must be a revision-pinned Hugging Face repository, not an unauthenticated local copy')
    return args


def main(argv=None):
    args = parse_args(argv)
    if args.output_dir.exists():
        raise ValueError('output directory already exists; historical evidence is never overwritten')
    manifest, rows = load_dataset(args.data_dir)
    from huggingface_hub import hf_hub_download
    published = hf_hub_download(args.dataset_repo, 'manifest.json', repo_type='dataset', revision=args.dataset_revision)
    if digest(published) != digest(args.data_dir / 'manifest.json'):
        raise ValueError('local dataset differs from the declared Hugging Face revision')
    import os
    os.environ['GENERALIZED_TOPIC_SANDBOX_IMAGE'] = args.sandbox_image
    from Reward_GRPO import generalized_cpp_topic_grpo as reward
    if manifest['combined_reward_sha256'] != reward.contract_digest():
        raise ValueError('dataset reward digest differs from the active verifier')
    image = reward.image_identity()  # Authenticate before spending GPU generation time.
    args.resolved_model, model_identity = resolve_model(args) if not args.generated else (None, None)
    adapter = adapter_identity(args.adapter)
    lora = adapter_settings(args.adapter)
    source_identity = None
    if args.generated:
        source_identity = json.loads((args.generated.parent / 'identity.json').read_text())
        for key, expected in {'model': args.model, 'model_revision': args.model_revision,
                              'checkpoint_id': args.checkpoint_id,
                              'dataset_manifest_sha256': digest(args.data_dir / 'manifest.json')}.items():
            if source_identity.get(key) != expected:
                raise ValueError(f'replay source identity mismatch: {key}')
        if adapter is not None and adapter != source_identity.get('adapter_files'):
            raise ValueError('replay adapter disagrees with source identity')
    mode = 'archived_output_replay' if args.generated else 'new_model_evaluation'
    args.output_dir.mkdir(parents=True, exist_ok=False)
    identity = {'mode': mode, 'label': args.label, 'cohort_version': manifest['cohort_version'],
                'cohort_sha256': manifest['cohort_sha256'], 'dataset_repo': args.dataset_repo,
                'dataset_revision': args.dataset_revision, 'dataset_manifest_sha256': digest(args.data_dir / 'manifest.json'),
                'model': args.model, 'model_revision': args.model_revision, 'checkpoint_id': args.checkpoint_id,
                'model_files': source_identity.get('model_files') if source_identity else model_identity,
                'adapter_files': source_identity.get('adapter_files') if source_identity else adapter, 'combined_reward_sha256': reward.contract_digest(), 'sandbox_image_id': image,
                'generation': {'seed': args.seed, 'temperature': args.temperature, 'top_p': 1.0,
                               'stop_token_ids': list(STOP_TOKEN_IDS), 'skip_special_tokens': True,
                               'max_tokens': args.max_tokens, 'trials': args.trials, 'tp_size': args.tp_size,
                               'chat_template_kwargs': {'enable_thinking': True},
                               'lora_rank': lora['rank'] if lora else None,
                               'lora_modules': lora['target_modules'] if lora else [], 'lora_alpha': lora['alpha'] if lora else None},
                'score_workers': args.score_workers,
                'source_generated_sha256': digest(args.generated) if args.generated else None,
                'source_generation_identity': source_identity, 'evaluation_driver_sha256': digest(__file__),
                'generation_helpers_sha256': digest(ROOT / 'scripts/evaluate.py'),
                'started_at': datetime.now(timezone.utc).isoformat()}
    if source_identity:
        identity['generation'] = source_identity['generation']
    write_json(args.output_dir / 'identity.json', identity)
    with (args.output_dir / 'prompts.jsonl').open('x') as handle:
        for row in rows:
            handle.write(json.dumps({'problem_id': row['problem_id'], 'split': row['evaluation_split'],
                                     'prompt': row['prompt'], 'prompt_sha256': row['prompt_sha256']},
                                    sort_keys=True, ensure_ascii=False) + '\n')
    generations = []
    try:
        stream = read_jsonl(args.generated) if args.generated else generate(args, rows)
        with (args.output_dir / 'generated.jsonl').open('x') as handle:
            for item in stream:
                generations.append(item)
                handle.write(json.dumps(item, sort_keys=True, allow_nan=False) + '\n')
                handle.flush()
        validate_generations(generations, rows, args.trials)
        if adapter != adapter_identity(args.adapter):
            raise ValueError('adapter changed during generation')
        records = score_generations(args, generations, rows, reward)
        summary = {**aggregate(records, rows, args.trials), 'mode': mode, 'identity': identity,
                   'completed_at': datetime.now(timezone.utc).isoformat()}
        write_json(args.output_dir / 'summary.json', summary)
        write_json(args.output_dir / 'evidence-sha256.json', {
            p.relative_to(args.output_dir).as_posix(): digest(p) for p in sorted(args.output_dir.rglob('*')) if p.is_file()})
        return 2 if any(r['verdict'] == 'INVALID' for r in records) else 0
    except Exception as error:
        write_json(args.output_dir / 'incomplete.json', {'mode': mode, 'error': f'{type(error).__name__}: {error}',
                                                      'status': 'incomplete', 'no_completed_evaluation_claim': True})
        raise


if __name__ == '__main__':
    raise SystemExit(main())
