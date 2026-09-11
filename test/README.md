# 测试输出

本文件夹中的文件会在测试结束后保留，可直接用 Excel 打开。

| 步骤 | 文件 | 内容 |
| --- | --- | --- |
| 1 | [json_to_excel.xlsx](json_to_excel.xlsx) | 按评论 ID 汇总，展开四元组 |
| 2 | [output.xlsx](output.xlsx) | 添加商家、整体情感与日期 |
| 3 | [filted.xlsx](filted.xlsx) | 商家评论数至少 20，按 ID 排序 |
| 4 | [sentiment_counted.xlsx](sentiment_counted.xlsx) | 将三个整体情感值转换为 sentiment |
| 5 | [yelp_data_processed.xlsx](yelp_data_processed.xlsx) | 仅 ID、business_name、date、sentiment 与方面向量列 |

小样例的每步文件在 demo/；各自动化测试文件在 unit/。test_results.json 记录实际执行命令和退出码，independent_validation.json 记录全量核验结果。

## 新增拓展的三步输出

| 步骤 | 文件 | 内容 |
| --- | --- | --- |
| 6 | [attribute_filter.xlsx](attribute_filter.xlsx) | 保留非 999 出现次数最多的 10 个方面 |
| 7 | [business_consistency_counted.xlsx](business_consistency_counted.xlsx) | 增加行标准差 consistency 和商家平均 business_aspect_consistency |
| 8 | [yelp_data_processed_updated.xlsx](yelp_data_processed_updated.xlsx) | 按 ID 排序并增加前 10 条记录的 average_sentiment_10 |

新小样例每步文件保存在 `extension_unit/`。`extension_report.json` 保存筛选次数和执行路径，`extension_validation.json` 保存独立全量核验结果，`iteration_audit.json` 记录原五步核心代码未改写的核对结果。

只测试已有最终数据的拓展步骤：`python scripts/run_tests.py --extension-input test/yelp_data_processed.xlsx`。

运行命令（在项目目录）：

`python scripts/run_tests.py --data-dir ../data`
