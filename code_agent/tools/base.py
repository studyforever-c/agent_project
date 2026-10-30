from abc import ABC, abstractmethod
# ABC表明该类为抽象类，不能直接实例化
# abstractmethod表明子类中必须实现该方法，否则不能实例化
import threading

# 并发时编辑文件的互斥锁
FILE_MUTATION_LOCK = threading.Lock()

class Tool(ABC):
    """工具的基类"""

    name: str
    description: str
    parameters: dict

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """调用工具得出结果"""
        pass

    @property
    def schema(self) -> dict:
        """将函数转为能够传给openai sdk的格式"""
        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': self.description,
                'parameters': self.parameters
            }
        }