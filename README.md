# AI短剧同质化数据新闻

2026年7—10月月榜数据的采集、整理与后续数据新闻分析。当前实现集中在`dataprocessing/`；分析、网页与创作报告分别维护。

| 目录 | 分工 | 当前状态 |
| --- | --- | --- |
| [dataprocessing/](dataprocessing/README.md) | 数据爬取、清洗、来源留存、作品与系列关联、交付索引 | 已实现 |
| [analysis/](analysis/README.md) | 封面与剧名相似度、简介/评论编码、统计与图表 | 后续分析位置 |
| [web/](web/README.md) | 数据新闻网页与交互展示 | 后续网页位置 |
| [report/](report/README.md) | 创作报告、方法描述、最终作品导出 | 后续报告位置 |

## 代码与数据分别交接

仓库只提交脚本、依赖和说明。原始网页、榜图、封面、完整数据表与Excel均由`.gitignore`排除，通过独立数据包交接，不使用Git LFS。

队友克隆仓库后，在仓库根目录解压数据包。包内路径以`dataprocessing/`开头，会自动还原到正确目录，然后运行：

```bash
cd dataprocessing
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
bash scripts/重建数据.sh
```

重建使用本地缓存，不联网、不自动确认待核作品。继续抓取评论的命令、字段口径和剩余工作见[数据处理说明](dataprocessing/README.md)。

用户原方案及两份课程Word保持本地原样，不纳入代码仓库。分析模块应明确区分上榜记录、作品候选与独立系列，并保留版本和证据的待核状态。
