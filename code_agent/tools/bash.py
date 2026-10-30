"""
带有安全检测的Shell命令执行
功能：
- 输出捕获并进行截断
- 超时支持
- 危险命令检测
- 工作目录追踪
"""

import os
import threading
import re
import subprocess
from .base import Tool
from ..src.shell import run_shell

# 复制一份当前工作目录保存，确保两个线程的工作不会互相干扰
_local = threading.local()

def get_tracked_cwd() -> str|None:
    """获取此线程的工作目录，可能为空"""
    return getattr(_local, 'cwd', None)

def set_tracked_cwd(path: str|None) -> None:
    if path is None:
        if hasattr(_local, 'cwd'):
            del _local.cwd
    else:
        _local.cwd = path

# 可能破坏系统文件或泄密的模式串
_DANGEROUS_PATTERNS = [
    # 对根目录的强制递归删除指令
    (r"\brm\s+(-\w*)?-r\w*\s+(/|~|\$HOME)", "在home/root目录上进行递归删除"),
    # 递归和强制参数一起使用
    (r"\brm\b(?=(?:.*\s)?-\w*[rR])(?=(?:.*\s)?-\w*f)", "强制递归删除"),
    # 相同意义的长参数
    (r"\brm\b.*--recursive\b.*--force\b|\brm\b.*--force\b.*--recursive\b", "强制递归删除"),
    (r"\bmkfs\b", "格式化文件系统"),
    (r"\bdd\s+.*of=/dev/", "在裸磁盘上写数据。"),
    (r">\s*/dev/sd[a-z]", "覆写块设备"),
    (r"\bchmod\s+(-R\s+)?777\s+/", "在根目录设置所有权限"),
    (r":\(\)\s*\{.*:\|:.*\}", "无限派生进程"),
    (r"\bcurl\b.*\|\s*(sudo\s+)?(ba)?sh\b", "把curl下载的内容直接输送给shell执行。"),
    (r"\bwget\b.*\|\s*(sudo\s+)?(ba)?sh\b", "把wget下载的内容直接输送给shell执行。"),
]

def _check_dangerous(cmd: str) -> str|None:
    """如果需要执行的命令能在危险模式串中被匹配就返回响应警告，否则返回None"""
    for pattern, warning in _DANGEROUS_PATTERNS:
        if re.search(pattern, cmd):
            return warning
    return None

def _split_words(statement: str) -> list[str]:
    """把命令中的单个语句按空格拆成单词，引号里的算一个单词"""
    words = []
    buf = []
    quote: str|None = None
    for ch in statement:
        if quote is not None:
            if ch == quote:
                quote = None
            else:
                buf.append(ch)
        elif ch in ("'", '"'):
            quote = ch
        elif ch.isspace():
            if buf:
                words.append(''.join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        words.append(''.join(buf))
    return words


def _split_statements(command: str) -> list[list[str]]:
    """将命令按';'，'&&'进行切分，引号内的内容不切"""
    statements = [] # 已经切好的
    quote: str|None = None
    start = 0
    i = 0

    while i < len(command):
        ch = command[i]
        if quote is not None: # 在引号内
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):# 引号刚开始
            quote = ch
        else:# 引号外
            is_and = command[i: i+2] == '&&'
            if ch == ';' or is_and:
                statement = command[start: i]
                if statement.strip():
                    statements.append(statement)
                i += 2 if is_and else 1
                start = i
                continue
        i += 1
    tail = command[start:]
    if tail.strip():
        statements.append(tail)
    return [_split_words(statement) for statement in statements]



def _update_cwd(command: str, current_cwd: str):
    """跟踪cd命令之后的工作目录的变动"""

    # 删除命令中被括号包裹的命令，因为这些属于开一个子bash并在其中运行命令
    # 并不会影响主bash的目录
    scrubbed = re.sub(r'\([^()]*\)', ' ',  command)
    running = current_cwd
    changed = False
    for words in _split_statements(scrubbed):
        if words and words[0] != 'cd': # 只有cd会改变目录
            continue
        # 单cd命令会返回根目录
        target = words[1] if len(words) > 1 else '~'
        new_dir = os.path.normpath(os.path.join(running, os.path.expanduser(target)))
        if os.path.isdir(new_dir):
            running = new_dir
            changed = True
    if changed:
        _local.cwd = running

class BashTool(Tool):
    name = 'bash'
    description = """
        1. 执行一个shell命令。返回标准输出，标准错误和退出码。
        2. 进行测试运行，安装包，git操作等。
    """
    parameters = {
        'type': 'object',
        'properties': {
            'command': {
                'type': 'string',
                'description': '需要运行的shell命令。'
            },
            'timeout': {
                'type': 'integer',
                'description': '超时的秒数（默认120s）'
            }
        },
        'required': ['command']
    }


    def execute(self, command: str, timeout: int = 120) -> str:

        warning = _check_dangerous(command)
        if warning:
            return f'''
            执行的命令被拒绝：{warning}
            命令：{command}，
            如果需要执行，请更换成更安全的命令。'''

        cwd = get_tracked_cwd() or os.getcwd()

        try:
            process = run_shell(
                command,
                check = False,
                capture_output = True,
                text = True,
                encoding = 'utf-8',
                errors = 'replace',
                timeout = timeout,
                cwd = cwd
            )

            if process.returncode == 0:
                _update_cwd(command, cwd)
            out = process.stdout
            if process.stderr:
                out += f'\n[stderr]\n{process.stderr}'
            if process.returncode != 0:
                out += f'\n[exit code: {process.returncode}]'

            if len(out) > 15_000:
                out = out[:6000] + \
                    f'\n\n...共计{len(out)}字符，已被截断' + \
                    out[-3000:]
            return out.strip() or "（没有输出结果）"
        except subprocess.TimeoutExpired:
            return f'错误：经过{timeout}s后运行超时。'
        except Exception as e:
            return f'在运行命令{command}时发生错误：{e}'

