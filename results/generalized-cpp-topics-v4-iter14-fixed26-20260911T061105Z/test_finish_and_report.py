import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('finish_report', ROOT / 'finish_and_report.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    original = json.loads((ROOT.parent / 'generalized-cpp-v2-iter14-fixed26-4trials-20260905/trials/t01/run_receipt.json').read_text())
    marker = {'status': 'complete', 'cohort_id': module.COHORT, 'sequential_trials': []}
    payloads = []
    for i, p1 in enumerate([2, 4, 6, 8], 1):
        r = copy.deepcopy(original)
        r.update(run_id=f'{module.COHORT}-t{i:02d}', source_run_id=module.SOURCE_RUN,
                 source_checkpoint='iter_0000014', adapter_sha256=module.ADAPTER_SHA256)
        tasks = sorted(r['validation']['testcases'])
        r['validation'].update(pass_at_1=p1, pass_at_k=p1+2,
            outcomes={t: [True] if j < p1 else [False, j < p1+2] for j,t in enumerate(tasks)})
        payload = json.dumps(r).encode()
        payloads.append(payload)
        marker['sequential_trials'].append({'trial':i, 'run_id':r['run_id'],
            'receipt_sha256':hashlib.sha256(payload).hexdigest(), 'pass_at_1':p1,
            'multiturn_feedback':p1+2})
    return marker, payloads


class ReportTests(unittest.TestCase):
    def test_means_and_medians(self):
        marker,payloads=fixture()
        metrics=module.aggregate(module.validate_cohort(marker,payloads))
        self.assertEqual(metrics['pass_at_1']['mean'],5)
        self.assertEqual(metrics['pass_at_1']['median'],5)
        self.assertEqual(metrics['pass_at_k']['mean'],7)
        self.assertAlmostEqual(metrics['pass_at_1']['mean_percent'],500/26)

    def test_partial_cohort_rejected(self):
        marker,payloads=fixture()
        with self.assertRaises(ValueError): module.validate_cohort(marker,payloads[:3])

    def test_hash_mismatch_rejected(self):
        marker,payloads=fixture()
        payloads[0]+=b' '
        with self.assertRaises(ValueError): module.validate_cohort(marker,payloads)

    def test_different_checkpoint_rejected(self):
        marker,payloads=fixture()
        r=json.loads(payloads[0]); r['source_checkpoint']='iter_0000044'
        payloads[0]=json.dumps(r).encode()
        with self.assertRaises(AssertionError): module.validate_cohort(marker,payloads)

    def test_report_and_audits_generated(self):
        marker,payloads=fixture()
        with tempfile.TemporaryDirectory(prefix='generalized-topics-report-test-') as tmp:
            with patch.object(module,'ROOT',Path(tmp)):
                artifacts=module.build_report(marker,payloads)
            self.assertEqual(len(artifacts),14)
            self.assertTrue(all(p.is_file() for p in artifacts))
            self.assertIn('| Mean | 5.00/26 | 7.00/26 |',(Path(tmp)/'RESULTS.md').read_text())
            self.assertEqual(json.loads((Path(tmp)/'results.json').read_text())['trial_count'],4)

    def test_failed_report_upload_prevents_success(self):
        with tempfile.TemporaryDirectory(prefix='generalized-topics-report-test-') as tmp:
            p=Path(tmp)/'result.json'; p.write_text('{}')
            with patch.object(module,'ROOT',Path(tmp)), patch.object(module.subprocess,'run'), patch.object(module,'fetch',return_value=b'wrong'):
                with self.assertRaises(ValueError): module.publish_report([p])

    def test_teardown_waits_for_job_completion(self):
        import sky
        from sky.skylet.job_lib import JobStatus
        with patch.object(sky,'status',return_value='status'), patch.object(sky,'queue',return_value='queue'), patch.object(sky,'get',side_effect=[[{'name':module.CLUSTER}],[{'job_id':1,'status':JobStatus.RUNNING}]]), patch.object(sky,'down') as down:
            self.assertIsNone(module.teardown_when_idle())
            down.assert_not_called()

    def test_teardown_targets_only_expected_cluster(self):
        import sky
        from sky.skylet.job_lib import JobStatus
        with patch.object(sky,'status',return_value='status'), patch.object(sky,'queue',return_value='queue'), patch.object(sky,'get',side_effect=[[{'name':module.CLUSTER}],[{'job_id':1,'status':JobStatus.SUCCEEDED}],None,[]]), patch.object(sky,'down',return_value='down') as down:
            self.assertEqual(module.teardown_when_idle(),'removed')
            down.assert_called_once_with(module.CLUSTER)


if __name__ == '__main__':
    unittest.main()
