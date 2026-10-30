"""
在工具调用前后执行钩子函数。每个人钩子函数都是一个
Shell命令，将工具调用以JSON形式通过stdin传入。
在工具调用之前的钩子函数可以通过返回码2给出是否调
用模型，若不调用，stderr作为决定后返回给模型的理由。工具调用
之后的钩子函数功能只有观察，在发生错误或挂起时给出警告。
"""
import json
import logging
import subprocess
from pathlib import Path

from .shell import run_shell

log = logging.getLogger(__name__)

HOOKS_FILE = Path.home() / '.code-agent' / 'hooks.json'
TIMEOUT = 10



def _fire(hook: dict, payload: dict):
    """
    如果matcher匹配到对应工具名或者‘*’就运行hook，将payload以json形式传给stdin，
    返回None意味着什么也没匹配到或运行hook失败，直接跳过。
    """
    matcher = hook.get('matcher', '')
    if matcher not in ('', '*', payload['tool_name']):
        return None
    try:
        process = run_shell(
            hook['command'], # 要执行的shell命令
            check = False, # 出错不抛异常，防影响主进程，
            input = json.dumps(payload),
            capture_output = True, # 获取输出或退出码
            text = True, # 返回结果为字符串
            encoding = 'utf-8', # 防止输出为乱码
            errors = 'replace', # 非法字节转换
            timeout = TIMEOUT
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        log.warning(f'此hook执行被跳过了({e.__class__.__name__}):{hook['command']}')
        return None
    if process.returncode not in (0, 2):
        log.warning(f'hook退出码为：{process.returncode}，{hook['command']}')
        return None
    return process

class Hooks:

    def __init__(self, pre: list[dict], post: list[dict]):
        self.pre = pre
        self.post = post

    def __bool__(self):
        return bool(self.pre or self.post)



    def run_pre(self, tool_name: str, tool_input: dict) -> str|None:
        payload = {'tool_name': tool_name, 'tool_input': tool_input}
        for hook in self.pre:
            out = _fire(hook, payload)
            if out is not None and out.returncode == 2:
                reason = out.stderr.strip() or 'not reason given'
                return '被hook阻拦：' +reason
        return None

    def run_post(self, tool_name: str, tool_input: dict, result: str):
        """只做展示"""
        payload = {
            'tool_name': tool_name,
            'tool_input': tool_input,
            'tool_response': result
        }
        for hook in self.post:
            _fire(hook, payload)

def load_hooks(path: Path = HOOKS_FILE) -> Hooks:
    try:
        data = json.loads(path.read_text(encoding = 'utf-8'))
    except FileNotFoundError:
        return Hooks([], [])
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f'ignoring {path}: {e}')
        return Hooks([], [])
    pre = [h for h in data.get('PreToolUse', []) if h.get('command')]
    post = [h for h in data.get('PostToolUse', []) if h.get('command')]

    return Hooks(pre, post)