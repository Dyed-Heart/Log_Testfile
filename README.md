### 基于大语言模型的日志模板生成方法与闭环验证体系构建

---

review_templates.py为主程序

输入：

* Log_templates_union.xlsx
  * 人工审查示例模板集合，用于形成system prompt

* Full_test_logs.xlsx
  * 待审查的模板

输出：

* Reviewed_templates_batch.xlsx
  * GPT批量输出的修正模板

---

evaluate.py为评估程序，用来计算GPT输出模板获得的准确率、回归率和F1

输入：

* Reviewed_templates_batch.xlsx
  * 上文GPT批量输出的修正模板

* Manual_revised_filled.xlsx
  * 人工审查后的标准结果

输出：

* Evaluation_output.xlsx
  * 比对结果
