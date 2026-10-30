"""
会话持久化，保存与恢复会话
"""

import time
import uuid
import re
import json
from pathlib import Path


SESSIONS_DIR = Path.home() / '.code-agent' / 'sessions'
_SAFE_SESSION_RE = re.compile(r'[^A-Za-z0-9._-]+')
_MAX_SESSION_ID_LEN = 100
_SESSION_ID = None

def _new_session_id() -> str:
    return f"session_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

def _normalize_session_id(session_id: str|None) -> str:
    if not session_id:
        return _new_session_id()

    name = session_id.strip().replace('\\', '/').split('/')[-1]
    name = _SAFE_SESSION_RE.sub('-', name).strip('.-_')
    if len(name) > _MAX_SESSION_ID_LEN:
        name = name[:_MAX_SESSION_ID_LEN].strip('.-_')
    return name or _new_session_id()

def _session_path(session_id: str) -> Path:
    path = (SESSIONS_DIR / f'{_normalize_session_id(session_id)}.json').resolve()
    root = SESSIONS_DIR.resolve()
    if root != path.parent:
        raise ValueError('无效的session_id')
    return path

def save_session(messages: list[dict], model: str, session_id: str|None = None) -> str:
    """将聊天记录保存在磁盘上，返回session_id"""
    global _SESSION_ID

    SESSIONS_DIR.mkdir(parents = True, exist_ok = True)
    if _SESSION_ID:
        session_id = _SESSION_ID

    session_id = _normalize_session_id(session_id)
    data = {
        'id': session_id,
        'model': model,
        'saved_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'messages': messages
    }

    if not _SESSION_ID:
        _SESSION_ID = session_id

    path = _session_path(session_id)
    path.write_text(json.dumps(data, ensure_ascii = False, indent = 2), encoding = 'utf-8')
    return session_id

def set_session_id(session_id: str):
    global _SESSION_ID
    _SESSION_ID = session_id

def load_session(session_id: str) -> tuple[list[dict], str]|None:
    """加载一个保存的会话，返回（messages, model）或者None"""
    path = _session_path(session_id)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding = 'utf-8'))
        return data['messages'], data['model']
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, OSError):
        return None

def list_session() -> list[dict]:
    """罗列可用的会话，最新创建地放在第一个"""
    if not SESSIONS_DIR.exists():
        return []

    sessions = []
    for f in sorted(SESSIONS_DIR.glob('*.json'), reverse = True):
        try:
            data = json.loads(f.read_text(encoding = 'utf-8'))
            preview = ''
            for m in data.get('messages', []):
                if m.get('role') == 'user' and m.get('content'):
                    preview = m['content'][:80]
                    break
            sessions.append({
                'id': data.get('id', f.stem),
                'model': data.get('model', '?'),
                'saved_at': data.get('saved_at', '?'),
                'preview': preview
            })
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError):
            continue

    return sessions[:20]