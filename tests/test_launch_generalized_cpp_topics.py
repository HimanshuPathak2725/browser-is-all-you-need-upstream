"""Launch admission tests: no credentials, cloud requests or training execution."""
from collections import Counter
from pathlib import Path
import copy
import importlib.util
import json
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('topic_launcher', ROOT / 'scripts/launch_generalized_cpp_topics.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    expected = Counter({('task', 'reference', 'reference'): 1,
                        ('task', 'topic_semantic', 'fault'): 1})
    monkeypatch.setattr(launcher, 'expected_control_catalog', lambda: (expected, ['task'], ['heldout']))
    monkeypatch.setattr(launcher.reward, 'contract_digest', lambda: 'current-digest')
    monkeypatch.setattr(launcher.reward, 'image_identity', lambda: 'sha256:current')
    monkeypatch.setattr(launcher.reward, 'TOPICS', {'task': None})
    receipt = dict(status='passed', cases=2, matched=2, combined_reward_sha256='current-digest',
                   train=['task'], validation=['heldout'], topic_tasks=['task'], sandbox_image_id='sha256:current')
    path = tmp_path / 'preflight.json'
    path.write_text(json.dumps(receipt))
    for index, (task, kind, control) in enumerate(expected):
        case = dict(task=task, kind=kind, control=control, matched=True, result=dict(
            problem_id=task, infrastructure_error=False, combined_reward_sha256='current-digest',
            sandbox_image_id='sha256:current'))
        (tmp_path / f'case-{index:03d}.json').write_text(json.dumps(case))
    return path


def test_complete_current_catalog_is_accepted(campaign):
    assert launcher.validate_preflight(campaign)['cases'] == 2


@pytest.mark.parametrize('corruption', ['old_count', 'old_hash', 'missing_case', 'duplicate_case',
                                        'failed_case', 'wrong_case_image', 'wrong_case_task', 'wrong_split'])
def test_incomplete_stale_or_mixed_campaign_is_rejected(campaign, corruption):
    receipt = json.loads(campaign.read_text())
    case_path = campaign.parent / 'case-001.json'
    case = json.loads(case_path.read_text())
    if corruption == 'old_count': receipt.update(cases=147, matched=147)
    elif corruption == 'old_hash': receipt['combined_reward_sha256'] = 'old-digest'
    elif corruption == 'wrong_split': receipt['train'] = ['phone-number']
    elif corruption == 'missing_case': case_path.unlink()
    elif corruption == 'duplicate_case': case = json.loads((campaign.parent / 'case-000.json').read_text())
    elif corruption == 'failed_case': case['matched'] = False
    elif corruption == 'wrong_case_image': case['result']['sandbox_image_id'] = 'sha256:old'
    elif corruption == 'wrong_case_task': case['result']['problem_id'] = 'other-task'
    campaign.write_text(json.dumps(receipt))
    if corruption != 'missing_case': case_path.write_text(json.dumps(case))
    with pytest.raises(RuntimeError): launcher.validate_preflight(campaign)


def test_current_exact_checkpoint_and_spot_h100_config_is_accepted():
    config = launcher.validate_launch_config(ROOT / 'Reward_GRPO/generalized_cpp_topic_grpo_skypilot.yaml')
    assert config['resources']['use_spot'] is True
    assert config['envs']['MILES_EXPECTED_SOURCE_ADAPTER_SHA256'] == launcher.SOURCE_ADAPTER_SHA256


@pytest.mark.parametrize('change', ['on_demand', 'other_gpu', 'other_instance', 'other_checkpoint', 'other_native_shard', 'other_source_path', 'wrong_reward_image'])
def test_checkpoint_or_hardware_fallback_is_rejected(tmp_path, change):
    config = yaml.safe_load((ROOT / 'Reward_GRPO/generalized_cpp_topic_grpo_skypilot.yaml').read_text())
    if change == 'on_demand': config['resources']['use_spot'] = False
    elif change == 'other_gpu': config['resources']['accelerators'] = 'A100:8'
    elif change == 'other_instance': config['resources']['instance_type'] = 'a2-highgpu-8g'
    elif change == 'other_checkpoint': config['envs']['MILES_EXPECTED_SOURCE_ADAPTER_SHA256'] = 'other'
    elif change == 'wrong_reward_image': config['envs']['GLM47_CPP_SANDBOX_IMAGE'] = 'glm47-generalized-cpp-topics:v3'
    elif change == 'other_native_shard':
        files = copy.deepcopy(launcher.SOURCE_FILES)
        files['adapter_megatron_tp0_pp0.pt'] = 'other'
        config['envs']['MILES_EXPECTED_WARMSTART_FILES'] = json.dumps(files)
    else: config['setup'] = config['setup'].replace('/iter_0000014/adapter', '/iter_0000019/adapter')
    path = tmp_path / 'config.yaml'
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(RuntimeError): launcher.validate_launch_config(path)
