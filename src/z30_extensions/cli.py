"""Local firmware build CLI; never connects to a camera or writes an SD card."""
import argparse
import json
from pathlib import Path
from .build import build
from .container import extract_eg, CONTAINER_SHA256


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('feature', nargs='?', default='full', choices=['full', 'liveview-dual', 'm900', 'shutter-sound', 'modular', 'mtp-fast'])
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
        supplied = args.source.read_bytes()
        source = supplied if args.extracted_eg else extract_eg(supplied)
        output, report = build(source, args.feature)
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
