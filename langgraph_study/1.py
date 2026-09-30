from typing import TypedDict, Annotated
from langgraph.graph import add_messages, StateGraph, START, END
from langchain_core.messages import convert_to_openai_messages
from openai import OpenAI
from dotenv import load_dotenv

class ChatState(TypedDict):
    messages: Annotated[list, add_messages]

load_dotenv()
client = OpenAI()

def llm(state: ChatState) -> ChatState:
    resp = client.chat.completions.create(
        model = 'qwen3.8-max',
        messages = convert_to_openai_messages(state['messages']),
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
        messages = [{'role': 'assistant', 'content': content}]
    )

def build():
    workflow = StateGraph(ChatState)

    workflow.add_node('llm', llm)

    workflow.add_edge(START, 'llm')
    workflow.add_edge('llm', END)

    app = workflow.compile()
    return app

def main():
    app = build()
    state = {
        'messages': [
            {'role': 'system', 'content': '你是一只小猪。'}
        ]
    }

    print('================你好，我是您的专属AI助理！=================')
    while True:
        print('有什么问题需要我来解决：(q退出对话)')
        query = input()
        if query == 'q':
            break
        state['messages'].append({'role': 'user', 'content': query})
        app.invoke(
            state,
            config = {'configurable': {'thread_id': 'test'}}
        )

if __name__ == '__main__':
    main()