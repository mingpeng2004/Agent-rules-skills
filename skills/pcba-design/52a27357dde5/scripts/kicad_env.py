#!/usr/bin/env python3
"""
PCBA Skill v5.0 — KiCad 环境探测（共用模块）

所有脚本统一从这里获取 kicad-cli / KiCad Python / 库路径，
禁止在各脚本里硬编码路径。优先级：
  1. 环境变量 KICAD_CLI / KICAD_PYTHON / KICAD_FOOTPRINT_LIB / KICAD_SYMBOL_LIB / KICAD_3DMODEL_DIR
  2. 常见安装目录自动探测（Windows/macOS/Linux）
"""
import os
import sys
import glob
import shutil
import subprocess


def _first_existing(candidates):
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def find_kicad_cli():
    """返回 kicad-cli 可执行文件路径，找不到返回 None"""
    env = os.environ.get('KICAD_CLI')
    if env and os.path.exists(env):
        return env
    on_path = shutil.which('kicad-cli')
    if on_path:
        return on_path
    candidates = []
    # Windows: 取最高版本号
    for d in sorted(glob.glob(r'C:\Program Files\KiCad\*\bin\kicad-cli.exe'), reverse=True):
        candidates.append(d)
    candidates += [
        '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli',
        '/usr/bin/kicad-cli',
        '/usr/local/bin/kicad-cli',
    ]
    return _first_existing(candidates)


def find_kicad_python():
    """返回带 pcbnew 的 Python 解释器。当前已在 KiCad Python 中运行则返回自身"""
    try:
        import pcbnew  # noqa: F401
        return sys.executable
    except ImportError:
        pass
    env = os.environ.get('KICAD_PYTHON')
    if env and os.path.exists(env):
        return env
    candidates = []
    for d in sorted(glob.glob(r'C:\Program Files\KiCad\*\bin\python.exe'), reverse=True):
        candidates.append(d)
    candidates += [
        '/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3',
        '/usr/bin/python3',
    ]
    return _first_existing(candidates)


def find_footprint_lib():
    env = os.environ.get('KICAD_FOOTPRINT_LIB')
    if env and os.path.isdir(env):
        return env
    candidates = []
    for d in sorted(glob.glob(r'C:\Program Files\KiCad\*\share\kicad\footprints'), reverse=True):
        candidates.append(d)
    candidates += [
        '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints',
        '/usr/share/kicad/footprints',
    ]
    return _first_existing(candidates)


def find_symbol_lib():
    env = os.environ.get('KICAD_SYMBOL_LIB')
    if env and os.path.isdir(env):
        return env
    candidates = []
    for d in sorted(glob.glob(r'C:\Program Files\KiCad\*\share\kicad\symbols'), reverse=True):
        candidates.append(d)
    candidates += [
        '/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols',
        '/usr/share/kicad/symbols',
    ]
    return _first_existing(candidates)


def kicad_version():
    cli = find_kicad_cli()
    if not cli:
        return None
    try:
        out = subprocess.run([cli, 'version'], capture_output=True, text=True, timeout=30)
        return out.stdout.strip() or None
    except Exception:
        return None


def run_kicad_python(script_path, args=None, timeout=600):
    """用 KiCad 自带 Python 运行脚本，返回 (exit_code, stdout, stderr)"""
    py = find_kicad_python()
    if not py:
        return 127, '', 'KiCad Python not found'
    cmd = [py, script_path] + (args or [])
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       encoding='utf-8', errors='replace')
    return p.returncode, p.stdout, p.stderr


def check_all():
    """环境自检，返回 dict（门禁 E-01..E-05）"""
    result = {
        'kicad_cli': find_kicad_cli(),
        'kicad_python': find_kicad_python(),
        'footprint_lib': find_footprint_lib(),
        'symbol_lib': find_symbol_lib(),
        'version': None,
        'ok': False,
    }
    result['version'] = kicad_version()
    result['ok'] = all([
        result['kicad_cli'], result['kicad_python'],
        result['footprint_lib'], result['symbol_lib'], result['version'],
    ])
    return result


if __name__ == '__main__':
    import json
    r = check_all()
    print(json.dumps(r, indent=2, ensure_ascii=False))
    sys.exit(0 if r['ok'] else 1)
