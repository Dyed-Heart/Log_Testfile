import pandas as pd
import json
import openai
import os
import time
from openai import OpenAI
from dotenv import load_dotenv

# 从.env中获取api key
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
host_url = "https://api.chatanywhere.tech/v1"
client = OpenAI(
    api_key=api_key,
    base_url=host_url,
    )

# ------------以下为原单次api请求代码--批处理代码前往Line 158-------------

# 读取标注模板 xlsx → system prompt
def xlsx_to_prompt_by_system(xlsx_path, system_name):
    """
    从 Excel 中提取指定系统的标注数据，格式化为可用于 GPT prompt 的文本。

    :param xlsx_path: Excel 文件路径
    :param system_name: 要筛选的 system 名称
    :return: prompt 字符串
    """
    df = pd.read_excel(xlsx_path, engine='openpyxl')

    # 校验字段
    required_columns = ['System', 'Content','EventId', 'EventTemplate', 'Revised', 'Guideline']
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"缺少必要字段：{missing}")
    
    # 去除 Content 和 EventTemplate 为空或全空格的行
    df = df[
            df['Content'].astype(str).str.strip().ne("") &
            df['EventTemplate'].astype(str).str.strip().ne("")
        ].dropna(subset=['Content', 'EventTemplate'])

    # 筛选指定 System
    filtered = df[df['System'] == system_name].dropna(subset=['Content', 'EventTemplate'])

    if filtered.empty:
        return f"未找到 system = {system_name} 的模板数据。"

    # 构造 prompt
    prompt_lines = [
        "You are a log template optimization assistant. Please learn the rules of template review and modification according to the following sample. Among them, the parameter placeholder is composed of two angle brackets and an asterisk: <*>.",
        "You need to: (1) According to the sample log, check if there are any lable errors in the template and correct them; (2) Determine if there are any variable recognition errors: Whether all the corresponding placeholders in a template are truly variables and whether there are any other variables that have not been recognized. Note: The log template must conform to the original log. There is no need to enhance readability, add punctuation, or follow human grammar.",
        "The following are examples that has been manually reviewed and revised. Please output the content in a format similar to JSON without any explanation or markdown wrapping:",
        """
{
  "Revised_template": "example_log <*> example_log"
  "Revision_suggestions": "The original template is complete."
}
        """,
        ""
        
    ]

    for _, row in filtered.iterrows():
        eventid = str(row['EventId']).strip()
        content = str(row['Content']).strip()
        event_template = str(row['EventTemplate']).strip()
        revised_template = str(row['Revised']).strip()
        guideline = str(row['Guideline']).strip()
        
        prompt_lines.append(f"""
            EventId: {eventid}
            Original_log: {content}
            Event_template: {event_template}
            Revised_template: {revised_template}
            Guideline: {guideline}
        """)

    return "\n".join(prompt_lines)


# 调用 GPT 对模板进行审查/优化
def review_template(system_prompt, event_id, template, occurrences, example_log):
    user_prompt = (
        f"Please review and optimize the following template: \n"
        f"EventId: {event_id}\n"
        f"Occurrences: {occurrences}\n"
        f"Template: {template}\n"
        f"Example: {example_log}\n"
        f"Please provide optimization suggestions based on the style of the previous samples and return the optimization template."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3,
            top_p=0.9
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"GPT 请求失败：{e}")
        return "ERROR"


# 读取gpt返回结果，提取模板和建议
def extract_result(gpt_response_text):
    try:
        result = json.loads(gpt_response_text)
        revised = result.get("Revised_template", "").strip()
        suggestion = result.get("Revision_suggestions", "").strip()
        return revised, suggestion
    except json.JSONDecodeError:
        return "ERROR", "ERROR"


# 主函数：读取 csv、逐条审查、写入新文件
def process_template_file(system_name, csv_path, xlsx_path, output_path):
    df = pd.read_csv(csv_path)
    # system_prompt = load_labeled_templates(json_path)
    system_prompt = xlsx_to_prompt_by_system(xlsx_path, system_name)

    reviewed = []

    for idx, row in df.iterrows():
        event_id = row['EventId']
        template = row['EventTemplate']
        occurrences = row['Occurrences']
        example_log = row['ExampleLog']

        print(f"审查模板 EventId={event_id} ...")

        gpt_response_text = review_template(system_prompt, event_id, template, occurrences, example_log)
        reviewed_template, suggestion = extract_result(gpt_response_text)

        reviewed.append({
            "EventId": event_id,
            "Occurrences": occurrences,
            "OriginalTemplate": template,
            "ReviewedTemplate": reviewed_template,
            "Suggestion": suggestion
        })

        time.sleep(1.5)  # 防止 API 速率过快

    # 保存为新 Excel
    out_df = pd.DataFrame(reviewed)
    out_df.to_excel(output_path, index=False)
    print(f"所有模板审查完成，结果保存至 {output_path}")

# ------------------------分隔符------------------------------------------

# 多系统system prompt生成
def xlsx_to_prompt_by_systems(xlsx_path, system_list):
    """
    根据多个 system 筛选示例模板，生成 system prompt。
    """
    df = pd.read_excel(xlsx_path, engine='openpyxl')

    required_columns = ['System', 'Content','EventId', 'EventTemplate', 'Revised', 'Guideline']
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"缺少必要字段：{missing}")

    df = df[
        df['Content'].astype(str).str.strip().ne("") &
        df['EventTemplate'].astype(str).str.strip().ne("")
    ].dropna(subset=['Content', 'EventTemplate'])

    filtered = df[df['System'].isin(system_list)]

    if filtered.empty:
        return f"未找到匹配的系统示例：{system_list}"

    prompt_lines = [
        "You are a log template optimization assistant. Please learn the rules of template review and modification according to the following sample. Among them, the parameter placeholder is composed of two angle brackets and an asterisk: <*>.",
        "You need to: (1) According to the sample log, check if there are any label errors in the template and correct them; (2) Determine if there are any variable recognition errors: Whether all the corresponding placeholders in a template are truly variables and whether there are any other variables that have not been recognized. Note: The log template must conform to the original log. There is no need to enhance readability, add punctuation, or follow human grammar.",
        "The following are examples that have been manually reviewed and revised. Please output the content in a format similar to JSON without any explanation or markdown wrapping:",
        """
[
  {
    "EventId": "E123",
    "System": "System_name",
    "Revised_template": "example_log <*> example_log",
    "Revision_suggestions": "The original template is complete."
  },
  ...
]

        """,
        ""
    ]

    for _, row in filtered.iterrows():
        system = str(row['System']).strip()
        eventid = str(row['EventId']).strip()
        content = str(row['Content']).strip()
        event_template = str(row['EventTemplate']).strip()
        revised_template = str(row['Revised']).strip()
        guideline = str(row['Guideline']).strip()
        prompt_lines.append(f"""
System：{system}
EventId: {eventid}
Original_log: {content}
Event_template: {event_template}
Revised_template: {revised_template}
Guideline: {guideline}
---
""")

    return "\n".join(prompt_lines)


# 调用GPT批量审查模板
def review_templates_batch(system_prompt, batch_rows):
    """
    一次性审查多个模板，构造批量 prompt 并调用 GPT。
    
    :param system_prompt: 多系统构造的示例样本
    :param batch_rows: List[dict]，每条包含 EventId、EventTemplate、Occurrences、ExampleLog 等字段
    :return: GPT 返回的全文字符串（期望为 JSON 数组）
    """
    user_prompt_lines = [
        "Please review and optimize the following log templates:\n",
    ]

    for row in batch_rows:
        user_prompt_lines.append(f"""
System: {row['System']}
EventId: {row['EventId']}
Occurrences: {row.get('Occurrences', 'N/A')}
EventTemplate: {row['EventTemplate']}
ExampleLog: {row['ExampleLog']}
---"""
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n".join(user_prompt_lines)}
    ]

    try:
        print
        start_time = time.time()

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # 可换成 gpt-4 / gpt-3.5 等
            messages=messages,
            temperature=0.3,
            top_p=0.9
        )

        end_time = time.time()
        elapsed = end_time - start_time
        print(f"[INFO] GPT API 调用耗时：{elapsed:.2f} 秒")

        return response.choices[0].message.content
    except Exception as e:
        print(f"[ERROR] GPT 批量请求失败：{e}")
        return "ERROR"


# 批量提取gpt结果
def extract_batch_results(gpt_response_text):
    """
    解析 GPT 的批量 JSON 响应，提取每条记录，以 EventId 为键进行组织。
    要求 GPT 输出为 JSON 数组，每项包含 EventId, System, Revised_template, Revision_suggestions
    """
    try:
        result = json.loads(gpt_response_text)
        assert isinstance(result, list)

        parsed = {}
        for item in result:
            event_id = str(item.get("EventId", "")).strip()
            system = item.get("System", "").strip()
            revised = item.get("Revised_template", "").strip()
            suggestion = item.get("Revision_suggestions", "").strip()

            if event_id:
                parsed[event_id] = {
                    "System": system,
                    "ReviewedTemplate": revised,
                    "Suggestion": suggestion
                }

        return parsed
    except Exception as e:
        print(f"[ERROR] 无法解析 GPT 响应：{e}")
        return {}


# 批处理主函数
def process_template_file_batch_mode(xlsx_path, input_path, output_path, batch_size=10):
    df = pd.read_excel(input_path, engine='openpyxl')
    reviewed = []

    for i in range(0, len(df), batch_size):
        batch_df = df.iloc[i:i + batch_size]
        batch_rows = batch_df.to_dict(orient='records')
        # print("-------batch_rows------")
        # print(batch_rows)
        # print("-----------------------")

        # 获取本 batch 中涉及到的系统
        batch_systems = set(row["System"] for row in batch_rows)

        # 构建 system prompt（从多个系统筛选示例）
        system_prompt = xlsx_to_prompt_by_systems(xlsx_path, list(batch_systems))

        # 调用 GPT 审查
        gpt_response = review_templates_batch(system_prompt, batch_rows)
        # print("------gpt_response-----")
        # print(gpt_response)
        # print("-----------------------")
        results = extract_batch_results(gpt_response)

        # 整理输出
        for row in batch_rows:
            eid = row["EventId"]
            result = results.get(eid, {"ReviewedTemplate": "ERROR", "Suggestion": "ERROR"})

            reviewed.append({
                "EventId": eid,
                "System": row["System"],
                "Occurrences": row["Occurrences"],
                "OriginalTemplate": row["EventTemplate"],
                "ReviewedTemplate": result["ReviewedTemplate"],
                "Suggestion": result["Suggestion"]
            })

        print(f"完成审查：{i + 1} - {i + len(batch_rows)}")
        time.sleep(2)  # 控制频率

    out_df = pd.DataFrame(reviewed)
    out_df.to_excel(output_path, index=False)
    print(f"全部审查完成，保存至：{output_path}")

# 原单次api调用
"""
if __name__ == "__main__":
    # 输入路径
    system_name = "BGL"                             # 提供系统名称
    csv_path = "BGL_2k.log_templates_test.csv"      # 用户提供的初始模板
    # json_path = "templates.json"                  # 人工标注模板 .json
    xlsx_path = "Log_templates_union.xlsx"          # 人工标注模板，包含各个系统 .xlsx
    output_path = "reviewed_templates.xlsx"         # 输出审查结果

    process_template_file(system_name, csv_path, xlsx_path, output_path)
"""

# 批量api调用
if __name__ == "__main__":
    xlsx_path = "Log_templates_union.xlsx"             # 人工审查示例模板集合
    input_path = "Full_test_logs.xlsx"                 # 待审查的模板
    output_path = "Reviewed_templates_batch.xlsx"      # GPT 审查后输出
    process_template_file_batch_mode(xlsx_path, input_path, output_path, batch_size=10)
