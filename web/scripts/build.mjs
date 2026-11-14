import { cp, mkdir, readFile, rm, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const dist = path.join(root, 'dist');
await rm(dist, { recursive:true, force:true });
await mkdir(dist, { recursive:true });
await cp(path.join(root,'public'), dist, { recursive:true });
await cp(path.join(root,'src'), path.join(dist,'src'), { recursive:true, filter:src => !src.endsWith('.txt') });
await cp(path.join(root,'index.html'), path.join(dist,'index.html'));
const gallery = JSON.parse(await readFile(path.join(dist,'data/gallery.json'),'utf8'));
await Promise.all(gallery.map(item => stat(path.join(dist,item.cover))));
const pythonCandidates = [...new Set([process.env.PYTHON, 'python3', 'python'].filter(Boolean))];
let bundled=false;
for (const python of pythonCandidates) {
  try {
    execFileSync(python, [path.join(root,'scripts/bundle.py')], { stdio:'inherit' });
    bundled=true;
    break;
  } catch(error) {
    // 找不到解释器才尝试下一候选；编译脚本本身失败时保留真正错误。
    if(error.code !== 'ENOENT') throw error;
  }
}
if(!bundled) throw new Error('需要Python 3生成离线页面；可用PYTHON指定解释器路径。');
console.log(`静态构建完成：dist/，已核对 ${gallery.length} 张本地封面。`);
