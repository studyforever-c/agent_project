from no_framework.src.llm import LLM
from tools_management import ToolsManagement
from prompts import system_prompt_react

import re
class React:
    def __init__(self,
                 llm: LLM,
                 tools_management: ToolsManagement,
                 max_step: int = 5,
                 ):

        self.max_step = max_step
        self.llm = llm
        self.tools_management = tools_management
    def run(self, question: str):

        history = [
            {'role': 'system', 'content': system_prompt_react.format(tools = self.tools_management.get_avail_tools())},
            {'role': 'user', 'content': question}
        ]

        for i in range(self.max_step):
            print(f"{'-'*5}第{i+1}轮{'-'*5}")
            try:
                resp = self.llm.generate(history)
            except Exception as e:
                print(f'模型调用失败:\n{e}')
                break

            action = re.search(r'Action:\s*(.*)', resp, re.DOTALL).group(1).strip()
            if not action:
                observation = '未识别到有效Action，请严格按照给定格式输出答案。'
                print(observation)
                history.append(
                    {'role': 'user', 'content': observation}
                )
                continue
            if action.startswith('Finish'):
                break
            history.append({
                'role': 'assistant', 'content': resp
            })
            name, args = self.parse_action(action)
            if not name or not args:
                observation = '工具调用格式错误'
                history.append({
                    'role': 'user', 'content': observation
                })
                print(observation)
                continue
            tool_main = self.tools_management.get_tool(name)
            if tool_main is None:
                observation = f'使用了未定义的工具{name}'
            else:
                observation = '工具调用结果：' + tool_main(*args)
            history.append(
                {'role': 'user', 'content': observation}
            )
            print(observation)
    def parse_action(self, text: str):
        action = re.search(r'(\w+)\[(.*)]', text)

        if action:
            name, args = action.group(1).strip(), action.group(2).strip()
            return name, args.split(',')
        return None, None