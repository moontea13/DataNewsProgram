# 红果 Part 1—3 与风格补充实验

统一从仓库根目录运行`python run_pipeline.py all`，详见[根目录说明](../README.md)。仅基础分析使用`base`，仅补充实验使用`style`。先准备独立数据包与完整模型依赖；源数据只读，模型与中间结果不提交Git。

## 路径设置

命令行参数优先于环境变量。所有相对路径以仓库根目录解析。

| 参数 | 环境变量 | 默认值 |
| --- | --- | --- |
| `--source` | `HONGGUO_SOURCE` | `dataprocessing/data` |
| `--output` | `HONGGUO_OUTPUT` | `outputs/part1-3` |
| `--style-output` | `HONGGUO_STYLE_OUTPUT` | `outputs/style` |
| `--results` | `HONGGUO_RESULTS` | `analysis/results` |
| `--model-cache` | `HONGGUO_MODEL_CACHE` | `analysis/.cache/models` |
| `--ocr-runtime` | `HONGGUO_OCR_RUNTIME` | `analysis/.cache/style_runtime` |

OCR通常直接使用虚拟环境内安装的包。`--ocr-runtime`仅兼容已有独立OCR依赖目录，无需特意创建。PowerShell兼容入口：`./analysis/run_analysis.ps1 -Python python -Stage all`。

## 程序与顺序

| 程序 | 功能 |
| --- | --- |
| `prepare.py` | 固定系列/作品/材料关系，选代表版本，核验来源哈希，生成缩略图与排除表 |
| `identity_review.json` | 两组已发现的关联疑点及双方来源，基础与补充口径共同排除 |
| `story_rules.py` | 确定性原文词项编码，30条重复运行试验、原文证据偏移核验 |
| `fetch_models.py` | 固定commit下载三个基础模型，保存权重哈希与官方说明 |
| `infer_models.py cover/text/aigc` | DINOv2、BGE-M3与官方中文文本检测实际推理 |
| `export_news.py` | Part 1—3指标、分布、矩阵、交集、网络、CSV与离线预览 |
| `validate_delivery.py` | 独立重算比例、去重、证据、路径与源文件哈希 |
| `style_features.py prepare/ocr` | 标题模板、身份筛查、OCR文字区域、布局与颜色特征 |
| `style_fetch_models.py` | 固定Chinese CLIP权重下载 |
| `style_models.py dinov2/clip` | 完整图、补边、标题区遮挡与零样本候选推理 |
| `style_export.py` | 补充成品、阈值曲线与关联排除后的基础模型对照 |
| `validate_style.py` | 配对、比例、路径、证据与数据来源验收 |
| `test_*.py` | 去重、未知、证据、路径保护与无数据运行测试 |

`run_pipeline.py`按表中依赖顺序执行；任一步失败立即停止。`--skip-inference`要求已有匹配输入的完整向量和元数据。规则或路径改变导致指纹变化时重新推理，不能手工改指纹绕过验收。风格OCR会核验代码/协议/代表材料及图片指纹，模型元数据还绑定输入和规则。

模型缓存的`manifest.json`保存commit与文件哈希；`results/`保存代表版本、编码、全配对、向量和推理环境。只有导出目录交给网页开发者。单独运行模块时可通过上表环境变量指定相同目录；更推荐统一入口，避免参数不一致。

研究方法、未知与探索属性见[补充复现说明](风格补充实验复现.md)和根目录README。零命中如实保留，不以提高比例为目标选择阈值。
