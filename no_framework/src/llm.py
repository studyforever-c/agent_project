from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class LLM:
    def __init__(self, model_id: str,
                 temperature: float = 0.7,
                 stream: bool = False):
        try:
            self.client = OpenAI()
            self.temperature = temperature
            self.stream = stream
        except Exception as e:
            print(f'出错了:\n{e}')
        self.model_id = model_id
    def generate(self, messages: list[dict]) -> str:
        try:
            completions = self.client.chat.completions.create(
                model = self.model_id,
                messages = messages,
                temperature = self.temperature,
                stream=self.stream
            )
        except:
            raise '模型调用失败！！！'
        if self.stream:
            content = []
            for chunk in completions:
                if not chunk.choices:
                    continue
                else:
                    chunk_content = chunk.choices[0].delta.content
                    content.append(chunk_content)
                    print(chunk_content, end = '', flush = True)
            print()
            content = ''.join(content)
        else:
            content = completions.choices[0].message.content
            print(content)
        return content if content else ''