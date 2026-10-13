# SPDX-License-Identifier: LicenseRef-Wonder-Lantern-Community
# Copyright (c) 2026 Wonder Lantern Z30 contributors
# See licenses/Wonder-Lantern.txt and THIRD_PARTY_NOTICES.md.
"""Build owned sound menus and native SD-WAV audio hooks from stock templates."""
import struct
from ..assembly import assemble, constant, invoke, jump
from .sound_layout import *
from .sound_audio import audio_code
from .sound_ui import ui_code


def add(plan, modules=False):
    im = plan.image
    if im.read(STATE_ANCHOR, 44) != bytes(44):
        raise ValueError('Sound state requires the unused stock page-zero slot')
    setup_header = list(im.words(SETUP_META_SOURCE, 7))
    if setup_header[5] & 65535 != 38:
        raise ValueError('Unexpected stock settings row count')
    # Copy a valid native callback table into the private state prefix. Page 0
    # remains absent from the flash layout; only its unused RAM pointer anchors
    # this allocation after opening sound. No Camera Status page is registered.
    anchor_table = im.words(0xC1832D50 + 16, 1)[0]
    sizes = {'get': 128, 'cas': 96, 'validate': 384, 'convert': 192,
             'load': 1024, 'start': 448, 'stop': 192, 'trigger': 384,
             'complete': 384, 'open': 192, 'config': 320, 'data': 320,
             'shot': 192, 'ensure': 512, 'labels': 1024, 'render': 512,
             'action': 768, 'row': 256, 'getter': 256, 'route': 320, 'setup_init': 128}
    f = {name: plan.alloc(bytes(size)) for name, size in sizes.items()}
    from . import ui_text
    text_resources = ui_text.prepare(plan, f)
    tables = {i: plan.alloc(bytes(32)) for i in (PAGE_INDEX, FILES_INDEX, SWITCH_INDEX)}
    metas = {i: plan.alloc(bytes(28)) for i in tables}
    texts = dict(entry='Shutter sound', title='Shutter sound', files='Select sound', switch='Sound enabled',
                 enable='Enabled', file='Sound file', preview='Preview sound', reload='Reload sound',
                 off='OFF', on='ON', none='None', root='SHUTTER.WAV',
                 one='1.WAV', two='2.WAV', three='3.WAV', four='4.WAV', empty='', current='*',
                 missing='File not found', read='Read failed', invalid='Invalid WAV', close='Close failed',
                 busy='Sound busy', queue='Play failed', audio='Audio failed')
    if modules:
        texts['entry'] = texts['title'] = 'Extensions'
    strings = {key: text_resources.alloc(text) for key, text in texts.items()}
    paths = [plan.alloc(path.encode() + b'\0') for path in ['A:\\SHUTTER.WAV'] + [f'A:\\SHUTTER\\{i}.WAV' for i in range(1, 5)]]
    path_table = plan.alloc(struct.pack('<5I', *paths))
    file_names = plan.alloc(struct.pack('<5I', *[strings[k] for k in ('root', 'one', 'two', 'three', 'four')]))
    fixed = plan.alloc(struct.pack('<15I', *[strings[k] for k in
        ('entry', 'title', 'enable', 'file', 'preview', 'reload', 'off', 'on', 'root', 'one', 'two', 'three', 'four', 'switch', 'files')]))
    errors = plan.alloc(struct.pack('<8I', *[strings[k] for k in ('title', 'missing', 'read', 'invalid', 'close', 'busy', 'queue', 'audio')]))
    file_ids = plan.alloc(struct.pack('<5I', *FILE_IDS))
    switch_ids = plan.alloc(struct.pack('<2I', *SWITCH_IDS))
    # Settings is a child of the native tab container. Returning to the
    # settings object directly skips reconstruction of the shared sidebar.
    # Match native settings leaf pages by parenting to that container.
    setup_parent = im.words(SETUP_OBJECT + 4, 1)[0]
    template = plan.alloc(struct.pack('<11I', (PAGE_INDEX << 16) | 2, setup_parent, 0, 0,
                                    tables[PAGE_INDEX], 0, 0, 0, 0, 0, metas[PAGE_INDEX]))
    child_templates = {i: plan.alloc(struct.pack('<11I', (i << 16) | 2, 0, 0, 0, tables[i],
                                                0, 0, 0, 0, 0, metas[i])) for i in (FILES_INDEX, SWITCH_INDEX)}
    extension = None
    if modules:
        from . import module_host as mh
        module_table = plan.alloc(bytes(32))
        module_meta = plan.alloc(bytes(28))
        tables[mh.PAGE_INDEX] = module_table
        metas[mh.PAGE_INDEX] = module_meta
        child_templates[mh.PAGE_INDEX] = plan.alloc(struct.pack('<11I',
            (mh.PAGE_INDEX << 16) | 2, 0, 0, 0, module_table, 0, 0, 0, 0, 0, module_meta))
        extension = mh.prepare(plan, f, text_resources)
        extension['template'] = child_templates[mh.PAGE_INDEX]
    codes = audio_code(f, path_table, anchor_table)
    codes.update(ui_code(f, strings, fixed, file_names, errors, file_ids, switch_ids,
                         anchor_table, template, child_templates, extension, sidebar_parent=setup_parent))
    c = constant
    call = lambda name: invoke(f[name])
    owned_pages = [PAGE_INDEX, FILES_INDEX, SWITCH_INDEX]
    if modules:
        owned_pages.append(mh.PAGE_INDEX)
    codes['row'] = ui_text.row_code(f, SETUP_OBJECT, ENTRY_ID, owned_pages)
    setup_controls = im.read(setup_header[3], 38 * 28)
    entry = bytearray(setup_controls[-28:])
    struct.pack_into('<I', entry, 0, 39)
    # Row bit 9 selects ASCII kind 2; bit 13 selects Unicode kind 3.
    struct.pack_into('<I', entry, 16, 0x3001)
    struct.pack_into('<I', entry, 24, ENTRY_ID)
    unicode_controls = plan.alloc(setup_controls + entry)
    struct.pack_into('<I', entry, 16, 0x1201)
    controls_address = plan.alloc(setup_controls + entry)
    ui_text.configure_entry(plan, f, controls_address, unicode_controls)

    original_setup = im.words(im.words(SETUP_OBJECT + 16, 1)[0], 1)[0]
    codes['setup_init'] = f"""
        push {{r4,lr}}; mov r4,r0; {call('entry_select')} {call('labels')} mov r0,r4;
        {invoke(original_setup)} pop {{r4,pc}};
    """
    code_sizes = {}
    for name, source in codes.items():
        raw = assemble(source, f[name], sizes[name])
        plan.put(f[name], raw)
        code_sizes[name] = len(raw)
    zero = plan.alloc(bytes.fromhex('00207047 01207047'))

    # Retain native navigation handlers. Never copy firmware-update/device
    # callbacks into owned sound pages for unrelated messages.
    source_events = []
    for n in range(200):
        row = im.words(0x1140ED20 + n * 16, 4)
        source_events.append(row)
        if row[0] == 0x31E:
            break
    else:
        raise ValueError('Missing native event-map terminator')
    navigation = {0x1045FA81, 0x1045FA83, 0x1045FAA9, 0x1045FA65,
                  0x1045FA71, 0x1045FA7D, 0x1045FAF7}
    def events(callback):
        words = []
        for event, fn, predicate, destination in source_events:
            if event in (0x256, 0x25B, 0x26F, 0x27E):
                fn, predicate, destination = callback | 1, 0, 0x3BB
            elif fn not in navigation:
                fn, predicate = 0, 0
                destination = 0x3BC if destination == 0x3BC else 0x3BB
            words.extend((event, fn, predicate, destination))
        return plan.alloc(struct.pack('<' + 'I' * len(words), *words))
    entry_events = events(f['open'])
    owned_events = events(f['action'])
    dispatch_address = plan.alloc(im.read(setup_header[4], 38 * 4) + struct.pack('<I', entry_events))
    plan.edit(SETUP_META_SOURCE + 12, struct.pack('<2I', controls_address, dispatch_address), 'Sound settings entry tables')
    plan.edit(SETUP_META_SOURCE + 20, struct.pack('<I', (setup_header[5] & 0xFFFF0000) | 39), 'Settings row count with sound only')
    plan.edit(im.words(SETUP_OBJECT + 16, 1)[0], struct.pack('<I', f['setup_init'] | 1), 'Seed sound entry before settings rows')

    # Stock leaf page 0x18f contains both a header and the native back bitmap.
    # Copy those records from the caller's stock, then use dynamic header text.
    leaf = im.words(0xC1832D24 + 0x18F * 44, 11)
    if not setup_parent or leaf[1] != setup_parent:
        raise ValueError('Unexpected native settings tab parent')
    leaf_header = list(im.words(leaf[10], 7))
    if leaf_header[0] != 0x1008:
        raise ValueError('Unexpected native leaf menu flags')
    base_layout = bytearray(im.read(leaf_header[2], 96))
    if im.words(leaf_header[2] + 32, 8)[1] != 4:
        raise ValueError('Native back icon record missing')
    if im.words(leaf_header[2] + 64, 8)[1] != 0:
        raise ValueError('Unexpected leaf layout terminator')
    # Layout kind 1 constructs a text widget. Kind 2 is not the dynamic
    # string selector; the render callback supplies that selector separately.
    struct.pack_into('<I', base_layout, 28, 0xA18 << 16)

    used = set()
    for index in range(955):
        page = im.words(0xC1832D24 + index * 44, 11)
        if not any(page):
            continue
        meta = im.words(page[10], 7)
        for row in range(meta[5] & 65535):
            used.add(struct.unpack('<H', im.read(meta[3] + row * 28 + 24, 2))[0])
    if set(ROOT_IDS + FILE_IDS + SWITCH_IDS + (ENTRY_ID,)) & used:
        raise ValueError('Custom control identifiers conflict with stock')
    pages = {}
    page_specs = [
        (PAGE_INDEX, 4, 41, 54, 40, ROOT_IDS),
        (FILES_INDEX, 5, 47, 60, 53, FILE_IDS),
        (SWITCH_INDEX, 2, 45, 58, 52, SWITCH_IDS),
    ]
    if modules:
        available = [i for i in range(0x2400,0x3000) if i not in used and i not in ROOT_IDS + FILE_IDS + SWITCH_IDS + (ENTRY_ID,)]
        if len(available) < 5:
            raise ValueError('No free module control IDs')
        module_ids = tuple(available[:4])
        page_specs[0] = (PAGE_INDEX, 5, 41, 54, 40, ROOT_IDS + (available[4],))
        page_specs.append((mh.PAGE_INDEX, 4, mh.LABEL_SLOT, mh.EMPTY_SLOT, mh.TITLE_SLOT, module_ids))
        plan.features['module_host']['controls'] = list(module_ids)
    for index, count, label, value, title, identifiers in page_specs:
        controls = bytearray()
        for i in range(count):
            control = bytearray(entry)
            struct.pack_into('<I', control, 0, mh.ROOT_SLOT if modules and index == PAGE_INDEX and i == 4 else label + i)
            struct.pack_into('<I', control, 16, 0x1209)
            struct.pack_into('<I', control, 20, (mh.STATUS_SLOT if i == 2 else mh.EMPTY_SLOT) if modules and index == mh.PAGE_INDEX else (value + i if index != PAGE_INDEX or i < 2 else 56))
            struct.pack_into('<I', control, 24, identifiers[i])
            controls.extend(control)
        control_address = plan.alloc(controls)
        dispatch = plan.alloc(struct.pack('<' + 'I' * count, *([owned_events] * count)))
        layout = bytearray(base_layout)
        struct.pack_into('<I', layout, 0, title)
        layout_address = plan.alloc(layout)
        # Menu boxes, label boxes, value boxes. Root filenames get a 330 px
        # value column; choices use a compact '*' marker in a 126 px column.
        boxes, labels, values = [], [], []
        for row in range(count):
            y = 62 + row * 52
            boxes.extend((72, y, 702, y + 48))
            label_right = (350 if row < 2 else 696) if index == PAGE_INDEX else (350 if row == 2 else 696) if modules and index == mh.PAGE_INDEX else 550
            labels.extend((78, y + 4, label_right, y + 44))
            has_value = (row < 2 if index == PAGE_INDEX else row == 2 if modules and index == mh.PAGE_INDEX else True)
            value_left = (366 if index == PAGE_INDEX or modules and index == mh.PAGE_INDEX else 570) if has_value else 696
            # Native row composition clips its label at the value box even
            # when that box contains an empty string. Give label-only rows
            # a zero-width value box at the right edge.
            values.extend((value_left, y, 696, y + 48))
        rectangles = [plan.alloc(struct.pack('<' + 'h' * len(rect), *rect)) for rect in (boxes, labels, values)]
        geometry = plan.alloc(struct.pack('<4I', count, *rectangles))
        header = leaf_header.copy()
        # Bit 3 makes the leaf replace its parent's drawing. Keep the
        # ancestor tab container visible while retaining owned leaf controls.
        header[0] &= ~8
        header[1:5] = [geometry, layout_address, control_address, dispatch]
        # Low half: total rows. High half: rows per screen. The source leaf
        # only shows three; owned geometry fits all rows and must own capacity.
        header[5] = (count << 16) | count
        plan.put(metas[index], struct.pack('<7I', *header))
        plan.put(tables[index], struct.pack('<8I', f['render'] | 1, zero | 1, 0x1045FDA1,
                                           (zero + 4) | 1, zero | 1, zero | 1, zero | 1, 0x1045FDA1))
        pages[str(index)] = {'metadata': hex(metas[index]), 'functions': hex(tables[index]),
                             'count': count, 'controls': hex(control_address), 'layout': hex(layout_address),
                             'geometry': hex(geometry), 'label_rectangles': [labels[i:i+4] for i in range(0, len(labels), 4)],
                             'value_rectangles': [values[i:i+4] for i in range(0, len(values), 4)],
                             'title_index': title, 'label_start': label, 'value_start': value,
                             'back_icon': True, 'header_object_id': hex(0xA18),
                             'ancestor_sidebar_visible': True, 'layout_flags': hex(header[0])}
    for site, name, length in ((0x1045E33C, 'row', 8), (0x104571FE, 'getter', 12),
                               (0x10072598, 'shot', 8), (0x1006BEDE, 'config', 12),
                               (0x1006BE90, 'data', 8), (0x103CE804, 'route', 8)):
        plan.edit(site, jump(site, f[name], length), 'Sound hook: ' + name)
    plan.features['shutter_sound'] = {
        'functions': {k: hex(v | 1) for k, v in f.items()}, 'code_sizes': code_sizes,
        'pages': pages, 'state_anchor': hex(STATE_ANCHOR + 16), 'anchor_table': hex(anchor_table),
        'page_template': hex(template), 'persistent_state_size': (extension['allocation_size'] if extension else NEW_SIZE) + 31,
        'root_parent': hex(setup_parent),
        'page_offsets': {str(PAGE_INDEX): PAGE_OFFSET, str(FILES_INDEX): FILES_OFFSET, str(SWITCH_INDEX): SWITCH_OFFSET, **({str(mh.PAGE_INDEX): mh.PAGE_OFFSET} if modules else {})},
        'control_identifiers': {str(index): list(identifiers) for index, _, _, _, _, identifiers in page_specs},
        'setup_entry_id': hex(ENTRY_ID), 'settings_count': 39,
        'setup_entry_controls': {'ascii': hex(controls_address), 'utf16': hex(unicode_controls)},
        'setup_entry_prefetch_refresh': True,
        'default_enabled': False, 'settings_persistence': 'RAM only; reset at reboot',
        'ui_languages': {'26': 'zh-Hans', '27': 'zh-Hant', 'other': 'en'},
        'ui_text_api': {'ascii': '0x10454efe', 'utf16': '0x10454f5a', 'language_key': '0x1400',
                        'ascii_widget_kind': 2, 'utf16_widget_kind': 3, 'unicode_style': 120,
                        'chinese_fonts': {'26': 2, '27': 0}, 'chinese_module_output_limit': 24},
        'sample_format': '8 kHz, mono, signed 16-bit, canonical 44-byte WAV, <=1.08 seconds',
        'card_paths': ['SHUTTER.WAV'] + [f'SHUTTER/{i}.WAV' for i in range(1, 5)],
        'selection_mark': '*', 'native_back_icon_preserved': True, 'no_status_ui': True,
        'physical_menu_audio_verified': False,
    }
