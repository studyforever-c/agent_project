from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class State(TypedDict):
    messages: Annotated[list, add_messages]
    user_query: str
    search_query: str
    search_result: str
    final_answer: str
    step: str
