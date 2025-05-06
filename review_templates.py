import pandas as pd
import json
import openai
import time
from openai import OpenAI

api_key = "sk-1ihU4FLfC7zcWZSNq70HGFpJ3iq5t5yMuNQE2lEJVtWGCak3"
host_url = "https://api.chatanywhere.tech/v1"
client = OpenAI(
    api_key=api_key,
    base_url=host_url,
    )

# 读取标注模板 json → system prompt
def load_labeled_templates(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    prompt_lines = [
        "你是一个日志模板优化助手，请根据以下样例学习模板审查与修改规律。其中，下面这个占位符代表模板中的参数：<*>。你需要判断：（1）分组层面错误：在同一个模板中挑选两个最不相似的模板，来确定这个组是否应该被分为多个模板，或者认为某几个模板是否应该合并；（2）变量识别错误：一个模板里面所有对应的占位符是否真的是变量，是否有其他变量并未被识别。输出要求：", ""
    ]

    for entry in data:
        block = [
            f"系统：{entry.get('system', '')}",
            f"原始日志：{entry.get('content', '')}",
            f"原始模板：{entry.get('event_template', '')}",
            f"优化模板：{entry.get('revised_template', '')}",
            f"修改标签：{entry.get('guideline', '')}",
            ""
        ]
        prompt_lines.extend(block)

    return "\n".join(prompt_lines)

# 调用 GPT 对模板进行审查/优化
def review_template(system_prompt, event_id, template, occurrences):
    user_prompt = (
        f"请审查并优化以下模板：\n"
        f"EventId: {event_id}\n"
        f"出现次数: {occurrences}\n"
        f"模板：{template}\n"
        f"请根据之前样例的风格，给出优化建议或直接返回优化模板。"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"GPT 请求失败：{e}")
        return "ERROR"

# 主函数：读取 csv、逐条审查、写入新文件
def process_template_file(csv_path, json_path, output_path):
    df = pd.read_csv(csv_path)
    system_prompt = load_labeled_templates(json_path)

    reviewed = []

    for idx, row in df.iterrows():
        event_id = row['EventId']
        template = row['EventTemplate']
        occurrences = row['Occurrences']

        print(f"审查模板 EventId={event_id} ...")

        reviewed_template = review_template(system_prompt, event_id, template, occurrences)
        reviewed.append({
            "EventId": event_id,
            "OriginalTemplate": template,
            "Occurrences": occurrences,
            "ReviewedTemplate": reviewed_template
        })

        time.sleep(3)  # 防止 API 速率过快

    # 保存为新 CSV
    out_df = pd.DataFrame(reviewed)
    out_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"所有模板审查完成，结果保存至 {output_path}")


if __name__ == "__main__":
    # 输入路径
    csv_path = "HDFS_2k.log_templates.csv" # 用户提供的初始模板
    json_path = "templates.json"           # 你的人工标注模板
    output_path = "reviewed_templates.csv" # 输出审查结果

    process_template_file(csv_path, json_path, output_path)
