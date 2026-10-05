from typing import TypedDict, Annotated, Optional
from langgraph.graph import add_messages, StateGraph, START as S, END as E

def dict_update(d1: dict, d2: dict) -> dict:
    return {**d1, **d2}

class ChatState(TypedDict):
    messages: Annotated[list, add_messages]
    task: Optional[str]
    step_count: int
    results: Annotated[dict, dict_update]
    error: Optional[str]
    tools: list[str]

def init_state() -> ChatState:
    return ChatState(
        messages = [
            {'role': 'system', 'content': '你是一个专业的AI助理，擅长解决用户各种问题。'}
        ],
        results = {},
        step_count = 0,
        tools = []
    )

def classify_task(state: ChatState) -> ChatState:
    task = state['messages'][-1].content
    task = task if task in state['tools'] else 'general'
    print(f'已获取任务分类:{task}')
    return ChatState(
        task = task
    )

def search(state: ChatState) -> ChatState:
    print('已进行查询')
    results = state['results']
    if 'search_result' not in results:
        results['search_result'] = [
                'search_result_1',
                'search_result_2'
        ]
    else:
        results['search_result'].extend(
            [
                'search_result_1',
                'search_result_2'
            ]
        )

    return ChatState(
        step_count = state['step_count'] + 1,
        results = {
            'search_result': [
                'search_result_1',
                'search_result_2',
            ]
        }
    )

def calculate(state: ChatState) -> ChatState:
    print('计算完成')
    return ChatState(
        step_count = state['step_count'] + 1,
        results = {
            'calculate_result': [
                'calculate_result_1',
                'calculate_result_2',
            ]
        }
    )

def general(state:ChatState) -> ChatState:
    return ChatState(
        step_count = state['step_count'] + 1,
        results = {
            'general_result': [
                '这是一个普通问题，无需调用工具，凭自身知识回答即可'
            ]
        }
    )

def select(state: ChatState) -> str:
    error = state.get('error', None)
    if error is not None:
        return 'error'
    tool = state.get('task', 'general')

    return tool if tool else 'general'

def generate(state: ChatState) -> ChatState:
    results = state.get('results', '')
    task = state.get('task', '')
    task_result = results.get(f'{task}_result', [])
    resp = ' '.join(task_result)
    print('最终结果：'+resp)
    return ChatState(
        messages = {'role': 'assistant', 'content': resp}
    )

def handle_error(state: ChatState) -> ChatState:
    error = state['error']
    print(f'error: {error}')
    return ChatState(
        messages = {'role': 'assistant', 'content': f'请求出现错误：{error}'},
        error = None
    )

def build_liner_graph():
    workflow = StateGraph(ChatState)

    workflow.add_node('classify_task', classify_task)
    workflow.add_node('search', search)
    workflow.add_node('generate', generate)

    workflow.add_edge(S, 'classify_task')
    workflow.add_edge('classify_task', 'search')
    workflow.add_edge('search', 'generate')
    workflow.add_edge('generate', E)

    return workflow.compile()

def liner():
    app = build_liner_graph()
    state = init_state()
    state['messages'].append(
        {'role': 'user', 'content': 'search'}
    )
    state['tools'].extend(['search', 'calculate', 'general'])
    config = {
        'configurable': {'thread_id': 'test'}
    }
    final = app.invoke(
        state,
        config = config
    )

    print(f'final:{final}')

def build_conditional_graph():
    workflow = StateGraph(ChatState)

    workflow.add_node('classify_task', classify_task)
    workflow.add_node('search', search)
    workflow.add_node('calculate', calculate)
    workflow.add_node('general', general)
    workflow.add_node('generate', generate)
    workflow.add_node('handle_error', handle_error)

    workflow.add_edge(S, 'classify_task')
    workflow.add_conditional_edges(
        'classify_task',
        select,
        {
            'error': 'handle_error',
            'search': 'search',
            'calculate': 'calculate',
            'general': 'general',
        }
    )

    workflow.add_edge('search', 'generate')
    workflow.add_edge('calculate', 'generate')
    workflow.add_edge('general', 'generate')
    workflow.add_edge('generate', E)
    workflow.add_edge('handle_error', E)

    return workflow.compile()

def condition():
    app = build_conditional_graph()
    state = init_state()
    state['messages'].append(
        {'role': 'user', 'content': 'general'}
    )
    state['tools'].extend(['search', 'calculate', 'calculate'])
    state['error'] = '发生错误'
    config = {
        'configurable': {'thread_id': 'test'}
    }

    app.invoke(
        state,
        config
    )

def should_continue(state: ChatState) -> str:
    step_count = state['step_count']
    max_step = 3
    if step_count < max_step:
        return 'True'
    return 'False'
def create_loop_graph():
    workflow = StateGraph(ChatState)

    workflow.add_node('classify_task', classify_task)
    workflow.add_node('search', search)
    workflow.add_node('generate', generate)
    workflow.add_node('should_continue', should_continue)

    workflow.add_edge(S, 'classify_task')
    workflow.add_edge('classify_task', 'search')
    workflow.add_conditional_edges(
        'search',
        should_continue,
        {
            'True': 'search',
            'False': 'generate'
        }
    )
    return workflow.compile()
def loop():
    state = init_state()
    app = create_loop_graph()
    state['messages'].append(
        {'role': 'user', 'content': 'search'}
    )
    state['tools'] = ['search']
    config = {
        'configurable': {'thread_id': 'test'}
    }
    app.invoke(
        state,
        config
    )

def father_and_son_graph():

    son_workflow = StateGraph(ChatState)
    son_workflow.add_node('search', search)
    son_workflow.add_edge(S, 'search')
    son_workflow.add_edge('search', E)
    son_graph = son_workflow.compile()

    father_workflow = StateGraph(ChatState)
    father_workflow.add_node('classify', classify_task)
    father_workflow.add_node('search', son_graph)
    father_workflow.add_node('generate', generate)
    father_workflow.add_edge(S, 'classify')
    father_workflow.add_edge('classify', 'search')
    father_workflow.add_edge('search', 'generate')
    father_workflow.add_edge('generate', E)
    return father_workflow.compile()

def main():
    app = father_and_son_graph()
    state = init_state()
    state['tools'] = ['search']
    state['messages'].append(
        {'role': 'user', 'content': 'search'}
    )
    config = {
        'configurable': {'thread_id': 'test'}
    }

    app.invoke(
        state,
        config
    )
if __name__ == '__main__':
    # liner()
    # condition()
    # loop()
    main()