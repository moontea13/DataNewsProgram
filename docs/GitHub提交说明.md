# 提交GitHub

在当前代码目录打开终端。先在GitHub创建一个空仓库，不勾选自动生成README。下面命令中的远程地址换成你自己的仓库地址。

```bash
git init -b main
git status --short
# 确认没有data、outputs、模型、个人文件
git add .
git diff --cached --stat
git commit -m "整合红果数据新闻分析与风格实验"
git remote add origin https://github.com/你的用户名/你的仓库名.git
git push -u origin main
```

若已初始化，则跳过`git init`；若已有origin，则先用`git remote -v`确认地址。首次提交需要已配置自己的Git用户名、邮箱和GitHub登录。代码包不保存账号或访问令牌。

`.gitignore`已排除原始数据、模型、缓存、图片、Excel、成品输出和虚拟环境；GitHub只接收脚本、依赖、模板、方法及结果说明。完整运行产物需另行交接，见[数据准备](数据准备.md)。压缩包是同一套源代码的便携副本，无需把ZIP再提交到仓库。

提交前可执行：

```bash
python run_pipeline.py check
python run_pipeline.py all --dry-run
```

GitHub Actions配置会在推送后运行Windows/Linux、Python 3.10/3.11检查；本地准备配置不等于这些远端任务已经通过。完整实验需要独立数据与模型，不在CI内自动运行。
