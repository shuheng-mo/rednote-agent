import json
import os

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


class FeishuConnector:
    def __init__(self, app_id, app_secret, user_access_token=None):
        self.app_id = app_id
        self.app_secret = app_secret
        self.user_access_token = user_access_token

        # 优先使用用户令牌，否则使用应用令牌
        if user_access_token:
            self.token = user_access_token
        else:
            self.token = self._get_tenant_access_token()

    def _get_tenant_access_token(self):
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(
            url, json={"app_id": self.app_id, "app_secret": self.app_secret}
        )
        result = resp.json()
        if result.get("code") == 0:
            return result.get("tenant_access_token")
        else:
            return None

    def get_records(self, app_token, table_id):
        if not self.token:
            return []

        # 读取"待分析"的数据
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        headers = {"Authorization": f"Bearer {self.token}"}
        # 筛选条件：状态=待分析 (这里简化处理，读取全部，代码里过滤)

        try:
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("code") == 0:
                    return result.get("data", {}).get("items", [])
                else:
                    return []
            else:
                return []
        except Exception as e:
            return []

    def update_record(self, app_token, table_id, record_id, ai_suggestion):
        if not self.token:
            return False

        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        payload = {
            "fields": {
                "AI建议": ai_suggestion,
                "状态": "已分析",  # 更新状态，避免重复跑
            }
        }

        try:
            response = requests.put(url, headers=headers, json=payload)
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    return True
                else:
                    return False
            else:
                return False
        except Exception as e:
            return False


class CloudQuantAgent:
    def __init__(self):
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        # 历史统计基准
        self.history_mean = 0.0
        self.history_std = 1.0
        self.has_history = False

    def _calc_h_score(self, like, comment, save, share):
        """核心因子公式"""
        return (like * 1) + (comment * 4) + (save * 5) + (share * 10)

    def build_history_baseline(self, all_records):
        """
        Step 1: 遍历所有记录，计算历史 H Score 的均值和标准差
        """
        h_scores = []

        for item in all_records:
            fields = item["fields"]
            status = fields.get("状态", "")

            # 只使用"已分析"的旧数据来构建基准线，避免数据偷窥
            if status == "已分析":
                h = self._calc_h_score(
                    fields.get("点赞", 0),
                    fields.get("评论", 0),
                    fields.get("收藏", 0),
                    fields.get("分享", 0),
                )
                h_scores.append(h)

        # 计算统计量
        if len(h_scores) > 2:
            self.history_mean = np.mean(h_scores)
            self.history_std = np.std(h_scores)
            if self.history_std == 0:
                self.history_std = 1e-5  # 防止除零
            self.has_history = True
        else:
            pass

    def analyze(self, post_data):
        """
        Step 2: 分析单条数据，结合 Z-Score
        """
        # 1. 计算绝对热度 H Score
        like = post_data["like"]
        comment = post_data["comment"]
        save = post_data["save"]
        share = post_data["share"]

        h_score = self._calc_h_score(like, comment, save, share)

        # 2. 计算相对表现 Z Score
        z_score = 0.0
        if self.has_history:
            z_score = (h_score - self.history_mean) / self.history_std

        # 3. 生成 Prompt
        prompt = f"""
        你是一个量化内容运营专家。请根据以下指标分析这篇笔记：

        【当前数据】
        - 标题: {post_data['title']}
        - H Score (绝对热度): {h_score}
        - Z Score (相对表现): {z_score:.2f} (历史均值: {self.history_mean:.2f})
        - 因子明细: 点赞{like}, 评论{comment}, 收藏{save}, 分享{share}

        【判断标准】
        - Z > 1.0 : 爆款 (Alpha收益) -> 建议追涨/出系列。
        - Z < -0.5: 跑输大盘 -> 建议止损/改进封面。
        - 收藏高但Z分低: 属于干货但流量池受限。

        请输出简短的 JSON 格式建议：
        {{
            "analysis": "一句话评价表现",
            "action": "下一步具体操作 (如：修改标题/回复评论/准备下一篇)",
            "next_title": "建议的下期标题"
        }}
        只输出 JSON 字符串。
        """

        try:
            resp = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
            return json.loads(resp.text), h_score, z_score
        except Exception as e:
            return {"analysis": f"Error: {str(e)}", "action": "Retry"}, h_score, z_score
