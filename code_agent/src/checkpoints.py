"""
会话内进行文件改动时的记录，以便后续进行撤销操作
"""

import base64
import json
from pathlib import Path

CHECKPOINTS_FILE = Path.home() / '.code-agent' / 'checkpoints.json'

# (路径， 改动前的内容，如果原文件不存在则为None)
_stack: list[tuple[str, bytes|None]] = []
_loaded = False

def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        entries = json.loads(CHECKPOINTS_FILE.read_text(encoding = 'utf-8'))
        for e in entries:
            prior = e['prior']
            _stack.append((e['path'], base64.b64decode(prior) if prior is not None else None))
    except (OSError, ValueError, KeyError, TypeError):
        # 堆栈损坏意味着无法进行撤销
        pass

def _save() -> None:
    entries = [
        {'path': path, 'prior': base64.b64encode(prior).decode('ascii') if prior is not None else None}
        for path, prior in _stack
    ]

    try:
        CHECKPOINTS_FILE.parent.mkdir(parents = True, exist_ok = True)
        tmp = CHECKPOINTS_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(entries), encoding = 'utf-8')
        tmp.replace(CHECKPOINTS_FILE)
    except OSError:
        # 保存记录失败不影响编辑文件
        pass

def record(path: Path) -> None:
    """保留修改文件之前的文件状态"""
    _ensure_loaded()
    _stack.append((str(path), path.read_bytes() if path.exists() else None))
    _save()

def undo() -> str:
    """回滚到最近的检查点"""
    _ensure_loaded()

    if not _stack:
        return '没有能撤销的记录'
    path_str, prior = _stack.pop()
    path = Path(path_str)
    if prior is None:
        path.unlink(missing_ok = True)
        msg = f'已移除{path_str}（在此次会话内创建的）。'
    else:
        recreated = not path.parent.exists()
        path.parent.mkdir(parents = True, exist_ok = True)
        path.write_bytes(prior)
        msg = f"{path_str}已恢复。" + '' if not recreated else \
             "（已重建父目录）"
    _save()
    return msg

def pending() -> int:
    _ensure_loaded()
    return len(_stack)

# 暂且没用到
# def clear() -> None:
#     global _loaded
#     _stack.clear()
#     _loaded = True
#
#     try:
#         CHECKPOINTS_FILE.unlink(missing_ok = True)
#     except OSError:
#         pass
#
