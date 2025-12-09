import unittest
import pandas as pd
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import QuantContentAgent


class TestQuantContentAgent(unittest.TestCase):
    """QuantContentAgent单元测试类"""

    def setUp(self):
        """测试前设置"""
        # 创建临时CSV文件用于测试
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w+", delete=False, suffix=".csv"
        )
        self.test_data = pd.DataFrame(
            {
                "title": ["测试标题1", "测试标题2", "测试标题3"],
                "like": [100, 200, 150],
                "comment": [20, 30, 25],
                "save": [50, 80, 60],
                "share": [5, 10, 8],
            }
        )
        self.test_data.to_csv(self.temp_file.name, index=False)
        self.temp_file.close()

        # 模拟环境变量
        os.environ["GEMINI_API_KEY"] = "test_api_key"

    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    @patch("agent.genai.Client")
    def test_init_with_existing_file(self, mock_client):
        """测试使用现有历史文件初始化"""
        agent = QuantContentAgent(history_file=self.temp_file.name)

        # 验证历史数据正确加载
        self.assertFalse(agent.history.empty)
        self.assertEqual(len(agent.history), 3)
        self.assertIn("title", agent.history.columns)
        self.assertIn("like", agent.history.columns)

        # 验证客户端初始化
        mock_client.assert_called_once()

    @patch("agent.genai.Client")
    def test_init_with_nonexistent_file(self, mock_client):
        """测试使用不存在的文件初始化"""
        agent = QuantContentAgent(history_file="nonexistent.csv")

        # 验证创建了空的DataFrame
        self.assertTrue(agent.history.empty)
        self.assertEqual(
            list(agent.history.columns), ["title", "like", "comment", "save", "share"]
        )

    def test_calculate_h_score_complete_data(self):
        """测试H Score计算 - 完整数据"""
        with patch("agent.genai.Client"):
            agent = QuantContentAgent(history_file=self.temp_file.name)

        test_post = {"like": 100, "comment": 20, "save": 50, "share": 5}

        # 预期计算: 100*1 + 20*4 + 50*5 + 5*10 = 100 + 80 + 250 + 50 = 480
        expected_score = 480
        actual_score = agent._calculate_h_score(test_post)

        self.assertEqual(actual_score, expected_score)

    def test_calculate_h_score_missing_fields(self):
        """测试H Score计算 - 缺少字段的容错处理"""
        with patch("agent.genai.Client"):
            agent = QuantContentAgent(history_file=self.temp_file.name)

        # 只包含部分字段
        test_post = {
            "like": 100,
            "save": 50,
            # comment和share缺失，应该默认为0
        }

        # 预期计算: 100*1 + 0*4 + 50*5 + 0*10 = 350
        expected_score = 350
        actual_score = agent._calculate_h_score(test_post)

        self.assertEqual(actual_score, expected_score)

    def test_calculate_h_score_empty_data(self):
        """测试H Score计算 - 空数据"""
        with patch("agent.genai.Client"):
            agent = QuantContentAgent(history_file=self.temp_file.name)

        test_post = {}

        # 所有字段默认为0: 0*1 + 0*4 + 0*5 + 0*10 = 0
        expected_score = 0
        actual_score = agent._calculate_h_score(test_post)

        self.assertEqual(actual_score, expected_score)

    def test_get_market_metrics_with_history(self):
        """测试市场指标计算 - 有历史数据"""
        with patch("agent.genai.Client"):
            agent = QuantContentAgent(history_file=self.temp_file.name)

        new_post = {"like": 300, "comment": 50, "save": 100, "share": 15}

        h_score, z_score = agent.get_market_metrics(new_post)

        # 验证H Score计算正确
        expected_h_score = 300 * 1 + 50 * 4 + 100 * 5 + 15 * 10  # = 1050
        self.assertEqual(h_score, expected_h_score)

        # 验证Z Score是数值类型
        self.assertIsInstance(z_score, float)

    def test_get_market_metrics_without_history(self):
        """测试市场指标计算 - 无历史数据"""
        with patch("agent.genai.Client"):
            # 创建空历史记录的agent
            agent = QuantContentAgent(history_file="nonexistent.csv")

        new_post = {"like": 300, "comment": 50, "save": 100, "share": 15}

        h_score, z_score = agent.get_market_metrics(new_post)

        # 验证H Score计算
        expected_h_score = 300 * 1 + 50 * 4 + 100 * 5 + 15 * 10  # = 1050
        self.assertEqual(h_score, expected_h_score)

        # 无历史数据时Z Score应为0
        self.assertEqual(z_score, 0.0)

    def test_get_market_metrics_insufficient_history(self):
        """测试市场指标计算 - 历史数据不足"""
        with patch("agent.genai.Client"):
            agent = QuantContentAgent(history_file="nonexistent.csv")
            # 添加少量历史数据（不足3条）
            agent.history = pd.DataFrame(
                {
                    "title": ["测试"],
                    "like": [100],
                    "comment": [20],
                    "save": [50],
                    "share": [5],
                }
            )

        new_post = {"like": 200, "comment": 30, "save": 80, "share": 10}
        h_score, z_score = agent.get_market_metrics(new_post)

        # 历史数据不足时Z Score应为0
        self.assertEqual(z_score, 0.0)

    @patch("agent.genai.Client")
    def test_ai_strategic_decision_success(self, mock_client):
        """测试AI策略决策 - 成功情况"""
        # 设置mock响应
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "analysis": "测试分析结果",
                "strategy": "追涨",
                "next_title_suggestions": ["建议标题1", "建议标题2"],
                "cover_prompt": "测试封面提示词",
            }
        )

        mock_client.return_value.models.generate_content.return_value = mock_response

        agent = QuantContentAgent(history_file=self.temp_file.name)

        new_post = {
            "title": "测试帖子",
            "like": 100,
            "comment": 20,
            "save": 50,
            "share": 5,
        }

        result = agent.ai_strategic_decision(new_post, 480, 1.5, "测试评论")

        # 验证返回结果
        self.assertIsNotNone(result)
        self.assertEqual(result["analysis"], "测试分析结果")
        self.assertEqual(result["strategy"], "追涨")
        self.assertIsInstance(result["next_title_suggestions"], list)

        # 验证API调用
        mock_client.return_value.models.generate_content.assert_called_once()

    @patch("agent.genai.Client")
    def test_ai_strategic_decision_api_error(self, mock_client):
        """测试AI策略决策 - API错误"""
        # 模拟API调用异常
        mock_client.return_value.models.generate_content.side_effect = Exception(
            "API Error"
        )

        agent = QuantContentAgent(history_file=self.temp_file.name)

        new_post = {
            "title": "测试帖子",
            "like": 100,
            "comment": 20,
            "save": 50,
            "share": 5,
        }

        with patch("builtins.print") as mock_print:
            result = agent.ai_strategic_decision(new_post, 480, 1.5, "测试评论")

        # 验证错误处理
        self.assertIsNone(result)

    @patch("agent.genai.Client")
    def test_ai_strategic_decision_invalid_json(self, mock_client):
        """测试AI策略决策 - 无效JSON响应"""
        # 设置无效JSON响应
        mock_response = MagicMock()
        mock_response.text = "invalid json response"

        mock_client.return_value.models.generate_content.return_value = mock_response

        agent = QuantContentAgent(history_file=self.temp_file.name)

        new_post = {
            "title": "测试帖子",
            "like": 100,
            "comment": 20,
            "save": 50,
            "share": 5,
        }

        result = agent.ai_strategic_decision(new_post, 480, 1.5, "测试评论")

        # JSON解析错误应返回None
        self.assertIsNone(result)

    @patch("agent.genai.Client")
    @patch("builtins.print")
    def test_run_review_complete_flow(self, mock_print, mock_client):
        """测试完整的review流程"""
        # 设置成功的API响应
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "analysis": "数据表现优秀",
                "strategy": "追涨",
                "next_title_suggestions": ["建议标题1", "建议标题2"],
                "cover_prompt": "专业封面设计",
            }
        )

        mock_client.return_value.models.generate_content.return_value = mock_response

        agent = QuantContentAgent(history_file=self.temp_file.name)

        new_post = {
            "title": "优质内容测试",
            "like": 500,
            "comment": 80,
            "save": 200,
            "share": 25,
        }

        result = agent.run_review(new_post, "用户评论很积极")

        # 验证返回结果
        self.assertIsNotNone(result)
        self.assertIn("analysis", result)
        self.assertIn("strategy", result)

    @patch("agent.genai.Client")
    @patch("builtins.print")
    def test_run_review_api_failure(self, mock_print, mock_client):
        """测试review流程 - API失败"""
        # 模拟API调用失败
        mock_client.return_value.models.generate_content.side_effect = Exception(
            "API 连接失败"
        )

        agent = QuantContentAgent(history_file=self.temp_file.name)

        new_post = {
            "title": "测试帖子",
            "like": 100,
            "comment": 20,
            "save": 50,
            "share": 5,
        }

        result = agent.run_review(new_post, "测试评论")

        # 验证方法正常返回（即使API失败）
        self.assertIsNone(result)

    def test_h_score_weights_accuracy(self):
        """测试H Score权重设置的准确性"""
        with patch("agent.genai.Client"):
            agent = QuantContentAgent(history_file=self.temp_file.name)

        # 测试各个因子的权重
        test_cases = [
            ({"like": 1, "comment": 0, "save": 0, "share": 0}, 1),  # 点赞权重 = 1
            ({"like": 0, "comment": 1, "save": 0, "share": 0}, 4),  # 评论权重 = 4
            ({"like": 0, "comment": 0, "save": 1, "share": 0}, 5),  # 收藏权重 = 5
            ({"like": 0, "comment": 0, "save": 0, "share": 1}, 10),  # 分享权重 = 10
        ]

        for post_data, expected_score in test_cases:
            actual_score = agent._calculate_h_score(post_data)
            self.assertEqual(
                actual_score,
                expected_score,
                f"权重测试失败: {post_data} 应得分 {expected_score}, 实际得分 {actual_score}",
            )

    def test_edge_cases(self):
        """测试边缘情况"""
        with patch("agent.genai.Client"):
            agent = QuantContentAgent(history_file=self.temp_file.name)

        # 测试负数值（虽然在实际场景中不应该出现）
        negative_post = {"like": -10, "comment": -5, "save": -2, "share": -1}
        score = agent._calculate_h_score(negative_post)
        expected = -10 * 1 + (-5) * 4 + (-2) * 5 + (-1) * 10  # = -50
        self.assertEqual(score, expected)

        # 测试极大值
        large_post = {
            "like": 999999,
            "comment": 999999,
            "save": 999999,
            "share": 999999,
        }
        score = agent._calculate_h_score(large_post)
        expected = 999999 * (1 + 4 + 5 + 10)  # = 999999 * 20
        self.assertEqual(score, expected)


if __name__ == "__main__":
    # 运行所有测试
    unittest.main(verbosity=2)
