"""
创建子Agent的工具
"""
from .base import Tool

class AgentTool(Tool):
    name = 'agent'
    description = """
    创建一个子agent来独立处理复杂任务中的一个子任务。
    子agent有自己独立的上下文与工具访问权限。子agent
    适合的工作有：“研究代码库、在独立环境中实施多步骤更改，
    或任何使用独立上下文能够获益的工作。”
    """

    parameters = {
        'type': 'object',
        'properties': {
            'task': {
                'type': 'string',
                'description': '子agent需要完成的任务'
            }
        },
        'required': ['task']
    }

    # 在主agent被创建时进行赋值
    _parent_agent = None

    def execute(self, task) -> str:
        if self._parent_agent is None:
            return 'Error: 子agent没有成功赋值，父agent为空'

        # 方法内导入防止循环导入
        from ..src.agent import Agent

        parent = self._parent_agent
        sub_agent = Agent(
            llm = parent.llm,
            tools = [t for t in parent.tools if t.name != 'agent'], # 子agent不允许在创建子agent
            max_context_tokens = parent.context.max_tokens,
            max_rounds = 20,
            permission = parent.permission,
            hooks = parent.hooks
        )

        # 子代码执行失败返回文本，不是影响父进程执行。
        # 子进程共享线程创建时的工作目录，结束后恢复，不会影响到父进程执行。
        from .bash import get_tracked_cwd, set_tracked_cwd
        parent_cwd = get_tracked_cwd()
        try:
            result = sub_agent.chat(task)
            # 删减长结果
            if len(result) > 5000:
                result = result[:4500] + '\n...（子agent的输出被删减）'
            return f'[子agent执行完毕]\n{result}'
        except Exception as e:
            return f'子agent执行过程中发生错误{e}'
        finally:
            if get_tracked_cwd() != parent_cwd:
                set_tracked_cwd(parent_cwd)
