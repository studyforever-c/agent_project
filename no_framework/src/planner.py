from prompts import system_prompt_plan
from src.llm import LLM
import re


class Planner:

    def __init__(self,
                 llm: LLM):
        self.llm = llm

    def plan(self, question: str) -> list[str]:
        messages = [
            {'role': 'system', 'content': system_prompt_plan},
            {'role': 'user', 'content': question}
        ]
        resp = self.llm.generate(messages)
        plan = re.search(r'\[(.*)]', resp, re.DOTALL)
        plan = plan.group(1).strip().split(',') if plan else ['']

        return [
            f'第{i+1}步：{step}'
            for i, step in enumerate(plan)
        ]