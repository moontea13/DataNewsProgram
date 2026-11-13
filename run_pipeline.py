"""Portable entry point. No data download or model inference occurs on import."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PATHS = {
    'source': ('HONGGUO_SOURCE', 'dataprocessing/data'),
    'output': ('HONGGUO_OUTPUT', 'outputs/part1-3'),
    'style_output': ('HONGGUO_STYLE_OUTPUT', 'outputs/style'),
    'results': ('HONGGUO_RESULTS', 'analysis/results'),
    'model_cache': ('HONGGUO_MODEL_CACHE', 'analysis/.cache/models'),
    'ocr_runtime': ('HONGGUO_OCR_RUNTIME', 'analysis/.cache/style_runtime'),
}
REQUIRED_SOURCE = (
    '红果400条交付/系列合并/上榜记录_系列季映射.json',
    '红果400条交付/系列合并/季作品表.json',
    '红果400条交付/系列合并/系列汇总.json',
    '红果400条交付/简介封面材料明细.json',
    '交付索引/上榜记录总索引.csv',
)


def resolve_path(value):
    path = Path(value).expanduser()
    return (ROOT / path).resolve() if not path.is_absolute() else path.resolve()


def overlaps(a, b):
    return a == b or a in b.parents or b in a.parents


def validate_paths(paths):
    # Generated artifacts must never replace source data or one another.
    names = ['source', 'output', 'style_output', 'results', 'model_cache']
    for i, name in enumerate(names):
        for other in names[i + 1:]:
            if overlaps(paths[name], paths[other]):
                raise ValueError(f'目录不能互相包含：{name}={paths[name]} / {other}={paths[other]}')
    for name in ['output', 'style_output', 'results', 'model_cache']:
        if paths[name] == ROOT or paths[name] in ROOT.parents:
            raise ValueError(f'{name}不能是仓库根目录或其父目录')


def commands(stage, skip_inference=False, skip_download=False):
    checks = [
        ['-m', 'unittest', 'discover', '-s', 'analysis', '-p', 'test_*.py'],
        ['-m', 'unittest', 'discover', '-s', 'analysis', '-p', 'validate_style.py'],
        ['-m', 'unittest', 'discover', '-s', 'dataprocessing/scripts', '-p', 'test_*.py'],
    ]
    if stage == 'check':
        return checks
    steps = []
    if stage in ('base', 'all'):
        steps += [['analysis/prepare.py'], ['analysis/story_rules.py']]
        if not skip_inference:
            if not skip_download:
                steps += [['analysis/fetch_models.py']]
            steps += [['analysis/infer_models.py', mode] for mode in ('cover', 'text', 'aigc')]
        steps += [['analysis/export_news.py'], ['analysis/validate_delivery.py']]
    if stage in ('style', 'all'):
        steps += [['analysis/style_features.py', 'prepare'], ['analysis/style_features.py', 'ocr']]
        if not skip_inference:
            if not skip_download:
                steps += [['analysis/style_fetch_models.py']]
            steps += [['analysis/style_models.py', mode] for mode in ('dinov2', 'clip')]
        steps += [['analysis/style_export.py'], ['analysis/validate_style.py']]
    return steps


def main(argv=None):
    parser = argparse.ArgumentParser(description='红果 Part 1—3 与风格实验：运行、导出和验收')
    parser.add_argument('stage', choices=['base', 'style', 'all', 'check'], nargs='?', default='all')
    for name, (env, default) in PATHS.items():
        parser.add_argument('--' + name.replace('_', '-'), default=os.environ.get(env) or default)
    parser.add_argument('--skip-inference', action='store_true', help='复用已存在且指纹一致的向量；OCR仍核验缓存并补齐预览图')
    parser.add_argument('--skip-download', action='store_true', help='使用本地模型权重，不运行下载器')
    parser.add_argument('--dry-run', action='store_true', help='仅打印路径和命令，不要求数据、不写文件、不联网')
    args = parser.parse_args(argv)
    paths = {name: resolve_path(getattr(args, name)) for name in PATHS}
    try:
        validate_paths(paths)
    except ValueError as error:
        parser.error(str(error))
    if args.stage != 'check' and not args.dry_run:
        missing = [str(paths['source'] / file) for file in REQUIRED_SOURCE if not (paths['source'] / file).is_file()]
        if missing:
            parser.error('源数据不完整；请解压独立数据包或用 --source 指定 data 目录：\n' + '\n'.join(missing))
        if args.stage == 'style':
            for file in (paths['results'] / 'representatives.json', paths['output'] / 'data/series.json'):
                if not file.is_file():
                    parser.error(f'请先运行 base 阶段：缺少 {file}')
    env = os.environ.copy()
    env.update({env_name: str(paths[name]) for name, (env_name, _) in PATHS.items()})
    env['PYTHONUTF8'] = '1'
    for name, path in paths.items():
        print(f'{name}: {path}', flush=True)
    try:
        for step in commands(args.stage, args.skip_inference, args.skip_download):
            command = [sys.executable, '-X', 'utf8', *step]
            print('> ' + shlex.join(command), flush=True)
            if not args.dry_run:
                subprocess.run(command, cwd=ROOT, env=env, check=True)
    except subprocess.CalledProcessError as error:
        return error.returncode
    return 0


if __name__ == '__main__':
    sys.exit(main())
