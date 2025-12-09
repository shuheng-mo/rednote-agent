#!/usr/bin/env python3
"""
云端代理运行器 - GitHub Actions入口点
"""

import json
import os

from cloud_agent import CloudQuantAgent, FeishuConnector


def main():
    """主运行函数"""
    # 从环境变量获取密钥
    FS_APP_ID = os.environ["FS_APP_ID"]
    FS_APP_SECRET = os.environ["FS_APP_SECRET"]
    FS_APP_TOKEN = os.environ["FS_APP_TOKEN"]
    FS_TABLE_ID = os.environ["FS_TABLE_ID"]
    FS_USER_ACCESS_TOKEN = os.environ.get("FS_USER_ACCESS_TOKEN")

    # 初始化连接器和代理
    fs = FeishuConnector(FS_APP_ID, FS_APP_SECRET, FS_USER_ACCESS_TOKEN)
    agent = CloudQuantAgent()

    # 获取记录
    records = fs.get_records(FS_APP_TOKEN, FS_TABLE_ID)
    if not records:
        print("未获取到任何记录")
        return

    # 构建历史基准线
    agent.build_history_baseline(records)

    # 处理待分析记录
    processed_count = 0
    for item in records:
        fields = item["fields"]
        record_id = item["record_id"]
        status = fields.get("状态", "")

        if status == "待分析":
            post_data = {
                "title": fields.get("标题", "无标题"),
                "like": fields.get("点赞", 0),
                "comment": fields.get("评论", 0),
                "save": fields.get("收藏", 0),
                "share": fields.get("分享", 0),
            }

            # 分析数据
            analysis_result, h_score, z_score = agent.analyze(post_data)

            # 转换为JSON字符串
            ai_suggestion_text = json.dumps(
                analysis_result, ensure_ascii=False, indent=2
            )

            # 更新记录
            success = fs.update_record(
                FS_APP_TOKEN, FS_TABLE_ID, record_id, ai_suggestion_text
            )

            if success:
                processed_count += 1

    print(f"处理完成，共分析 {processed_count} 条记录")


if __name__ == "__main__":
    main()
