import unittest
import tempfile
import os
import pandas as pd
import sys
from unittest.mock import patch, MagicMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import QuantContentAgent


class TestIntegration(unittest.TestCase):
    """集成测试 - 测试完整的工作流程"""

    def setUp(self):
        """测试前设置"""
        # 创建临时历史数据文件
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w+", delete=False, suffix=".csv"
        )
        self.history_data = pd.DataFrame(
            {
                "title": [
                    "量化策略入门指南",
                    "Python数据分析实战",
                    "机器学习算法详解",
                    "金融数据可视化",
                    "投资组合优化方法",
                ],
                "like": [150, 300, 500, 200, 400],
                "comment": [25, 45, 80, 35, 60],
                "save": [80, 150, 250, 100, 200],
                "share": [8, 15, 25, 12, 20],
            }
        )
        self.history_data.to_csv(self.temp_file.name, index=False)
        self.temp_file.close()

        os.environ["GEMINI_API_KEY"] = "test_api_key"

    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    @patch("agent.genai.Client")
    def test_complete_analysis_workflow(self, mock_client):
        """测试完整的分析工作流程"""
        # 设置模拟的AI响应
        mock_response = MagicMock()
        mock_response.text = """
        {
            "analysis": "这是一篇高质量的技术干货文章。收藏数(300)远超点赞数(600)，说明内容具有很强的实用价值和保存意义。评论数(50)适中，表明读者有一定的互动意愿。分享数(15)较高，说明内容具备传播价值。",
            "strategy": "追涨",
            "next_title_suggestions": [
                "深度解析：量化交易策略的核心要素",
                "从零开始：构建你的第一个量化模型"
            ],
            "cover_prompt": "现代科技风格，深蓝色背景，金融图表元素，专业简洁的文字排版，突出技术和数据分析主题"
        }
        """
        mock_client.return_value.models.generate_content.return_value = mock_response

        # 创建agent实例
        agent = QuantContentAgent(history_file=self.temp_file.name)

        # 测试一篇新的高质量帖子
        high_quality_post = {
            "title": "量化投资策略实战分析",
            "like": 600,
            "comment": 50,
            "save": 300,
            "share": 15,
        }

        comments = "内容很实用！请问有没有更多的案例分析？能否分享下代码实现？"

        # 测试市场指标计算
        h_score, z_score = agent.get_market_metrics(high_quality_post)

        # 验证H Score计算
        expected_h_score = (
            600 * 1 + 50 * 4 + 300 * 5 + 15 * 10
        )  # = 600 + 200 + 1500 + 150 = 2450
        self.assertEqual(h_score, expected_h_score)

        # 验证Z Score为数值类型（具体值取决于历史数据分布）
        self.assertIsInstance(z_score, float)

        # 测试AI决策
        decision = agent.ai_strategic_decision(
            high_quality_post, h_score, z_score, comments
        )

        # 验证决策结果
        self.assertIsNotNone(decision)
        self.assertIn("analysis", decision)
        self.assertIn("strategy", decision)
        self.assertEqual(decision["strategy"], "追涨")
        self.assertIn("next_title_suggestions", decision)
        self.assertIsInstance(decision["next_title_suggestions"], list)
        self.assertEqual(len(decision["next_title_suggestions"]), 2)

    @patch("agent.genai.Client")
    @patch("builtins.print")
    def test_full_review_process(self, mock_print, mock_client):
        """测试完整的review流程"""
        # 设置模拟响应
        mock_response = MagicMock()
        mock_response.text = """
        {
            "analysis": "帖子表现平平，各项指标都在平均水平，需要优化内容策略",
            "strategy": "修正",
            "next_title_suggestions": [
                "改进版：如何提升内容吸引力",
                "实用技巧：让你的内容更有价值"
            ],
            "cover_prompt": "温暖色调，简洁设计，突出改进和优化主题"
        }
        """
        mock_client.return_value.models.generate_content.return_value = mock_response

        agent = QuantContentAgent(history_file=self.temp_file.name)

        # 测试一篇表现一般的帖子
        average_post = {
            "title": "基础投资知识分享",
            "like": 100,
            "comment": 15,
            "save": 30,
            "share": 3,
        }

        comments = "内容比较基础，希望能有更深入的分析"

        # 运行完整review
        result = agent.run_review(average_post, comments)

        # 验证返回结果
        self.assertIsNotNone(result)
        self.assertIn("analysis", result)
        self.assertIn("strategy", result)
        self.assertEqual(result["strategy"], "修正")
        self.assertIn("表现平平", result["analysis"])

    @patch("agent.genai.Client")
    def test_different_content_types(self, mock_client):
        """测试不同类型内容的分析"""

        # 设置不同的模拟响应
        def mock_generate_content(*args, **kwargs):
            response = MagicMock()
            # 检查prompt内容来决定返回什么策略
            prompt_text = (
                str(args[1]) if len(args) > 1 else str(kwargs.get("contents", ""))
            )

            if "爆款投资策略" in prompt_text:
                response.text = '{"analysis": "爆款内容分析", "strategy": "追涨", "next_title_suggestions": ["爆款续集1", "爆款续集2"], "cover_prompt": "爆款封面"}'
            elif "低质量内容" in prompt_text:
                response.text = '{"analysis": "内容质量需要提升", "strategy": "止损", "next_title_suggestions": ["改进标题1", "改进标题2"], "cover_prompt": "改进封面"}'
            else:
                response.text = '{"analysis": "普通内容", "strategy": "互动", "next_title_suggestions": ["互动标题1", "互动标题2"], "cover_prompt": "互动封面"}'
            return response

        mock_client.return_value.models.generate_content.side_effect = (
            mock_generate_content
        )

        agent = QuantContentAgent(history_file=self.temp_file.name)

        # 测试不同类型的帖子
        test_posts = [
            {
                "name": "爆款帖子",
                "data": {
                    "title": "爆款投资策略",
                    "like": 1000,
                    "comment": 200,
                    "save": 500,
                    "share": 50,
                },
                "expected_strategy": "追涨",
            },
            {
                "name": "低质量帖子",
                "data": {
                    "title": "低质量内容",
                    "like": 10,
                    "comment": 2,
                    "save": 5,
                    "share": 0,
                },
                "expected_strategy": "止损",
            },
            {
                "name": "普通帖子",
                "data": {
                    "title": "普通分享",
                    "like": 100,
                    "comment": 20,
                    "save": 40,
                    "share": 5,
                },
                "expected_strategy": "互动",
            },
        ]

        for post_info in test_posts:
            with self.subTest(post_type=post_info["name"]):
                decision = agent.ai_strategic_decision(
                    post_info["data"],
                    agent._calculate_h_score(post_info["data"]),
                    1.0,  # 模拟Z score
                    "测试评论",
                )

                self.assertIsNotNone(decision)
                self.assertEqual(decision["strategy"], post_info["expected_strategy"])

    def test_historical_data_impact(self):
        """测试历史数据对Z Score计算的影响"""
        with patch("agent.genai.Client"):
            agent = QuantContentAgent(history_file=self.temp_file.name)

        # 测试相同的帖子数据
        test_post = {"like": 300, "comment": 50, "save": 150, "share": 12}

        # 计算原始Z Score
        h_score1, z_score1 = agent.get_market_metrics(test_post)

        # 添加一些高性能的历史数据
        high_performance_data = pd.DataFrame(
            {
                "title": ["超级爆款1", "超级爆款2"],
                "like": [2000, 2500],
                "comment": [400, 500],
                "save": [1000, 1200],
                "share": [100, 120],
            }
        )

        agent.history = pd.concat(
            [agent.history, high_performance_data], ignore_index=True
        )

        # 重新计算Z Score
        h_score2, z_score2 = agent.get_market_metrics(test_post)

        # H Score应该相同
        self.assertEqual(h_score1, h_score2)

        # 但Z Score应该发生变化（因为历史数据分布改变了）
        self.assertNotEqual(z_score1, z_score2)

    @patch("agent.genai.Client")
    def test_error_recovery(self, mock_client):
        """测试错误恢复机制"""
        # 第一次调用失败，第二次成功
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("网络错误")
            else:
                response = MagicMock()
                response.text = '{"analysis": "成功分析", "strategy": "追涨", "next_title_suggestions": ["标题1", "标题2"], "cover_prompt": "封面"}'
                return response

        mock_client.return_value.models.generate_content.side_effect = side_effect

        agent = QuantContentAgent(history_file=self.temp_file.name)

        test_post = {
            "title": "测试帖子",
            "like": 100,
            "comment": 20,
            "save": 50,
            "share": 5,
        }

        # 第一次调用应该失败
        result1 = agent.ai_strategic_decision(test_post, 480, 1.0, "测试评论")
        self.assertIsNone(result1)

        # 第二次调用应该成功
        result2 = agent.ai_strategic_decision(test_post, 480, 1.0, "测试评论")
        self.assertIsNotNone(result2)
        self.assertEqual(result2["strategy"], "追涨")


if __name__ == "__main__":
    unittest.main(verbosity=2)
