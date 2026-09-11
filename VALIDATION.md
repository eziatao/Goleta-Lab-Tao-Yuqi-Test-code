# 1.2.0 拓展与验证记录

## 迭代范围

新增 extensions 包中的方面筛选、标准差及商家均值、前序情感均值模块和独立编排器。原五个核心处理模块，以及原 pipeline.py、common.py、excel_io.py 的 SHA-256 与修改前完全相同。原 tests/test_pipeline.py 也保持不变。

对现有代码仅作局部接入：cli.py 增加四个命令，analysis.py 排除三个新增统计字段，scripts/run_tests.py 增加拓展测试入口，并更新版本号和 README。详见 test/iteration_audit.json。没有整库重写。

## 实际执行

工作副本：`C:\Users\EzioTao\Documents\Codex\2026-09-11\c-codex-project-yelp-data-processing\work\project`。Python 3.12.14、openpyxl 3.1.5，已实际安装项目 1.2.0。

```text
.venv\Scripts\python.exe -m pip install --no-cache-dir --no-build-isolation --no-deps --force-reinstall .
.venv\Scripts\python.exe scripts/run_tests.py --extension-input test/yelp_data_processed.xlsx
```

统一测试入口的展开命令和退出码见 test/test_results.json。33 项测试全部通过，包括原 21 项测试、12 项新增测试、逐个执行原五个 CLI 命令、三个新增独立命令、extend 编排、查询和分析兼容性测试。原五步小样例也执行成功。

真实数据的三个拓展步骤全部成功，随后独立脚本通过重新计算逐单元格核对三个工作簿，未调用新模块的计算函数。

## 三步真实输出

| 文件 | 数据行 | 列数 |
| --- | ---: | ---: |
| attribute_filter.xlsx | 81,577 | 14 |
| business_consistency_counted.xlsx | 81,577 | 16 |
| yelp_data_processed_updated.xlsx | 81,577 | 17 |

三个文件均在 test/ 根目录持久保存，测试结束不删除。小型边界测试输入及每步输出在 test/extension_unit/ 下。新步骤实测总耗时 76.619 秒，不含独立全量核验。

选出的方面及非 999 评论数：

| 方面 | 非 999 数量 |
| --- | ---: |
| food quality | 40,705 |
| service general | 23,892 |
| restaurant general | 22,663 |
| restaurant miscellaneous | 13,714 |
| ambience general | 11,517 |
| food style_options | 5,912 |
| drinks quality | 5,083 |
| food prices | 2,646 |
| restaurant prices | 1,956 |
| location general | 1,930 |

## 计算口径及检查结果

- 按用户确认，标准差排除 999，使用总体标准差（ddof=0）。单个有效值为 0，无有效值留空；商家均值忽略空值但包含 0。
- 370 条评论的所选方面全为 999，其 consistency 留空。全部 consistency 为空的商家数为 0。
- 全表按 ID 数字段升序排序。average_sentiment_10 使用前最多 10 条记录，不包含当前行，不按商家分组；首行留空。
- 核验通过：筛选频数、字段选择与次序、三个文件的全部字段值、全部 81,577 行的 ID 与排序、行标准差、商家均值、前序均值和空值规则。报告见 test/extension_validation.json。
- 原五步输入和输出保留，原 run 命令仍只执行五步；新步骤通过 extend 或三个独立子命令显式执行。

## 交付位置

当前交付目录 outputs/test 和完整项目 ZIP 中包含全部新旧测试产物。原指定目录 C:\codex project\YELP-DATA-PROCESSING 的最终同步状态另见同步结果；此前因 Windows 授权刷新故障，已验证版本一直在上述工作副本中维护。已准备 complete_install.cmd / complete_install.py，必要时可把完整项目包同步至指定目录并重新安装测试。

本次最终同步尝试：用户已授予目标目录写权限，但执行环境仍返回 `setup refresh had errors`，安装进程未启动，目标目录尚未同步。当前有效交付为 outputs 中的完整项目包和 test 文件夹。详情见 test/sync_status.json。
