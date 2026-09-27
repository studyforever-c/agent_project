from no_framework.tools import get_weather, get_attraction
from no_framework.src.tools_management import ToolsManagement
from config import model_id_1
from no_framework.src.llm import LLM
from no_framework.src.react import React
tools_management = ToolsManagement()
tools_management.register(get_weather.name,
                          get_weather.description,
                          get_weather.get_weather)
tools_management.register(get_attraction.name,
                          get_attraction.description,
                          get_attraction.get_attraction)

llm = LLM(model_id_1, 0.2, True)

react = React(llm ,tools_management, 5)

react.run('查询合肥天气，并推荐合适的旅游景点')