"""按文件名/路径匹配文件"""

from pathlib import Path
from .base import Tool

class GlobTool(Tool):
    name = 'glob'
    description = f"""
通过通配符查找符合条件的文件名
支持**递归查找
"""
    parameters = {
        'type': 'object',
        'properties': {
            'pattern': {
                'type': 'string',
                'description': '通配符'
            },
            'path': {
                'type': 'string',
                'description': '需要查找的目录路径，默认工作目录。'
            }
        },
        'required': ['pattern']
    }

    def execute(self, pattern: str, path: str = '.') -> str:
        try:
            base = Path(path).expanduser().resolve()
            if not base.exists():
                return f'错误：{path}不存在'
            if not base.is_dir():
                return f'错误：{path}不是一个目录'
            hits = list(base.glob(pattern))

            hits.sort(key = lambda p: p.stat().st_mtime if p.exists() else 0, reverse = True)

            total = len(hits)
            shown = hits[:100]
            lines = [str(h) for h in shown]
            result = '\n'.join(lines)

            if total > 100:
                result += f'\n...({total}条符合条件，展示前100条)'
            return result or '没有文件符合条件'

        except Exception as e:
            # 查找信息的格式有误
            return f'Error:{e}'