"""
langgraph简单流式输出学习
"""

from langgraph.graph import StateGraph, START as S, END as E, add_messages
from typing import TypedDict, Annotated

class ChatState(TypedDict):
    messages: Annotated[list, add_messages]

def think(state: ChatState) -> dict:
    return {
        'messages': [
            {'role': 'assistant', 'content': 'think...'}
        ]
    }
def generate(state: ChatState) -> dict:
    return {
        'messages': [
            {'role': 'assistant', 'content': 'generate...'}
        ]
    }
def build():
    workflow = StateGraph(ChatState)
    workflow.add_node('think', think)
    workflow.add_node('generate', generate)

    workflow.add_edge(S, 'think')
    workflow.add_edge('think', 'generate')
    workflow.add_edge('generate', E)

    return workflow.compile()
def main():
    app = build()
    state = {
        'messages': []
    }
    events = app.stream(
        state,
        {'configurable': {'thread_id': 'test'}},
        stream_mode = 'updates'
    )

    for event in events:
        print(event)
main()