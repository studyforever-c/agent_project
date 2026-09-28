from tavily import TavilyClient
from dotenv import load_dotenv
from state import State
import os

load_dotenv()

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

def tavily_search(state: State) -> dict:

    search_query = state['search_query']

    try:
        resp = tavily.search(
            query = search_query,
            include_answer = True,
        )

        if 'answer' in resp:
            search_result = resp['answer']
        else:
            search_result = '\n'.join(
                [f'title:{result['title']}, content:{result['content']}'
                 for result in resp['results']]
            )
        print(f'查询结果:{search_result}')
        return {
            'messages': {'role': 'assistant', 'content': f'搜索结果{search_result}'},
            'search_result': search_result,
            'step': 'search',
        }
    except Exception as e:
        print(f'搜索失败！！！{e}')
        return {
            'messages': {'role': 'assistant', 'content': '搜索失败。'},
            'search_result': f'搜索失败{e}',
            'step':'search_failed'
        }