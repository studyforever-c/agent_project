"""
带行号的文件读取
"""

from pathlib import Path

from .base import Tool

class ReadFileTool(Tool):
    name = 'read_file'
    description = """
读取文件的内容和对应行号。
总是在编辑文件之前读文件。
    """
    parameters = {
        'type': 'object',
        'properties': {
            'file_path': {
                'type': 'string',
                'description': '文件路径'
            },
            'offset': {
                'type': 'integer',
                'description': '开始行号(默认为1)'
            },
            'limit': {
                'type': 'integer',
                'description': '读取的最大行数，默认为2000'
            }
        },
        'required': ['file_path']
    }

    def execute(self, file_path: str, offset: int = 1, limit: int = 2000) -> str:

        try:
            p = Path(file_path).expanduser().resolve()
            if not p.exists():
                return f'错误：{file_path}不存在'
            if not p.is_file():
                return f'错误：{file_path}不是一个文件'
            text = p.read_text(encoding = 'utf-8', errors = 'replace')
            lines = text.splitlines()
            total = len(lines)
            start = max(0, offset - 1)
            chunk = lines[start: start + limit]
            numbered = [f"{start + i + 1}:{ln}" for i, ln in enumerate(chunk)]
            result = '\n'.join(numbered)

            if total > start + limit:
                result += f'\n...(总共{total}行)，展示{start + 1} - {start + limit}行'

            return result or '(这是一个空文件)'
        except Exception as e:
            return f'错误：{e}'