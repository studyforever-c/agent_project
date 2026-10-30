"""
创建文件或覆盖文件
"""

from pathlib import Path

from .base import Tool
from .edit import _changed_files
from ..src.checkpoints import record as _record_checkpoint

class WriteFileTool(Tool):
    name = 'write_file'
    description = """
创建一个新文件或者完全覆盖一个已经存在的文件
在编辑已经存在的小文件时，使用edit_file更合适
    """
    parameters = {
        'type': 'object',
        'properties': {
            'file_path': {
                'type': 'string',
                'description': '文件路径'
            },
            'content': {
                'type': 'string',
                'description': '需要写入的完整文件内容'
            }
        },
        'required': ['file_path', 'content']
    }

    def execute(self, file_path: str, content: str) -> str:
        from .base import FILE_MUTATION_LOCK

        try:
            with FILE_MUTATION_LOCK:
                p = Path(file_path).expanduser().resolve()
                p.parent.mkdir(parents = True, exist_ok = True)
                _record_checkpoint(p)
                p.write_text(content, encoding = 'utf-8')
                _changed_files.add(str(p))
            n_lines = content.count('\n') + (1 if content and not content.endswith('\n') else 0)
            return f'在{file_path}写入{n_lines}行内容'
        except Exception as e:
            return f'Error{e}'