#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 scfilter 日志里的绝对 pc/lr 地址解析成 so名!偏移。

作者：小肩膀   微信：xiaojianbang8888

用法:
  ./resolve.py <maps文件> <scfilter日志>       # 单 maps：所有行都用这份 maps
  ./resolve.py --pid <PID> <scfilter日志>       # 在线：从设备 /proc/PID/maps 取(需adb+su)
  ./resolve.py --mapsdir <目录> <scfilter日志>  # 多进程：目录里放 maps_<tgid>.txt，
                                                #          每行按其 tgid 选对应 maps 解析

输出: 每条命中行后追加 [pc] so!off  [lr] so!off
      多进程模式下，某行的 tgid 没有对应 maps 文件时，pc/lr 显示 (no-maps:tgid)
"""
import sys, re, os, subprocess

ADB = os.environ.get("XJB_ADB") or os.environ.get("ADB") or "adb"

def load_maps_from_text(text):
    # 解析 /proc/pid/maps，返回 [(start, end, path), ...]
    regions = []
    for line in text.splitlines():
        m = re.match(r'^([0-9a-f]+)-([0-9a-f]+)\s+\S+\s+\S+\s+\S+\s+\S+\s*(.*)$', line)
        if not m:
            continue
        regions.append((int(m.group(1), 16), int(m.group(2), 16), m.group(3).strip()))
    return regions

def maps_from_pid(pid):
    out = subprocess.run([ADB, "shell", "su", "-c", f"cat /proc/{pid}/maps"],
                         capture_output=True, text=True)
    return load_maps_from_text(out.stdout)

def build_base_map(regions):
    # 每个 so 取最小 start 作为加载基址（用于算偏移）
    base = {}
    for start, end, path in regions:
        if not path or path.startswith('['):
            continue
        if path not in base or start < base[path]:
            base[path] = start
    return base

def resolve(addr, regions, base):
    if not regions:
        return "??"
    for start, end, path in regions:
        if start <= addr < end:
            if not path:
                # 无名匿名段（常是加固壳/VMP 动态生成的可执行内存）。
                # 显示段基址+偏移，便于 dump 该段后定位。
                return f"anon:{start:x}+0x{addr-start:x}"
            if path.startswith('['):
                # 内核命名的匿名区间，如 [anon:.bss]、[stack]，附上段内偏移
                return f"{path}+0x{addr-start:x}"
            b = base.get(path, start)
            return f"{path.split('/')[-1]}!0x{addr-b:x}"
    return "??"

# 一个 maps 上下文：regions + base 缓存
class MapsCtx:
    def __init__(self, regions):
        self.regions = regions
        self.base = build_base_map(regions)
    def res(self, addr):
        return resolve(addr, self.regions, self.base)

def load_mapsdir(d):
    # 返回 {tgid(str): MapsCtx}
    ctxs = {}
    for fn in os.listdir(d):
        m = re.match(r'maps_(\d+)\.txt$', fn)
        if not m:
            continue
        with open(os.path.join(d, fn)) as f:
            ctxs[m.group(1)] = MapsCtx(load_maps_from_text(f.read()))
    return ctxs

def main():
    args = sys.argv[1:]
    mode_dir = None
    single = None

    if len(args) >= 2 and args[0] == "--mapsdir":
        mode_dir = load_mapsdir(args[1]); logf = args[2]
    elif len(args) >= 2 and args[0] == "--pid":
        single = MapsCtx(maps_from_pid(args[1])); logf = args[2]
    elif len(args) >= 2:
        with open(args[0]) as f:
            single = MapsCtx(load_maps_from_text(f.read()))
        logf = args[1]
    else:
        print(__doc__); sys.exit(1)

    with open(logf) as f:
        for line in f:
            line = line.rstrip('\n')
            mpc = re.search(r'pc:([0-9a-f]+)', line)
            mlr = re.search(r'lr:([0-9a-f]+)', line)
            if not (mpc and mlr):
                print(line); continue
            pc = int(mpc.group(1), 16)
            lr = int(mlr.group(1), 16)

            if mode_dir is not None:
                mt = re.search(r'tgid:(\d+)', line)
                tgid = mt.group(1) if mt else None
                ctx = mode_dir.get(tgid)
                if ctx is None:
                    pcs = lrs = f"(no-maps:{tgid})"
                else:
                    pcs, lrs = ctx.res(pc), ctx.res(lr)
            else:
                pcs, lrs = single.res(pc), single.res(lr)

            print(f"{line}\n        [pc] {pcs}   [lr] {lrs}")

def kresolve(logf):
    """日志已含内核态 pcsym/lrsym，提取成易读的 [分类] 路径 <-- 调用者 形式。"""
    pat = re.compile(
        r'comm:(?P<comm>\S+)\s+(?P<sc>[a-z0-9_]+)\s+'
        r'(?P<cat>\[[^\]]+\]|DUMP).*?'
        r'pcsym:(?P<pcsym>\S*)\s+lrsym:(?P<lrsym>\S*)\s+path:(?P<path>.*)$')
    event_pat = re.compile(
        r'comm:(?P<comm>\S+)\s+(?P<sc>[a-z0-9_]+)\s+'
        r'(?P<event>\[(?:EXIT|SIGNAL)/[^\]]+\]).*?'
        r'pcsym:(?P<pcsym>\S*)\s+lrsym:(?P<lrsym>\S*)(?P<detail>.*)$')
    for line in open(logf):
        line = line.rstrip('\n')
        m = pat.search(line)
        if m:
            g = m.groupdict()
            pcsym = g['pcsym'] or '??'
            lrsym = g['lrsym'] or '??'
            print(f"{g['cat']} {g['sc']} path:{g['path']}")
            print(f"        [pc] {pcsym}   [lr] {lrsym}   (comm:{g['comm']})")
            continue

        m = event_pat.search(line)
        if m:
            g = m.groupdict()
            pcsym = g['pcsym'] or '??'
            lrsym = g['lrsym'] or '??'
            detail = g['detail'].strip()
            if detail:
                print(f"{g['event']} {g['sc']} {detail}")
            else:
                print(f"{g['event']} {g['sc']}")
            print(f"        [pc] {pcsym}   [lr] {lrsym}   (comm:{g['comm']})")
            continue

        # 跳过 FAKE 等无 pcsym 的杂行；其它带 pcsym 但格式异常的才原样保留
        if 'pcsym:' in line:
            print(line)

if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--kresolve":
        kresolve(sys.argv[2])
    else:
        main()
