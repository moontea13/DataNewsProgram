"""兼容代码与数据分开存放的本地交付目录。"""
from pathlib import Path

代码目录 = Path(__file__).resolve().parents[1]
ROOT = 代码目录 if (代码目录 / "data").is_dir() else 代码目录.parents[1] / "dataprocessing"
