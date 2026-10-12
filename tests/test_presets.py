import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from z30_extensions.build import resolve_presets
from z30_extensions.cli import choose_presets, main


class PresetTests(unittest.TestCase):
    def test_aliases_and_duplicates_have_stable_order(self):
        selected, features = resolve_presets(['shutter-sound', 'full', 'm900', 'full'])
        self.assertEqual(selected, ['shutter-sound', 'full', 'm900'])
        self.assertEqual(features, ['liveview-dual', 'm900', 'shutter-sound', 'mtp-fast', 'module-host'])
        self.assertEqual(resolve_presets(['modular', 'full'])[1], features)

    def test_full_includes_every_feature_and_modular_keeps_its_scope(self):
        self.assertEqual(resolve_presets('full')[1],
                         ['liveview-dual', 'm900', 'shutter-sound', 'mtp-fast', 'module-host'])
        self.assertEqual(resolve_presets('modular')[1],
                         ['liveview-dual', 'm900', 'shutter-sound', 'module-host'])
        self.assertEqual(resolve_presets(['full', 'mtp-fast', 'modular'])[1],
                         resolve_presets('full')[1])

    def test_independent_combination(self):
        self.assertEqual(resolve_presets(['m900', 'liveview-dual'])[1],
                         ['liveview-dual', 'm900'])
        self.assertEqual(resolve_presets(['mtp-fast', 'full'])[1],
                         ['liveview-dual', 'm900', 'shutter-sound', 'mtp-fast', 'module-host'])

    def test_invalid_and_empty_selection(self):
        for selection in ([], 'unknown', ['full', 'unknown']):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                resolve_presets(selection)

    def test_interactive_numbers_names_and_retry(self):
        with patch('builtins.input', side_effect=['0', '2, m900 2']), patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(choose_presets(), ['liveview-dual', 'm900'])
        with patch('builtins.input', return_value=''), patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(choose_presets(), ['full'])

    def test_cli_combination_and_noninteractive_default(self):
        for selection in ([], ['liveview-dual', 'm900']):
            with self.subTest(selection=selection), tempfile.TemporaryDirectory() as folder:
                source = Path(folder) / 'stock.bin'
                output = Path(folder) / 'EG209020.BIN'
                source.write_bytes(b'stock')
                with patch('sys.stdin.isatty', return_value=False), \
                     patch('z30_extensions.cli.extract_eg', return_value=b'eg'), \
                     patch('z30_extensions.cli.build', return_value=(b'patched', {'sha256': 'test'})) as builder, \
                     patch('sys.stdout', new=io.StringIO()):
                    self.assertEqual(main(selection + ['--source', str(source), '--output', str(output)]), 0)
                builder.assert_called_once_with(b'eg', selection or ['full'])
                self.assertEqual(output.read_bytes(), b'patched')
                self.assertEqual(json.loads(output.with_suffix('.json').read_text())['input_kind'], 'stock_container')

    def test_cli_interactive_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'stock.bin'
            source.write_bytes(b'eg')
            with patch('sys.stdin.isatty', return_value=True), \
                 patch('builtins.input', return_value='2 4'), \
                 patch('z30_extensions.cli.build', return_value=(b'patched', {'sha256': 'test'})) as builder, \
                 patch('sys.stdout', new=io.StringIO()):
                main(['--extracted-eg', '--source', str(source), '--output', str(Path(folder) / 'out.bin')])
            builder.assert_called_once_with(b'eg', ['liveview-dual', 'm900'])


if __name__ == '__main__':
    unittest.main()
