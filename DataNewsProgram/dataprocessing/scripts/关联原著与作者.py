"""月榜—第三方改编线索—官方书目关联，保留多来源及更名差异。"""
import json
from 持续补采 import OUT,records,save
def read(name):
    p=OUT/(name+'.json');return json.loads(p.read_text()) if p.exists() else []
books={r['book_id']:r for r in read('原著官方书目核验')};rows=[]
for r in read('百科原著线索')+read('第三方作品证据'):
    bid=r.get('book_id_candidate') or r.get('book_id')
    if not bid:continue
    official=books.get(bid,{})
    for rid in r['candidate_ranking_ids']:
        old_title=r.get('original_title_as_listed') or r.get('original_title','')
        rows.append({'ranking_id':rid,'drama_title_as_listed':r['title'],'book_id_candidate':bid,'third_party_original_title':old_title,'third_party_author':r.get('author_as_listed',''),'third_party_evidence_url':r['source_url'],'third_party_evidence_file':r['source_file'],'third_party_evidence_sha256':r['source_sha256'],'official_book_title':official.get('official_book_title',''),'official_author':official.get('official_author',''),'official_author_id':official.get('official_author_id',''),'official_book_url':official.get('source_url',''),'official_book_file':official.get('source_file',''),'official_book_sha256':official.get('source_sha256',''),'book_identity_status':'官方书目ID已核实' if official else '原著页尚未核实','adaptation_status':'第三方改编线索；原著官方页另含改编声明，具体剧集/季数待核' if official.get('has_adaptation_statement') else '第三方改编线索；具体剧集关系待独立确认','title_difference_note':'第三方未提供书名，不当作更名差异' if not old_title else '第三方书名与当前官方书名不同，保留原文，可能更名或线索错误' if official and old_title!=official.get('official_book_title') else ''})
records('月榜_原著_作者关系候选',rows)
save('原著作者关系统计.json',{'evidence_rows':len(rows),'ranking_rows_with_candidate':len({r['ranking_id'] for r in rows}),'distinct_candidate_book_ids':len({r['book_id_candidate'] for r in rows}),'candidate_links_with_official_book':sum(r['book_identity_status']=='官方书目ID已核实' for r in rows),'official_books_linked_to_monthly_candidates':len({r['book_id_candidate'] for r in rows if r['official_book_title']}),'official_authors_linked_to_monthly_candidates':len({r['official_author_id'] for r in rows if r['official_author_id']}),'confirmed_season_adaptation_links':0,'limits':'书目核实不等于具体季改编确认；第三方关系不作为原创/改编比例的确认分子。'})
print('关联线索',len(rows),'上榜记录',len({r['ranking_id'] for r in rows}))
