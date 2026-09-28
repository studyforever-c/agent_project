from llm import LLM
from prompts import understand_prompt
from state import State
from config import model_id_1

llm = LLM(model_id_1, 0.2, True)
def understand(state: State) -> dict:
    query = state['messages'][-1].content
    messages = [
        {'role': 'user', 'content': understand_prompt.format(
            query = query
        )}
    ]
    resp = llm.generate(messages)
    search_query = query
    if '搜索词：' in resp:
        search_query = resp.split('搜索词：')[1].strip()
    return {
        'messages': {'role': 'assistant', 'content': f'搜索：{search_query}'},
        'user_query': resp,
        'search_query': search_query,
        'step': 'understand'
    }
