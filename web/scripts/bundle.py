"""为本项目的本地ES模块生成离线入口。开发仍使用原始、可维护模块。"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
modules = {}
blocks = []

def bundle(path):
    path = path.resolve()
    if path in modules:
        return modules[path]
    name = f'__module{len(modules)}'
    modules[path] = name
    code = path.read_text(encoding='utf-8')
    def imports(match):
        binding, target = match.groups()
        dep = bundle(path.parent / target)
        if binding.startswith('* as '):
            return f'const {binding[5:].strip()} = {dep};'
        if binding.startswith('{'):
            binding = re.sub(r'\b(\w+)\s+as\s+(\w+)\b', r'\1: \2', binding)
            return f'const {binding} = {dep};'
        return f'const {binding} = {dep}.default;'
    code = re.sub(r'^import\s+(.+?)\s+from\s+[\'"](.+?)[\'"];?\s*$', imports, code, flags=re.M)
    exports = []
    def export_list(match):
        for item in match.group(1).split(','):
            parts = re.split(r'\s+as\s+', item.strip())
            if parts[0]:
                exports.append(f'{json.dumps(parts[-1])}: {parts[0]}')
        return ''
    code = re.sub(r'\bexport\s*\{([^}]+)\}\s*;?', export_list, code)
    for match in re.finditer(r'^export\s+(?:const|let|var|function|class)\s+(\w+)', code, flags=re.M):
        exports.append(match.group(1))
    code = re.sub(r'\bexport\s+(?=(?:const|let|var|function|class)\b)', '', code)
    code = re.sub(r'^//# sourceMappingURL=.*$', '', code, flags=re.M)
    blocks.append(f'const {name} = (() => {{\n{code}\nreturn {{{",".join(exports)}}};\n}})();')
    return name

def main():
    bundle(ROOT / 'src/main.js')
    data = {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in (ROOT / 'public/data').glob('*.json')}
    data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    script = '\n'.join(blocks).replace('</script', '<\\/script')
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    # 源码入口双击时跳到离线版；离线版本身不能再次跳转。
    html = re.sub(r'    <script id="local-preview">[\s\S]*?</script>\n', '', html)
    html = html.replace('<script type="module" src="./src/main.js"></script>', '<script>window.__STORY_DATA__=' + data_json + ';\n' + script + '</script>')
    (ROOT / 'dist/index.html').write_text(html, encoding='utf-8')
    (ROOT / 'dist/src/offline-bundle.js').write_text(script, encoding='utf-8')
    print(f'已内嵌{len(data)}份数据、{len(modules)}个模块；dist/index.html可直接双击预览。')

if __name__ == '__main__':
    main()
