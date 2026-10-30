from __future__ import annotations
import re
from math import ceil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .llm import LLM


# 匹配汉字和标点
_CJK_RE = re.compile(r'[一-鿿㐀-䶿豈-﫿　-〿＀-･]')
# 匹配半角符号
_SYMBOL_RE = re.compile(r'[^\w\s]')

def _approx_tokens(text: str) -> int:
    """
    估算当前聊天历史里的token总量
    经验：1.5个汉字1token，2.8个符号1token，3.4个英文1token
    """
    cjk = len(_CJK_RE.findall(text))
    rest = len(text) - cjk # 英文、空格和半角标点

    # 判断是否为符号密集文本
    dense = rest > 0 and len(_SYMBOL_RE.findall(text)) / len(text) > 0.25
    return ceil(cjk / 1.5) + int(rest / (2.8 if dense else 3.4))

def estimate_tokens(messages: list[dict]) -> int:
    """估算当前上下文token总量"""
    total = 0
    for msg in messages:
        if msg.get('content'):
            total += _approx_tokens(msg['content'])
        if msg.get('tool_calls'):
            total += _approx_tokens(str(msg['tool_calls']))
    return total

class ContextManager:
    def __init__(self, max_tokens: int = 128_000):
        self.max_tokens = max_tokens
        self._snip_at = int(max_tokens * 0.5)
        self._summarize_at = int(max_tokens * 0.7)
        self._collapse_at = int(max_tokens * 0.9)

    @staticmethod
    def _snip_tool_outputs(messages: list[dict]) -> bool:
        """阶段旧的工具调用结果"""
        changed = False
        for msg in messages:
            if msg.get('role') != 'tool':
                continue
            content = msg.get('content', '')
            if len(content) <= 1500:
                continue
            lines = content.splitlines()
            if len(lines) <= 6:
                continue

            # 保留首位三行，通常记录重要结果
            snipped = '\n'.join(lines[:3]) + \
                    f'\n...({len(lines)}行，为节省上下文进行截断)...\n' + \
                    '\n'.join(lines[-3:])
            msg['content'] = snipped
            changed = True
        return changed

    @staticmethod
    def _safe_split(messages: list[dict], keep_recent: int) -> int:
        """确保保留下来的context每个tool message对应一个assistant message"""
        split = max(0, len(messages) - keep_recent)
        while split > 0 and messages[split].get('role') == 'tool':
            split -= 1
        return split

    @staticmethod
    def _flatten(messages: list[dict]) -> str:
        """提取要总结的历史的角色和内容，去除掉message里的tool_call_id等没有的东西"""
        parts = []
        for msg in messages:
            role = msg.get('role', '?')
            content = msg.get('content', '') or ''
            if content:
                parts.append(f'{role}:{content[:400]}')
        return '\n'.join(parts)

    @staticmethod
    def _extract_key_info(messages: list[dict]) -> str:
        # 调用llm进行总结失败，改为手动提取
        import re
        files = set()
        errors = []
        for msg in messages:
            text = msg.get('content', '') or ''
            # 提取文件路径
            for item in re.finditer(r'[\w./\-]+\.\w{1,5}', text):
                files.add(item.group())
            # 提取错误列表
            for line in text.splitlines():
                if 'error' in line.lower():
                    errors.append(line.strip()[:150])
        extracted = []
        if files:
            extracted.append(f'编辑的文件列表：{';'.join(files)}')
        if errors:
            extracted.append(f'发生过的错误：{';'.join(errors)}')
        return '\n'.join(extracted)

    def _get_summary(self, messages: list[dict], llm: LLM|None) -> str:
        """总结历史，提取关键信息"""
        flatted = self._flatten(messages)
        if llm:
            try:
                messages = [
                    {
                        'role': 'system',
                        'content': '''
                        你是一个擅长进行长文本总结的助理，把用户给的聊天记录文本进行精炼总结，
                        注意事项：
                        - 保留已编辑的文件路径，做出的关键决策，遇到的错误，当前任务状态。
                        - 删除冗余的命令输出，代码清单，无意义的交流过程
                        '''
                    },
                    {'role': 'user', 'content': flatted[:15000]}
                ]
                resp = llm.chat(messages = messages)
                return resp.content
            except:
                pass
        # 没传llm或llm调用失败时降级处理
        return self._extract_key_info(messages)

    def _summarize_old(self, messages: list[dict],
                       llm: LLM|None,
                       keep_recent: int = 8
    ) -> bool:
        """对历史进行总结"""
        if len(messages) <= keep_recent:
            return False
        split = self._safe_split(messages, keep_recent)
        left = messages[:split]
        right = messages[split:]
        summary = self._get_summary(left, llm)
        messages.clear()
        messages.append(
            {'role': 'user', 'content': f'[这是对历史聊天记录的总结]\n{summary}'}
        )
        messages.append(
            {'role': 'assistant', 'content': '我知道了，这是之前聊天记录的总结。'}
        )
        messages.extend(right)
        return True

    def _hard_collapse(self, messages: list[dict], llm: LLM|None) -> bool:
        """对历史进行总结，但保留的新消息更少"""
        split = self._safe_split(messages, 4 if len(messages) > 4 else 2)
        left = messages[:split]
        right = messages[split:]
        summary = self._get_summary(left, llm)
        messages.clear()
        messages.append({
            'role': 'user',
            'content': f'[对历史聊天记录进行较大程度压缩]\n{summary}'
        })
        messages.append({
            'role': 'assistant',
            'content': '历史聊天记录已被压缩，继续之前的聊天话题。'
        })
        messages.extend(right)
        return True
    def maybe_compress(self, messages: list[dict], llm: LLM|None = None) -> bool:
        """发生任意一种状态压缩就返回True"""
        current = estimate_tokens(messages)
        compressed = False
        if current > self._snip_at and self._snip_tool_outputs(messages):
            compressed = True
        if current > self._summarize_at and self._summarize_old(messages, llm):
            compressed = True
        if current > self._collapse_at and self._hard_collapse(messages, llm):
            compressed = True
        return compressed