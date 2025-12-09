import unittest
import os
import sys
from unittest.mock import patch, MagicMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from cloud_agent import CloudQuantAgent, FeishuConnector


class TestCloudAgentIntegration(unittest.TestCase):
    """测试云端代理的集成工作流程"""

    def setUp(self):
        """测试前设置"""
        # 设置环境变量
        os.environ['GEMINI_API_KEY'] = 'test_gemini_key'
        
        # 模拟飞书数据 - 至少3条已分析记录用于构建基准线
        self.mock_records = [
            {
                "fields": {
                    "标题": "测试技术分享",
                    "状态": "已分析",
                    "点赞": 120,
                    "评论": 25,
                    "收藏": 60,
                    "分享": 8,
                    "AI建议": "之前的建议"
                },
                "record_id": "rec123"
            },
            {
                "fields": {
                    "标题": "投资心得分享",
                    "状态": "已分析",
                    "点赞": 200,
                    "评论": 45,
                    "收藏": 100,
                    "分享": 15,
                    "AI建议": "保持频率"
                },
                "record_id": "rec456"
            },
            {
                "fields": {
                    "标题": "生活方式分享",
                    "状态": "已分析",
                    "点赞": 300,
                    "评论": 60,
                    "收藏": 150,
                    "分享": 20,
                    "AI建议": "继续这个风格"
                },
                "record_id": "rec789"
            },
            {
                "fields": {
                    "标题": "新的热门话题",
                    "状态": "待分析",
                    "点赞": 500,
                    "评论": 80,
                    "收藏": 200,
                    "分享": 25,
                },
                "record_id": "rec999"
            }
        ]

    @patch('cloud_agent.requests.post')
    @patch('cloud_agent.requests.get')
    @patch('cloud_agent.requests.put')
    @patch('cloud_agent.genai.Client')
    def test_complete_cloud_workflow(self, mock_genai, mock_put, mock_get, mock_post):
        """测试完整的云端分析工作流程"""
        # 1. 模拟飞书API响应
        # Token获取成功
        mock_token_response = MagicMock()
        mock_token_response.json.return_value = {
            "code": 0,
            "tenant_access_token": "mock_token_123"
        }
        mock_post.return_value = mock_token_response
        
        # 获取记录成功
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "code": 0,
            "data": {"items": self.mock_records}
        }
        mock_get.return_value = mock_get_response
        
        # 更新记录成功
        mock_put_response = MagicMock()
        mock_put_response.status_code = 200
        mock_put_response.json.return_value = {"code": 0}
        mock_put_response.text = '{"code": 0}'
        mock_put.return_value = mock_put_response
        
        # 2. 模拟Gemini API响应
        mock_gemini_response = MagicMock()
        mock_gemini_response.text = '''
        {
            "analysis": "这是一个爆款内容，Z Score远高于历史平均水平",
            "action": "建议制作续集内容，保持这个话题的热度",
            "next_title": "热门话题深度解析：用户最关心的5个问题"
        }
        '''
        mock_genai.return_value.models.generate_content.return_value = mock_gemini_response
        
        # 3. 执行完整工作流程
        with patch('builtins.print'):  # 抑制打印输出
            # 初始化连接器和代理
            fs = FeishuConnector("test_app_id", "test_app_secret")
            agent = CloudQuantAgent()
            
            # 获取记录
            records = fs.get_records("test_app_token", "test_table_id")
            
            # 验证记录获取成功
            self.assertEqual(len(records), 4)
            
            # 构建历史基准线
            agent.build_history_baseline(records)
            
            # 验证基准线构建成功
            self.assertTrue(agent.has_history)
            self.assertGreater(agent.history_mean, 0)
            self.assertGreater(agent.history_std, 0)
            
            # 查找待分析的记录
            pending_record = None
            for record in records:
                if record["fields"].get("状态") == "待分析":
                    pending_record = record
                    break
            
            self.assertIsNotNone(pending_record)
            
            # 分析待分析的记录
            fields = pending_record["fields"]
            post_data = {
                "title": fields["标题"],
                "like": fields["点赞"],
                "comment": fields["评论"],
                "save": fields["收藏"],
                "share": fields["分享"]
            }
            
            result, h_score, z_score = agent.analyze(post_data)
            
            # 验证分析结果
            self.assertIsInstance(result, dict)
            self.assertIn("analysis", result)
            self.assertIn("action", result)
            self.assertIn("next_title", result)
            self.assertGreater(h_score, 0)
            self.assertIsInstance(z_score, (int, float))
            
            # 更新飞书记录
            success = fs.update_record(
                "test_app_token",
                "test_table_id", 
                pending_record["record_id"],
                result["analysis"]
            )
            
            # 验证更新成功
            self.assertTrue(success)

    @patch('cloud_agent.requests.post')
    def test_feishu_token_error_handling(self, mock_post):
        """测试飞书token获取错误处理"""
        # 模拟token获取失败
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 99991663,
            "msg": "App does not exist or has been deleted"
        }
        mock_post.return_value = mock_response
        
        with patch('builtins.print'):
            fs = FeishuConnector("invalid_app_id", "invalid_secret")
        
        # 验证token获取失败
        self.assertIsNone(fs.token)
        
        # 验证后续操作失败
        records = fs.get_records("app_token", "table_id")
        self.assertEqual(records, [])

    @patch('cloud_agent.genai.Client')
    def test_gemini_api_integration(self, mock_genai):
        """测试Gemini API集成"""
        # 模拟不同类型的Gemini响应
        test_cases = [
            {
                "name": "爆款内容",
                "response": '{"analysis": "爆款分析", "action": "追涨操作", "next_title": "续集标题"}',
                "data": {"title": "爆款", "like": 1000, "comment": 200, "save": 300, "share": 50}
            },
            {
                "name": "普通内容",
                "response": '{"analysis": "普通分析", "action": "优化操作", "next_title": "改进标题"}',
                "data": {"title": "普通", "like": 100, "comment": 20, "save": 30, "share": 5}
            }
        ]
        
        agent = CloudQuantAgent()
        
        for case in test_cases:
            with self.subTest(content_type=case["name"]):
                # 设置mock响应
                mock_response = MagicMock()
                mock_response.text = case["response"]
                mock_genai.return_value.models.generate_content.return_value = mock_response
                
                # 执行分析
                result, h_score, z_score = agent.analyze(case["data"])
                
                # 验证结果
                self.assertIn("analysis", result)
                self.assertIn("action", result)
                self.assertIn("next_title", result)
                self.assertGreater(h_score, 0)

    def test_h_score_calculation_consistency(self):
        """测试H Score计算一致性"""
        with patch('cloud_agent.genai.Client'):
            agent = CloudQuantAgent()
        
        # 测试数据
        test_data = [
            {"like": 100, "comment": 20, "save": 50, "share": 5},
            {"like": 500, "comment": 100, "save": 200, "share": 25},
            {"like": 1000, "comment": 300, "save": 400, "share": 50},
        ]
        
        for data in test_data:
            with self.subTest(data=data):
                h_score = agent._calc_h_score(
                    data["like"], data["comment"], 
                    data["save"], data["share"]
                )
                
                # 验证H Score计算
                expected = (data["like"] * 1) + (data["comment"] * 4) + \
                          (data["save"] * 5) + (data["share"] * 10)
                
                self.assertEqual(h_score, expected)

    @patch('cloud_agent.requests.post')
    @patch('cloud_agent.requests.get')
    @patch('cloud_agent.genai.Client')
    def test_error_resilience(self, mock_genai, mock_get, mock_post):
        """测试错误恢复能力"""
        # 设置飞书连接成功
        mock_token_response = MagicMock()
        mock_token_response.json.return_value = {"code": 0, "tenant_access_token": "token"}
        mock_post.return_value = mock_token_response
        
        # 设置获取记录成功
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "code": 0,
            "data": {"items": self.mock_records}
        }
        mock_get.return_value = mock_get_response
        
        # 模拟Gemini API错误
        mock_genai.return_value.models.generate_content.side_effect = Exception("Network Error")
        
        with patch('builtins.print'):
            fs = FeishuConnector("app_id", "app_secret")
            agent = CloudQuantAgent()
            
            # 获取记录应该成功
            records = fs.get_records("app_token", "table_id")
            self.assertEqual(len(records), 4)
            
            # 构建基准线应该成功
            agent.build_history_baseline(records)
            self.assertTrue(agent.has_history)
            
            # 分析即使API失败也应该返回默认结果
            post_data = {"title": "测试", "like": 100, "comment": 20, "save": 50, "share": 5}
            result, h_score, z_score = agent.analyze(post_data)
            
            # 验证错误处理
            self.assertIn("Error", result["analysis"])
            self.assertEqual(result["action"], "Retry")
            self.assertEqual(h_score, 480)  # H Score应该正常计算


if __name__ == '__main__':
    unittest.main(verbosity=2)