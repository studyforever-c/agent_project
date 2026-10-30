"""
离线示例脚本：在不依靠API的情况下查看整个agent循环流程
"""
import tempfile
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .llm import LLMResponse, ToolCall
from .agent import Agent
from .cli import _brief

class ScriptedLLM:
    """
    用于离线演示和测试的LLM
    """

    total_prompt_tokens = 0
    total_completion_tokens = 0
    estimated_cost = None

    def __init__(self,
                 script: list[LLMResponse],
                 model: str = 'scripted-demo'):
        self._turns = list(script)
        self.model = model

    def chat(self,
             messages,
             tools = None,
             on_token = None,
             on_reasoning = None
        ) -> LLMResponse:
        if not self._turns:
            raise RuntimeError('示例LLM运行轮次已达上限。')

        resp = self._turns.pop(0)
        if on_token and resp.content:
            on_token(resp.content)
        self.total_completion_tokens += len(resp.content.split())
        return resp

_TASK = """
在fib.py文件中写一个函数`fib(n)`返回第n个斐波那契数
添加一个pytest文件并运行测试。
"""

def _script(workdir: Path) -> list[LLMResponse]:
    fib_py = """
def fib(n):
    if n < 2:
        return n
    a, b = 0, 1
    for _ in range(2, n+1):
        a, b = b, a + b
    return b            
    """

    test_py = """
from fib import fib
def test_fb():
    assert fib(0) == 0 
    assert fib(1) == 1 
    assert fib(10) == 55
    """
    return [
        LLMResponse(
            content = '我已经用迭代法实现了fib.py',
            tool_calls = [ToolCall(id = 'c1', name = 'write_file', arguments = {'file_path': str(workdir/'fib.py'), 'content': fib_py})]
        ),
        LLMResponse(
            content = '现在测试文件包含基本代码和fib(10)的测试。',
            tool_calls = [ToolCall(id = 'c2', name = 'write_file', arguments = {'file_path': str(workdir/'test_fib.py'), 'content': test_py})]
        ),
        LLMResponse(
            content = "运行测试。",
            tool_calls = [ToolCall(id = 'c3', name = 'bash', arguments = {'command': f'cd {workdir} && python -m pytest test_fib.py -q'})]
        ),
        LLMResponse(
            content = '所有三个测试都通过了。'
        )
    ]

console = Console()
def run_demo() -> int:
    workdir = Path.home() / '.code-agent' / 'demo-run'
    agent = Agent(llm = ScriptedLLM(_script(workdir)))

    console.print(
        Panel.fit(f'[bold]{_TASK}[/]', title = 'code-agent-demo(offline)')
    )

    result = agent.chat(
        _TASK,
        on_tool = lambda name, args: console.print(f'[cyan]tool:[/]{name} {_brief(args)}')
    )
    return 0
