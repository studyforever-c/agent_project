from typing import TypedDict, Annotated, Optional
from langgraph.graph import add_messages, StateGraph, START as S, END as E
from langchain_core.messages import convert_to_openai_messages
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
client = OpenAI()


def update(a: dict, b: dict) -> dict:
    return {**a, **b}
class ChatState(TypedDict):
    query: str
    messages: Annotated[list, add_messages]
    query_count: int

def init() -> ChatState:
    return ChatState(
        messages = [{'role': 'system', 'content': '你是一个AI助理，擅长解决用户提出问题。'}],
        query_count = 0
    )



def user_input(state: ChatState) -> ChatState:
    query = state['query']
    query_count = state['query_count'] + 1
    return ChatState(
        messages = [{'role': 'user', 'content': query}],
        query_count = query_count
    )

def llm(state: ChatState) -> ChatState:
    messages = convert_to_openai_messages(state['messages'])
    resp = client.chat.completions.create(
        model = 'qwen3.8-max',
        messages = messages,
        temperature = 0.9,
        stream = True
    )
    content = []
    for chunk in resp:
        if not chunk.choices:
            continue
        chunk_content = chunk.choices[0].delta.content
        content.append(chunk_content)
        print(chunk_content, end = '', flush = True)
    print()
    content = ''.join(content)
    return ChatState(
        messages = [{'role': 'assistant', 'content': content}],
    )

def should_continue(state: ChatState) -> str:
    prompt = """
你是一个决策大师，根据历史任务完成情况决定是否继续任务，
输出只能是`True,False`中的其中一个，继续任务则输出`True`，
终止任务则输出`False`，不要有多余的输出。
任务完成情况：
{history}
    """
    messages = [
        {'role': 'user', 'content': prompt.format(
            history = state['messages']
        )}
    ]
    resp = client.chat.completions.create(
        model = 'qwen3.8-max',
        messages = messages
    )
    content = resp.choices[0].message.content
    return content if content else "True"

def build():
    workflow = StateGraph(ChatState)

    workflow.add_node('user_input', user_input)
    workflow.add_node('llm', llm)

    workflow.add_edge(S, 'user_input')
    workflow.add_edge('user_input', 'llm')
    workflow.add_conditional_edges(
        'llm',
        should_continue,
        {
            'True': 'llm',
            'False': E
        }
    )
    return workflow.compile()

def main():
    app = build()
    state = init()
    config = {
        'configurable': {'thread_id': 'test'}
    }
    query = '1+1=?'
    state['query'] = query
    app.invoke(
        state,
        config = config
    )

if __name__ == '__main__':
    main()