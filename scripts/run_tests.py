#!/usr/bin/env python3
"""
测试运行脚本

提供统一的测试运行接口，支持不同类型的测试。
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_command(cmd, cwd=None):
    """运行命令并返回结果"""
    print(f"运行命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    
    return result.returncode == 0


def run_unit_tests(coverage=False, verbose=False):
    """运行单元测试"""
    cmd = ["python", "-m", "pytest", "workspace/tests/unit/"]
    
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")
    
    if coverage:
        cmd.extend([
            "--cov=src",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-fail-under=80"
        ])
    
    return run_command(cmd)


def run_integration_tests(verbose=False):
    """运行集成测试"""
    cmd = ["python", "-m", "pytest", "workspace/tests/integration/"]
    
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")
    
    return run_command(cmd)


def run_validation_tests(verbose=False):
    """运行验证测试"""
    cmd = ["python", "-m", "pytest", "workspace/validation/"]
    
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")
    
    return run_command(cmd)


def run_all_tests(coverage=False, verbose=False):
    """运行所有测试"""
    print("=" * 60)
    print("运行所有测试")
    print("=" * 60)
    
    # 1. 运行单元测试
    print("\n1. 运行单元测试...")
    unit_success = run_unit_tests(coverage=coverage, verbose=verbose)
    
    # 2. 运行集成测试
    print("\n2. 运行集成测试...")
    integration_success = run_integration_tests(verbose=verbose)
    
    # 3. 运行验证测试
    print("\n3. 运行验证测试...")
    validation_success = run_validation_tests(verbose=verbose)
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    print(f"单元测试: {'通过' if unit_success else '失败'}")
    print(f"集成测试: {'通过' if integration_success else '失败'}")
    print(f"验证测试: {'通过' if validation_success else '失败'}")
    
    overall_success = unit_success and integration_success and validation_success
    print(f"总体结果: {'通过' if overall_success else '失败'}")
    print("=" * 60)
    
    return overall_success


def run_specific_test(test_path, verbose=False):
    """运行特定测试"""
    cmd = ["python", "-m", "pytest", test_path]
    
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")
    
    return run_command(cmd)


def run_performance_tests():
    """运行性能测试"""
    cmd = ["python", "-m", "pytest", "workspace/tests/performance/", "-v"]
    return run_command(cmd)


def generate_test_report():
    """生成测试报告"""
    print("生成测试报告...")
    
    # 创建报告目录
    report_dir = project_root / "workspace" / "tests" / "reports"
    report_dir.mkdir(exist_ok=True)
    
    # 运行测试并生成HTML报告
    cmd = [
        "python", "-m", "pytest",
        "workspace/tests/",
        "--html=workspace/tests/reports/report.html",
        "--self-contained-html",
        "--cov=src",
        "--cov-report=html:workspace/tests/reports/coverage",
        "--cov-report=xml:workspace/tests/reports/coverage.xml"
    ]
    
    success = run_command(cmd)
    
    if success:
        print(f"测试报告已生成: {report_dir / 'report.html'}")
        print(f"覆盖率报告已生成: {report_dir / 'coverage' / 'index.html'}")
    
    return success


def check_test_dependencies():
    """检查测试依赖"""
    print("检查测试依赖...")
    
    required_packages = [
        "pytest",
        "pytest-asyncio",
        "pytest-cov",
        "pytest-mock"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"缺少测试依赖: {', '.join(missing_packages)}")
        print("请运行: pip install " + " ".join(missing_packages))
        return False
    
    print("所有测试依赖已安装")
    return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="UnityLangPX 测试运行器")
    
    parser.add_argument(
        "test_type",
        choices=["unit", "integration", "validation", "all", "performance", "report"],
        help="测试类型"
    )
    
    parser.add_argument(
        "--path",
        help="运行特定测试路径"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="生成覆盖率报告"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细输出"
    )
    
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="检查测试依赖"
    )
    
    args = parser.parse_args()
    
    # 检查依赖
    if args.check_deps:
        if not check_test_dependencies():
            sys.exit(1)
        return
    
    # 切换到项目根目录
    os.chdir(project_root)
    
    # 运行测试
    success = True
    
    if args.path:
        success = run_specific_test(args.path, args.verbose)
    elif args.test_type == "unit":
        success = run_unit_tests(coverage=args.coverage, verbose=args.verbose)
    elif args.test_type == "integration":
        success = run_integration_tests(verbose=args.verbose)
    elif args.test_type == "validation":
        success = run_validation_tests(verbose=args.verbose)
    elif args.test_type == "all":
        success = run_all_tests(coverage=args.coverage, verbose=args.verbose)
    elif args.test_type == "performance":
        success = run_performance_tests()
    elif args.test_type == "report":
        success = generate_test_report()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()