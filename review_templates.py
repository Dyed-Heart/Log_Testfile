import pandas as pd
import json
import openai
import time
from openai import OpenAI

api_key = ""
host_url = "https://api.chatanywhere.tech/v1"
client = OpenAI(
    api_key=api_key,
    base_url=host_url,
    )

# 读取标注模板 json → system prompt （已弃置）
def load_labeled_templates(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    prompt_lines = [
        "You are a log template optimization assistant. Please learn the rules of template review and modification according to the following sample. Among them, the following placeholder represents the parameter in the template: <*>. You need to: (1) According to the sample log, check if there are any symbol errors in the template and correct them; (2) Determine if there are any variable recognition errors: Whether all the corresponding placeholders in a template are truly variables and whether there are any other variables that have not been recognized. Note: The log template needs to be consistent with the original log. There is no need to increase readability, add punctuation, or conform to human grammar, etc.", ""
    ]

    for entry in data:
        block = [
            f"System: {entry.get('system', '')}",
            f"Original_log: {entry.get('content', '')}",
            f"Event_template: {entry.get('event_template', '')}",
            f"Revised_template: {entry.get('revised_template', '')}",
            f"Guideline: {entry.get('guideline', '')}",
            ""
        ]
        prompt_lines.extend(block)

    return "\n".join(prompt_lines)


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
        "You are a log template optimization assistant. Please learn the rules of template review and modification according to the following sample. Among them, the following placeholder represents the parameter in the template: <*>. You need to: (1) According to the sample log, check if there are any symbol errors in the template and correct them; (2) Determine if there are any variable recognition errors: Whether all the corresponding placeholders in a template are truly variables and whether there are any other variables that have not been recognized. Note: The log template needs to be consistent with the original log. There is no need to increase readability, add punctuation, or conform to human grammar, etc.", ""
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
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"GPT 请求失败：{e}")
        return "ERROR"

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

        reviewed_template = review_template(system_prompt, event_id, template, occurrences, example_log)
        reviewed.append({
            "EventId": event_id,
            "Occurrences": occurrences,
            "OriginalTemplate": template,
            "ReviewedTemplate": reviewed_template
        })

        time.sleep(3)  # 防止 API 速率过快

    # 保存为新 CSV
    out_df = pd.DataFrame(reviewed)
    out_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"所有模板审查完成，结果保存至 {output_path}")


if __name__ == "__main__":
    # 输入路径
    system_name = "BGL"                             # 提供系统名称
    csv_path = "BGL_2k.log_templates_with_log.csv"  # 用户提供的初始模板
    # json_path = "templates.json"                  # 人工标注模板 .json
    xlsx_path = "fixed.xlsx"                        # 人工标注模板，包含各个系统 .xlsx
    output_path = "reviewed_templates_1.csv"        # 输出审查结果

    process_template_file(system_name, csv_path, xlsx_path, output_path)
