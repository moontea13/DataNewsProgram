import http from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const web = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const root = process.argv.includes('--dist') ? path.join(web, 'dist') : web;
const portIndex = process.argv.indexOf('--port');
const port = Number(portIndex > -1 ? process.argv[portIndex + 1] : process.env.PORT || 5173);
const mime = { '.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.css':'text/css; charset=utf-8', '.json':'application/json; charset=utf-8', '.svg':'image/svg+xml', '.webp':'image/webp', '.png':'image/png', '.jpg':'image/jpeg' };
const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://localhost');
    const resource = decodeURIComponent(url.pathname);
    const file = resource === '/' ? '/index.html' : resource;
    const isPublic = !process.argv.includes('--dist') && /^\/(data|assets)\/|^\/favicon.svg$/.test(file);
    const filename = path.resolve(isPublic ? path.join(web, 'public') : root, '.' + file);
    if (!filename.startsWith(root + path.sep)) { res.writeHead(403); res.end(); return; }
    if (!(await stat(filename)).isFile()) throw new Error('not a file');
    res.writeHead(200, { 'Content-Type':mime[path.extname(filename)] || 'application/octet-stream', 'Cache-Control':'no-cache' });
    res.end(await readFile(filename));
  } catch { res.writeHead(404, { 'Content-Type':'text/plain; charset=utf-8' }); res.end('未找到页面或文件'); }
});
server.listen(port, '127.0.0.1', () => console.log(`本地预览：http://127.0.0.1:${port}/`));
for (const signal of ['SIGINT','SIGTERM']) process.on(signal, () => server.close(() => process.exit(0)));
