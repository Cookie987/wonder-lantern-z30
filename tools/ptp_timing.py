"""Time raw MTP/PTP transactions against a camera through the stock Windows
MTP driver (WPD vendor-command passthrough). Read-only operations only."""
import argparse, ctypes, statistics, struct, time
import comtypes, comtypes.client as cc
from comtypes import GUID

api = cc.GetModule('portabledeviceapi.dll')
typ = cc.GetModule('portabledevicetypes.dll')
COMMON, MTP = '{F0422A9C-5DC8-4440-B5BD-5DF28835658A}', '{4D545058-1A2E-4106-A357-771E0819FC56}'


def key(guid, pid):
    k = api._tagpropertykey(); k.fmtid = GUID(guid); k.pid = pid
    return ctypes.pointer(k)

CATEGORY, COMMAND, HRESULT_KEY = key(COMMON, 1001), key(COMMON, 1002), key(COMMON, 1003)
OPCODE, PARAMS, RESPONSE, RESPONSE_PARAMS = (key(MTP, p) for p in (1001, 1002, 1003, 1004))
CONTEXT, TOTAL, TO_READ, DATA = key(MTP, 1006), key(MTP, 1007), key(MTP, 1008), key(MTP, 1012)
NO_DATA, DATA_TO_READ, READ_DATA, END_TRANSFER = 12, 13, 15, 17


def values():
    return cc.CreateObject(typ.PortableDeviceValues, interface=api.IPortableDeviceValues)


def command(command_id):
    v = values()
    v.SetGuidValue(CATEGORY, ctypes.pointer(GUID(MTP)))
    v.SetUnsignedIntegerValue(COMMAND, command_id)
    return v


def send(dev, v):
    r = dev.SendCommand(0, v)
    try:
        hr = r.GetErrorValue(HRESULT_KEY) & 0xFFFFFFFF
    except comtypes.COMError:
        hr = 0
    if hr & 0x80000000:
        raise OSError(f'driver HRESULT {hr:08x}')
    return r


def mtp(dev, op, params=(), read=True, chunk=1 << 20, keep=True):
    """Returns (response_code, data, seconds)."""
    start = time.perf_counter()
    v = command(DATA_TO_READ if read else NO_DATA)
    v.SetUnsignedIntegerValue(OPCODE, op)
    coll = cc.CreateObject(typ.PortableDevicePropVariantCollection,
                           interface=api.IPortableDevicePropVariantCollection)
    for p in params:
        pv = api.tag_inner_PROPVARIANT(); pv.vt = 19
        ctypes.c_ulong.from_address(ctypes.addressof(pv) + 8).value = p & 0xFFFFFFFF
        coll.Add(ctypes.pointer(pv))
    v.SetIPortableDevicePropVariantCollectionValue(PARAMS, coll)
    r = send(dev, v)
    if not read:
        return r.GetUnsignedIntegerValue(RESPONSE), b'', time.perf_counter() - start
    context = r.GetStringValue(CONTEXT)
    total = r.GetUnsignedLargeIntegerValue(TOTAL)
    parts, got = [], 0
    buffer = (ctypes.c_ubyte * chunk)()
    while got < total:
        n = min(chunk, total - got)
        v = command(READ_DATA)
        v.SetStringValue(CONTEXT, context)
        v.SetUnsignedIntegerValue(TO_READ, n)
        v.SetBufferValue(DATA, buffer, n)
        pointer, size = send(dev, v).GetBufferValue(DATA)
        if keep:
            parts.append(ctypes.string_at(pointer, size))
        ctypes.windll.ole32.CoTaskMemFree(pointer)
        if not size:
            break
        got += size
    v = command(END_TRANSFER)
    v.SetStringValue(CONTEXT, context)
    code = send(dev, v).GetUnsignedIntegerValue(RESPONSE)
    return code, (b''.join(parts) if keep else got), time.perf_counter() - start


def handles(data):
    if len(data) < 4:
        return []
    return list(struct.unpack_from(f'<{struct.unpack_from("<I", data)[0]}I', data, 4))


def object_info(data):
    fmt, = struct.unpack_from('<H', data, 4)
    size, = struct.unpack_from('<I', data, 8)
    n = data[52]
    name = data[53:53 + n * 2].decode('utf-16le', 'replace').rstrip('\0')
    return fmt, size, name


def stats(label, seconds):
    if not seconds:
        return print(f'  {label}: no samples')
    s = sorted(seconds)
    print(f'  {label}: n={len(s)} mean={statistics.mean(s) * 1000:.1f} ms  median={statistics.median(s) * 1000:.1f}'
          f'  p95={s[max(int(len(s) * .95) - 1, 0)] * 1000:.1f}  max={s[-1] * 1000:.1f}')
    return statistics.mean(s)


def devices():
    manager = cc.CreateObject(api.PortableDeviceManager, interface=api.IPortableDeviceManager)
    manager.RefreshDeviceList()
    count = ctypes.c_ulong(0)
    manager._IPortableDeviceManager__com_GetDevices(None, ctypes.byref(count))
    ids = (ctypes.c_wchar_p * max(count.value, 1))()
    if count.value:
        manager._IPortableDeviceManager__com_GetDevices(
            ctypes.cast(ids, ctypes.POINTER(ctypes.c_wchar_p)), ctypes.byref(count))
    return [ids[i] for i in range(count.value)]


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--samples', type=int, default=100)
    a.add_argument('--megabytes', type=int, default=64)
    a = a.parse_args()
    comtypes.CoInitialize()
    found = [d for d in devices() if 'vid_04b0' in d.lower()]
    if not found:
        return print('No Nikon MTP device found. Connect the camera (USB: MTP/PTP) and switch it on.')
    dev = cc.CreateObject(api.PortableDevice, interface=api.IPortableDevice)
    dev.Open(found[0], values())
    print('device', found[0])

    def run(name, op, params=(), **kw):
        try:
            code, data, t = mtp(dev, op, params, **kw)
            size = data if isinstance(data, int) else len(data)
            print(f'{name}: response {code:04x}, {size} bytes, {t * 1000:.1f} ms')
            return code, data, t
        except Exception as e:
            print(f'{name}: FAILED {e!r}')
            return None, b'', 0.0

    _, data, _ = run('GetStorageIDs', 0x1004)
    for sid in handles(data):
        print(f'== storage {sid:08x}')
        run('GetStorageInfo', 0x1005, (sid,))
        run('GetNumObjects(all)', 0x1006, (sid, 0, 0), read=False)
        _, data, _ = run('GetObjectHandles(all)', 0x1007, (sid, 0, 0))
        print(f'  {len(handles(data))} objects total')
        _, data, _ = run('GetObjectHandles(root)', 0x1007, (sid, 0, 0xFFFFFFFF))
        pending, folders, seen = handles(data), [], set()
        while pending:
            h = pending.pop()
            if h in seen:
                continue
            seen.add(h)
            code, data, _ = mtp(dev, 0x1008, (h,))
            if code != 0x2001 or object_info(data)[0] != 0x3001:
                continue
            name = object_info(data)[2]
            code, data, t = mtp(dev, 0x1007, (sid, 0, h))
            children = handles(data)
            folders.append((len(children), h, name, t, children))
            # Nikon handles carry the DCF file number in the low 14 bits; folders have none.
            pending += [c for c in children if (c & 0x3FFF) == 0]
        for n, h, name, t, _ in sorted(folders, reverse=True):
            print(f'  folder {h:08x} {name!r}: {n} children, GetObjectHandles {t * 1000:.1f} ms')
        if not folders:
            continue
        n, folder, name, _, children = max(folders)
        sample = children[:a.samples]
        print(f'== per-object cost in {name!r} ({len(sample)} of {n} objects)')
        info, props, thumbs, sizes = [], [], [], {}
        for h in sample:
            code, data, t = mtp(dev, 0x1008, (h,))
            if code == 0x2001:
                info.append(t); sizes[h] = object_info(data)[1]
        for h in sample:
            code, data, t = mtp(dev, 0x9805, (h, 0, 0xFFFFFFFF, 0, 0))
            if code == 0x2001:
                props.append(t)
        for h in sample:
            code, data, t = mtp(dev, 0x100A, (h,))
            if code == 0x2001:
                thumbs.append(t)
        per = [stats('GetObjectInfo', info), stats('GetObjectPropList(object)', props), stats('GetThumb', thumbs)]
        for label, value in zip(('ObjectInfo', 'PropList', 'Thumb'), per):
            if value:
                print(f'  projected for all {n} objects via {label}: {value * n:.1f} s')
        print('== bulk property queries')
        run('GetObjectPropList(folder, depth 1)', 0x9805, (folder, 0, 0xFFFFFFFF, 0, 1))
        run('GetObjectPropList(all, depth max)', 0x9805, (0xFFFFFFFF, 0, 0xFFFFFFFF, 0, 0xFFFFFFFF))
        if sizes:
            h = max(sizes, key=sizes.get)
            want = min(sizes[h], a.megabytes << 20)
            print(f'== throughput: {want / 1048576:.1f} MiB of object {h:08x}')
            code, got, t = run('GetPartialObject', 0x101B, (h, 0, want), chunk=4 << 20, keep=False)
            if code == 0x2001 and t:
                print(f'  {got / 1048576 / t:.1f} MiB/s')
    dev.Close()


if __name__ == '__main__':
    main()
