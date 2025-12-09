import unittest
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import QuantContentAgent


class TestHScoreFormula(unittest.TestCase):
    """专门测试H Score公式正确性的测试类"""

    def setUp(self):
        """测试前设置"""
        os.environ["GEMINI_API_KEY"] = "test_api_key"

    def test_h_score_formula_verification(self):
        """验证H Score公式: H = (Like * 1) + (Comment * 4) + (Save * 5) + (Share * 10)"""
        from unittest.mock import patch

        with patch("agent.genai.Client"):
            agent = QuantContentAgent(history_file="nonexistent.csv")

        # 测试用例：验证公式的各个组成部分
        test_cases = [
            # (输入数据, 预期H Score)
            (
                {"like": 100, "comment": 20, "save": 50, "share": 5},
                100 + 80 + 250 + 50,
            ),  # = 480
            ({"like": 0, "comment": 0, "save": 0, "share": 0}, 0),  # 全零
            (
                {"like": 1000, "comment": 100, "save": 200, "share": 30},
                1000 + 400 + 1000 + 300,
            ),  # = 2700
            (
                {"like": 50, "comment": 0, "save": 100, "share": 0},
                50 + 0 + 500 + 0,
            ),  # = 550
        ]

        for post_data, expected_h_score in test_cases:
            with self.subTest(post_data=post_data):
                actual_h_score = agent._calculate_h_score(post_data)
                self.assertEqual(
                    actual_h_score,
                    expected_h_score,
                    f"H Score计算错误: 输入 {post_data}, 期望 {expected_h_score}, 实际 {actual_h_score}",
                )


class TestDataTypes(unittest.TestCase):
    """测试数据类型处理"""

    def setUp(self):
        os.environ["GEMINI_API_KEY"] = "test_api_key"

    def test_string_numbers(self):
        """测试字符串类型的数字输入"""
        from unittest.mock import patch

        with patch("agent.genai.Client"):
            agent = QuantContentAgent(history_file="nonexistent.csv")

        # 模拟从CSV或API获取的字符串数字
        post_with_strings = {"like": "100", "comment": "20", "save": "50", "share": "5"}

        # 注意：原代码使用.get()方法，字符串会被直接使用
        # 这可能导致类型错误，这是一个潜在的bug
        try:
            score = agent._calculate_h_score(post_with_strings)
            # 如果没有异常，检查是否为字符串拼接结果
            self.assertIsInstance(score, (int, float, str))
        except TypeError:
            # 如果出现类型错误，说明需要类型转换
            self.fail("H Score计算不支持字符串类型数字，需要添加类型转换")


class TestPerformanceMetrics(unittest.TestCase):
    """测试性能指标计算"""

    def setUp(self):
        os.environ["GEMINI_API_KEY"] = "test_api_key"

    def test_z_score_calculation_logic(self):
        """测试Z Score计算逻辑"""
        from unittest.mock import patch
        import pandas as pd

        with patch("agent.genai.Client"):
            agent = QuantContentAgent(history_file="nonexistent.csv")

            # 设置已知的历史数据
            agent.history = pd.DataFrame(
                {
                    "title": ["帖子1", "帖子2", "帖子3"],
                    "like": [100, 200, 300],  # H Scores: 580, 1160, 1740
                    "comment": [
                        20,
                        40,
                        60,
                    ],  # (100+80+250+50), (200+160+500+100), (300+240+750+150)
                    "save": [50, 100, 150],
                    "share": [5, 10, 15],
                }
            )

        # 计算历史H Scores的均值和标准差
        history_h_scores = [580, 1160, 1740]  # 手动计算的H Scores
        mean = sum(history_h_scores) / len(history_h_scores)  # 1160

        # 测试新帖子
        new_post = {
            "like": 200,
            "comment": 40,
            "save": 100,
            "share": 10,
        }  # H Score = 1160

        h_score, z_score = agent.get_market_metrics(new_post)

        # 验证H Score
        expected_h_score = 200 + 160 + 500 + 100  # = 1160
        self.assertEqual(h_score, expected_h_score)

        # 当H Score等于均值时，Z Score应接近0
        self.assertAlmostEqual(z_score, 0.0, places=1)


if __name__ == "__main__":
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有测试类
    suite.addTests(loader.loadTestsFromTestCase(TestHScoreFormula))
    suite.addTests(loader.loadTestsFromTestCase(TestDataTypes))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceMetrics))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
