from simpe_langgraph.state import State
from simpe_langgraph.prompts import failed_prompt, success_prompt
from simpe_langgraph.llm import LLM
from config import model_id_1

llm = LLM(model_id_1, 0.2, True)

def generate(state: State) -> dict:
    user_query = state['user_query']
    search_result = state['search_result']
    step = state['step']

    if step == 'search_failed':
        messages = [{'role': 'system', 'content': failed_prompt.format(
            user_query = user_query
        )}]
    else:
        messages = [{'role': 'system', 'content': success_prompt.format(
            search_result = search_result,
            user_query = user_query
        )}]
    answer = llm.generate(messages)
    return {
        'messages': {'role': 'assistant', 'content': answer},
        'final_answer': answer,
        'step': 'completed'
    }