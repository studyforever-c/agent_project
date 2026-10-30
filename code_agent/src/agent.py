"""
Agent模块
对外接口：
    chat：接收用户输入，整合包含系统提示词的完整上下文
    reset：清空上下文和工作列表
系统提示词，若开启计划模式，则拼接上计划模式提示词，
若已有计划，则需拼接当前计划列表。
主要流程：
    1.接收用户输入，加入到上下文中
    2.拼接完整上下文，包含系统提示词与历史聊天记录
    3.判断是否需要压缩上下文
    4.调用大模型，返回响应，将响应加入上下文中
    5.判断有无工具调用请求
    6.无工具调用则结束本轮对话
    7.有工具调用时，首先通过pre_hooks规避危险指令，通过permit接收用户是否同意执行。
    8.两个请求都通过则同意执行，对于单工具调用则直接执行，多工具则使用多线程，最多八个工具并行执行。
    9.将所有工具调用结果加入上下文中，若未达到最大工具调用轮次，则重新从3开始执行。

"""

import inspect
import concurrent.futures
from .llm import LLM
from .context import ContextManager
from .prompt import PLAN_MODE_PROMPT, system_prompt
from ..tools.base import Tool
from ..tools import ALL_TOOLS
from ..tools import AgentTool
from ..tools import TodoWriteTool
from ..tools.bash import get_tracked_cwd, set_tracked_cwd


class Agent:
    def __init__(self,
                 llm: LLM,
                 tools: list[Tool]|None = None,
                 max_context_tokens: int = 128_000,
                 max_rounds: int = 50,
                 permission = None,
                 hooks = None
    ):
        self.llm = llm
        self.tools = tools if tools is not None else ALL_TOOLS
        self.permission = permission
        self.hooks = hooks
        self._tool_by_name = {t.name: t for t in self.tools}
        self._tool_schema = self._get_tool_schema()
        self.messages: list[dict] = []
        self.context = ContextManager(max_tokens = max_context_tokens)
        self.max_rounds = max_rounds
        self._system = system_prompt(self.tools)
        self.plan_mode = False # 计划模式通过命令行指令/plan开启，开启后，任何编辑文件的工具都将失效。

        # 连接子agent
        for t in self.tools:
            if isinstance(t, AgentTool):
                t._parent_agent = self

        self._todo = next((t for t in self.tools if isinstance(t, TodoWriteTool)), None)

    def _full_messages(self) -> list[dict]:
        system = self._system
        if self.plan_mode:
            system += '\n\n' + PLAN_MODE_PROMPT
        if self._todo is not None:
            rendered = self._todo.render()
            if rendered:
                system += '\n\n# 当前工作列表：\n' + rendered
        return [{'role': 'system', 'content': system}] + self.messages

    def _get_tool_schema(self) -> list[dict]:
        return [t.schema for t in self.tools]

    def _pre_hooks(self, tc) -> str|None:
        """
        在工具调用前请求用户同意，返回一个字符串时阻止工具调用，并将字符串
        作为工具调用结果，返回None时工具正常调用。
        """
        if self.hooks is None:
            return None
        return self.hooks.run_pre(tc.name, tc.arguments)

    def _post_hooks(self, tc, result: str):
        """仅展示"""
        if self.hooks is not None:
            self.hooks.run_post(tc.name, tc.arguments, result)

    def _permit(self, tc) -> str|None:
        """
        返回None允许进行，返回字符串则拒绝运行并将字符串作为工具
        调用结果返回给大模型
        """
        if self.plan_mode and tc.name not in self.permission.READ_ONLY:
            return """
            计划模式已经启动，计划模式下只能进行`只读`操作，不用再继续尝试了，
            继续使用只读工具完成任务，然后呈现给用户并停止，用户可以通过输入
            `批准`进行批准，或通过/plan退出计划模式。
            """
        if self.permission is None:
            return None
        return self.permission.check(tc.name, tc.arguments)

    def _exec_tool(self, tc) -> str:
        """调用单个工具"""
        tool = self._tool_by_name.get(tc.name)
        if tool is None:
            return f"错误，未知工具名{tc.name}"
        # 先排除可能的参数错误
        try:
            inspect.signature(tool.execute).bind(**tc.arguments)
        except TypeError as e:
            return f'错误：{tc.name}的参数错误：{e}'

        # 参数名对了，类型可能不对，因此函数执行过程中也可能出现TypeError
        try:
            return tool.execute(**tc.arguments)
        except Exception as e:
            return f'{tc.name}在执行过程中发生错误：{e}'

    def _exec_tools_parallel(self, tool_calls, on_tool = None) -> list[str]:
        """使用多线程同时调用多个工具"""

        if on_tool:
            for tc in tool_calls:
                on_tool(tc.name, tc.arguments)

        # 批量判断每个工具是否能调用
        results = [
            self._pre_hooks(tc) or self._permit(tc)
            for tc in tool_calls
        ]

        session_cwd = get_tracked_cwd()
        with concurrent.futures.ThreadPoolExecutor(max_workers = 8) as pool:
            def run(i, tc, base_cwd):
                is_bash = tc.name == 'bash'
                if is_bash and base_cwd is not None:
                    set_tracked_cwd(base_cwd)
                out = self._exec_tool(tc)
                if not is_bash:
                    return i, out, None
                cwd_after = get_tracked_cwd()

                return i, out, cwd_after if cwd_after != base_cwd else None

            futures = {
                i: pool.submit(run, i, tc, session_cwd)
                for i, tc in enumerate(tool_calls) if results[i] is None
            }

            for i, future in futures.items():
                i, results[i], worker_cwd = future.result()
                if worker_cwd is not None:
                    session_cwd = worker_cwd
                    set_tracked_cwd(worker_cwd)
        for i in futures:
            self._post_hooks(tool_calls[i], results[i])

        return results

    def _pending_tool_calls(self, tool_calls):
        """一个工具调用多次，id不一样，因此id可以区分一次工具调用"""
        answered = {m.get('tool_call_id') for m in self.messages if m.get('role') == 'tool'}
        for tc in tool_calls:
            if tc.id in answered:
                continue
            self.messages.append({
                'role': 'tool',
                'tool_call_id': tc.id,
                'content': '[interrupted]'
            })

    def chat(self, user_input: str,
             on_token = None,
             on_tool = None,
             on_reasoning = None) -> str:

        self.messages.append(
            {'role': 'user', 'content': user_input}
        )
        self.context.maybe_compress(self.messages, self.llm)

        for _ in range(self.max_rounds):
            resp = self.llm.chat(
                messages = self._full_messages(),
                tools = self._tool_schema,
                on_token = on_token,
                on_reasoning = on_reasoning
            )

            self.messages.append(resp.message)
            if not resp.tool_calls:
                return resp.content

            try:
                if len(resp.tool_calls) == 1:
                    tc = resp.tool_calls[0]
                    if on_tool:
                        on_tool(tc.name, tc.arguments)
                    result = self._pre_hooks(tc) or self._permit(tc)
                    if result is None:
                        result = self._exec_tool(tc)
                        self._post_hooks(tc, result)
                    self.messages.append({
                        'role': 'tool',
                        'tool_call_id': tc.id,
                        'content': result
                    })
                else:
                    results = self._exec_tools_parallel(resp.tool_calls, on_tool)
                    for tc, result in zip(resp.tool_calls, results):
                        self.messages.append({
                            'role': 'tool',
                            'tool_call_id': tc.id,
                            'content': result
                        })
            except KeyboardInterrupt:
                # 手动按Ctrl+C中断影响工具调用过程，影响下一轮请求

                self._pending_tool_calls(resp.tool_calls)
                raise
            self.context.maybe_compress(self.messages)
        return '（达到最大工具调用次数）'

    def reset(self):
        """仅清空聊天记录和工作列表"""
        self.messages.clear()
        todo = self._tool_by_name.get('todo_write')
        if isinstance(todo, TodoWriteTool):
            todo._tasks = []
