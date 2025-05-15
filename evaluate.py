import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score

def jaccard_similarity(str1, str2):
    tokens1 = set(str1.strip().split())
    tokens2 = set(str2.strip().split())
    if not tokens1 or not tokens2:
        return 0.0
    return len(tokens1 & tokens2) / len(tokens1 | tokens2)

def evaluate_template_match_by_system(gpt_path, human_path, output_path, threshold):
    # 1. 读取数据
    gpt_df = pd.read_excel(gpt_path, engine="openpyxl")
    human_df = pd.read_excel(human_path, engine="openpyxl")

    # 2. 检查字段存在
    required_cols = ["EventId", "System", "ReviewedTemplate"]
    for col in required_cols:
        if col not in gpt_df.columns:
            raise ValueError(f"GPT 文件缺少字段: {col}")
    if "Revised" not in human_df.columns:
        raise ValueError("人工文件缺少字段: Revised")

    # 3. 按 System + EventId 进行合并
    merged_df = pd.merge(
        gpt_df,
        human_df[["EventId", "System", "Revised"]],
        on=["EventId", "System"],
        suffixes=("_GPT", "_Human")
    )

    similarity_scores = []
    match_results = []

    for _, row in merged_df.iterrows():
        gpt_template = str(row["ReviewedTemplate"]).strip()
        human_template = str(row["Revised"]).strip()

        similarity = jaccard_similarity(gpt_template, human_template)
        match = 1 if similarity >= threshold else 0

        similarity_scores.append(similarity)
        match_results.append(match)

    merged_df["SimilarityScore"] = similarity_scores
    merged_df["MatchResult"] = match_results

    # 4. 评估指标
    y_true = [1] * len(match_results)
    y_pred = match_results
    precision = precision_score(y_true, y_pred)
    recall = recall_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred)

    # 5. 将统计指标也写入 Excel（附加一行在末尾）
    summary_row = pd.DataFrame([{
        "EventId": "指标统计",
        "System": "",
        "ReviewedTemplate": "",
        "Revised": f"Precision={precision:.4f}",
        "SimilarityScore": f"Recall={recall:.4f}",
        "MatchResult": f"F1={f1:.4f}"
    }])

    final_df = pd.concat([merged_df, summary_row], ignore_index=True)

    # 6. 保存
    final_df.to_excel(output_path, index=False)
    print(f"模板比对完成（阈值={threshold}）")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 Score:  {f1:.4f}")
    print(f"结果已保存至：{output_path}")

# 示例调用
if __name__ == "__main__":
    evaluate_template_match_by_system(
        gpt_path="Reviewed_templates_batch.xlsx",   # GPT生成的结果
        human_path="Manual_revised_filled.xlsx",    # 人工审查后的标准结果
        output_path="Evaluation_output.xlsx",       # 比对结果
        threshold=0.9
    )
