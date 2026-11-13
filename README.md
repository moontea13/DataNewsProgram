# 红果短剧同质化 · 数据新闻分析

2026年7—10月红果月榜400条记录的数据处理、Part 1—3分析、封面与标题风格补充实验，以及可直接交给新闻网页使用的JSON、CSV和素材导出。

研究不预设结论：整图相似、标题语义相似、标题结构重复、文字布局接近分别统计；同系列续季不用于证明跨系列相似。全流程自动化，不包含同学匿名评价。当前分析入口不运行抖音、评论采集或完整新闻网站。

## 目录

```text
.
├── run_pipeline.py             跨平台统一入口
├── requirements.txt            轻量检查、整理和导出依赖
├── requirements-models.txt     完整模型与OCR依赖
├── analysis/                   Part 1—3、风格实验、导出、验收、预览模板
├── dataprocessing/             历史采集、清洗、来源与系列关系脚本
├── docs/                       结果解读、数据准备和GitHub提交说明
├── .github/workflows/check.yml Windows/Linux自动检查配置
├── web/                        完整新闻网站的后续位置
└── report/                     创作报告的后续位置
```

源数据、模型、分析缓存、导出成品均单独保存，不进入Git。代码模板本身没有实际数据；直接打开模板HTML不会显示研究结果。

## 安装与检查

建议Python 3.10或3.11，在仓库根目录建立虚拟环境：

```bash
python -m venv .venv
# Windows PowerShell
.venv/Scripts/Activate.ps1
# macOS / Linux 改用：source .venv/bin/activate
python -m pip install -r requirements.txt
python run_pipeline.py check
python run_pipeline.py all --dry-run
```

以上检查不需要数据或模型、不进行采集。完整推理需另安装：

```bash
python -m pip install -r requirements-models.txt
```

模型使用固定commit及权重哈希：DINOv2-small、BGE-M3、中文AIGC检测模型、Chinese CLIP；OCR固定RapidOCR/ONNX Runtime版本。首次模型下载约3.6GB，另需安装依赖和运行内存。默认CPU运行，不需要付费API。原实验曾使用Python 3.10、torch 1.12 CPU、transformers 4.39.3；安装新运行环境后必须重新推理，不能声称跨环境分数逐位相同。

## 数据准备与运行

将独立数据包中的`dataprocessing/data/`放到仓库同名位置；或通过`--source`指定完整的`data`目录。不能只提供一张汇总CSV。输入结构见[数据准备](docs/数据准备.md)。

```bash
# 完整执行：基础分析 → 风格补充 → 两套交付验收
python run_pipeline.py all

# 数据在仓库外，路径有空格时请加引号
python run_pipeline.py all --source "../独立数据包/dataprocessing/data"

# 分阶段运行
python run_pipeline.py base
python run_pipeline.py style

# 已有完整且指纹一致的结果缓存，仅重导出；不是首次运行命令
python run_pipeline.py all --skip-inference

# 模型已下载，仍重新执行推理
python run_pipeline.py all --skip-download
```

相对路径统一以仓库根目录解析，命令从其他目录调用也适用。`style`依赖已完成的`base`。`--skip-inference`仍执行OCR缓存核验并补齐预览图；规则、输入或代码变化时会使旧缓存失效，风格向量需重新计算。

可选参数：`--output`、`--style-output`、`--results`、`--model-cache`、`--ocr-runtime`；对应环境变量见[分析模块](analysis/README.md)。输出、缓存与源数据不得互相包含，避免改写输入。数据处理的历史重建脚本另见[dataprocessing](dataprocessing/README.md)，分析运行不需要重建采集数据。

## 给网页开发者的成品

```text
outputs/
├── part1-3/                    基础成品
│   ├── data/                   指标、分布、矩阵、网络、系列和来源JSON
│   ├── tables/                 CSV及配对明细
│   ├── assets/                 实际封面与缩略图
│   ├── preview/index.html      带数据的离线验收预览
│   └── 数据使用说明.md
└── style/                      标题结构、OCR布局和模型对照成品
    ├── data/
    ├── tables/
    ├── assets/                 封面及OCR框叠图
    ├── preview/index.html
    └── 补充实验结果解读.md
```

运行成功后在Edge等浏览器打开输出目录的`preview/index.html`。预览内嵌数据，不需要启动服务器。分享时打包整个对应输出目录，不能只发送HTML。前端接入以`data/metrics.json`和各包说明为准；完整向量、原文编码和模型元数据在`analysis/results/`，不随网页发布。

## 统计边界与结果版本

- 400条上榜记录、368部分季作品候选、169个确认平台系列、27个待核单元分别保留；169个平台系列不等于已证明互不相关的169个故事。
- 每个系列每种材料仅选一个代表版本；同系列跨季、跨月重复不增加Part 2权重；疑点配对排除而不擅自合并系列。
- [identity_review.json](analysis/identity_review.json)登记两组已发现的人物/设定关联疑点，现在基础分析与补充实验均排除。补充实验另有固定自动筛查。
- 封面、标题、简介的0.85为研究中的模型候选阈值，另输出敏感性分析；不同模型分数不直接比较。风格指标不能改称整图高相似率。
- 简介标签为带原文证据的词项规则提取，未知保留；自动验收不代表人工语义准确率。AIGC检测标签不是作品AI制作或真实AI写作比例。
- 封面和简介来自采集时材料，不冒充上榜月份历史版本；全榜样本不等于已确认AI制作样本。

已有研究结果见[风格补充实验结果](docs/风格补充实验结果.md)。[初轮解读](docs/初轮结果解读.md)是历史分析，包含排除疑点前的旧比例，不作最新引用。补充实验在阅读初轮结果后设计，属于探索分析。以新代码重跑的输出、来源和验收结果为最终引用依据。

## 提交GitHub

本地整理目录可直接作为仓库根目录。[提交说明](docs/GitHub提交说明.md)包含创建远程仓库与推送步骤。`.gitignore`已排除原始数据、图片、Excel、模型、缓存、虚拟环境和导出目录；结果数字与方法解读保留在`docs/`。

GitHub Actions仅运行不依赖数据的单元测试、命令预演及语法检查，不下载大模型，不宣称云端已经复现实验。完整数据验收需在本地运行`all`。
