"""
mcp客户端
"""

import logging
import threading
import subprocess
import os
import json
import time
import atexit
from pathlib import Path

from . import __version__
from ..tools.base import Tool

log = logging.getLogger(__name__)

CONFIG_FILE = Path.home() / '.code-agent' / 'mcp.json'
PROTOCOL_VERSION = "2025-06-18"
INIT_TIMEOUT = 15 # 初始化tools/call需要的时间
CALL_TIMEOUT = 60 # 一次工具调用的时间

class MCPError(RuntimeError):
    """与某个服务器通信失败或协议失效"""

class MCPClient:
    """
    stdio服务进程：握手，获取工具列表，调用工具，关闭
    """

    def __init__(self, name: str, command: str, args: list = (), env: dict|None = None):
        self.name = name
        self._command = command
        self._args = args
        self._env = env
        self._next_id = 0
        self._dead: MCPError|None = None
        self._response: dict[int, dict] = {}
        self._cond = threading.Condition()
        self._write_lock = threading.Lock()
        self._start()

    @property
    def error(self) -> MCPError|None:
        """获取服务器终止的原因，正常运行时为None"""
        return self._dead

    def _write(self, msg: dict):
        try:
            with self._write_lock:
                self._process.stdin.write(json.dumps(msg) + '\n')
                self._process.stdin.flush()
        except OSError as e:
            raise MCPError(f'MCP服务器{self.name!r}不可写：{e}') from e

    def _notify(self, method: str):
        try:
            self._write(
                {'jsonrpc': '2.0', 'method': method, 'params': {}}
            )
        except MCPError:
            pass

    def _read_loop(self, process: subprocess.Popen):
        try:
            for line in process.stdout:
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    log.warning(f'MCP服务器{self.name!r}发送了一个非json格式数据，已被跳过。')
                    continue
                if 'id' not in msg:
                    continue
                with self._cond:
                    self._response[msg['id']] = msg
                    self._cond.notify_all()
        except (OSError, ValueError):
            pass
        with self._cond:
            if process is self._process and self._dead is None:
                self._dead = MCPError(f'MCP 服务器{self.name!r}已经关闭')

    def _request(self, method: str, params: dict, timeout: float) -> dict:
        with self._cond:
            if self._dead is not None:
                raise self._dead
            self._next_id += 1
            req_id = self._next_id
        self._write(
            {'jsonrpc': '2.0', 'id': req_id, 'method': method, 'params': params}
        )

        deadline = time.monotonic() + timeout
        with self._cond:
            while req_id not in self._response:
                if self._dead is not None:
                    raise self._dead
                left = deadline - time.monotonic()
                if left < 0:
                    raise MCPError(f'MCP服务器{self.name!r}没有在{timeout:g}时间内给出{method}的答案。')
                self._cond.wait(left)
            msg: dict = self._response.pop(req_id)
        if 'error' in msg:
            raise MCPError(f'MCP服务器{self.name!r}拒绝{method}：{msg['error'].get('message', msg['error'])}')
        return msg.get('result', {})

    def _start(self):
        """生成服务器并运行开始握手"""
        self._process = subprocess.Popen(
            [self._command, *self._args],
            stdin = subprocess.PIPE,
            stdout = subprocess.PIPE,
            env = {**os.environ, **(self._env or {})},
            encoding = 'utf-8',
            errors = 'replace',
            bufsize = 1
        )
        threading.Thread(target = self._read_loop, args = (self._process, ), daemon = True).start()

        with self._cond:
            self._dead = None
            self._response.clear()

        try:
            self._request(
                method = 'initialize',
                params = {
                    'protocolVersion': PROTOCOL_VERSION,
                    'capabilities': {},
                    'clientInfo': {'name': 'code-agent', 'version': __version__}
                },
                timeout = INIT_TIMEOUT
            )
            self._notify('notifications/initialized')
            listed = self._request('tools/list', {}, INIT_TIMEOUT)
            self.tools = [MCPTool(self, t) for t in listed.get('tools', [])]
        except BaseException:
            # 初始化过程中有任何错误就关闭子进程并抛出异常
            self.close()
            raise

    def close(self):
        """关闭子进程"""

        # 当前进程已经结束，不需要再关闭
        if self._process.poll() is not None:
            return
        try:
            self._process.wait(timeout = 5)
        except subprocess.TimeoutExpired:
            self._process.kill()

    def reconnect(self):
        """为服务器重启一个进程并进行握手"""
        self.close()
        try:
            self._start()
        except (MCPError, OSError) as e:
            with self._cond:
                self._dead = e if isinstance(e, MCPError) else MCPError(str(e))
            raise

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        """运行一个远程工具，返回运行获取的文本结果"""
        result = self._request(
            method = 'tools/call',
            params = {'name': tool_name, 'arguments': arguments},
            timeout = CALL_TIMEOUT
        )

        text = '\n'.join(
            part.get('text', '')
            for part in (result.get('content', []) or [])
            if part.get('type') == 'text'
        )
        if result.get('isError'):
            raise MCPError(text or f'{tool_name}运行报错')
        return text or json.dumps(result)


class MCPTool(Tool):
    """
    MCP工具，与内部工具互不干扰，不放在Permission.READ_ONLY中，
    执行前需要询问用户。
    """
    def __init__(self, client: MCPClient, spec: dict):
        self._client = client
        self._remote_name = spec['name']
        self.name = f'mcp__{client.name}__{spec['name']}'
        self.description = spec.get('description') or ''
        self.parameters = spec.get('inputSchema') or {'type': 'object', 'properties': {}}

    def execute(self, **kwargs) -> str:
        return self._client.call_tool(self._remote_name, kwargs)

_live_clients : list[MCPClient] = []

def load_mcp_tools(path: Path = CONFIG_FILE) -> list[Tool]:
    """
    启动已经配置好的服务器，返回可用工具，缺少文件意味着没有MCP服务器，
    文件损坏或无法启动会收到明确警告，agent会继续处理已加载的内容
    """
    try:
        data = json.loads(path.read_text(encoding = 'utf-8'))
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f'忽略{path}:{e}')
        return []
    tools: list[Tool] = []
    for name, spec in (data.get('mcpServers') or {}).items():
        try:
            client = MCPClient(
                name,
                spec['command'],
                spec.get('args', []),
                spec.get('env')
            )
        except (MCPError, OSError, KeyError, TypeError) as e:
            log.warning(f"MCP服务器{name}被跳过：{e}")
            continue

        _live_clients.append(client)
        tools.extend(client.tools)

    return tools

def get_clients() -> list[MCPClient]:
    return _live_clients

@atexit.register
def _exit():
    for client in _live_clients:
        client.close()

