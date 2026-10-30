"""
REPL:读取->评估->输出->循环，面向用户的终端界面
"""
import argparse
import sys
import os
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings

from . import __version__
from .config import Config
from .llm import LLM
from .permissions import Permission, DEFAULT_STORE
from .agent import Agent
from .session import load_session, list_session
from .hooks import load_hooks
from .mcp import load_mcp_tools
from .session import save_session, set_session_id
from ..tools import ALL_TOOLS

console = Console()
err_console = Console(stderr = True)

def _parse_args():
    p = argparse.ArgumentParser(
        prog = 'code_agent',
        description = '小型编码agent，适合任何OpenAI兼容模型。'
    )
    p.add_argument('-m', '--model', help = '传入模型名称')
    p.add_argument('--base-url', help = '传入模型API的base url')
    p.add_argument('--api-key', help = '传入模型API key')
    p.add_argument('-p', '--prompt', help = '无人模式，非交互式，只跑一次')
    p.add_argument('--yes', action = 'store_true', help = '自动批准所有工具调用')
    p.add_argument('--demo', action = 'store_true', help = '运行离线示例脚本（不需要API key）')
    p.add_argument('-r', '--resume', metavar = 'ID', help = '继续一个已经保存的会话')
    p.add_argument('-v', '--version', action = 'version', version = f'%(prog)s {__version__}')
    return p.parse_args()

def _brief(kwargs: dict, max_len: int = 100) -> str:
    s = ','.join(f'{k} = {(repr(v) if len(repr(v)) < 30 else repr(v)[:15] + '...' + repr(v)[-15:])}'
                 for k, v in kwargs.items())
    return s[:max_len] + ('...' if len(s) > max_len else '')

def _ask_permission(tool_name: str, arguments: dict) -> str:
    """除了输入明确同意运行，其余全部代表不同意"""
    console.print(f'\n[bold yellow]授权请求：[/] [cyan]{tool_name}[/cyan]({_brief(arguments)})')
    try:
        answer = pt_prompt("  [y] allow once  [a] always allow this tool  [n] deny: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print('[dim]denied[/dim]')
        return 'deny'
    if answer in ("y", 'yes'):
        return 'once'
    if answer in ('a', 'always'):
        return 'always'
    return 'deny'

def _run_once(agent: Agent, prompt: str):
    """非交互式，运行一次后退出"""
    permission = agent.permission
    if permission is not None and permission.ask is None and not permission.allow_all:
        console.print('[dim]一次性模式：除非使用--yes，否则禁止使用编辑型文件[/dim]')

    def on_token(tok):
        print(tok, end = '', flush = True)

    def on_tool(name, kwargs):
        console.print(f'\n[dim]> {name}({_brief(kwargs)})[/dim]')

    def on_reasoning(tok):
        """思考会被输出到stderr，确保stdout是问题的答案"""
        err_console.print(f'[dim]{tok}[/dim]', end = '')

    try:
        agent.chat(prompt, on_token = on_token, on_tool = on_tool, on_reasoning = on_reasoning)
    except KeyboardInterrupt:
        console.print('\n[yellow]被打断[/yellow]')
        sys.exit(130)
    except Exception as e:
        console.print(f'\n[red]错误:{e}[/red]')
        sys.exit(1)
    print()

def _show_help():
    console.print(Panel("""
[bold]Command:[/bold]
    /help                   显示此帮助
    /reset                  清空交谈历史
    /model                  显示当前使用的模型
    /model <name>           在对话过程中切换模型
    /tokens                 显示当前token使用量
    /compact                手动压缩对话上下文
    /diff                   展示当前会话修改的文件
    /undo                   撤销最近一次文件修改
    /plan                   切换成计划模式，只能调用只读工具，可制定一个待批准的计划
    /save                   加会话保存到磁盘
    /sessions               显示所有已保存的会话
    /mcp                    显示MCP服务器的状态
    /mcp reconnect <name>   恢复一个已死的服务器
    quit                    退出code-agent
    
[bold]Input:[/bold]
    Enter                   提交信息
    Esc+Enter               插入新的一行（用于粘贴代码）
    """,
    title = 'code-agent help',
    border_style = 'dim'
    ))


def _mcp(arg: str):
    """查看服务器状态，或者使用`reconnect <name>`回复服务器状态"""
    from . import mcp
    parts = arg.split()
    clients = mcp.get_clients()
    if not parts:
        if not clients:
            console.print('[dim]没有正在运行的MCP服务器（配置 ~/.code-agent/mcp.json）[/dim]')
        else:
            for client in clients:
                if client.error is None:
                    console.print(f'  [cyan]{client.name}[/cyan]: 正常运行，{len(client.tools)}个工具')
                else:
                    console.print(
                        f'[cyan]{client.name}[/cyan]:[red]故障[/red]({client.error})',
                        f'可使用 /mcp reconnect {client.name}恢复'
                    )
        return
    if len(parts) == 2 and parts[0] == 'reconnect':
        client = next((c for c in clients if c.name == parts[1]), None)
        if client is None:
            console.print(f'[red]没有名为`{parts[1]}`的MCP服务器。')
            return
        try:
            client.reconnect()
        except (mcp.MCPError, OSError) as e:
            console.print(f'[red]重连失败：[/red]{e}')
        else:
            console.print(f'[green]已重连[/green][cyan]{client.name}[/cyna], (共计{len(client.tools)}个工具)')
        return
    console.print('[yellow]用法：/mcp [reconnect <name>][/yellow]')

def _repl(agent: Agent, config: Config):
    """交互的repl"""
    permission = agent.permission
    mode = '自动批准所有工具调用(--yes)' if (permission and permission.allow_all) else '在任何编辑型工具调用前询问。'
    hooks_msg = (f"[cyan]{len(agent.hooks.pre)} pre, {len(agent.hooks.post)} post[/cyan] "
                 f"from '~/.code-agent/hooks.json'") if agent.hooks else ''
    mcp_count = sum(1 for t in agent.tools if t.name.startswith('mcp__'))
    mcp_msg = f'[cyan]{mcp_count} tools[/cyan] from ~/.code-agent/mcp.json'\
                if mcp_count else ''

    console.print(Panel(f"""
[bold]code-agent[/bold] v{__version__}
Model: [cyan]{config.model}[/cyan]
Base: [dim]{config.base_url}[/dim]
Permission: [cyan]{mode}[/cyan]
Hooks: {hooks_msg}
MCP: {mcp_msg}
输入 [bold]/help[/bold] 查看命令，[bold]Ctrl+C[/bold] 退出，[bold]quit[/bold] 退出
""",
border_style = 'blue'
    ))

    history_path = os.path.expanduser('~/.code-agent_history')
    history = FileHistory(history_path)

    kb = KeyBindings()

    @kb.add('enter')
    def _submit(event):
        event.current_buffer.validate_and_handle()

    @kb.add('escape', 'enter')
    def _newline(event):
        event.current_buffer.insert_text('\n')

    while True:
        try:
            user_input = pt_prompt(
                'You (plan) > ' if agent.plan_mode else 'You > ',
                history = history,
                multiline = True,
                key_bindings = kb,
                prompt_continuation = '...  '
            ).strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input:
            continue

        if user_input.lower() in ('quit', 'exit', '/quit', '/exit'):
            break
        if user_input == '/help':
            _show_help()
            continue
        if user_input == '/reset':
            agent.reset()
            console.print(
                '[yellow]对话已重置。[/yellow]'
            )
            continue
        if user_input == '/plan':
            agent.plan_mode = not agent.plan_mode
            if agent.plan_mode:
                console.print("""
[yellow]计划模式启动。[/yellow]agent只能进行只读操作来交付一个计划，
输入 [bold]approve[/bold]同意这个计划，或者再次输入[bold]/plan[/bold]退出计划模式
                """)
            else:
                console.print('[yellow]计划模式已关闭。[/yellow]')
            continue

        if agent.plan_mode and user_input.lower() in ('approve', '/approve'):
            agent.plan_mode = False
            console.print('[yellow]计划模式已关闭。[/yellow]')
            user_input = 'approve'

        if user_input == '/tokens':
            prompt_tokens = agent.llm.total_prompt_tokens
            completion_tokens = agent.llm.total_completion_tokens
            show = f'''Tokens:
输入：{prompt_tokens}
输出：{completion_tokens}
'''
            console.print(show)
            continue

        if user_input == '/model' or user_input.startswith('/model '):
            new_model = user_input[7:].strip() if user_input.startswith('/model ') else ''
            if new_model:
                agent.llm.model = new_model
                config.model = new_model
                console.print(f'已将模型切换为[cyan]{new_model}[/cyan]')
            else:
                console.print(f'当前模型为：[cyan]{config.model}[/cyan]')
            continue
        if user_input == '/compact':
            from .context import estimate_tokens
            before = estimate_tokens(agent.messages)
            compressed = agent.context.maybe_compress(agent.messages, agent.llm)
            after = estimate_tokens(agent.messages)
            if compressed:
                console.print(f'[green]压缩成功：{before} -> {after}tokens({len(agent.messages)}条信息。)[/green]')
            else:
                console.print(f'[dim]当前无需压缩(约{before}tokens，共计{len(agent.messages)}条信息)[/dim]')
            continue
        if user_input == '/save':
            sid = save_session(agent.messages, config.model)
            console.print(f'[green]会话保存成功：{sid}[/green]')
            console.print(f'重启会话：code_agent -r {sid}')
            continue

        if user_input == '/diff':
            from ..tools.edit import get_changed_files
            changed_files = get_changed_files()
            if not changed_files:
                console.print('[dim]此次会话过程中没有文件被修改。[/dim]')
            else:
                console.print(f'[bold]此次会话过程中修改的文件（共计{len(changed_files)}）：[/bold]')
                for f in sorted(changed_files):
                    console.print(f'  [cyan]{f}[/cyan]')
            continue
        if user_input == '/undo':
            from .checkpoints import pending, undo
            console.print(undo())
            left = pending()
            if left:
                console.print(f'[dim]堆栈中还有{left}个检查点。[/dim]')
            continue
        if user_input == '/sessions':
            sessions = list_session()
            if not sessions:
                console.print('[dim]当前没有保存的会话[/dim]')
            else:
                for s in sessions:
                    console.print(f' [cyan]{s['id']}[/cyan] ({s['model']}, {s['saved_at']}){s['preview']}')
            continue

        if user_input == '/mcp' or user_input.startswith('/mcp '):
            _mcp(user_input[4:].strip())
            continue

        if user_input.startswith('/'):
            console.print(f'[yellow]未知命令：{user_input.split()[0]}(尝试使用/help获取帮助)[/yellow]')
            continue

        streamed: list[str] = []

        def on_token(tok):
            streamed.append(tok)
            print(tok, end = '', flush = True)

        def on_tool(name, kwargs):
            console.print(f'\n[dim]>{name}({_brief(kwargs)})[/dim]')

        def on_reasoning(tok):
            streamed.append(tok)
            console.print(f'[dim]{tok}[/dim]', end = '')

        try:
            resp = agent.chat(user_input,
                              on_token = on_token,
                              on_tool = on_tool,
                              on_reasoning = on_reasoning
                        )
            if streamed:
                print()
            else:
                console.print(Markdown(resp))
        except Exception as e:
            console.print(f'[red]错误：{e}[/red]')

def main():
    args = _parse_args()

    if args.demo:
        from .demo import run_demo
        raise SystemExit(run_demo())
    config = Config.from_env()

    if args.model:
        config.model = args.model
    if args.base_url:
        config.base_url = args.base_url
    if args.api_key:
        config.api_key = args.api_key

    if not config.api_key:
        console.print('[red bold]没有API key。[/]')
        console.print("""
设置其中的一个：OPENAI_API_KEY, DEEPSEEK_API_KEY
示例：
    # qwen:
        export OPENAI_API_KEY=sk-... OPENAI_BASR_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
    # deepseek:
        export DEEPSEEK_API_KEY=sk-... DEEPSEEK_BASR_URL=https://api.deepseek.com
        """)
        sys.exit(1)

    llm = LLM(
        model = config.model,
        api_key = config.api_key,
        base_url = config.base_url,
        temperature = config.temperature,
        max_tokens = config.max_tokens
    )


    if args.yes:
        permission = Permission(allow_all = True)
    elif args.prompt:
        permission = Permission()
    else:
        permission = Permission(ask = _ask_permission, persist_path = DEFAULT_STORE)

    agent = Agent(
        llm = llm,
        tools = [*ALL_TOOLS, *load_mcp_tools()],
        max_context_tokens = config.max_context_tokens,
        permission = permission,
        hooks = load_hooks()
    )

    if args.resume:
        loaded = load_session(args.resume)

        if loaded:
            agent.messages, loaded_model = loaded
            set_session_id(args.resume)
            # 除非在加载会话时手动更换模型，否则从已保存的会话中获取模型
            if not args.model:
                agent.llm.model = loaded_model
                config.model = loaded_model
            console.print(f'[green]已加载会话：{args.resume}(model:{agent.llm.model})[/green]')
        else:
            console.print(f'[red]会话{args.resume}不存在[/red]')
            sys.exit(1)

    if args.prompt:
        _run_once(agent, args.prompt)
        return

    # 交互式repl
    _repl(agent, config)
    console.print('再见！')
