"""
posix命令无法在windows原生终端运行，需要使用git bash
"""
import re
import subprocess
import os
import shutil
from functools import lru_cache

# 分离命令中的路径                盘符         :  路径
_DRIVE_PATH_RE = re.compile(r"([A-Za-z]):((?:\\[^\s;&|<>()'\"]+)+)")

def _posixify_drive_paths(command: str) -> str:
    """
    把路径中的'\'转为'/'，因为'\'在bash会被当成转义字符
    """
    return _DRIVE_PATH_RE.sub(
        lambda m: m.group(1) + ':' + m.group(2).replace('\\', '/'), command
    )

# 无参，每次结果都一样，一次运行过程中只运行一次，之后一直保存供之后使用
@lru_cache(maxsize = 1)
def _git_bash() -> str|None:
    """在windows目录找git bash的bash.exe"""
    if os.name != 'nt': # nt为windows，posix为linux/macos
        return None
    candidate = os.path.join(
        os.environ.get('ProgramFiles', r'C:\Program Files'), "Git", 'bin', 'bash.exe'
    )
    if os.path.isfile(candidate):
        return candidate
    git = shutil.which('git')
    if git:
        derived = os.path.join(os.path.dirname(os.path.dirname(git)), 'bin', 'bash.exe')
        if os.path.isfile(derived):
            return derived
    return None

def run_shell(command: str,
              check: bool = False,
              **kwargs
              ) -> subprocess.CompletedProcess:
    """通过git bash在windows上运行posix命令"""
    bash = _git_bash()

    # 找到git bash则在git bash中运行命令
    if bash is not None:
        return subprocess.run(
            [bash, '-c', _posixify_drive_paths(command)],
            shell = False,
            check = check,
            **kwargs
        )

    return subprocess.run(
        command, shell = True, check = check, **kwargs
    )
