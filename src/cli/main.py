"""
UnityLangPX CLI主入口

这个模块提供了UnityLangPX命令行工具的主入口点。
"""

import sys
from .commands import cli

def main():
    """CLI主入口函数"""
    try:
        cli()
    except KeyboardInterrupt:
        print("\n用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"程序异常退出: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()