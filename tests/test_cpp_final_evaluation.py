"""Deterministic evaluation accounting, binding and whole-file prompt regressions."""
import copy
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

from scripts import evaluate_cpp_grpo_final as evaluation


def successful_record():
    run = dict(verified_pass=True, execution_completed=True, harness_returncode=0, returncode=0)
    facts = {'reference': {'status': 'OK'}, 'candidate': {'status': 'RAN', 'run': run}}
    return {'score': 1.0, 'infrastructure_error': False, 'topic_required': False,
            'verifier_receipt': {'status': 'pass', 'policy_results': [
                {'policy_id': 'G03', 'status': 'pass', 'kernels': [
                    {'kernel_id': 'G03-2', 'status': 'pass', 'facts': facts}]}]}}


def test_authentication_precedes_rounded_reward():
    result = successful_record()
    assert evaluation.classify(result) == ('PASS', None)
    run = result['verifier_receipt']['policy_results'][0]['kernels'][0]['facts']['candidate']['run']
    run.update(verified_pass=False, execution_completed=False, returncode=1, score=1.0)
    assert evaluation.classify(result) == ('INVALID', 'inconsistent_verifier_receipt')
    result['verifier_receipt']['status'] = 'fail'
    result['verifier_receipt']['policy_results'][0]['kernels'][0]['status'] = 'fail'
    assert evaluation.classify(result) == ('FAIL', 'semantic')


@pytest.mark.parametrize('status,expected', [('CE-1', 'compile'), ('CE-2', 'compile'), ('LE', 'link')])
def test_candidate_build_failures_are_not_invalid(status, expected):
    result = successful_record()
    result['verifier_receipt']['status'] = 'fail'
    facts = result['verifier_receipt']['policy_results'][0]['kernels'][0]['facts']
    facts['candidate'] = {'status': 'BUILD_FAIL', 'build': {'status': status}}
    assert evaluation.classify(result) == ('FAIL', expected)
    result['infrastructure_error'] = True
    assert evaluation.classify(result) == ('INVALID', 'infrastructure')


def test_topic_completion_required_and_runtime_distinguished():
    result = successful_record()
    result['topic_required'] = True
    assert evaluation.classify(result)[0] == 'INVALID'
    result['topic_coverage'] = {'status': 'fail', 'reference_status': 'pass', 'candidate': {'groups': [{'runs': [{'reason': 'runtime_timeout'}]}]}}
    assert evaluation.classify(result) == ('FAIL', 'runtime')
    result['topic_coverage'] = {'status': 'pass', 'reference_status': 'pass'}
    assert evaluation.classify(result) == ('PASS', None)


def grid():
    rows = [{'problem_id': 'train-task', 'evaluation_split': 'development'},
            {'problem_id': 'held-task', 'evaluation_split': 'held_out'}]
    records = [dict(problem_id=task, trial=i, verdict=status, failure_kind=kind)
               for task, values in [('train-task', [('PASS', None), ('FAIL', 'semantic'), ('INVALID', 'infrastructure')]),
                                    ('held-task', [('FAIL', 'compile'), ('FAIL', 'runtime'), ('INVALID', 'infrastructure')])]
               for i, (status, kind) in enumerate(values, 1)]
    return rows, records


def test_invalid_is_separate_and_splits_never_pooled():
    rows, records = grid()
    result = evaluation.aggregate(records, rows, 3)
    development = result['splits']['development']
    held = result['splits']['held_out']
    assert development['pass_at_1'] == {'passes': 1, 'valid_trials': 2}
    assert development['invalid_trials'] == 1
    assert development['direct_pass_at_k']['passed_tasks'] == 1
    assert held['direct_pass_at_k']['unknown_tasks'] == 1
    assert held['direct_pass_at_k']['known_tasks'] == 0
    assert held['failure_breakdown'] == {'compile': 1, 'runtime': 1, 'infrastructure': 1}
    assert held['trial_pass_at_1'][2]['valid_trials'] == 0
    with pytest.raises(ValueError, match='trial grid'):
        evaluation.aggregate(records[:-1], rows, 3)
    with pytest.raises(ValueError, match='trial grid'):
        evaluation.aggregate(records + records[:1], rows, 3)


def dataset(tmp_path):
    manifest = {'cohort_version': evaluation.COHORT_VERSION, 'cohort_sha256': 'cohort',
                'combined_reward_sha256': 'reward', 'train_tasks': ['train-task'],
                'validation_tasks': ['held-task'], 'task_identities': {}, 'file_sha256s': {}}
    prompt = [{'role': 'system', 'content': 'Write complete files.'},
              {'role': 'user', 'content': 'Implement task.h and task.cpp.'}]
    for task, relative in [('train-task', 'grpo/train.jsonl'), ('held-task', 'eval/validation.jsonl')]:
        manifest['task_identities'][task] = {'manifest_sha256': task}
        metadata = {key: manifest[key] for key in ('cohort_version', 'cohort_sha256', 'combined_reward_sha256')}
        metadata.update(problem_id=task, generalized_verifier_manifest_sha256=task)
        path = tmp_path / relative
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'problem_id': task, 'prompt': prompt, 'metadata': metadata}) + '\n')
        manifest['file_sha256s'][relative] = evaluation.digest(path)
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    return prompt


def test_dataset_binds_prompts_and_exact_task_membership(tmp_path):
    prompt = dataset(tmp_path)
    manifest, rows = evaluation.load_dataset(tmp_path)
    assert evaluation.messages(rows[0]) == prompt
    assert rows[0]['prompt_sha256'] == evaluation.canonical_hash(prompt)
    path = tmp_path / 'grpo/train.jsonl'
    path.write_text(path.read_text().replace('Implement', 'Changed'))
    with pytest.raises(ValueError, match='file hash mismatch'):
        evaluation.load_dataset(tmp_path)
    with pytest.raises(ValueError, match='chat-message'):
        evaluation.messages({'prompt': str(prompt)})


def test_replay_requires_complete_hash_bound_outputs(tmp_path):
    dataset(tmp_path)
    _, rows = evaluation.load_dataset(tmp_path)
    generations = [dict(problem_id=row['problem_id'], trial=trial,
                        prompt_sha256=row['prompt_sha256'], response='source files',
                        response_sha256=evaluation.canonical_hash('source files'))
                   for row in rows for trial in range(1, 4)]
    evaluation.validate_generations(generations, rows, 3)
    changed = copy.deepcopy(generations)
    changed[0]['response'] = 'different output'
    with pytest.raises(ValueError, match='hash mismatch'):
        evaluation.validate_generations(changed, rows, 3)
    with pytest.raises(ValueError, match='incomplete'):
        evaluation.validate_generations(generations[:-1], rows, 3)


def test_seeds_stable_independent_of_iteration_order():
    assert evaluation.trial_seed(10, 'sublist', 1) == evaluation.trial_seed(10, 'sublist', 1)
    assert len({evaluation.trial_seed(10, task, trial) for task in ('sublist', 'clock') for trial in range(1, 4)}) == 6


@pytest.mark.parametrize('mode', ['valid', 'unsupported_module', 'load_failure'])
def test_generation_uses_original_messages_pinned_revision_and_request_seeds(monkeypatch, tmp_path, mode):
    captured = {'calls': [], 'messages': []}
    bridge = ModuleType('glm47_posttraining.integrations.miles_glm47_bridge')
    bridge.register_glm47_bridge = lambda: captured.update(bridge=True)
    monkeypatch.setitem(sys.modules, bridge.__name__, bridge)
    sglang = ModuleType('sglang')
    class Engine:
        def __init__(self, **kwargs): captured['engine'] = kwargs
        def load_lora_adapter(self, name, path):
            captured['adapter'] = (name, path)
            return SimpleNamespace(success=mode != 'load_failure', error_message='load rejected')
        def generate(self, prompt, sampling, **kwargs):
            captured['calls'].append((prompt, sampling, kwargs))
            return {'text': 'task.cpp\n```cpp\ncode\n```'}
        def shutdown(self): captured['shutdown'] = True
    sglang.Engine = Engine
    monkeypatch.setitem(sys.modules, 'sglang', sglang)
    sampling = ModuleType('sglang.srt.sampling.sampling_params')
    class SamplingParams:
        def __init__(self, sampling_seed=None, stop_token_ids=None, skip_special_tokens=True): pass
    sampling.SamplingParams = SamplingParams
    common = ModuleType('sglang.srt.utils.common')
    common.SUPPORTED_LORA_TARGET_MODULES = ['q_a_proj', 'kv_a_proj_with_mqa', 'o_proj', 'gate_proj', 'up_proj', 'down_proj']
    if mode == 'unsupported_module':
        common.SUPPORTED_LORA_TARGET_MODULES.remove('q_a_proj')
    monkeypatch.setitem(sys.modules, common.__name__, common)
    monkeypatch.setitem(sys.modules, sampling.__name__, sampling)
    transformers = ModuleType('transformers')
    class Tokenizer:
        @classmethod
        def from_pretrained(cls, model, **kwargs):
            captured['tokenizer'] = (model, kwargs)
            return cls()
        def apply_chat_template(self, prompt, **kwargs):
            captured['messages'].append(prompt)
            captured['chat_kwargs'] = kwargs
            return 'rendered whole-file messages'
    transformers.AutoTokenizer = Tokenizer
    monkeypatch.setitem(sys.modules, 'transformers', transformers)
    helpers = ModuleType('scripts.evaluate')
    helpers.sglang_engine_kwargs = lambda value: value
    helpers.output_text = lambda value: value['text']
    helpers.output_finish_reason = lambda value: 'stop'
    helpers.output_token_count = lambda value, kind: 10
    helpers.output_is_truncated = lambda value, maximum: False
    monkeypatch.setitem(sys.modules, helpers.__name__, helpers)
    modules = ['q_a_proj', 'kv_a_proj_with_mqa', 'o_proj', 'gate_proj', 'up_proj', 'down_proj']
    (tmp_path/'adapter_config.json').write_text(json.dumps({'peft_type': 'LORA', 'r': 16, 'target_modules': modules, 'lora_alpha': 32}))
    args = SimpleNamespace(model='org/model', model_revision='a'*40, adapter=str(tmp_path), tp_size=4,
                           mem_fraction_static=.7, seed=10, trials=3, max_tokens=8192, temperature=.7)
    prompt = [{'role': 'system', 'content': 'whole files'}, {'role': 'user', 'content': 'task'}]
    rows = [{'problem_id': 'sublist', 'prompt': prompt, 'prompt_sha256': evaluation.canonical_hash(prompt)}]
    if mode != 'valid':
        message = 'target modules' if mode == 'unsupported_module' else 'adapter loading'
        with pytest.raises(RuntimeError, match=message):
            list(evaluation.generate(args, rows))
        assert not captured['calls']
        return
    outputs = list(evaluation.generate(args, rows))
    assert captured['bridge'] and captured['shutdown']
    assert captured['messages'] == [prompt]
    assert captured['engine']['revision'] == 'a'*40
    assert captured['engine']['lora_target_modules'] == modules
    assert captured['engine']['max_lora_rank'] == 16
    assert captured['chat_kwargs']['enable_thinking'] is True
    assert captured['engine']['experts_shared_outer_loras']
    assert captured['engine']['lora_use_virtual_experts']
    assert captured['tokenizer'][1]['revision'] == 'a'*40
    assert [item['sampling_seed'] for item in outputs] == [call[1]['sampling_seed'] for call in captured['calls']]
    assert len(outputs) == 3 and all(call[1]['max_new_tokens'] == 8192 for call in captured['calls'])
    assert all(call[1]['stop_token_ids'] == [154820, 154827, 154829] for call in captured['calls'])
    assert all(call[1]['skip_special_tokens'] is True for call in captured['calls'])


@pytest.mark.parametrize('filename', ['adapter_model.bin', 'adapter_model.safetensors'])
def test_native_adapter_formats_are_hashed(tmp_path, filename):
    (tmp_path / 'adapter_config.json').write_text('{}')
    (tmp_path / filename).write_bytes(b'fixed adapter bytes')
    assert set(evaluation.adapter_identity(tmp_path)) == {'adapter_config.json', filename}
    other = 'adapter_model.bin' if filename.endswith('safetensors') else 'adapter_model.safetensors'
    (tmp_path / other).write_bytes(b'ambiguous other weights')
    with pytest.raises(ValueError, match='exactly one'):
        evaluation.adapter_identity(tmp_path)


def test_mounted_model_must_match_pinned_source_catalog(tmp_path):
    model = tmp_path / 'model'
    model.mkdir()
    (model / 'config.json').write_text('{}')
    (model / 'model.safetensors').write_bytes(b'fixed model bytes')
    catalog = tmp_path / 'model-files.json'
    data = {'model': 'org/model', 'revision': 'a'*40, 'source': 'gs://pinned/source',
            'authentication': 'huggingface-pinned-revision', 'hf_revision': 'a'*40,
            'files': {p.name: evaluation.digest(p) for p in model.iterdir()}}
    catalog.write_text(json.dumps(data))
    args = SimpleNamespace(model='org/model', model_revision='a'*40,
                           model_path=model, model_file_manifest=catalog)
    resolved, identity = evaluation.resolve_model(args)
    assert resolved == str(model) and identity['files'] == data['files']
    (model / 'model.safetensors').write_bytes(b'changed weights')
    with pytest.raises(ValueError, match='hash mismatch'):
        evaluation.resolve_model(args)


def test_generation_reports_missing_runtime_without_install(monkeypatch):
    bridge = ModuleType('glm47_posttraining.integrations.miles_glm47_bridge')
    bridge.register_glm47_bridge = lambda: None
    monkeypatch.setitem(sys.modules, bridge.__name__, bridge)
    monkeypatch.setitem(sys.modules, 'sglang', None)
    with pytest.raises(RuntimeError, match='nothing was installed'):
        list(evaluation.generate(SimpleNamespace(), []))


def test_existing_output_directory_is_never_overwritten(tmp_path):
    marker = tmp_path / 'historical.json'
    marker.write_text('preserve')
    argv = ['--data-dir', str(tmp_path/'dataset'), '--dataset-repo', 'org/data',
            '--dataset-revision', 'a'*40, '--model', 'org/model', '--model-revision', 'b'*40,
            '--checkpoint-id', 'checkpoint', '--label', 'test', '--output-dir', str(tmp_path)]
    with pytest.raises(ValueError, match='never overwritten'):
        evaluation.main(argv)
    assert marker.read_text() == 'preserve'


def test_replay_cli_preserves_source_and_separates_invalid(tmp_path, monkeypatch):
    from Reward_GRPO import generalized_cpp_topic_grpo as reward
    data = tmp_path / 'data'
    data.mkdir()
    dataset(data)
    _, rows = evaluation.load_dataset(data)
    source = tmp_path / 'source'
    source.mkdir()
    generations = [dict(problem_id=row['problem_id'], trial=trial,
                        prompt_sha256=row['prompt_sha256'], response='source files',
                        response_sha256=evaluation.canonical_hash('source files'))
                   for row in rows for trial in range(1, 4)]
    generated = source / 'generated.jsonl'
    generated.write_text(''.join(json.dumps(row) + '\n' for row in generations))
    before = evaluation.digest(generated)
    (source / 'identity.json').write_text(json.dumps({
        'model': 'org/model', 'model_revision': 'b'*40, 'checkpoint_id': 'checkpoint',
        'dataset_manifest_sha256': evaluation.digest(data/'manifest.json'),
        'adapter_files': None, 'generation': {'seed': 10, 'trials': 3},
    }))
    hub = ModuleType('huggingface_hub')
    hub.hf_hub_download = lambda *args, **kwargs: str(data/'manifest.json')
    monkeypatch.setitem(sys.modules, 'huggingface_hub', hub)
    monkeypatch.setattr(reward, 'contract_digest', lambda: 'reward')
    monkeypatch.setattr(reward, 'image_identity', lambda: 'sha256:image')
    def score(sample):
        if sample['index'] == 0:
            return {'infrastructure_error': True}
        return successful_record()
    monkeypatch.setattr(reward, 'score_sample', score)
    output = tmp_path / 'replay'
    exit_code = evaluation.main([
        '--data-dir', str(data), '--dataset-repo', 'org/data', '--dataset-revision', 'a'*40,
        '--model', 'org/model', '--model-revision', 'b'*40, '--checkpoint-id', 'checkpoint',
        '--label', 'rescore', '--generated', str(generated), '--output-dir', str(output),
    ])
    summary = json.loads((output/'summary.json').read_text())
    assert exit_code == 2 and summary['mode'] == 'archived_output_replay'
    assert sum(part['invalid_trials'] for part in summary['splits'].values()) == 1
    assert summary['identity']['generation'] == {'seed': 10, 'trials': 3}
    assert evaluation.digest(generated) == before
    assert len(evaluation.read_jsonl(output/'records.jsonl')) == 6
    assert (output/'evidence-sha256.json').is_file()
    assert not (output/'incomplete.json').exists()


@pytest.mark.parametrize('config', [
    {'peft_type': 'LORA', 'r': 16, 'target_modules': 'all-linear'},
    {'peft_type': 'LORA', 'r': 16, 'target_modules': ['q_a_proj', 'q_a_proj']},
    {'peft_type': 'LORA', 'r': 0, 'target_modules': ['q_a_proj']},
    {'peft_type': 'LORA', 'r': 16, 'target_modules': ['q_a_proj'], 'use_dora': True},
])
def test_unsupported_adapter_settings_fail_without_silent_module_loss(tmp_path, config):
    (tmp_path/'adapter_config.json').write_text(json.dumps(config))
    with pytest.raises(ValueError, match='adapter'):
        evaluation.adapter_settings(tmp_path)


def test_parallel_scoring_is_bounded_and_results_stay_ordered(tmp_path):
    import threading
    import time
    lock = threading.Lock()
    active = peak = 0
    def score(sample):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(active, peak)
        time.sleep(.02 if sample['index'] % 2 == 0 else .005)
        with lock:
            active -= 1
        if sample['index'] == 2:
            raise RuntimeError('worker unavailable')
        return successful_record()
    rows = [{'problem_id': 'task', 'metadata': {'problem_id': 'task'}}]
    generated = [{'problem_id': 'task', 'trial': trial, 'response': 'cpp',
                  'response_sha256': evaluation.canonical_hash('cpp')} for trial in range(1, 7)]
    args = SimpleNamespace(output_dir=tmp_path, label='parallel', score_workers=2)
    records = evaluation.score_generations(args, generated, rows, SimpleNamespace(score_sample=score))
    assert peak == 2 and active == 0
    assert [record['trial'] for record in records] == list(range(1, 7))
    assert records[2]['verdict'] == 'INVALID'
    assert len(list((tmp_path/'receipts').glob('*.json'))) == 6
    assert evaluation.read_jsonl(tmp_path/'records.jsonl') == records
