"""
LLM定义模块
对外接口为chat，接收上下文即可用工具给出响应
1、当调用模型时出现指定的参数错误，或者连接模型超时，调用模型频繁等问题时采用指数退避，重新尝试的方法
2、模型采用流式输出，输出的content，tool_calls均不是一次给出完整内容，需要通过字符串拼接的方式获取
完整的content，tool_calls，其中在开启流式输出后，tool_call可以通过index进行区分
3、开启流式输出后，获取到的usage由最后一个chunk携带
"""

from openai import OpenAI, BadRequestError, RateLimitError, APITimeoutError, APIConnectionError, APIError
from dataclasses import dataclass, field
from typing import Any
import json
import time

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

@dataclass
class LLMResponse:
    content: str = ''
    tool_calls: list[ToolCall] = field(default_factory = list)
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def message(self) -> dict:
        """将LLM响应转为字典"""
        msg: dict[str, Any] = {'role': 'assistant', 'content': self.content or ''}
        if self.tool_calls:
            msg['tool_calls'] = [
                {
                    'id': tc.id,
                    'type': 'function',
                    'function': {
                        'name': tc.name,
                        'arguments': json.dumps(tc.arguments)
                    }
                }
                for tc in self.tool_calls
            ]
        return msg

def _adapt_rejected_param(params: dict, err: BadRequestError) -> bool:
    """
    新模型参数变了
    返回True意味着被拒参数已被处理，False表明被拒参数的处理不在该函数
    """
    err_content = str(err).lower()

    if "'max_tokens'" in err_content and "max_tokens" in params:
        params['max_completion_tokens'] = params.pop('max_tokens')
        return True
    if "'temperature'" in err_content and 'temperature' in params:
        params.pop('temperature')
        return True
    return False

class LLM:
    def __init__(self,
                 model: str,
                 api_key: str,
                 base_url: str|None = None,
                 **kwargs
    ):
        self.model = model
        self.client = OpenAI(api_key = api_key, base_url = base_url)
        self.extra = kwargs
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    def _call_with_retry(self, params: dict, max_retries: int = 3):
        """尝试调用模型，发生临时错误时使用指数退避重试。"""
        wait = 1
        for attempt in range(max_retries):
            try:
                return self.client.chat.completions.create(
                    **params
                )
            except (RateLimitError, APITimeoutError, APIConnectionError):
                # 短时间多次调用模型，模型连接超时，连接出错，允许重试
                if attempt == max_retries - 1:
                    raise
                time.sleep(wait)
                wait *= 2
            except APIError as e:
                # 错误码为4xx表客户端错误，需修改代码，5xx表服务端问题，可重试
                status_code: int|None = getattr(e, 'status_code', None)
                if status_code and status_code >= 500 and attempt < max_retries - 1:
                    time.sleep(wait)
                    wait *= 2
                else:
                    raise
    def _drain(self, stream, on_token, on_reasoning) -> LLMResponse:
        """处理LLM流式输出"""
        content = []
        tc_map = {}
        prompt_tokens = 0
        completion_tokens = 0

        for chunk in stream:
            usage = getattr(chunk, 'usage', None)
            if usage:
                # 模型可能有返回但是返回内容是None
                prompt_tokens = getattr(usage, 'prompt_tokens', 0) or 0
                completion_tokens = getattr(usage, 'completion_tokens', 0) or 0
            if not getattr(chunk, 'choices', None):
                continue
            delta = chunk.choices[0].delta
            reasoning = getattr(delta, 'reasoning_content', None) or getattr(delta, 'reasoning', None)
            if reasoning and on_reasoning:
                on_reasoning(reasoning)

            # 如果delta.content不为空，累加content
            if getattr(delta, 'content', None):
                content.append(delta.content)
                if on_token:
                    on_token(delta.content)

            # 如果delta.tool_calls不为空，累加tool_calls
            if getattr(delta, 'tool_calls', None):
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tc_map:
                        tc_map[idx] = {'id': '', 'name': '', 'args': ''}
                    if tc_delta.id:
                        tc_map[idx]['id'] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tc_map[idx]['name'] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            tc_map[idx]['args'] += tc_delta.function.arguments
        parsed = []
        for idx, tc in tc_map.items():
            try:
                args = json.loads(tc['args'])
            except (json.JSONDecodeError, KeyError):
                args = {}
            parsed.append(ToolCall(
                id = tc['id'],
                name = tc['name'],
                arguments = args
            ))
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens

        return LLMResponse(
            content = ''.join(content),
            tool_calls = parsed,
            prompt_tokens = prompt_tokens,
            completion_tokens = completion_tokens
        )

    def chat(self,
             messages: list[dict],
             tools: list[dict] | None = None,
             on_token = None,
             on_reasoning = None) -> LLMResponse:

        params: dict[str, Any] = {
            'model': self.model,
            'messages': messages,
            'stream': True,
            **self.extra
        }
        if tools:
            params['tools'] = tools

        params['stream_options'] = {'include_usage': True}

        last_err = None

        wait = 1
        for attempt in range(3):
            while True:
                try:
                    stream = self._call_with_retry(params)
                    break
                except BadRequestError as e:
                    # 参数错误
                    if _adapt_rejected_param(params, e):
                        continue
                    if 'stream_options' not in params:
                        raise
                    params.pop('stream_options')
            try:
                return self._drain(stream, on_token, on_reasoning)
            except (RateLimitError, APITimeoutError, APIConnectionError) as e:
                last_err = e
            except APIError as e:
                status_code: int|None = getattr(e, 'status_code', None)
                if not status_code or status_code < 500:
                    raise
                last_err = e
                if attempt < 2:
                    time.sleep(wait)
                    wait *= 2
        raise last_err