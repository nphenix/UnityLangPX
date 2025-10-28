#!/usr/bin/env python3
"""
UnityLangPX 代码质量检查脚本

运行各种代码质量检查工具，生成综合报告。
"""

import os
import sys
import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
import argparse


class QualityChecker:
    """代码质量检查器"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.results = {}
        self.start_time = time.time()
    
    def run_command(self, cmd: List[str], description: str) -> Dict[str, Any]:
        """运行命令并返回结果"""
        print(f"🔍 运行 {description}...")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": "命令执行超时",
                "returncode": -1
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1
            }
    
    def check_formatting(self) -> Dict[str, Any]:
        """检查代码格式"""
        # Black检查
        black_result = self.run_command(
            ["black", "--check", "--diff", "src/"],
            "Black代码格式检查"
        )
        
        # isort检查
        isort_result = self.run_command(
            ["isort", "--check-only", "--diff", "src/"],
            "isort导入排序检查"
        )
        
        return {
            "black": black_result,
            "isort": isort_result,
            "overall": black_result["success"] and isort_result["success"]
        }
    
    def check_linting(self) -> Dict[str, Any]:
        """检查代码质量"""
        # flake8检查
        flake8_result = self.run_command(
            ["flake8", "src/", "--format=json"],
            "flake8代码质量检查"
        )
        
        # 解析flake8输出
        flake8_issues = []
        if flake8_result["stdout"]:
            try:
                flake8_issues = json.loads(flake8_result["stdout"])
            except json.JSONDecodeError:
                pass
        
        return {
            "flake8": flake8_result,
            "issues": flake8_issues,
            "issue_count": len(flake8_issues),
            "overall": flake8_result["success"] and len(flake8_issues) == 0
        }
    
    def check_types(self) -> Dict[str, Any]:
        """检查类型注解"""
        mypy_result = self.run_command(
            ["mypy", "src/", "--json-report", ".mypy-cache"],
            "mypy类型检查"
        )
        
        # 解析mypy输出
        mypy_issues = []
        mypy_cache_file = self.project_root / ".mypy-cache" / "index.json"
        if mypy_cache_file.exists():
            try:
                with open(mypy_cache_file, 'r') as f:
                    mypy_data = json.load(f)
                    for file_data in mypy_data.get("files", []):
                        mypy_issues.extend(file_data.get("issues", []))
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        
        return {
            "mypy": mypy_result,
            "issues": mypy_issues,
            "issue_count": len(mypy_issues),
            "overall": mypy_result["success"] and len(mypy_issues) == 0
        }
    
    def check_security(self) -> Dict[str, Any]:
        """检查安全问题"""
        # bandit安全检查
        bandit_result = self.run_command(
            ["bandit", "-r", "src/", "-f", "json"],
            "bandit安全检查"
        )
        
        # 解析bandit输出
        bandit_issues = []
        if bandit_result["stdout"]:
            try:
                bandit_data = json.loads(bandit_result["stdout"])
                bandit_issues = bandit_data.get("results", [])
            except json.JSONDecodeError:
                pass
        
        # 计算安全评分
        high_issues = len([i for i in bandit_issues if i.get("issue_severity") == "HIGH"])
        medium_issues = len([i for i in bandit_issues if i.get("issue_severity") == "MEDIUM"])
        low_issues = len([i for i in bandit_issues if i.get("issue_severity") == "LOW"])
        
        security_score = max(0, 100 - (high_issues * 10 + medium_issues * 5 + low_issues * 1))
        
        return {
            "bandit": bandit_result,
            "issues": bandit_issues,
            "issue_count": len(bandit_issues),
            "high_issues": high_issues,
            "medium_issues": medium_issues,
            "low_issues": low_issues,
            "security_score": security_score,
            "overall": bandit_result["success"] and len(bandit_issues) == 0
        }
    
    def check_tests(self) -> Dict[str, Any]:
        """运行测试"""
        # pytest测试
        pytest_result = self.run_command(
            ["pytest", "tests/", "--cov=src", "--cov-report=json", "--json-report", "--json-report-file=test_results.json"],
            "pytest测试"
        )
        
        # 解析测试结果
        test_data = {}
        test_results_file = self.project_root / "test_results.json"
        if test_results_file.exists():
            try:
                with open(test_results_file, 'r') as f:
                    test_data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        
        # 解析覆盖率结果
        coverage_data = {}
        coverage_file = self.project_root / "coverage.json"
        if coverage_file.exists():
            try:
                with open(coverage_file, 'r') as f:
                    coverage_data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        
        total_tests = test_data.get("summary", {}).get("total", 0)
        passed_tests = test_data.get("summary", {}).get("passed", 0)
        failed_tests = test_data.get("summary", {}).get("failed", 0)
        skipped_tests = test_data.get("summary", {}).get("skipped", 0)
        
        coverage_percent = coverage_data.get("totals", {}).get("percent_covered", 0)
        
        return {
            "pytest": pytest_result,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "skipped_tests": skipped_tests,
            "test_success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            "coverage_percent": coverage_percent,
            "overall": pytest_result["success"] and failed_tests == 0
        }
    
    def check_complexity(self) -> Dict[str, Any]:
        """检查代码复杂度"""
        # xenon复杂度检查
        xenon_result = self.run_command(
            ["xenon", "--max-average=A", "--max-modules=B", "--max-absolute=B", "src/"],
            "xenon复杂度检查"
        )
        
        # 使用radon进行更详细的复杂度分析
        radon_result = self.run_command(
            ["radon", "cc", "src/", "--json"],
            "radon复杂度分析"
        )
        
        complexity_data = {}
        if radon_result["stdout"]:
            try:
                complexity_data = json.loads(radon_result["stdout"])
            except json.JSONDecodeError:
                pass
        
        return {
            "xenon": xenon_result,
            "radon": radon_result,
            "complexity_data": complexity_data,
            "overall": xenon_result["success"]
        }
    
    def check_dependencies(self) -> Dict[str, Any]:
        """检查依赖安全性"""
        # safety检查
        safety_result = self.run_command(
            ["safety", "check", "--json"],
            "safety依赖安全检查"
        )
        
        # 解析safety输出
        safety_issues = []
        if safety_result["stdout"]:
            try:
                safety_data = json.loads(safety_result["stdout"])
                safety_issues = safety_data.get("vulnerabilities", [])
            except json.JSONDecodeError:
                pass
        
        return {
            "safety": safety_result,
            "issues": safety_issues,
            "issue_count": len(safety_issues),
            "overall": safety_result["success"] and len(safety_issues) == 0
        }
    
    def generate_report(self) -> Dict[str, Any]:
        """生成综合质量报告"""
        print("📊 生成质量报告...")
        
        # 运行所有检查
        self.results["formatting"] = self.check_formatting()
        self.results["linting"] = self.check_linting()
        self.results["types"] = self.check_types()
        self.results["security"] = self.check_security()
        self.results["tests"] = self.check_tests()
        self.results["complexity"] = self.check_complexity()
        self.results["dependencies"] = self.check_dependencies()
        
        # 计算总体评分
        scores = {
            "formatting": 100 if self.results["formatting"]["overall"] else 0,
            "linting": max(0, 100 - self.results["linting"]["issue_count"] * 2),
            "types": max(0, 100 - self.results["types"]["issue_count"] * 5),
            "security": self.results["security"]["security_score"],
            "tests": self.results["tests"]["test_success_rate"] * 0.7 + self.results["tests"]["coverage_percent"] * 0.3,
            "complexity": 100 if self.results["complexity"]["overall"] else 70,
            "dependencies": max(0, 100 - self.results["dependencies"]["issue_count"] * 10)
        }
        
        overall_score = sum(scores.values()) / len(scores)
        
        # 生成报告
        report = {
            "timestamp": time.time(),
            "duration": time.time() - self.start_time,
            "overall_score": overall_score,
            "scores": scores,
            "results": self.results,
            "summary": {
                "total_issues": (
                    self.results["linting"]["issue_count"] +
                    self.results["types"]["issue_count"] +
                    self.results["security"]["issue_count"] +
                    self.results["dependencies"]["issue_count"]
                ),
                "test_coverage": self.results["tests"]["coverage_percent"],
                "security_issues": self.results["security"]["issue_count"],
                "failed_tests": self.results["tests"]["failed_tests"]
            }
        }
        
        return report
    
    def save_report(self, report: Dict[str, Any], output_file: Path):
        """保存报告到文件"""
        print(f"💾 保存报告到 {output_file}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    
    def print_summary(self, report: Dict[str, Any]):
        """打印报告摘要"""
        print("\n" + "="*60)
        print("📋 代码质量检查报告")
        print("="*60)
        
        print(f"⏱️  检查耗时: {report['duration']:.2f}秒")
        print(f"📊 总体评分: {report['overall_score']:.1f}/100")
        
        print("\n📈 各项评分:")
        for category, score in report["scores"].items():
            status = "✅" if score >= 90 else "⚠️" if score >= 70 else "❌"
            print(f"  {status} {category.title()}: {score:.1f}/100")
        
        print("\n📋 摘要信息:")
        summary = report["summary"]
        print(f"  🔍 总问题数: {summary['total_issues']}")
        print(f"  🧪 测试覆盖率: {summary['test_coverage']:.1f}%")
        print(f"  🔒 安全问题: {summary['security_issues']}")
        print(f"  ❌ 失败测试: {summary['failed_tests']}")
        
        # 状态判断
        if report['overall_score'] >= 90:
            print("\n🎉 代码质量优秀！")
        elif report['overall_score'] >= 70:
            print("\n👍 代码质量良好，有改进空间")
        else:
            print("\n⚠️ 代码质量需要改进")
        
        print("="*60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="UnityLangPX代码质量检查")
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="quality_report.json",
        help="输出报告文件路径"
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="非交互模式，不显示详细输出"
    )
    
    args = parser.parse_args()
    
    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    
    # 创建质量检查器
    checker = QualityChecker(project_root)
    
    try:
        # 生成报告
        report = checker.generate_report()
        
        # 保存报告
        output_file = project_root / args.output
        checker.save_report(report, output_file)
        
        # 显示摘要
        if not args.no_interactive:
            checker.print_summary(report)
        
        # 设置退出码
        exit_code = 0 if report['overall_score'] >= 70 else 1
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print("\n❌ 检查被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 检查过程中发生错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()