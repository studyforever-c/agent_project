from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LLM:
    def __init__(self,
                 model_id: str,
                 temperature: float = 0.7,
                 stream: bool = False
                 ):
        self.client = OpenAI()
        self.model_id = model_id
        self.temperature = temperature
        self.stream = stream

    def generate(self, messages) -> str:
        try:
            resp = self.client.chat.completions.create(
                model = self.model_id,
                messages = messages,
                temperature = self.temperature,
                stream = self.stream,
            )
        except Exception as e:
            print(f'调用模型时出错啦！{e}')
            return ''

        if self.stream:
            content = []
            for chunk in resp:
                if not chunk.choices:
                    continue
                content.append(chunk.choices[0].delta.content)
                print(
                    content[-1],
                    end = '',
                    flush = True
                )
            print()
            content = ''.join(content)
        else:
            content = resp.choices[0].message.content
            print(content)
        return content if content else ''