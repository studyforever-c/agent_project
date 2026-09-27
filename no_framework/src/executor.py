from llm import LLM
from prompts import system_prompt_executor, user_prompt_executor

class Executor:

    def __init__(self,
                 question: str,
                 plan: list[str],
                 llm: LLM):
        self.question = question,
        self.plan = plan
        self.llm = llm

    def execute(self):
        history = [
            {'role': 'system', 'content': system_prompt_executor.format(
                question = self.question,
                plan = ' '.join(self.plan)
            )},
        ]

        for i, step in enumerate(self.plan):
            print(f'当前进度：{i+1}/{len(self.plan)}')
            history.append({
                'role': 'user', 'content': f'当前步骤：{step}'
            })
            resp = self.llm.generate(history)
            history.append({
                'role': 'assistant', 'content': resp
            })