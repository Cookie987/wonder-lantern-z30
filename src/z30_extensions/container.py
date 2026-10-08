"""Decode the exact stock C 1.20 container using an input-derived XOR mask.

The known-zero offsets are version-specific observations, not bundled firmware
bytes or copied XOR tables. The full input hash is checked before mask recovery.
"""
import binascii
import json
import struct
from importlib.resources import files
from .platform.z30_120 import StockImage, sha256

CONTAINER_SHA256 = '1a5449ef505f1f347ed4e066a6a3f588ea542240680e83f4ebcae3b16da3434a'
CONTAINER_SIZE = 34496798
ZERO_ANCHOR = 0x3A00


def recover_mask(encoded_body):
    samples = json.loads(files('z30_extensions.platform').joinpath('z30_120_zero_samples.json').read_text(encoding='utf-8'))
    if len(encoded_body) <= max(samples + [ZERO_ANCHOR + 255]):
        raise ValueError('Body is too short for this version-specific decoder')
    # A known-zero 256-byte aligned span yields column mask differences.
    columns = bytes(value ^ encoded_body[ZERO_ANCHOR]
                    for value in encoded_body[ZERO_ANCHOR:ZERO_ANCHOR + 256])
    # At known-zero offsets: encoded[i] ^ columns[i & 255] = row ^ block.
    # Normalize row[0] to zero. Samples form a spanning tree of 512 nodes.
    values = [None] * 512
    values[0] = 0
    for offset in samples:
        row = (offset >> 8) & 255
        block = 256 + ((offset >> 16) & 255)
        value = encoded_body[offset] ^ columns[offset & 255]
        if values[row] is not None:
            recovered = values[row] ^ value
            if values[block] is not None and values[block] != recovered:
                raise ValueError('Inconsistent known-zero mask samples')
            values[block] = recovered
        elif values[block] is not None:
            values[row] = values[block] ^ value
        else:
            raise ValueError('Disconnected mask sample ordering')
    if any(value is None for value in values):
        raise ValueError('Incomplete mask recovery')
    return columns, bytes(values[:256]), bytes(values[256:])


def decode_body(encoded_body):
    columns, rows, blocks = recover_mask(encoded_body)
    # Build 64 KiB column/row mask; the high-byte mask repeats every 16 MiB.
    pattern = b''.join(columns.translate(bytes(v ^ row for v in range(256))) for row in rows)
    body = bytearray(encoded_body)
    for start in range(0, len(body), 65536):
        high = blocks[(start >> 16) & 255]
        stop = min(start + 65536, len(body))
        low = max(start, 32)
        body[low:stop] = bytes(value ^ pattern[i - start] ^ high
                              for i, value in enumerate(encoded_body[low:stop], low))
    return bytes(body)


def extract_eg(encoded):
    encoded = bytes(encoded)
    # No source inspection, decode, patching or file output precedes this guard.
    if len(encoded) != CONTAINER_SIZE or sha256(encoded) != CONTAINER_SHA256:
        raise ValueError('Original Z_30_0120.bin SHA-256 mismatch; only stock Z30 C 1.20 is supported')
    body = decode_body(encoded[32:])
    if body[:32] != b' ' * 32 or struct.unpack_from('>4I', body, 32) != (3, 144, 0, 0):
        raise ValueError('Unexpected decoded stock header')
    if body[-14:] != bytes(14) or binascii.crc_hqx(body[:-16], 0) != int.from_bytes(body[-16:-14], 'big'):
        raise ValueError('Decoded container CRC mismatch')
    cursor = 144
    main = None
    names = set()
    for index in range(3):
        raw_name, start, size, reserved0, reserved1 = struct.unpack_from('>16s4I', body, 48 + index * 32)
        name = raw_name.rstrip(b'\0')
        if name in names or reserved0 or reserved1 or start != cursor or size < 2 or start + size > len(body) - 16:
            raise ValueError('Unexpected decoded module bounds')
        names.add(name)
        module = body[start:start + size]
        if binascii.crc_hqx(module, 0):
            raise ValueError('Decoded module CRC mismatch')
        if name == b'eg2090_0120a0.bi':
            main = module
        cursor += size
    if cursor != len(body) - 16 or main is None:
        raise ValueError('Missing EG module or incomplete body coverage')
    # A second cryptographic identity guard confirms the entire recovered EG.
    return StockImage(main).data
