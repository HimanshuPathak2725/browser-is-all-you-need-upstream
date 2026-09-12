"""Regressions for the September 10 GRPO verifier abort and lost evidence."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import threading
import time
from types import SimpleNamespace

import pytest

from Reward_GRPO import generalized_cpp_topic_grpo as reward


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv('MILES_RUN_ROOT', str(tmp_path))
    monkeypatch.setenv('GENERALIZED_CPP_REWARD_WORKERS', '2')
    monkeypatch.delenv('GENERALIZED_CPP_FAILURE_DIR', raising=False)
    monkeypatch.setattr(reward, '_SCORING_POOL', None)
    yield
    if reward._SCORING_POOL is not None:
        reward._SCORING_POOL[2].shutdown(wait=True, cancel_futures=True)


def bad():
    return dict(problem_id='complex-numbers', sample_index=42, score=0., reward=0.,
                infrastructure_error=True, reason='verifier_invalid', policy_results=[
                    dict(policy_id='G02', status='invalid', reason='compiler unavailable',
                         stderr_tail='compiler diagnostic retained')])


def sample():
    return dict(metadata={'problem_id': 'complex-numbers'}, response='complete source text',
                index=42, rollout_id=7)


@pytest.mark.parametrize('mode', ['single', 'list', 'mixed', 'two_loops'])
@pytest.mark.parametrize('worker_count', [2, 24])
def test_worker_limit_is_shared_across_call_shapes(mode, worker_count, monkeypatch):
    monkeypatch.setenv('GENERALIZED_CPP_REWARD_WORKERS', str(worker_count))
    active = peak = 0
    lock = threading.Lock()
    def score(item):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(.015)
        with lock:
            active -= 1
        return dict(score=-.65, infrastructure_error=False)
    monkeypatch.setattr(reward, 'score_sample', score)
    async def run():
        calls = [] if mode == 'list' else [reward.reward_func(None, sample()) for _ in range(24)]
        if mode == 'list':
            calls = [reward.reward_func(None, [sample() for _ in range(24)])]
        if mode == 'mixed':
            calls.append(reward.reward_func(None, [sample() for _ in range(24)]))
        return await asyncio.gather(*calls)
    if mode == 'two_loops':
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: asyncio.run(run()), range(2)))
    else:
        asyncio.run(run())
    assert peak == worker_count and active == 0


def test_cancellation_keeps_physical_limit_and_failed_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv('GENERALIZED_CPP_REWARD_WORKERS', '1')
    started, release = threading.Event(), threading.Event()
    count = 0
    def score(item):
        nonlocal count
        count += 1
        if count == 1:
            started.set()
            assert release.wait(5)
            return bad()
        return dict(score=1., infrastructure_error=False)
    monkeypatch.setattr(reward, 'score_sample', score)
    async def run():
        first = asyncio.create_task(reward.reward_func(None, sample()))
        assert await asyncio.to_thread(started.wait, 3)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        second = asyncio.create_task(reward.reward_func(None, sample()))
        try:
            await asyncio.sleep(.05)
            assert count == 1
        finally:
            release.set()
        assert (await second)['score'] == 1.
    asyncio.run(run())
    files = list((tmp_path / 'reward_failures').glob('*.json'))
    assert len(files) == 1
    assert json.loads(files[0].read_text())['record']['reason'] == 'verifier_invalid'


def test_all_failed_attempts_are_preserved_and_no_reward_returned(tmp_path, monkeypatch):
    monkeypatch.setattr(reward, 'score_sample', lambda item: bad())
    with pytest.raises(reward.RewardInfrastructureError, match='no reward returned') as error:
        asyncio.run(reward.reward_func(None, sample()))
    files = sorted((tmp_path / 'reward_failures').glob('*.json'))
    assert len(files) == 3 and 'G02' in str(error.value)
    for number, path in enumerate(files, 1):
        data = json.loads(path.read_text())
        assert data['attempt'] == number
        assert data['sample'] == reward.sample_dict(sample())
        assert data['response_sha256'] == hashlib.sha256(sample()['response'].encode()).hexdigest()
        assert data['record']['policy_results'][0]['stderr_tail'] == 'compiler diagnostic retained'
        assert str(path) in str(error.value)
    assert not list((tmp_path / 'reward_failures').glob('*.tmp'))


def test_recovery_keeps_failed_attempt_receipts(tmp_path, monkeypatch):
    results = iter([bad(), bad(), dict(score=1., infrastructure_error=False)])
    monkeypatch.setattr(reward, 'score_sample', lambda item: next(results))
    record = asyncio.run(reward.reward_func(None, sample()))
    assert record['reward'] == 1 and record['infrastructure_attempts'] == 3
    assert len(record['infrastructure_failure_receipts']) == 2
    assert all(Path(p).is_file() for p in record['infrastructure_failure_receipts'])


def test_persistence_failure_never_fabricates_reward(monkeypatch):
    monkeypatch.setattr(reward, 'score_sample', lambda item: bad())
    def no_space(*args):
        raise OSError('disk full')
    monkeypatch.setattr(reward, '_save_failed_attempt', no_space)
    with pytest.raises(reward.RewardInfrastructureError, match='Cannot preserve'):
        asyncio.run(reward.reward_func(None, sample()))


def test_unexpected_scorer_exception_is_preserved(tmp_path, monkeypatch):
    def crash(item):
        raise RuntimeError('unexpected compiler bridge failure')
    monkeypatch.setattr(reward, 'score_sample', crash)
    with pytest.raises(reward.RewardInfrastructureError):
        asyncio.run(reward.reward_func(None, sample()))
    files = list((tmp_path / 'reward_failures').glob('*.json'))
    assert len(files) == 3
    assert 'unexpected compiler bridge failure' in json.loads(files[0].read_text())['record']['exception']


@pytest.mark.parametrize('mode', ['nonzero', 'timeout', 'cleanup'])
def test_worker_errors_keep_diagnostics(mode, monkeypatch):
    monkeypatch.setattr(reward, 'contract_digest', lambda: 'test')
    monkeypatch.setattr(reward, 'docker_command', lambda name: ['docker', 'run'])
    monkeypatch.setattr(reward, 'image_identity', lambda: 'sha256:test')
    def run(command, **kwargs):
        if command[:2] == ['docker', 'rm']:
            if mode == 'cleanup':
                raise OSError('docker cleanup unavailable')
            return SimpleNamespace(returncode=1, stderr='No such container', stdout='')
        if mode == 'timeout':
            raise subprocess.TimeoutExpired(command, 900, stderr=b'last diagnostic')
        result = dict(problem_id='complex-numbers', reward_contract=reward.CURRICULUM,
                      score=1., infrastructure_error=False)
        return SimpleNamespace(returncode=137 if mode == 'nonzero' else 0,
                               stderr='worker diagnostic', stdout=json.dumps(result))
    monkeypatch.setattr(reward.subprocess, 'run', run)
    item = sample()
    item['metadata']['combined_reward_sha256'] = 'test'
    result = reward.score_sample(item)
    assert result['infrastructure_error']
    if mode == 'timeout':
        assert result['worker']['timed_out'] and result['worker']['stderr_tail'] == 'last diagnostic'
    elif mode == 'nonzero':
        assert result['worker']['returncode'] == 137
        assert result['worker']['stderr_tail'] == 'worker diagnostic'
    else:
        assert 'cleanup unavailable' in result['worker']['cleanup_error']


@pytest.fixture
def engine():
    path = reward.ROOT / 'generalized_verifier_docs/03_two_stage_build_verifier.py'
    spec = importlib.util.spec_from_file_location('build_reliability', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tiny_build(tmp_path):
    root = tmp_path / 'fixture'
    (root / 'test').mkdir(parents=True)
    (root / 'tiny_test.cpp').write_text('#include "tiny.h"\nint run_tests(){return value()==7?0:1;}\n')
    (root / 'test/tests-main.cpp').write_text('int run_tests(); int main(){return run_tests();}\n')
    (root / 'tiny.h').write_text('#pragma once\nint value();\n')
    (root / 'tiny.cpp').write_text('#include "tiny.h"\nint value(){return 7;}\n')
    return root


@pytest.mark.parametrize('kind', ['separate', 'inline', 'duplicate', 'missing'])
def test_real_multitu_link_classification(engine, tiny_build, kind):
    root = tiny_build
    if kind in {'inline', 'duplicate'}:
        (root / 'tiny.h').write_text('#pragma once\n' + ('inline ' if kind == 'inline' else '') +
                                    'int value(){return 7;}\n')
        (root / 'tiny.cpp').write_text('#include "tiny.h"\n')
    elif kind == 'missing':
        (root / 'tiny.cpp').write_text('#include "tiny.h"\n')
    result = engine.build_candidate(str(root), str(root / 'tiny.h'), str(root / 'tiny.cpp'))
    try:
        if kind in {'separate', 'inline'}:
            assert result.status == 'PASS'
            assert subprocess.run([result.binary], check=False).returncode == 0
        else:
            assert result.status == 'LE'
            assert result.failure_kind == ('duplicate_definition' if kind == 'duplicate' else 'undefined_reference')
            if kind == 'duplicate':
                assert 'inline' in result.feedback and 'Missing definitions' not in result.feedback
            else:
                assert 'namespace and signature' in result.feedback
    finally:
        if result.workspace:
            shutil.rmtree(result.workspace)


@pytest.mark.parametrize('kind', ['missing_compiler', 'timeout', 'signal', 'tool_error', 'unknown_link'])
def test_toolchain_failures_remain_infrastructure(engine, tiny_build, monkeypatch, kind):
    real_run = engine.subprocess.run
    def run(command, **kwargs):
        if kind == 'missing_compiler':
            raise FileNotFoundError('compiler absent')
        if kind == 'timeout':
            raise subprocess.TimeoutExpired(command, 300, stderr=b'compile diagnostic')
        if kind == 'signal':
            return SimpleNamespace(returncode=-9, stderr='')
        if kind == 'tool_error':
            return SimpleNamespace(returncode=1, stderr='g++: fatal error: Killed signal terminated program cc1plus')
        if '-pthread' in command:
            return SimpleNamespace(returncode=1, stderr='/usr/bin/ld: unknown tool failure')
        return real_run(command, **kwargs)
    monkeypatch.setattr(engine.subprocess, 'run', run)
    result = engine.build_candidate(str(tiny_build), str(tiny_build/'tiny.h'), str(tiny_build/'tiny.cpp'))
    try:
        assert result.status == 'ERROR'
        assert result.failure_kind in {'compiler_unavailable', 'compiler_timeout', 'toolchain_failure', 'unclassified_link_failure'}
        if kind == 'timeout':
            assert result.stderr == 'compile diagnostic'
    finally:
        if result.workspace:
            shutil.rmtree(result.workspace)


def test_g03_never_hides_candidate_tool_failure(tiny_build, monkeypatch):
    pack = reward.ROOT / 'Reward_GRPO/Generalized Cpp Verifiers/verifiers'
    spec = importlib.util.spec_from_file_location('g03_reliability', pack/'verifier_03_differential_semantic.py')
    wrapper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wrapper)
    (tiny_build/'.meta').mkdir()
    (tiny_build/'.meta/example.h').write_text('int value();')
    report = {'reference': {'status': 'OK'}, 'candidate': {'status': 'BUILD_FAIL',
              'build': {'status': 'ERROR', 'feedback': 'compiler unavailable',
                        'stderr_tail': 'lost compiler process'}}}
    monkeypatch.setattr(wrapper.common, 'run_engine', lambda *args, **kwargs: dict(
        return_code=1, stdout=json.dumps(report), stderr='', command=['engine'], duration_seconds=.1))
    kernels, status, reason = wrapper.run_checks(SimpleNamespace(candidate_dir=str(tiny_build)),
        {'fixture_dir': str(tiny_build), 'candidate_files': ['tiny.h', 'tiny.cpp']})
    assert status == 'invalid' and kernels[-1]['status'] == 'invalid'
    assert kernels[-1]['facts']['candidate']['build']['stderr_tail'] == 'lost compiler process'
