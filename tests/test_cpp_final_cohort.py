"""Version binding and split admission regressions for the final GRPO cohort."""
import copy
import json
from types import SimpleNamespace

import pytest
from Reward_GRPO import generalized_cpp_cohort as cohort
from Reward_GRPO import generalized_cpp_grpo as reward


@pytest.mark.parametrize('defect', ['overlap', 'missing_identity', 'registry', 'verifier', 'fixture'])
def test_frozen_cohort_rejects_drift(tmp_path, defect):
    data = json.loads(cohort.DEFAULT_COHORT.read_text())
    if defect == 'overlap':
        data['validation'].append(data['train'][0])
    elif defect == 'missing_identity':
        del data['tasks'][data['train'][0]]
    elif defect == 'registry':
        data['registry_sha256'] = '0' * 64
    elif defect == 'verifier':
        data['verifier_files'] = {}
    else:
        data['tasks'][data['train'][0]]['manifest_sha256'] = '0' * 64
    path = tmp_path/'cohort.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='cohort'):
        cohort.load_cohort(path)


def test_export_selection_preserves_original_admission():
    registry = reward._registry()
    original = copy.deepcopy(registry.payload)
    data = cohort.load_cohort(registry=registry)
    view = cohort.selected_registry(data, registry)
    assert reward._curriculum_task_ids(view) == sorted(data['train'])
    assert reward._validation_task_ids(view) == sorted(data['validation'])
    assert not set(data['held']) & set(reward._curriculum_task_ids(view))
    assert registry.payload == original


def test_worker_rejects_held_task_before_candidate_execution():
    from Reward_GRPO.generalized_cpp_topic_grpo import worker_score
    record = worker_score({'metadata': {'problem_id': 'dnd-character'}, 'response': ''})
    assert record['infrastructure_error'] is True
    assert record['reason'] == 'task_not_admitted'
    assert record['score'] == 0 and record['reward'] == 0
