"""
只读工具直接执行
需要编辑的文件需要人工确认
无法寻求人工确认的问题直接拒绝
"""

import json
from pathlib import Path

_PERMISSIONS_STORE = Path.home() / '.code-agent' / 'permissions.json'

saved = {}
if _PERMISSIONS_STORE.exists():
    saved = json.loads(_PERMISSIONS_STORE.read_text(encoding = 'utf-8'))

class Permission:

    READ_ONLY = frozenset({
        'read_file', 'glob', 'grep', 'todo_write'
    })

    def __init__(self,
                 session_id: str|None = None,
                 ask = None, # 询问是否执行，为None时直接拒绝
                 allow_all: bool = False,
                 ):
        self.session_id = session_id
        self.ask = ask
        self.allow_all = allow_all
        self._always: set[str] = set()

        if session_id is not None:
            try:
                self._always = {t for t in saved.get(session_id, []) if isinstance(t, str)}
            except (OSError, ValueError, AttributeError):
                # 意味着没有赋予任何权限
                pass

    def check(self, tool_name: str, arguments: dict) -> str|None:
        """
        决定一个工具是否应该被调用，返回None时说明允许，返回字符串时不允许。
        """
        if tool_name in self.READ_ONLY or self.allow_all or tool_name in self._always:
            return None
        if self.ask is None:
            return f"""
拒绝执行，{tool_name}会改变状态，但是这个回话是非交互式的，
请求无法被批准。建议用户重新运行时加上--yes或给出具体步骤交
由用户自己操作。
"""
        verdict = self.ask(tool_name, arguments)
        if verdict == 'always':
            self._always.add(tool_name)
            return None
        elif verdict == 'once':
            return None
        return f"""
拒绝执行：用户拒绝执行{tool_name}，不要再继续尝试了，问下一他们希望改成什么样
"""

    def save(self, session_id: str|None = None) -> None:
        if not self._always:
            return

        if self.session_id:
            session_id = self.session_id
        try:
            _PERMISSIONS_STORE.parent.mkdir(parents = True, exist_ok = True)

            global saved
            saved[session_id] = sorted(self._always)
            _PERMISSIONS_STORE.write_text(
                json.dumps(saved, indent = 2) + '\n', encoding = 'utf-8'
            )
        except OSError:
            pass