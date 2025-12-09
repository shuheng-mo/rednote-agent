import json
import os

import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


class QuantContentAgent:
    def __init__(self, history_file="post_data.csv"):
        # 1. 初始化 Client
        self.client = genai.Client()

        # 2. 读取历史数据
        try:
            self.history = pd.read_csv(history_file)
        except FileNotFoundError:
            # 确保列名包含计算 H Score 所需的所有字段
            self.history = pd.DataFrame(
                columns=["title", "like", "comment", "save", "share"]
            )

    def _calculate_h_score(self, row):
        """
        核心因子公式：干货热度指数 (H Score)
        H = (Like * 1) + (Comment * 4) + (Save * 5) + (Share * 10)
        """
        # 定义因子权重 (Factor Weights)
        W_LIKE = 1
        W_COMMENT = 4
        W_SAVE = 5
        W_SHARE = 10

        # 容错处理：使用 .get() 防止缺少字段，默认值为 0
        likes = row.get("like", 0)
        comments = row.get("comment", 0)
        saves = row.get("save", 0)
        shares = row.get("share", 0)

        return likes * W_LIKE + comments * W_COMMENT + saves * W_SAVE + shares * W_SHARE

    def get_market_metrics(self, new_post):
        """
        计算当前帖子的市场表现指标 (Raw Score & Z-Score)
        """
        # 1. 计算当前帖子的 H Score
        current_h_score = self._calculate_h_score(new_post)

        # 2. 计算历史 H Score 分布 (用于计算 Z-Score)
        z_score = 0.0
        if not self.history.empty and len(self.history) > 2:
            # 对历史每一行数据应用 H Score 公式
            history_scores = self.history.apply(self._calculate_h_score, axis=1)

            mean = history_scores.mean()
            std = history_scores.std()

            # 防止标准差为 0
            if std == 0:
                std = 1e-5

            z_score = (current_h_score - mean) / std

        return current_h_score, z_score

    def ai_strategic_decision(self, new_post, h_score, z_score, user_comments):
        # 构造详细的因子解释，让 AI 理解分数的构成
        factor_breakdown = (
            f"点赞({new_post.get('like',0)}) + "
            f"评论({new_post.get('comment',0)}x4) + "
            f"收藏({new_post.get('save',0)}x5) + "
            f"分享({new_post.get('share',0)}x10)"
        )

        prompt = f"""
        你是一个资深的【小红书量化运营专家】。我们使用【干货热度指数 (H Score)】来评估内容质量。

        【当前行情数据】
        - 帖子标题: "{new_post['title']}"
        - H Score (绝对热度): {h_score} (因子构成: {factor_breakdown})
        - Z Score (相对表现): {z_score:.2f} ( > 1.0 为显著爆款, < -0.5 为表现不及预期)
        - 用户评论摘录: "{user_comments}"

        【决策逻辑】
        - 如果 H Score 高且由“收藏/分享”主导 -> 判定为“硬核干货”，策略应为【追涨/出进阶版】。
        - 如果 H Score 高且由“评论”主导 -> 判定为“高争议/高互动”，策略应为【互动/答疑】。
        - 如果 Z Score 低 -> 判定为“冷门”，策略应为【止损/换方向】。

        【任务】
        请基于上述逻辑，输出 JSON 格式决策：
        1. analysis: 结合因子构成，分析数据背后的用户行为。
        2. strategy: 决策类型 (追涨/止损/互动/修正)。
        3. next_title_suggestions: [2个建议标题]。
        4. cover_prompt: 封面提示词。
        """

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", temperature=0.7
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            return None

    def run_review(self, new_post, comments):
        h_score, z_score = self.get_market_metrics(new_post)
        decision = self.ai_strategic_decision(new_post, h_score, z_score, comments)
        return decision
