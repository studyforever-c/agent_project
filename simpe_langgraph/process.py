from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

from state import State
from simpe_langgraph.nodes.generate import generate
from simpe_langgraph.nodes.tavily_search import tavily_search
from simpe_langgraph.nodes.understand import understand
def process():
    workflow = StateGraph(State)

    workflow.add_node('understand', understand)
    workflow.add_node('search', tavily_search)
    workflow.add_node('generate', generate)

    workflow.add_edge(START, 'understand')
    workflow.add_edge('understand', 'search')
    workflow.add_edge('search', 'generate')
    workflow.add_edge('generate', END)

    memory = InMemorySaver()
    app = workflow.compile(checkpointer = memory)
    return app

if __name__ == '__main__':
    app = process()
    app.invoke(
        {
            'messages': [{'role': 'user', 'content': 'LLM是什么'}]
        },
        config={
            "configurable": {"thread_id": "test"}
        }
    )