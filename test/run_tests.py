#!/usr/bin/env python3
"""
测试运行器 - 运行所有测试并生成报告
"""

import unittest
import sys
import os
from io import StringIO

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def run_all_tests():
    """运行所有测试"""
    # 发现并加载所有测试
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(__file__)
    suite = loader.discover(start_dir, pattern="test_*.py")

    # 创建测试运行器
    stream = StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)

    print("开始运行 QuantContentAgent 单元测试...")
    print("=" * 60)

    # 运行测试
    result = runner.run(suite)

    # 输出结果
    output = stream.getvalue()
    print(output)

    # 生成总结报告
    print(" 测试结果总结:")
    print(f"   总计测试: {result.testsRun}")
    print(f"   成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"   失败: {len(result.failures)}")
    print(f"   错误: {len(result.errors)}")

    if result.failures:
        print("\n 失败的测试:")
        for test, error in result.failures:
            error_msg = error.split("AssertionError: ")[-1].split("\n")[0]
            print(f"   - {test}: {error_msg}")

    if result.errors:
        print("\n 错误的测试:")
        for test, error in result.errors:
            error_msg = error.split("\n")[-2]
            print(f"   - {test}: {error_msg}")

    if result.wasSuccessful():
        print("\n 所有测试通过！")
        return 0
    else:
        print("\n 部分测试失败，请检查代码！")
        return 1


def run_specific_test(test_name):
    """运行特定的测试"""
    if test_name == "agent":
        from test_agent import TestQuantContentAgent

        suite = unittest.TestLoader().loadTestsFromTestCase(TestQuantContentAgent)
    elif test_name == "formulas":
        from test_formulas import TestHScoreFormula

        suite = unittest.TestLoader().loadTestsFromTestCase(TestHScoreFormula)
    elif test_name == "integration":
        from test_integration import TestIntegration

        suite = unittest.TestLoader().loadTestsFromTestCase(TestIntegration)
    elif test_name == "cloud_agent":
        from test_cloud_agent import TestCloudQuantAgent, TestFeishuConnector

        suite = unittest.TestSuite()
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCloudQuantAgent))
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestFeishuConnector))
    elif test_name == "cloud_integration":
        from test_cloud_agent_integration import TestCloudAgentIntegration

        suite = unittest.TestLoader().loadTestsFromTestCase(TestCloudAgentIntegration)
    else:
        print(f"未知的测试名称: {test_name}")
        print(
            "可用的测试: agent, formulas, integration, cloud_agent, cloud_integration"
        )
        return 1

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 运行特定测试
        exit_code = run_specific_test(sys.argv[1])
    else:
        # 运行所有测试
        exit_code = run_all_tests()

    sys.exit(exit_code)
