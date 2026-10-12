"""Local firmware build CLI; never connects to a camera or writes an SD card."""
import argparse
import json
import sys
from pathlib import Path
from .build import build, PRESETS, resolve_presets
from .container import extract_eg, CONTAINER_SHA256


def choose_presets():
    """Read a runtime selection without changing firmware on the camera."""
    print('Select presets (combine numbers or names, separated by spaces or commas):')
    for index, name in enumerate(PRESETS, 1):
        label = ' (all features, including MTP acceleration and SD module host)' if name == 'full' else ''
        print(f'  {index}. {name}{label}')
    while True:
        try:
            answer = input('Presets [full]: ').strip()
        except (EOFError, KeyboardInterrupt):
            raise ValueError('Preset selection cancelled') from None
        tokens = answer.replace(',', ' ').split() if answer else ['full']
        selected = [PRESETS[int(t) - 1] if t.isdigit() and 1 <= int(t) <= len(PRESETS)
                    else t for t in tokens]
        try:
            return resolve_presets(selected)[0]
        except ValueError as error:
            print(error)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('feature', nargs='*', metavar='PRESET',
                        help='Combine presets with spaces: ' + ', '.join(PRESETS) +
                             '; full enables all features, including MTP acceleration and SD module host')
    parser.add_argument('--interactive', action='store_true', help='Prompt for presets even when stdin is redirected')
    parser.add_argument('--source', type=Path, required=True, help='Original Z_30_0120.bin, SHA-256 checked before decoding')
    parser.add_argument('--extracted-eg', action='store_true', help='Developer mode: input is an extracted stock EG module')
    parser.add_argument('--output', type=Path, required=True, help='New output path; existing files are refused')
    args = parser.parse_args(argv)
    metadata = args.output.with_suffix('.json')
    if args.output.resolve() == metadata.resolve():
        parser.error('Output path must not have a .json suffix')
    if args.output.exists() or metadata.exists():
        parser.error('Output or report already exists; choose fresh paths')
    try:
        selected = args.feature
        if args.interactive or (not selected and sys.stdin.isatty()):
            selected = choose_presets()
        if not selected:
            selected = ['full']
        selected, features = resolve_presets(selected)
        print('Enabled features: ' + ', '.join(features))
        supplied = args.source.read_bytes()
        source = supplied if args.extracted_eg else extract_eg(supplied)
        output, report = build(source, selected)
        report['input_kind'] = 'extracted_eg' if args.extracted_eg else 'stock_container'
        if not args.extracted_eg:
            report['container_sha256'] = CONTAINER_SHA256
        # Create exclusively; never overwrite an existing image or report.
        with metadata.open('x', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps(report, indent=2) + '\n')
        try:
            with args.output.open('xb') as f:
                f.write(output)
        except OSError:
            metadata.unlink()
            raise
    except (ValueError, OSError) as error:
        parser.exit(1, f'Build failed: {error}\n')
    print(f'Built {args.output}: {report["sha256"]}')
    print(f'Report: {metadata}')
    return 0
