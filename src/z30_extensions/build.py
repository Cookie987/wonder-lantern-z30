"""Compose stock-relative firmware features."""
from .plan import Plan
from .patch import Edit
from .features.liveview_dual import build as build_dual, VIDEO_STOCK_WINDOWS
from .platform.z30_120 import BASE


def build(source, preset='full'):
    if preset not in ('full', 'liveview-dual', 'm900', 'shutter-sound', 'modular'):
        raise ValueError('Unknown feature preset')
    if preset == 'liveview-dual':
        return build_dual(source)
    plan = Plan(source)
    if preset in ('full', 'modular'):
        dual, report = build_dual(source)
        plan.tail.extend(dual[len(source) - 2:-2])
        plan.edits.extend(Edit(int(e['offset'], 16), bytes.fromhex(e['expected_hex']),
                              bytes.fromhex(e['replacement_hex']), e['name']) for e in report['edits'])
        plan.features['liveview_dual'] = {'hooks': report['hooks'], 'mask_rom_address': report['mask_rom_address']}
    if preset in ('full', 'm900', 'modular'):
        from .features.long_exposure import add
        add(plan)
    if preset in ('full', 'shutter-sound', 'modular'):
        from .features.shutter_sound import add
        add(plan, modules=preset == 'modular')
    output, report = plan.finish()
    for address, expected in VIDEO_STOCK_WINDOWS:
        if output[address - BASE:address - BASE + len(expected)] != expected:
            raise ValueError('Video shutter differs from stock')
    report['preset'] = preset
    report['video_shutter_stock'] = True
    return output, report
