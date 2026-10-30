## 声明
本项目参考自[CoreCoder](https://github.com/he-yufeng/CoreCoder)

## 修改日志
1. 将读文件工具中行号和内容之间的'\t'换为':'，实际运行时发现'\t'有时候会导致模型认为内容之前有空格，导致读python代码时认为原代码缩进有误。 
2. 在显示调用工具的函数(_brief)，原函数实测cd命令时，路径较长时看起来像是一直在对一个目录进行操作，选择在参数超长时选择显示前15和后15个字符。 
3. 修改_brief时忽略了参数类型对其进行`len()`操作，狠狠查半天错误。
4. 测试/save时发现每次save都会创建一个新文件，即使是对同一个会话进行save，于是在session.py中加入全局变量_SESSION_ID，在启动时使用-r参数时会把resume中的session_id设置为_SESSION_ID。
5. 在设置_SESSION_ID时学到了函数参数的默认值在函数定义时确定，save_session初始时希望把_SESSION_ID作为session_id的默认值（session_id: str|None = _SESSION_ID），之后通过改变_SESSION_ID的方式改变session_id，实测发现session_id并不会在之后随之改变。
6. 在agent.py文件中，将每次chat获取tool_schema改为初始化时获取一次，之后每次chat都直接使用。
7. 发现/save执行时缺少对_SESSION_ID的更新，对于一个新对话，多次保存还是会存多个文件，已改正。


## 项目结构
```text
code_agent/
├── src/
│   ├── __init__.py
│   ├── agent.py        # agent定义
│   ├── checkpoints.py  # 记录文件修改记录，用于回滚
│   ├── cli.py          # repl定义
│   ├── config.py       # 项目配置文件
│   ├── context.py      # 上下文管理
│   ├── demo.py         # 项目运行实例展示
│   ├── hooks.py        # 加载和运行hook函数
│   ├── llm.py          # 大模型定义
│   ├── mcp.py          # mcp服务器加载
│   ├── permissions.py  # 决定工具是否能执行
│   ├── prompt.py       
│   ├── session.py      # 会话管理，保存，加载
│   ├── shell.py        # shell命令执行
│   └── tools/          # 所有工具定义
│       ├── __init__.py
│       ├── agent.py
│       ├── base.py     # 工具基类
│       ├── bash.py
│       ├── edit.py
│       ├── glob_tool.py
│       ├── grep.py
│       ├── read.py
│       ├── todo.py
│       └── write.py
├── __init__.py         
└── __main__.py         # 项目启动文件
```

## 快速启动

将仓库克隆到本地（ssh版）
```
git clone git@github.com:studyforever-c/agent_project.git && cd agent_project
```

安装依赖
```
pip install -r requirements.txt
```

运行demo
```
python -m code_agent.demo_run
```

运行主程序(需确保code_agent目录下有__main__.py文件)
```
python -m code_agent
```