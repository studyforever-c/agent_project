"""
agent的工具清单

对于多步骤任务，agent首先列出完整工作清单，之后根据任务完
成情况进行重写，该清单一致保存，每轮任务有agent放到对话上
下文中，确保模型从当前状态工作，无需查看历史工具结果。

子agent共享父agent的工作清单。
"""

from .base import Tool

# 单条任务的进行状态
_VALID_STATUS = (
    'pending',
    'in_progress',
    'done'
)

class TodoWriteTool(Tool):
    name = 'todo_write'
    description = """
    管理任务清单。每次都需要传递完整的任务清单，它会替代旧的清单。
    合理使用任务清单进行多步骤任务的规划。使用方法如下：
    1. 写出完成任务的完整清单
    2. 一次处理一个正在进行的任务，任务完成时将其状态标为`done`
    3. 当前任务清单传给下一轮作为系统上下文。
    """

    parameters = {
        'type': 'object',
        'properties': {
            'tasks': {
                'type': 'array',
                'description': '管理当前工作清单列表',
                'items': {
                    'type': 'object',
                    'properties': {
                        'content': {
                            'type': 'string',
                            'description': '当前阶段需要完成的工作内容。'
                        },
                        'status': {
                            'type': 'string',
                            'enum': list(_VALID_STATUS),
                            'description': '当前任务的状态'
                        }
                    },
                    'required': ['content', 'status']
                }
            }
        },
        'required': ['tasks']
    }

    def __init__(self):
        self._tasks: list[dict] = []

    def render(self) -> str:
        """将任务列表转为文本，以便之后agent将其插入系统上下文。"""
        return '\n'.join(
            f'{i}.[{t['status']}] {t['content']}'
            for i, t in enumerate(self._tasks, 1)
        )
    def execute(self, tasks: list) -> str:
        if not isinstance(tasks, list):
            return '错误：任务列表必须是一个{content, status}列表'

        checked = []
        # 在更新任务列表前
        for i, t in enumerate(tasks, 1):
            content = t.get('content') if isinstance(t, dict) else None
            if not isinstance(content, str) or not content.strip():
                return f"错误：任务{i}非空且为'string'类型的'content'"
            status = t.get('status')
            if status not in _VALID_STATUS:
                return f"错误：任务{i}使用了无效的状态{status!r}，请使用{_VALID_STATUS}"
            checked.append(
                {'content': content.strip(), 'status': status}
            )
        self._tasks = checked

        if not checked:
            return '任务列表已清空。'
        return '任务列表已更新：\n' + self.render()
    