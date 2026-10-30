"""
通过正则表达式匹配内容
"""

import re
from pathlib import Path
from .base import Tool
# 这些文件不在查找范围内
_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "dist", "build"
}

class GrepTool(Tool):
    name = 'grep'
    description = f"""
通过正则表达式查找文件内容
返回匹配的文件，匹配到的行号的内容
"""
    parameters = {
        'type': 'object',
        'properties': {
            'pattern': {
                'type': 'string',
                'description': '要匹配的正则模式串。'
            },
            'path': {
                'type': 'string',
                'description': '要查找的目录或文件（默认工作目录）'
            },
            'include': {
                'type': 'string',
                'description': '只查找配合这些通配符的文件'
            }
        },
        'required': ['pattern']
    }

    @staticmethod
    def _walk(root: Path, include: str|None) -> tuple[list[Path], bool]:
        """递归遍历目录"""
        results = []
        truncated = False
        for item in root.rglob(include or '*'):
            if any(part in _SKIP_DIRS for part in item.relative_to(root).parts):
                continue
            if item.is_file():
                results.append(item)
            if len(results) >= 5000:
                truncated = True
                break
        return results, truncated

    def execute(self, pattern: str, path: str = '.', include: str|None = None):

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f'无效的正则模式串：{e}'

        base = Path(path).expanduser().resolve()

        if not base.exists():
            return f'错误{path}不存在。'

        if base.is_file():
            files = [base]
            scan_truncated = False
        else:
            files, scan_truncated = self._walk(base, include)

        scan_limit_msg = '...(已达到5000个文件的扫描上限，可能有更多文件。)'
        matches = []
        for file in files:
            try:
                text = file.read_text(encoding = 'utf-8', errors = 'ignore')
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    matches.append(f'{file}: {lineno}: {line.rstrip()}')
                    if len(matches) >= 200:
                        matches.append('...(已达到200条的匹配上限)')
                        return '\n'.join(matches)
        if matches:
            if scan_truncated:
                matches.append(scan_limit_msg)
            return '\n'.join(matches)
        if scan_truncated:
            return f'没有在扫描到的文件中匹配到任何相关信息。\n{scan_limit_msg}'
        return '没有任何匹配项。'
