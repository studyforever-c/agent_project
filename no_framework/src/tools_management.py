class ToolsManagement:
    def __init__(self):
        self.tools = {}

    def register(self, name: str, description: str, main: callable) -> None:
        """
        注册一个新工具
        """
        if name in self.tools:
            raise f'{name}已存在'
        self.tools[name] = {
            'description': description,
            'main': main
        }
        print(f'{name}工具注册成功')

    def get_tool(self, name):
        """
        根据工具名获取工具
        """
        return self.tools.get(name, {}).get('main')

    def get_avail_tools(self):
        """获取所有工具"""
        return '\n'.join(
            f'名称：{name},描述：{item['description']}'
            for name, item in self.tools.items()
        )
