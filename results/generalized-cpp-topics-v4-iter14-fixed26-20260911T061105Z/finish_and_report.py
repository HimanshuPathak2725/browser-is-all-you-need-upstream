#!/usr/bin/env python3
"""Local sidecar: verify four durable evaluations, report, then remove this cluster only."""
import argparse
import fcntl
import hashlib
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COHORT = 'generalized-cpp-topics-v4-iter14-fixed26-20260911T061105Z'
CLUSTER = 'generalized-topics-v4-iter14-eval4-r2-20260911-071950'
GCS = 'gs://lifeandhalf-24122025-w8-biayn/runs/glm47/evaluations/aider-fixed26'
AUDITOR = '/home/ubuntu/.codex/skills/aider-run-audit/scripts/generate_aider_run_audit.py'
sys.path.insert(0, str(ROOT / 'method'))
from run_four_sequential import validate_receipt, ADAPTER_SHA256, SOURCE_RUN


def log(message):
    print(datetime.now(timezone.utc).isoformat() + ' ' + message, flush=True)


def save_json(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


def fetch(uri):
    result = subprocess.run(['gcloud', 'storage', 'cat', uri], capture_output=True, timeout=90)
    if result.returncode:
        return None
    return result.stdout


def validate_cohort(marker, payloads):
    if marker.get('status') != 'complete' or marker.get('cohort_id') != COHORT:
        raise ValueError('wrong/incomplete cohort marker')
    entries = marker.get('sequential_trials', [])
    if [e['trial'] for e in entries] != [1, 2, 3, 4] or len(payloads) != 4:
        raise ValueError('four ordered trials are required')
    receipts = []
    for index, (entry, payload) in enumerate(zip(entries, payloads), 1):
        run_id = f'{COHORT}-t{index:02d}'
        receipt = json.loads(payload)
        validate_receipt(receipt, run_id)
        if entry['run_id'] != run_id or hashlib.sha256(payload).hexdigest() != entry['receipt_sha256']:
            raise ValueError('trial receipt does not match durable cohort marker')
        if entry['pass_at_1'] != receipt['validation']['pass_at_1'] or entry['multiturn_feedback'] != receipt['validation']['pass_at_k']:
            raise ValueError('cohort scores differ from trial receipt')
        outcomes = receipt['validation']['outcomes']
        if set(outcomes) != set(receipt['validation']['testcases']):
            raise ValueError('outcome/task inventory mismatch')
        if any(not isinstance(o, list) or not 1 <= len(o) <= 2 or any(type(x) is not bool for x in o) for o in outcomes.values()):
            raise ValueError('invalid outcome records')
        if sum(o[0] for o in outcomes.values()) != receipt['validation']['pass_at_1'] or sum(any(o) for o in outcomes.values()) != receipt['validation']['pass_at_k']:
            raise ValueError('reported scores disagree with task outcomes')
        receipts.append(receipt)
    pinned = ['source_checkpoint', 'adapter_sha256', 'adapter_config_sha256',
              'training_data_manifest_sha256', 'model_revision', 'aider_commit',
              'polyglot_commit', 'temperature', 'top_p', 'max_tokens',
              'thinking_disabled', 'tries', 'eval_set_version', 'contract_overlay_sha256',
              'prompt_test_audit_sha256', 'image']
    for r in receipts[1:]:
        if any(r[k] != receipts[0][k] for k in pinned):
            raise ValueError('trial evaluation contracts differ')
        if set(r['validation']['testcases']) != set(receipts[0]['validation']['testcases']):
            raise ValueError('trial task sets differ')
    return receipts


def aggregate(receipts):
    fields = ['pass_at_1', 'pass_at_k', 'well_formed_tasks', 'malformed_responses',
              'error_outputs', 'context_exhaustions', 'test_timeouts']
    metrics = {}
    for field in fields:
        values = [r['validation'][field] for r in receipts]
        metrics[field] = {'per_trial': values, 'mean': statistics.mean(values),
                          'median': statistics.median(values), 'total': sum(values),
                          'sample_stddev': statistics.stdev(values)}
        if field in ('pass_at_1', 'pass_at_k', 'well_formed_tasks'):
            metrics[field]['mean_percent'] = statistics.mean(values) / 26 * 100
    return metrics


def build_report(marker, payloads):
    receipts = validate_cohort(marker, payloads)
    metrics = aggregate(receipts)
    artifacts = []
    for i, payload in enumerate(payloads, 1):
        trial = ROOT / 'trials' / f't{i:02d}'
        trial.mkdir(parents=True, exist_ok=True)
        path = trial / 'run_receipt.json'
        if path.exists() and path.read_bytes() != payload:
            raise ValueError('refusing to replace different saved receipt')
        path.write_bytes(payload)
        subprocess.run([sys.executable, AUDITOR, '--receipt', str(path),
                        '--output-md', str(trial / 'audit.md'),
                        '--output-json', str(trial / 'audit.json')],
                       check=True, capture_output=True, timeout=60)
        artifacts.extend([path, trial / 'audit.md', trial / 'audit.json'])
    summary = {'status': 'complete', 'cohort_id': COHORT, 'checkpoint': 'iter_0000014',
               'source_run_id': SOURCE_RUN, 'adapter_sha256': ADAPTER_SHA256,
               'trials': marker['sequential_trials'], 'trial_count': 4,
               'tasks_per_trial': 26, 'task_trial_observations': 104, 'metrics': metrics,
               'note': 'pass_at_k means two-turn Multiturn with error feedback (MEF), not independent pass@2. Repeated tasks are not 104 independent observations.',
               'completed_at_utc': datetime.now(timezone.utc).isoformat()}
    save_json(ROOT / 'results.json', summary)
    lines = ['# Generalized topics iter_0000014 — four sequential evaluations', '',
             'All four fixed26-contract-v2 trials completed with 26 unique C++ tasks and two tries per task.', '',
             f'Source: `{SOURCE_RUN}`; checkpoint: `iter_0000014`; adapter SHA-256: `{ADAPTER_SHA256}`.', '',
             '| Trial | Pass@1 | Multiturn with error feedback (MEF) | Well formed |',
             '| --- | ---: | ---: | ---: |']
    for i, r in enumerate(receipts, 1):
        v = r['validation']
        lines.append(f"| {i} | {v['pass_at_1']}/26 | {v['pass_at_k']}/26 | {v['well_formed_tasks']}/26 |")
    for label in ('mean', 'median'):
        lines.append('| ' + label.title() + ' | ' + ' | '.join(f"{metrics[k][label]:.2f}/26" for k in ('pass_at_1', 'pass_at_k', 'well_formed_tasks')) + ' |')
    lines += ['', f"Mean Pass@1: **{metrics['pass_at_1']['mean_percent']:.2f}%**. Mean MEF: **{metrics['pass_at_k']['mean_percent']:.2f}%**.", '',
              '## Historical PDF baseline (not a matched control)', '',
              '| Metric (counts per 26 tasks) | PDF base | Four-trial mean | Delta |',
              '| --- | ---: | ---: | ---: |']
    for name, key, base in [('Pass@1','pass_at_1',0), ('MEF','pass_at_k',4), ('Well formed','well_formed_tasks',26), ('Malformed','malformed_responses',0), ('Error outputs','error_outputs',6), ('Context exhausted','context_exhaustions',6), ('Test timeouts','test_timeouts',0)]:
        mean = metrics[key]['mean']
        lines.append(f'| {name} | {base} | {mean:.2f} | {mean-base:+.2f} |')
    lines += ['', 'The PDF baseline is historical and may differ in prompt/contract details; these deltas alone do not prove a training gain. Per-trial audits contain task-level outcomes and integrity notes.', '',
              'The same 26 tasks recur across all four trials: 104 task-trial observations are not independent samples. Error categories may overlap. MEF is assisted repair, not independent pass@2.', '',
              'Verdict: matched-comparator improvement remains unconfirmed; the four-run means summarize this checkpoint only.', '',
              '## Trial evidence', '']
    for i, r in enumerate(receipts, 1):
        lines.append(f"- `{r['run_id']}`: [receipt](trials/t{i:02d}/run_receipt.json), [audit](trials/t{i:02d}/audit.md).")
    (ROOT / 'RESULTS.md').write_text('\n'.join(lines) + '\n')
    artifacts += [ROOT / 'results.json', ROOT / 'RESULTS.md']
    return artifacts


def publish_report(artifacts):
    for path in artifacts:
        uri = f'{GCS}/{COHORT}/report/{path.relative_to(ROOT).as_posix()}'
        subprocess.run(['gcloud', 'storage', 'cp', str(path), uri], check=True,
                       capture_output=True, timeout=120)
        if fetch(uri) != path.read_bytes():
            raise ValueError('report GCS verification failed; no explicit teardown')
    log('Combined report and all trial audits saved locally and verified in GCS')


def teardown_when_idle():
    import sky
    records = sky.get(sky.status(cluster_names=[CLUSTER], refresh=sky.StatusRefreshMode.FORCE))
    if not records:
        return 'already_removed'
    jobs = sky.get(sky.queue(CLUSTER, all_users=True))
    target = [j for j in jobs if j['job_id'] == 1]
    if not target or str(target[0]['status']).split('.')[-1] != 'SUCCEEDED':
        return None
    if any(not j['status'].is_terminal() for j in jobs):
        return None
    log('All four durable results verified and job 1 succeeded; tearing down ' + CLUSTER)
    sky.get(sky.down(CLUSTER))
    remaining = sky.get(sky.status(cluster_names=[CLUSTER], refresh=sky.StatusRefreshMode.FORCE))
    if remaining:
        raise RuntimeError('cluster teardown not yet verified')
    return 'removed'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    if not args.watch:
        parser.error('Use --watch to install the reporting/teardown sidecar')
    with (ROOT / 'finish_watcher.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        deadline = time.monotonic() + 24 * 3600
        report_saved = False
        log('Watcher active; waiting for four-trial durable completion marker')
        while time.monotonic() < deadline:
            try:
                if not report_saved:
                    raw = fetch(f'{GCS}/{COHORT}/cohort_receipt.json')
                    if raw is None:
                        time.sleep(30)
                        continue
                    payloads = [fetch(f'{GCS}/{COHORT}-t{i:02d}/run_receipt.json') for i in range(1, 5)]
                    if any(p is None for p in payloads):
                        time.sleep(30)
                        continue
                    artifacts = build_report(json.loads(raw), payloads)
                    publish_report(artifacts)
                    report_saved = True
                result = teardown_when_idle()
                if result:
                    receipt = {'status': 'complete', 'cluster': CLUSTER, 'teardown': result,
                               'four_trials_verified': True, 'report_gcs_verified': True,
                               'completed_at_utc': datetime.now(timezone.utc).isoformat()}
                    save_json(ROOT / 'teardown_receipt.json', receipt)
                    subprocess.run(['gcloud', 'storage', 'cp', str(ROOT / 'teardown_receipt.json'),
                                    f'{GCS}/{COHORT}/report/teardown_receipt.json'],
                                   check=True, capture_output=True, timeout=120)
                    log('DONE: report saved and cluster teardown verified')
                    return
            except Exception as error:
                # Do not print SDK/credential-bearing exception payloads.
                log('Check deferred after ' + type(error).__name__ + '; no unverified teardown')
            time.sleep(30)
        raise TimeoutError('24-hour watcher deadline reached; existing idle autodown remains configured')


if __name__ == '__main__':
    main()
