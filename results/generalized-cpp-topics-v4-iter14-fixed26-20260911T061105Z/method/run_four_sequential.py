#!/usr/bin/env python3
"""Run the unchanged, pinned evaluator four times with a durable gate between trials."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

DRIVER_SHA256 = '39044988bb9a73ff62aee78fbfa1051c8c5a3b165dcb02c0b2d4c162d9f015c4'
SOURCE_RUN = 'generalized-cpp-topics-v4-grpo20-20260911-015941'
ADAPTER_SHA256 = 'e6c55d244a69b1f630810b3f42f203f89d166f9d8d9e77743126cdf7b3812255'


def validate_receipt(receipt, run_id):
    assert receipt['status'] == 'complete'
    assert receipt['run_id'] == run_id
    assert receipt['source_run_id'] == SOURCE_RUN
    assert receipt['source_checkpoint'] == 'iter_0000014'
    assert receipt['adapter_sha256'] == ADAPTER_SHA256
    assert receipt['tries'] == 2 and receipt['lora_activation_verified'] is True
    assert receipt['aider_commit'] == '5dc9490bb35f9729ef2c95d00a19ccd30c26339c'
    assert receipt['polyglot_commit'] == '7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f'
    validation = receipt['validation']
    assert validation['terminal_tasks'] == validation['unique_testcases'] == 26
    assert len(set(validation['testcases'])) == 26


def main():
    driver = Path(__file__).with_name('eval_driver.py')
    assert hashlib.sha256(driver.read_bytes()).hexdigest() == DRIVER_SHA256
    cohort = os.environ['EVAL_COHORT_ID']
    assert cohort.startswith('generalized-cpp-topics-v4-iter14-fixed26-')
    workspace = Path.home() / 'glm47-eval-workspace'
    durable = os.environ['EVAL_DURABLE_ROOT'].rstrip('/')
    results = []
    for trial in range(1, 5):
        run_id = f'{cohort}-t{trial:02d}'
        run_dir = workspace / f'eval-{run_id}'
        assert not run_dir.exists(), 'Refusing to reuse a previous trial workspace'
        print(f'START trial {trial}/4: {run_id}', flush=True)
        env = dict(os.environ, EVAL_RUN_ID=run_id, EVAL_WORKSPACE=str(workspace))
        status = subprocess.run([sys.executable, str(driver)], env=env).returncode
        # The original driver warns on sync failure. This wrapper instead blocks
        # the next trial unless the full workspace sync and receipt verification pass.
        if run_dir.exists():
            subprocess.run(['gcloud', 'storage', 'rsync', '--recursive', str(run_dir),
                            f'{durable}/{run_id}/'], check=True)
        if status:
            raise RuntimeError(f'Trial {trial} failed with exit status {status}; cohort stopped')
        receipt_path = run_dir / 'run_receipt.json'
        payload = receipt_path.read_bytes()
        receipt = json.loads(payload)
        validate_receipt(receipt, run_id)
        remote = subprocess.run(['gcloud', 'storage', 'cat',
                                 f'{durable}/{run_id}/run_receipt.json'],
                                capture_output=True, check=True).stdout
        assert hashlib.sha256(remote).digest() == hashlib.sha256(payload).digest()
        results.append({'trial': trial, 'run_id': run_id,
                        'receipt_sha256': hashlib.sha256(payload).hexdigest(),
                        'pass_at_1': receipt['validation']['pass_at_1'],
                        'multiturn_feedback': receipt['validation']['pass_at_k'],
                        'durable_receipt': f'{durable}/{run_id}/run_receipt.json'})
        print('DURABLE_TRIAL_COMPLETE ' + json.dumps(results[-1]), flush=True)
    summary = workspace / f'{cohort}-summary.json'
    with summary.open('x') as stream:
        json.dump({'status': 'complete', 'cohort_id': cohort,
                   'source_checkpoint': 'iter_0000014', 'sequential_trials': results}, stream, indent=2)
    subprocess.run(['gcloud', 'storage', 'cp', str(summary),
                    f'{durable}/{cohort}/cohort_receipt.json'], check=True)
    print('ALL_FOUR_TRIALS_COMPLETE ' + cohort, flush=True)


if __name__ == '__main__':
    main()
