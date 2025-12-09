import unittest
import json
import os
import sys
import numpy as np
from unittest.mock import patch, MagicMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cloud_agent import CloudQuantAgent, FeishuConnector


class TestCloudQuantAgent(unittest.TestCase):
    """测试CloudQuantAgent类"""

    def setUp(self):
        """测试前设置"""
        os.environ["GEMINI_API_KEY"] = "test_api_key"

    @patch("cloud_agent.genai.Client")
    def test_init_cloud_agent(self, mock_client):
        """测试CloudQuantAgent初始化"""
        agent = CloudQuantAgent()

        # 验证初始状态
        self.assertEqual(agent.history_mean, 0.0)
        self.assertEqual(agent.history_std, 1.0)
        self.assertFalse(agent.has_history)

        # 验证客户端初始化
        mock_client.assert_called_once()

    def test_calc_h_score_formula(self):
        """测试H Score计算公式"""
        with patch("cloud_agent.genai.Client"):
            agent = CloudQuantAgent()

        # 测试公式: H = (like * 1) + (comment * 4) + (save * 5) + (share * 10)
        test_cases = [
            (100, 20, 50, 5, 100 + 80 + 250 + 50),  # = 480
            (0, 0, 0, 0, 0),  # 全零
            (1000, 100, 200, 30, 1000 + 400 + 1000 + 300),  # = 2700
        ]

        for like, comment, save, share, expected in test_cases:
            with self.subTest(like=like, comment=comment, save=save, share=share):
                result = agent._calc_h_score(like, comment, save, share)
                self.assertEqual(result, expected)

    def test_build_history_baseline_sufficient_data(self):
        """测试历史基准线构建 - 足够数据"""
        with patch("cloud_agent.genai.Client"):
            agent = CloudQuantAgent()

        # 模拟历史记录数据
        mock_records = [
            {
                "fields": {
                    "状态": "已分析",
                    "点赞": 100,
                    "评论": 20,
                    "收藏": 50,
                    "分享": 5,
                }
            },
            {
                "fields": {
                    "状态": "已分析",
                    "点赞": 200,
                    "评论": 40,
                    "收藏": 100,
                    "分享": 10,
                }
            },
            {
                "fields": {
                    "状态": "已分析",
                    "点赞": 300,
                    "评论": 60,
                    "收藏": 150,
                    "分享": 15,
                }
            },
            {
                "fields": {
                    "状态": "待分析",  # 这条应该被忽略
                    "点赞": 999,
                    "评论": 999,
                    "收藏": 999,
                    "分享": 999,
                }
            },
        ]

        with patch("builtins.print") as mock_print:
            agent.build_history_baseline(mock_records)

        # 验证基准线计算
        self.assertTrue(agent.has_history)
        self.assertGreater(agent.history_mean, 0)
        self.assertGreater(agent.history_std, 0)

        # 验证只使用了"已分析"的数据
        expected_h_scores = [480, 960, 1440]  # 重新计算的H Scores
        expected_mean = np.mean(expected_h_scores)  # = 960.0
        expected_std = np.std(expected_h_scores)  # = 393.44

        self.assertAlmostEqual(agent.history_mean, expected_mean, places=1)
        self.assertAlmostEqual(agent.history_std, expected_std, places=1)

    def test_build_history_baseline_insufficient_data(self):
        """测试历史基准线构建 - 数据不足"""
        with patch("cloud_agent.genai.Client"):
            agent = CloudQuantAgent()

        # 模拟数据不足的记录
        mock_records = [
            {
                "fields": {
                    "状态": "已分析",
                    "点赞": 100,
                    "评论": 20,
                    "收藏": 50,
                    "分享": 5,
                }
            },
            {
                "fields": {
                    "状态": "待分析",
                    "点赞": 200,
                    "评论": 40,
                    "收藏": 100,
                    "分享": 10,
                }
            },
        ]

        with patch("builtins.print"):
            agent.build_history_baseline(mock_records)

        # 验证数据不足时的处理
        self.assertFalse(agent.has_history)

    def test_build_history_baseline_zero_std(self):
        """测试历史基准线构建 - 标准差为零的情况"""
        with patch("cloud_agent.genai.Client"):
            agent = CloudQuantAgent()

        # 模拟相同H Score的记录
        same_score_records = [
            {
                "fields": {
                    "状态": "已分析",
                    "点赞": 100,
                    "评论": 20,
                    "收藏": 50,
                    "分享": 5,
                }
            },
            {
                "fields": {
                    "状态": "已分析",
                    "点赞": 100,
                    "评论": 20,
                    "收藏": 50,
                    "分享": 5,
                }
            },
            {
                "fields": {
                    "状态": "已分析",
                    "点赞": 100,
                    "评论": 20,
                    "收藏": 50,
                    "分享": 5,
                }
            },
        ]

        agent.build_history_baseline(same_score_records)

        # 验证标准差被设置为最小值
        self.assertEqual(agent.history_std, 1e-5)

    @patch("cloud_agent.genai.Client")
    def test_analyze_without_history(self, mock_client):
        """测试分析功能 - 无历史数据"""
        # 设置mock响应
        mock_response = MagicMock()
        mock_response.text = (
            '{"analysis": "测试分析", "action": "测试行动", "next_title": "测试标题"}'
        )
        mock_client.return_value.models.generate_content.return_value = mock_response

        agent = CloudQuantAgent()

        post_data = {
            "title": "测试帖子",
            "like": 100,
            "comment": 20,
            "save": 50,
            "share": 5,
        }

        result, h_score, z_score = agent.analyze(post_data)

        # 验证H Score计算
        expected_h_score = 100 + 20 * 4 + 50 * 5 + 5 * 10  # = 480
        self.assertEqual(h_score, expected_h_score)

        # 无历史数据时Z Score应为0
        self.assertEqual(z_score, 0.0)

        # 验证返回结果
        self.assertIsInstance(result, dict)
        self.assertIn("analysis", result)
        self.assertIn("action", result)
        self.assertIn("next_title", result)

    @patch("cloud_agent.genai.Client")
    def test_analyze_with_history(self, mock_client):
        """测试分析功能 - 有历史数据"""
        # 设置mock响应
        mock_response = MagicMock()
        mock_response.text = (
            '{"analysis": "爆款内容", "action": "追涨", "next_title": "续集标题"}'
        )
        mock_client.return_value.models.generate_content.return_value = mock_response

        agent = CloudQuantAgent()

        # 手动设置历史基准
        agent.has_history = True
        agent.history_mean = 1000
        agent.history_std = 500

        post_data = {
            "title": "爆款帖子",
            "like": 500,
            "comment": 100,
            "save": 200,
            "share": 20,
        }

        result, h_score, z_score = agent.analyze(post_data)

        # 验证H Score计算
        expected_h_score = 500 + 100 * 4 + 200 * 5 + 20 * 10  # = 2100
        self.assertEqual(h_score, expected_h_score)

        # 验证Z Score计算
        expected_z_score = (2100 - 1000) / 500  # = 2.2
        self.assertAlmostEqual(z_score, expected_z_score, places=1)

        # 验证API调用
        mock_client.return_value.models.generate_content.assert_called_once()

    @patch("cloud_agent.genai.Client")
    def test_analyze_api_error(self, mock_client):
        """测试分析功能 - API错误处理"""
        # 模拟API错误
        mock_client.return_value.models.generate_content.side_effect = Exception(
            "API Error"
        )

        agent = CloudQuantAgent()

        post_data = {
            "title": "测试帖子",
            "like": 100,
            "comment": 20,
            "save": 50,
            "share": 5,
        }

        result, h_score, z_score = agent.analyze(post_data)

        # 验证错误处理
        self.assertIn("Error", result["analysis"])
        self.assertEqual(result["action"], "Retry")

        # H Score应该正常计算
        self.assertEqual(h_score, 480)

    @patch("cloud_agent.genai.Client")
    def test_analyze_invalid_json(self, mock_client):
        """测试分析功能 - 无效JSON处理"""
        # 设置无效JSON响应
        mock_response = MagicMock()
        mock_response.text = "invalid json response"
        mock_client.return_value.models.generate_content.return_value = mock_response

        agent = CloudQuantAgent()

        post_data = {
            "title": "测试帖子",
            "like": 100,
            "comment": 20,
            "save": 50,
            "share": 5,
        }

        result, h_score, z_score = agent.analyze(post_data)

        # 应该返回错误处理结果
        self.assertIn("Error", result["analysis"])
        self.assertEqual(result["action"], "Retry")


class TestFeishuConnector(unittest.TestCase):
    """测试FeishuConnector类"""

    def setUp(self):
        """测试前设置"""
        self.app_id = "test_app_id"
        self.app_secret = "test_app_secret"

    @patch("cloud_agent.requests.post")
    def test_get_tenant_access_token_success(self, mock_post):
        """测试获取租户访问令牌 - 成功"""
        # 模拟成功响应
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 0,
            "tenant_access_token": "test_token_123",
            "expire": 7200,
            "msg": "ok",
        }
        mock_post.return_value = mock_response

        with patch("builtins.print"):
            connector = FeishuConnector(self.app_id, self.app_secret)

        # 验证token获取
        self.assertEqual(connector.token, "test_token_123")

        # 验证API调用
        mock_post.assert_called_once_with(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
        )

    @patch("cloud_agent.requests.post")
    def test_get_tenant_access_token_failure(self, mock_post):
        """测试获取租户访问令牌 - 失败"""
        # 模拟失败响应
        mock_response = MagicMock()
        mock_response.json.return_value = {"code": 1, "msg": "invalid app_id"}
        mock_post.return_value = mock_response

        with patch("builtins.print"):
            connector = FeishuConnector(self.app_id, self.app_secret)

        # 验证token为None
        self.assertIsNone(connector.token)

    def test_init_with_user_token(self):
        """测试使用用户令牌初始化"""
        user_token = "user_token_123"

        connector = FeishuConnector(self.app_id, self.app_secret, user_token)

        # 验证使用用户令牌
        self.assertEqual(connector.token, user_token)

    @patch("cloud_agent.requests.get")
    def test_get_records_success(self, mock_get):
        """测试获取记录 - 成功"""
        # 模拟成功响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "items": [
                    {"fields": {"标题": "测试标题1"}, "record_id": "rec123"},
                    {"fields": {"标题": "测试标题2"}, "record_id": "rec456"},
                ]
            },
            "msg": "success",
        }
        mock_get.return_value = mock_response

        with patch("cloud_agent.requests.post") as mock_post:
            # 模拟token获取成功
            mock_token_response = MagicMock()
            mock_token_response.json.return_value = {
                "code": 0,
                "tenant_access_token": "token123",
            }
            mock_post.return_value = mock_token_response

            with patch("builtins.print"):
                connector = FeishuConnector(self.app_id, self.app_secret)

        records = connector.get_records("app_token", "table_id")

        # 验证返回结果
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["record_id"], "rec123")

    def test_get_records_no_token(self):
        """测试获取记录 - 无令牌"""
        with patch("cloud_agent.requests.post") as mock_post:
            # 模拟token获取失败
            mock_response = MagicMock()
            mock_response.json.return_value = {"code": 1, "msg": "error"}
            mock_post.return_value = mock_response

            with patch("builtins.print"):
                connector = FeishuConnector(self.app_id, self.app_secret)

        records = connector.get_records("app_token", "table_id")

        # 应该返回空列表
        self.assertEqual(records, [])

    @patch("cloud_agent.requests.get")
    def test_get_records_api_error(self, mock_get):
        """测试获取记录 - API错误"""
        # 模拟API错误
        mock_get.side_effect = Exception("Network Error")

        with patch("cloud_agent.requests.post") as mock_post:
            mock_token_response = MagicMock()
            mock_token_response.json.return_value = {
                "code": 0,
                "tenant_access_token": "token123",
            }
            mock_post.return_value = mock_token_response

            with patch("builtins.print"):
                connector = FeishuConnector(self.app_id, self.app_secret)

        records = connector.get_records("app_token", "table_id")

        # 应该返回空列表
        self.assertEqual(records, [])

    @patch("cloud_agent.requests.put")
    def test_update_record_success(self, mock_put):
        """测试更新记录 - 成功"""
        # 模拟成功响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0, "msg": "success"}
        mock_response.text = '{"code": 0, "msg": "success"}'
        mock_put.return_value = mock_response

        with patch("cloud_agent.requests.post") as mock_post:
            mock_token_response = MagicMock()
            mock_token_response.json.return_value = {
                "code": 0,
                "tenant_access_token": "token123",
            }
            mock_post.return_value = mock_token_response

            with patch("builtins.print"):
                connector = FeishuConnector(self.app_id, self.app_secret)

        success = connector.update_record(
            "app_token", "table_id", "record_id", "AI建议内容"
        )

        # 验证更新成功
        self.assertTrue(success)

    @patch("cloud_agent.requests.put")
    def test_update_record_403_error(self, mock_put):
        """测试更新记录 - 403权限错误"""
        # 模拟403响应
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = '{"code": 91403, "msg": "Forbidden"}'
        mock_put.return_value = mock_response

        with patch("cloud_agent.requests.post") as mock_post:
            mock_token_response = MagicMock()
            mock_token_response.json.return_value = {
                "code": 0,
                "tenant_access_token": "token123",
            }
            mock_post.return_value = mock_token_response

            with patch("builtins.print"):
                connector = FeishuConnector(self.app_id, self.app_secret)

        success = connector.update_record(
            "app_token", "table_id", "record_id", "AI建议内容"
        )

        # 验证更新失败
        self.assertFalse(success)

    @patch("cloud_agent.requests.put")
    def test_update_record_api_error(self, mock_put):
        """测试更新记录 - API异常"""
        # 模拟API异常
        mock_put.side_effect = Exception("Network Error")

        with patch("cloud_agent.requests.post") as mock_post:
            mock_token_response = MagicMock()
            mock_token_response.json.return_value = {
                "code": 0,
                "tenant_access_token": "token123",
            }
            mock_post.return_value = mock_token_response

            with patch("builtins.print"):
                connector = FeishuConnector(self.app_id, self.app_secret)

        success = connector.update_record(
            "app_token", "table_id", "record_id", "AI建议内容"
        )

        # 验证更新失败
        self.assertFalse(success)


if __name__ == "__main__":
    unittest.main(verbosity=2)
