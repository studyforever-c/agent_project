from src.planner import Planner
from src.executor import Executor
from src.llm import LLM
from config import model_id_1

llm = LLM(model_id_1)
planner = Planner(llm)
question = ' 一个水果店周一卖出了15个苹果。周二卖出的苹果数量是周一的两倍。周三卖出的数量比周二少了5个。请问这三天总共卖出了多少个苹果？'

plan = planner.plan(question)

executor = Executor(question, plan, llm)

executor.execute()