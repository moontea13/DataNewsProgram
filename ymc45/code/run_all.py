"""一键复算并把过程和测试输出保存在ymc45/logs。"""
import os
from pathlib import Path
import subprocess
import sys
import json


base=Path(__file__).resolve().parents[1]
env=dict(os.environ,PYTHONIOENCODING='utf-8')
commands=[('候选检索复现',[sys.executable,str(base/'code/screen_candidates.py')]),
          ('pipeline.py',[sys.executable,str(base/'code/pipeline.py')]),
          ('抽样复现',[sys.executable,str(base/'code/check_sampling.py')]),
          ('必要测试',[sys.executable,'-m','unittest','discover','-s',str(base/'code'),'-p','test_*.py','-v']),
          ('说明生成',[sys.executable,str(base/'code/generate_docs.py')])]
if (base/'annotations/final_authorization.json').exists():
    commands.insert(3,('授权定稿',[sys.executable,str(base/'code/finalize.py')]))
log=[]
for name,command in commands:
    result=subprocess.run(command,cwd=base.parent,env=env,encoding='utf-8',stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    log.append(f'## {name}\n{result.stdout}\n退出码：{result.returncode}\n')
    (base/'logs/复算与测试日志.txt').write_text('\n'.join(log),encoding='utf-8')
    print(name,'通过' if result.returncode==0 else '失败')
    result.check_returncode()
acceptance_path=base/'验收结果.json'
acceptance=json.loads(acceptance_path.read_text(encoding='utf-8'))
acceptance.update(necessary_scenario_tests_passed=True,frozen_trial_sampling_reproduced=True,
                  test_log='logs/复算与测试日志.txt',all_requested_artifacts_under='ymc45')
acceptance_path.write_text(json.dumps(acceptance,ensure_ascii=False,indent=2),encoding='utf-8')
