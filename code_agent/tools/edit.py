"""
找出文件中出现次数唯一的字符串，对其进行替换
"""

import difflib
from pathlib import Path
from .base import Tool, FILE_MUTATION_LOCK
from ..src.checkpoints import record as _record_checkpoint
# 跟踪会话过程中编辑过的文件
_changed_files: set[str] = set()

def _unified_diff(old: str, new: str, filename: str, context: int = 3) -> str:
    old_lines = old.splitlines(keepends = True)
    new_lines = new.splitlines(keepends = True)
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile = f'a/{filename}', tofile = f'b/{filename}',
        n = context
    )
    result = ''.join(diff)
    if len(result) > 3000:
        result = result[:2500] + '\n...(diff文件已被裁剪)\n'
    return result

def get_changed_files() -> set[str]:
    return _changed_files

class EditFileTool(Tool):
    name = 'edit_file'
    description = f"""
通过替换文件中一个确切的字符串来实现编辑文件
需要确保旧字符串在文件中出现次数唯一以确保编辑安全
替换的字符串需包含足够的上下文确保唯一性
"""
    parameters = {
        'type': 'object',
        'properties': {
            'file_path': {
                'type': 'string',
                'description': '要编辑的文件的路径'
            },
            'old_string': {
                'type': 'string',
                'description': '文件中要被替换的字符串，需确保字符串在文件中唯一出现。'
            },
            'new_string': {
                'type': 'string',
                'description': '替换后的字符串'
            }
        },
        'required': ['file_path', 'old_string', 'new_string']
    }

    def execute(self, file_path: str, old_string: str, new_string: str) -> str:

        try:
            with FILE_MUTATION_LOCK:
                p = Path(file_path).expanduser().resolve()
                if not p.exists():
                    return f'错误：文件路径{p}不存在。'
                try:
                    content = p.read_text(encoding = 'utf-8')
                except UnicodeDecodeError:
                    return f'错误：{p}不是一个UTF-8编码的文本文件（`edit_file`只能编辑文本文件）。'
                occurrences = content.count(old_string)

                if occurrences == 0:
                    preview = content[:500] + ('...' if len(content) > 500 else '')
                    return f"""
错误：旧字符串未在{p}文件中找到，
该文件开头为：\n{preview}
"""
                if occurrences > 1:
                    return f"""
错误：旧字符串在{p}中出现{occurrences}次，
请包含更多上下文使其在文件中出现次数唯一。
"""
                new_content = content.replace(old_string, new_string, 1)
                _record_checkpoint(p) # 在对文件进行改动前记录旧文件
                p.write_text(new_content, encoding = 'utf-8')
                _changed_files.add(str(p))

            # 生成一个diff文件
            diff = _unified_diff(content, new_content, str(p))
            return f'{file_path}编辑完成\n{diff}'
        except Exception as e:
            return f'错误：{e}'
