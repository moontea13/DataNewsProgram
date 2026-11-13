"""Guard the portable entry point and research identity exclusions."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from common import ROOT, load

SPEC = importlib.util.spec_from_file_location('pipeline', ROOT.parent / 'run_pipeline.py')
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


class PipelineTests(unittest.TestCase):
    def test_relative_settings_use_repository_root(self):
        self.assertEqual(pipeline.resolve_path('dataprocessing/data'), ROOT.parent / 'dataprocessing/data')

    def test_outputs_cannot_overwrite_source(self):
        paths = {name: pipeline.resolve_path(default) for name, (_, default) in pipeline.PATHS.items()}
        paths['output'] = paths['source'] / 'generated'
        with self.assertRaises(ValueError):
            pipeline.validate_paths(paths)
        paths['output'] = paths['source'].parent
        with self.assertRaises(ValueError):
            pipeline.validate_paths(paths)

    def test_skip_inference_never_downloads_models(self):
        steps = pipeline.commands('all', skip_inference=True)
        self.assertFalse(any('fetch_models' in arg or 'infer_models' in arg or 'style_models' in arg for step in steps for arg in step))
        self.assertIn(['analysis/style_features.py', 'ocr'], steps)

    def test_dry_run_works_from_another_directory_without_data(self):
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [sys.executable, '-X', 'utf8', str(ROOT.parent/'run_pipeline.py'), 'all', '--dry-run',
                 '--source', str(Path(directory)/'absent')],
                cwd=directory, capture_output=True, text=True, encoding='utf-8', check=True)
            self.assertIn('analysis/validate_style.py', completed.stdout)
            self.assertFalse((Path(directory)/'absent').exists())

    def test_identity_review_matches_supplement_pending_pairs(self):
        review = load(ROOT/'identity_review.json')
        pairs = {tuple(sorted([row['series_a'], row['series_b']])) for row in review}
        expected = {tuple(sorted(pair)) for pair in load(ROOT/'style_protocol.json')['identity']['known_pending_pairs']}
        self.assertEqual(pairs, expected)
        self.assertTrue(all(len(row['sources']) == 2 and row['reason'] for row in review))


if __name__ == '__main__':
    unittest.main()
