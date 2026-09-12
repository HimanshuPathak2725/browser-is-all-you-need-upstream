#!/usr/bin/env python3
"""Freeze and launch the old-task generalized + topic GRPO experiment."""
import argparse
from collections import Counter
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT))
import charm_grpo_hub as credentials
from Reward_GRPO import generalized_cpp_topic_grpo as reward


SOURCE_CHECKPOINT = 'generalized-cpp-kernel-grpo20-spot-20260829-083214-retry1/iter_0000014'
SOURCE_ADAPTER_SHA256 = 'b4bb3a250e28696c597d84db459caa75978e160996818dbfce22b8896b2c794b'
SOURCE_FILES = {
    'adapter_config.json': '0bd6d85f88fc42fefa52627b3c261f1ad58bb2c9519332ae8034dd5dffe2498e',
    'adapter_megatron_tp0_pp0.pt': 'c86de4b9aa5abcbf1aaf4a7e1fdd4500d20a79d4675536d543ca870bfa004d62',
    'adapter_megatron_tp1_pp0.pt': 'f250588892c220b9529e04271c7c7c5c7cdfe1a625b55c5c767ca67158a2b2ba',
    'adapter_megatron_tp2_pp0.pt': 'e487b196fd40ffbcff74c21924a3596bec249b0655fe0b9c82c6efd964c0650b',
    'adapter_megatron_tp3_pp0.pt': 'f1288a109358975b35d2492ed407a8fe1a674d3f004cb63a5cc8d0e165d31bd8',
    'adapter_model.bin': SOURCE_ADAPTER_SHA256,
}


def expected_control_catalog():
    """Derive the full current campaign, rather than pinning an obsolete count."""
    from Reward_GRPO.topic_coverage.controls import controls
    registry = reward.base._registry()
    train = reward.base._curriculum_task_ids(registry)
    validation = reward.base._validation_task_ids(registry)
    expected = Counter()
    for task in registry.task_ids():
        if registry.resolve(task).preflight_response or task in train + validation:
            expected[(task, 'reference', 'reference')] += 1
    for sample in reward.base._mutation_control_samples(registry):
        metadata = sample['metadata']
        expected[(metadata['problem_id'], 'generalized_control', metadata['mutation_case'])] += 1
    for task in reward.TOPICS:
        sources = reward.control_sources(registry.resolve(task), task)
        for control in controls(task, sources):
            if control.kind != 'diagnostic':
                expected[(task, 'topic_' + control.kind, control.name)] += 1
    for sample in reward.base._heldout_negative_samples(registry):
        expected[(sample['metadata']['problem_id'], 'heldout_negative', 'starter')] += 1
    return expected, train, validation


def validate_preflight(path):
    receipt = json.loads(path.read_text())
    expected, train, validation = expected_control_catalog()
    count, digest = sum(expected.values()), reward.contract_digest()
    if (receipt.get('status') != 'passed' or receipt.get('cases') != count
            or receipt.get('matched') != count or receipt.get('combined_reward_sha256') != digest
            or receipt.get('train') != train or receipt.get('validation') != validation
            or receipt.get('topic_tasks') != sorted(reward.TOPICS)):
        raise RuntimeError('a passing full control campaign for the current reward is required')
    observed = Counter()
    for case_file in sorted(path.parent.glob('case-*.json')):
        case = json.loads(case_file.read_text())
        result = case.get('result', {})
        if (case.get('matched') is not True or result.get('infrastructure_error')
                or result.get('combined_reward_sha256') != digest
                or result.get('sandbox_image_id') != receipt.get('sandbox_image_id')
                or result.get('problem_id') != case.get('task')):
            raise RuntimeError('preflight case does not bind a passing current-verifier result')
        observed[(case.get('task'), case.get('kind'), case.get('control'))] += 1
    if observed != expected:
        raise RuntimeError('preflight control catalog is incomplete or contains duplicate/unknown cases')
    if receipt.get('sandbox_image_id') != reward.image_identity():
        raise RuntimeError('preflight image does not match the current verifier image')
    return receipt


def validate_launch_config(path):
    config = yaml.safe_load(path.read_text())
    resources, env = config['resources'], config['envs']
    if (config.get('num_nodes') != 1 or not isinstance(resources, dict)
            or resources.get('infra') not in ('gcp', 'gcp/europe-west4')
            or resources.get('use_spot') is not True
            or resources.get('accelerators') not in ('H100:8', {'H100': 8})
            or resources.get('instance_type') != 'a3-highgpu-8g'
            or 'any_of' in resources or 'ordered' in resources):
        raise RuntimeError('this run requires exactly one Spot machine with eight H100 GPUs')
    if env.get('GLM47_CPP_SANDBOX_IMAGE') != reward.IMAGE:
        raise RuntimeError('launch must use the current validated verifier image')
    expected_source = '/workspace/runs/' + SOURCE_CHECKPOINT.replace(
        '/iter_0000014', '/checkpoints/grpo_lora_r16/iter_0000014/adapter')
    if (env.get('MILES_EXPECTED_SOURCE_ADAPTER_SHA256') != SOURCE_ADAPTER_SHA256
            or json.loads(env.get('MILES_EXPECTED_WARMSTART_FILES', '{}')) != SOURCE_FILES
            or 'source_adapter=' + expected_source not in config.get('setup', '')):
        raise RuntimeError('warm start must be the evaluated August 29 kernel iter14 checkpoint')
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launch', action='store_true')
    parser.add_argument('--preflight-receipt', type=Path, required=True)
    args = parser.parse_args()
    receipt = validate_preflight(args.preflight_receipt)
    launch_config = validate_launch_config(ROOT / 'Reward_GRPO/generalized_cpp_topic_grpo_skypilot.yaml')
    env = dict(os.environ)
    env.update(MILES_WANDB_EXPECTED_USER='himanshu2725pathak',
               WANDB_ENTITY='himanshu2725pathak-wootzapp',
               MILES_WANDB_PROJECT='glm47-generalized-cpp-grpo')
    env.setdefault('MILES_WANDB_ENV_FILE', '/data/Himanshu/browser-is-all-you-need-generalized-cpp-v2-launch/.env')
    env['WANDB_API_KEY'] = credentials.wandb_key(env)
    credentials.PROJECT = env['MILES_WANDB_PROJECT']
    identity = credentials.check_wandb(env)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    run_id = 'generalized-cpp-topics-v4-grpo20-' + stamp
    cluster = 'generalized-cpp-topics-v4-' + stamp
    snapshot = ROOT / '.glm47-posttraining/generalized-cpp-topics/launches' / run_id
    staged = reward.stage_launch(argparse.Namespace(out=snapshot, run_id=run_id))
    evidence = ROOT / 'results' / ('generalized-cpp-topics-' + stamp[:8]) / run_id
    evidence.mkdir(parents=True, exist_ok=False)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    command = ['sky', 'launch', '-y', '--retry-until-up', '--detach-run', '--gpus', 'H100:8',
               '--use-spot', '-c', cluster,
               '--workdir', str(snapshot), str(snapshot / 'Reward_GRPO/generalized_cpp_topic_grpo_skypilot.yaml'),
               '--env', 'MILES_RUN_ID=' + run_id, '--env', 'GLM47_SOURCE_COMMIT=' + commit,
               '--env', 'WANDB_ENTITY=' + env['WANDB_ENTITY'],
               '--env', 'MILES_WANDB_PROJECT=' + env['MILES_WANDB_PROJECT'],
               '--env', 'WANDB_TAGS=generalized-cpp,topics-v4,15train-4heldout,generalized-aug29-iter14,gcp,skypilot,spot,8xh100',
               '--secret', 'WANDB_API_KEY']
    record = dict(run_id=run_id, cluster=cluster, snapshot=staged, wandb=identity, source_commit=commit,
                  combined_reward_sha256=reward.contract_digest(), control_receipt=str(args.preflight_receipt.resolve()),
                  source_checkpoint=SOURCE_CHECKPOINT,
                  source_adapter_sha256=SOURCE_ADAPTER_SHA256,
                  reward_scoring_version=reward.SCORING_VERSION, full_preflight_cases=receipt['cases'],
                  preflight_receipt_sha256=hashlib.sha256(args.preflight_receipt.read_bytes()).hexdigest(),
                  strict_spot=True, accelerator='H100:8',
                  requested_infra=launch_config['resources']['infra'],
                  source_eval_selected_four_pass_at_1=11.75, effective_epochs=20*8/15,
                  prompts_per_update=8, training_samples_total=20*8*32, samples_per_update=8*32,
                  train_tasks=15, validation_tasks=4, updates=20, samples_per_prompt=32,
                  gpus='8 x H100 Spot', command=command, launch_requested=args.launch)
    reward.write_json(evidence / 'launch.json', record)
    print(json.dumps(record, indent=2), flush=True)
    if args.launch:
        result = subprocess.run(command, env=env, cwd=ROOT)
        reward.write_json(evidence / 'launch-result.json', dict(exit_code=result.returncode))
        return result.returncode
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except credentials.GateError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
