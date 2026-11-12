// 使用预置 artifact-tool，读取生成交付索引.py 的统一数据导出可筛选清单。
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const runtimeDir = path.join(os.tmpdir(), 'datacrawl-delivery-export');
const deps = path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
await fs.mkdir(runtimeDir, {recursive: true});
try { await fs.symlink(deps, path.join(runtimeDir, 'node_modules'), 'dir'); }
catch (e) { if (e.code !== 'EEXIST') throw e; }
const req = createRequire(path.join(runtimeDir, 'package.json'));
const { Workbook, SpreadsheetFile, FileBlob } = await import(pathToFileURL(req.resolve('@oai/artifact-tool')).href);
if (process.argv.includes('--inspect-existing')) {
  const existing = await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(root, 'outputs/采集交付清单.xlsx')));
  console.log((await existing.inspect({kind: 'sheet', include: 'id,name', maxChars: 2000})).ndjson);
  console.log((await existing.inspect({kind: 'table', range: '缺口明细!A5:C10', tableMaxRows: 6, tableMaxCols: 3, maxChars: 1500})).ndjson);
  const preview = await existing.render({sheetName: '缺口明细', range: 'A1:C10', scale: 1.4, format: 'png'});
  await fs.writeFile(path.join(runtimeDir, '修改前缺口.png'), new Uint8Array(await preview.arrayBuffer()));
  process.exit(0);
}
const input = JSON.parse(await fs.readFile(path.join(root, 'data/交付索引/表格数据.json'), 'utf8'));
const out = path.join(root, 'outputs');
const previews = path.join(runtimeDir, 'previews');
await fs.mkdir(out, {recursive: true});
await fs.mkdir(previews, {recursive: true});
const wb = Workbook.create();
const schemas = [
  ['总览', ['项目', '数量', '说明'], [34, 12, 86]],
  ['上榜索引', ['上榜记录ID', '月份', '平台', '名次', '榜单原名', '作品ID', '系列ID', '季号', '材料状态', '评论状态', '选定候选可见热评数', '全部候选可见热评数', '抖音待核索引片段数', '同作品其他上榜记录', '本条缺口类别', '当前权威映射表路径'], [31, 12, 9, 8, 46, 42, 33, 10, 33, 38, 20, 20, 20, 46, 72, 90]],
  ['红果作品', ['系列ID', '系列名称', '作品ID', '剧名', '季号', '系列状态', '上榜次数', '上榜记录ID列表', '同系列其他作品数', '素材ID列表', '候选热评数', '季号状态', '来源表路径'], [33, 42, 42, 46, 10, 36, 12, 58, 20, 48, 14, 58, 75]],
  ['素材明细', ['上榜记录ID', '系列ID', '作品ID', '素材ID', '材料标题', '是否选定候选', '来源类别', '简介字数', '封面路径', '原始页面路径', '来源网址', '来源明细表'], [31, 33, 42, 36, 46, 14, 25, 12, 85, 100, 90, 70]],
  ['缺口明细', ['缺口类别', '范围', '上榜记录ID', '作品ID', '系列ID', '标题', '说明', '依据表路径'], [29, 10, 31, 42, 33, 46, 105, 90]],
  ['关系对应', ['关系类型', '对象A', '对象B', '对应上榜记录ID列表', '判断说明', '依据表路径'], [31, 84, 84, 75, 100, 95]],
];
input['素材明细'] = input['素材明细'].map(r => ({...r, 简介字数: [...r['简介正文']].length}));
input['红果作品'] = input['红果作品'].map(r => ({...r, 同系列其他作品数: JSON.parse(r['同系列其他作品ID']).length}));

for (const [name, cols, widths] of schemas) {
  const s = wb.worksheets.add(name);
  s.showGridLines = false;
  const rows = input[name];
  const title = name === '总览' ? '数据采集交付清单' : name;
  s.getRange('A2').values = [[title]];
  s.getRange('A2').format.font = {name: 'Arial', size: 15, bold: true, color: '#18314D'};
  s.getRange('A2:D2').format.borders = {bottom: {style: 'thin', color: '#9AAABA'}};
  s.getRange('A3').values = [[name === '总览' ? '2026年7—10月；缺口与候选状态按来源保留。' : '筛选表头查找；本地路径相对于dataprocessing目录；完整原文与来源见对应CSV。']];
  s.getRange('A3').format.font = {name: 'Arial', size: 10, italic: true, color: '#516171'};
  const numeric = new Set(['数量', '名次', '上榜次数', '候选热评数', '简介字数', '同系列其他作品数', '选定候选可见热评数', '全部候选可见热评数', '抖音待核索引片段数']);
  const values = [cols, ...rows.map(row => cols.map(c => {
    const v = row[c] ?? '';
    if (numeric.has(c) && /^\d+$/.test(String(v))) return Number(v);
    return typeof v === 'string' && v.startsWith('=') ? "'" + v : v;
  }))];
  const rg = s.getRangeByIndexes(4, 0, values.length, cols.length);
  rg.values = values;
  rg.format.font = {name: 'Arial', size: 10, color: '#243447'};
  rg.format.verticalAlignment = 'center';
  rg.format.wrapText = true;
  const header = s.getRangeByIndexes(4, 0, 1, cols.length);
  header.format.fill = '#243F5B';
  header.format.font = {name: 'Arial', size: 10, bold: true, color: '#FFFFFF'};
  header.format.horizontalAlignment = 'center';
  header.format.rowHeight = 32;
  const body = s.getRangeByIndexes(5, 0, rows.length, cols.length);
  body.format.rowHeight = 30;
  for (let i = 0; i < rows.length; i++) {
    const maxLines = Math.max(...cols.map((c, j) => {
      const text = String(rows[i][c] ?? '');
      const units = [...text].reduce((n, ch) => n + (/[^\x00-\x7F]/.test(ch) ? 2 : 1), 0);
      return Math.ceil(units / Math.max(8, widths[j] - 3));
    }));
    s.getRangeByIndexes(i + 5, 0, 1, cols.length).format.rowHeight = Math.max(30, maxLines * 15 + 10);
  }
  cols.forEach((col, j) => {
    const cr = s.getRangeByIndexes(4, j, rows.length + 1, 1);
    cr.format.columnWidth = widths[j];
    if (numeric.has(col)) {
      s.getRangeByIndexes(5, j, rows.length, 1).setNumberFormat('#,##0');
      s.getRangeByIndexes(5, j, rows.length, 1).format.horizontalAlignment = 'right';
    } else {
      s.getRangeByIndexes(5, j, rows.length, 1).setNumberFormat('@');
    }
  });
  const table = s.tables.add(rg, true, 'DeliveryTable' + (schemas.findIndex(v => v[0] === name) + 1));
  table.style = 'TableStyleMedium2';
  table.showFilterButton = true;
  table.showBandedColumns = false;
  if (name !== '总览') {
    s.freezePanes.freezeRows(5);
    s.freezePanes.freezeColumns(name === '缺口明细' ? 3 : 1);
  }
  if (name === '缺口明细') {
    s.getRangeByIndexes(5, 0, rows.length, 1).conditionalFormats.add('containsText', {text: '缺失', format: {fill: '#FCE9E7', font: {color: '#9B2C2C'}}});
    s.getRangeByIndexes(5, 0, rows.length, 1).conditionalFormats.add('containsText', {text: '待核', format: {fill: '#FFF2D6', font: {color: '#7C5200'}}});
  }
}

// 总览在主结果之后列出使用方式，路径是用户要求交付的信息。
const summary = wb.worksheets.getItem('总览');
summary.tabColor = '#243F5B';
summary.getRange('A14:C18').values = [
  ['查找方式', '位置', '说明'],
  ['按月看全部素材', 'README.md', '从项目首页点月份或系列，直接打开本地榜图、简介快照及封面。'],
  ['完整简介与来源', 'data/交付索引/素材路径明细.csv', '401条关联含简介正文，保留同名双版本。'],
  ['目录、文件副本与路径核验', 'data/交付索引/', '原目录文件清单、字节相同文件组与路径核验明细均在此目录。'],
  ['刷新清单', 'README.md', '重新运行索引脚本后，再执行导出脚本；本清单是生成时的快照。'],
];
summary.getRange('A14:C18').format.font = {name: 'Arial', size: 10, color: '#243447'};
summary.getRange('A14:C18').format.wrapText = true;
summary.getRange('A14:C18').format.rowHeight = 52;
summary.getRange('A14:C18').format.verticalAlignment = 'center';
summary.getRange('A14:C14').format.horizontalAlignment = 'center';
summary.getRange('A14:C14').format.font = {name: 'Arial', size: 10, bold: true, color: '#FFFFFF'};
summary.getRange('A14:C14').format.fill = '#243F5B';
// 总览B列较窄，说明路径单独占用C列，使第一屏与路径都可读。
summary.getRange('A16:C18').values = [
  ['完整简介与来源', 'CSV', 'data/交付索引/素材路径明细.csv（含全部简介正文和各候选版本）'],
  ['目录、文件副本与路径核验', 'CSV', 'data/交付索引/（文件清单、重复组与路径核验明细）'],
  ['刷新清单', '命令', '见README.md；本工作簿为生成时快照，重建索引后再导出。'],
];
wb.recalculate();
console.log((await wb.inspect({kind: 'table', range: '总览!A5:C11', include: 'values,formulas', tableMaxRows: 8, tableMaxCols: 3, maxChars: 3000})).ndjson);
console.log((await wb.inspect({kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!', options: {useRegex: true, maxResults: 20}, maxChars: 2000})).ndjson);
for (const [name, cols] of schemas) {
  const preview = await wb.render({sheetName: name, range: name === '总览' ? 'A1:C18' : (name === '缺口明细' ? 'A1:C10' : 'A1:F9'), scale: 1.4, format: 'png'});
  await fs.writeFile(path.join(previews, name + '.png'), new Uint8Array(await preview.arrayBuffer()));
}
const xlsx = await SpreadsheetFile.exportXlsx(wb);
const target = path.join(out, '采集交付清单.xlsx');
await xlsx.save(target);
// 软件检查转储不是交付数据，避免每次导出再产生大型副本。
await fs.rm(target + '.inspect.ndjson', {force: true});
console.log(JSON.stringify({output: target, previews, sheets: schemas.map(([name]) => ({name, rows: input[name].length}))}));
