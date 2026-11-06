"""
permissions对外接口为check，save
加载该文件时首先从指定文件中读取所有会话被赋予的权限
当有工具请求时调用check，当工具为只读或在被赋予了永久权限的工具列表中则直接执行
当项目以--prompt(-p)模式启动时，Permission实例化时没有传入ask，因此无法审批编辑型工具，被直接拒绝
当审批工具请求时选择总是同意该工具执行，则工具名会被加入到always集合中，在保存会话时将always集合保存在权限文件中
"""

import json
from pathlib import Path

_PERMISSIONS_STORE = Path.home() / '.code-agent' / 'permissions.json'

_saved = {}
if _PERMISSIONS_STORE.exists():
    _saved = json.loads(_PERMISSIONS_STORE.read_text(encoding = 'utf-8'))

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
                self._always = {t for t in _saved.get(session_id, []) if isinstance(t, str)}
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

            global _saved
            # sorted()将集合转为列表并进行排序，确保之后的结果一致性
            _saved[session_id] = sorted(self._always)
            _PERMISSIONS_STORE.write_text(
                json.dumps(_saved, indent = 2) + '\n', encoding = 'utf-8'
            )
        except OSError:
            pass