"""Controlled image-preprocessing comparisons and exploratory Chinese CLIP labels."""
import argparse
import sys
import time
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageOps
import torch
from transformers import AutoImageProcessor, AutoModel, ChineseCLIPModel, ChineseCLIPProcessor, BertTokenizer, ChineseCLIPImageProcessor
from common import ROOT, RESULTS, MODEL_CACHE, load, save, sha256
from style_features import STYLE_RESULTS, PROTOCOL

PROMPTS = {
    'render_style': {
        '仿真人或摄影': ['一张真人摄影或仿真人影视剧海报', '一张写实真人风格的短剧封面'],
        '三维动画': ['一张三维建模动画人物的短剧海报', '一张3D动漫渲染风格的短剧封面'],
        '二维插画': ['一张二维平面动漫人物插画海报', '一张手绘漫画风格的短剧封面'],
    },
    'people_count': {
        '无明显人物': ['一张没有人物的风景或物品海报', '一张以文字风景为主没有人物的封面'],
        '单人': ['一张只有一个主要人物的短剧海报', '一张单个主角形象的影视封面'],
        '双人': ['一张有两个主要人物的短剧海报', '一张男女双人或两人组合的影视封面'],
        '多人群像': ['一张有三个或更多人物的短剧海报', '一张多个人物群像组合的影视封面'],
    },
    'shot': {
        '脸部特写': ['一张以人物面部大特写为主的海报', '一张人脸占据大部分画面的影视封面'],
        '半身或胸像': ['一张以人物上半身或胸像为主的海报', '一张半身人物近景的影视封面'],
        '全身或远景': ['一张人物全身和周围大场景的海报', '一张展示人物全身的远景影视封面'],
    },
    'composition': {
        '主体居中': ['一张主要人物在画面中央的海报', '一张人物主体居中排列的影视封面'],
        '主体偏左': ['一张主要人物位于画面左侧的海报', '一张左侧是人物右侧留空的影视封面'],
        '主体偏右': ['一张主要人物位于画面右侧的海报', '一张右侧是人物左侧留空的影视封面'],
        '左右双主体': ['一张两个人物左右并列构图的海报', '一张左边和右边分别有主角的影视封面'],
    },
}


def input_fingerprint(include_ocr=False):
    result = {'input_sha256': sha256(RESULTS/'representatives.json'),
              'protocol_sha256': sha256(ROOT/'style_protocol.json'),
              'model_code_sha256': sha256(Path(__file__)),
              'torch': torch.__version__, 'device': 'cpu', 'seed': 20261113}
    if include_ocr:
        result['ocr_sha256'] = sha256(STYLE_RESULTS/'cover_ocr.json')
    return result

def padded(im, size=224):
    # Padding colour follows the processor mean approximately, avoiding a black frame.
    resampling = getattr(Image, 'Resampling', Image)
    return ImageOps.pad(im, (size,size), method=resampling.BICUBIC, color=(124,116,104), centering=(.5,.5))

def dinov2():
    rows=[r for r in load(RESULTS/'representatives.json') if r['modality']=='cover']
    ocr={r['series_id']:r for r in load(STYLE_RESULTS/'cover_ocr.json')}
    processor=AutoImageProcessor.from_pretrained(MODEL_CACHE/'dinov2',local_files_only=True)
    model=AutoModel.from_pretrained(MODEL_CACHE/'dinov2',local_files_only=True).eval()
    start=time.time()
    for variant in ['full_pad','title_masked_pad']:
        vectors=[]
        with torch.inference_mode():
            for i in range(0,len(rows),4):
                images=[]
                for r in rows[i:i+4]:
                    with Image.open(r['cover_path']) as im:im=im.convert('RGB')
                    if variant=='title_masked_pad' and ocr[r['series_id']]['valid_title_layout']:
                        draw=ImageDraw.Draw(im)
                        for b in ocr[r['series_id']]['title_boxes']:
                            draw.polygon([tuple(p) for p in b['polygon']],fill=(124,116,104))
                    images.append(padded(im))
                inp=processor(images=images,do_resize=False,do_center_crop=False,return_tensors='pt')
                feature=model(**inp).last_hidden_state[:,0]
                vectors.append(torch.nn.functional.normalize(feature,dim=1).cpu().numpy())
                if i%40==0:print('DINOv2',variant,min(i+4,len(rows)),flush=True)
        np.save(STYLE_RESULTS/f'dinov2_{variant}.npy',np.concatenate(vectors))
    save(STYLE_RESULTS/'dinov2_metadata.json',{**input_fingerprint(include_ocr=True),'model':load(RESULTS/'cover_model.json')['model'],
         'revision':load(RESULTS/'cover_model.json')['revision'],'series_ids':[r['series_id'] for r in rows],
         'preprocessing':'保留比例补边224×224，RGB(124,116,104)，关闭额外resize和center_crop；mask只在OCR标题有效时施加',
         'title_masked_valid_series_ids':[r['series_id'] for r in rows if ocr[r['series_id']]['valid_title_layout']],
         'elapsed_seconds':round(time.time()-start,2)})

def clip():
    folder=MODEL_CACHE/'chinese_clip'
    model=ChineseCLIPModel.from_pretrained(folder,local_files_only=True).eval()
    image_processor=ChineseCLIPImageProcessor.from_pretrained(folder,local_files_only=True)
    tokenizer=BertTokenizer(vocab_file=str(folder/'vocab.txt'),do_lower_case=True)
    rows=[r for r in load(RESULTS/'representatives.json') if r['modality']=='cover']
    start=time.time();all_vectors={}
    with torch.inference_mode():
        for variant in ['official_full_resize','full_pad']:
            vectors=[]
            for i in range(0,len(rows),4):
                images=[]
                for r in rows[i:i+4]:
                    with Image.open(r['cover_path']) as im:im=im.convert('RGB')
                    images.append(padded(im) if variant=='full_pad' else im)
                inp=image_processor(images=images,return_tensors='pt')
                feat=model.get_image_features(**inp)
                vectors.append(torch.nn.functional.normalize(feat,dim=1).cpu().numpy())
                if i%40==0:print('Chinese CLIP',variant,min(i+4,len(rows)),flush=True)
            all_vectors[variant]=np.concatenate(vectors)
            np.save(STYLE_RESULTS/f'chinese_clip_{variant}.npy',all_vectors[variant])
        labels=[{'series_id':r['series_id'],'fields':{}} for r in rows]
        for field,classes in PROMPTS.items():
            descriptions=[p for pair in classes.values() for p in pair]
            inp=tokenizer(descriptions,padding=True,return_tensors='pt')
            feats=torch.nn.functional.normalize(model.get_text_features(**inp),dim=1).cpu().numpy()
            scores=(all_vectors['official_full_resize']@feats.T).reshape(len(rows),len(classes),2).mean(axis=2)
            for i,record in enumerate(labels):
                order=np.argsort(-scores[i]);gap=float(scores[i,order[0]]-scores[i,order[1]])
                record['fields'][field]={'label':list(classes)[order[0]] if gap>=.02 else None,
                    'top_candidate':list(classes)[order[0]],'margin':gap,'status':'模型候选' if gap>=.02 else '候选分差不足，未知',
                    'scores':{label:float(scores[i,j]) for j,label in enumerate(classes)}}
    save(STYLE_RESULTS/'clip_visual_labels.json',labels)
    save(STYLE_RESULTS/'chinese_clip_metadata.json',{**input_fingerprint(),'repo':PROTOCOL['cover_models']['chinese_clip']['repo'],
         'revision':PROTOCOL['cover_models']['chinese_clip']['revision'], 'series_ids':[r['series_id'] for r in rows],
         'prompts':PROMPTS,'margin_cutoff':.02,'processor':image_processor.to_dict(),
         'elapsed_seconds':round(time.time()-start,2),'limits':'零样本候选描述匹配，分差不是校准概率；未作人工准确性核验。人物数、景别等可能识别错误，不能替代检测框或人工标签。'})
    print('Chinese CLIP done',flush=True)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');torch.set_num_threads(6);torch.manual_seed(20261113);np.random.seed(20261113)
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['dinov2','clip']);a=p.parse_args()
    {'dinov2':dinov2,'clip':clip}[a.mode]()
