"""prepare JOBS BATCH [EXCLUDE_JOBS...]；finalize BATCH。

prepare 生成 curl 配置，curl 成功状态与临时文件逐项记录；finalize 仅将
HTTP成功且完整传输的文件原子移入缓存。curl 命令须单独执行。
"""
import hashlib
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
from 持续补采 import OUT,save

mode=sys.argv[1]
if mode=='prepare':
    source=Path(sys.argv[2]);batch=sys.argv[3]
    if not batch.replace('_','').replace('-','').isalnum():raise ValueError('batch仅含字母数字下划线横线')
    excluded=set()
    for p in sys.argv[4:]:excluded.update(j['file'] for j in json.loads(Path(p).read_text()))
    jobs=[]
    for job in json.loads(source.read_text()):
        p=Path(job['file'])
        if p.exists() or job['file'] in excluded:continue
        part=p.with_name(p.name+'.'+batch+'.part');part.parent.mkdir(parents=True,exist_ok=True)
        log=part.with_suffix(part.suffix+'.result.json');jobs.append({**job,'part_file':str(part),'result_file':str(log)})
    config=['rate = "1/s"']
    for i,j in enumerate(jobs):
        if i:config+=['next']
        config+=['fail','silent','show-error','location','connect-timeout = 8','max-time = 30','max-filesize = 12582912','proto = "=https"','proto-redir = "=https"']
        config+=['url = '+json.dumps(j['url']),'output = '+json.dumps(j['part_file'],ensure_ascii=False),'write-out = '+json.dumps('%output{'+j['result_file']+'}%{json}\n',ensure_ascii=False)]
    save(batch+'_原子任务.json',jobs);(OUT/(batch+'.curl')).write_text('\n'.join(config)+'\n');print('atomic jobs',len(jobs))
elif mode=='finalize':
    batch=sys.argv[2];states=[]
    for j in json.loads((OUT/(batch+'_原子任务.json')).read_text()):
        p=Path(j['part_file']);log=Path(j['result_file']);state={**j,'finalized_at':datetime.now(timezone.utc).isoformat()}
        try:
            result=json.loads(log.read_text())
            target=Path(j['file'])
            if not p.exists() and target.exists() and result.get('exitcode')==0 and 200<=result.get('http_code',0)<300 and target.stat().st_size==int(result.get('size_download',-1)):
                state.update(status='成功入库；重复执行核对传输日志与文件大小',sha256=hashlib.sha256(target.read_bytes()).hexdigest(),http_code=result['http_code'])
            elif result.get('exitcode')!=0 or not 200<=result.get('http_code',0)<300 or not p.exists() or p.stat().st_size==0:
                state.update(status='下载未成功；保留临时材料待重试',curl_result=result)
            elif Path(j['file']).exists():state['status']='目标文件已存在；保留临时版本供差异核对'
            else:
                state.update(status='成功传输并入库；内容身份仍须解析核验',sha256=hashlib.sha256(p.read_bytes()).hexdigest(),http_code=result['http_code']);p.replace(j['file'])
        except (ValueError,OSError) as e:state.update(status='未完成或缺少结果日志',error=str(e))
        states.append(state)
    save(batch+'_下载状态.json',states);print('finalized',sum(r['status'].startswith('成功') for r in states),'of',len(states))
else:raise ValueError(mode)
