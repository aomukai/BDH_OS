#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, io, json, re, sys, zipfile
from collections import defaultdict, deque
from pathlib import Path
import jsonschema

REQUIRED_FILES = {
    'ninereeds_curriculum_v4.md','ninereeds_curriculum_v4.json','ninereeds_curriculum_v4_schemas.json',
    'v4_world_registry.csv','v4_point_registry.csv','v4_lexeme_registry.csv','v4_lessons.csv',
    'v4_source_accounting.csv','v4_response_forms.csv','v4_discourse_operations.csv',
    'v4_character_bindings.csv','v4_location_bindings.csv','v4_audit.json','v4_audit.csv',
    'v4_independent_validation.json','validate_v4_independent.py','MANIFEST.json','SHA256SUMS.txt'
}

def load_source(path: Path):
    if path.is_dir():
        names={p.name for p in path.iterdir() if p.is_file()}
        def read(name): return (path/name).read_bytes()
    else:
        z=zipfile.ZipFile(path)
        names=set(z.namelist())
        def read(name): return z.read(name)
    return names, read

def csv_count(raw):
    return sum(1 for _ in csv.DictReader(io.StringIO(raw.decode('utf-8'))))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('bundle', type=Path)
    ap.add_argument('--json-output', type=Path)
    args=ap.parse_args()
    errors=[]; warnings=[]; checks=[]
    names, read=load_source(args.bundle)
    missing=sorted(REQUIRED_FILES-names)
    checks.append({'check':'required_files','ok':not missing,'details':{'missing':missing}})
    if missing: errors.append(f'Missing required files: {missing}')
    data=json.loads(read('ninereeds_curriculum_v4.json'))
    schema=json.loads(read('ninereeds_curriculum_v4_schemas.json'))
    schema_errors=sorted(jsonschema.Draft202012Validator(schema).iter_errors(data),key=lambda e:list(e.path))
    checks.append({'check':'json_schema','ok':not schema_errors,'details':{'errors':[e.message for e in schema_errors[:20]]}})
    errors += [f'Schema: {e.message}' for e in schema_errors]
    W=data['world_registry']; P=data['point_registry']; B=data['lexeme_registry']; L=data['lesson_sequence']; S=data['source_accounting']
    expected={'world':157,'point':131,'bundle':288,'lesson':295,'source':240}
    actual={'world':len(W),'point':len(P),'bundle':len(B),'lesson':len(L),'source':len(S)}
    checks.append({'check':'counts','ok':actual==expected,'details':{'expected':expected,'actual':actual}})
    if actual!=expected: errors.append(f'Count mismatch: {actual}')
    ids={
      'world':[x['world_id'] for x in W], 'point':[x['point_id'] for x in P], 'bundle':[x['bundle_id'] for x in B],
      'lesson':[x['lesson_id'] for x in L], 'source':[x['source_id'] for x in S],
      'response':[x['response_form_id'] for x in data['response_forms']],
      'discourse':[x['operation_id'] for x in data['discourse_operations']],
      'character':[x['character_id'] for x in data['character_bindings']],
      'location':[x['location_id'] for x in data['location_bindings']],
    }
    dups={k:sorted({x for x in v if v.count(x)>1}) for k,v in ids.items() if len(v)!=len(set(v))}
    checks.append({'check':'duplicate_ids','ok':not dups,'details':dups})
    if dups: errors.append(f'Duplicate IDs: {dups}')
    sets={k:set(v) for k,v in ids.items()}
    pos={lid:i for i,lid in enumerate(ids['lesson'])}
    acq={}
    for x in W: acq[x['world_id']]=x['acquisition_lesson_id']
    for x in P: acq[x['point_id']]=x['acquisition_lesson_id']
    bundle_intro={x['bundle_id']:x['introduction_lesson_id'] for x in B}
    rf_intro={x['response_form_id']:x['introduction_lesson_id'] for x in data['response_forms']}
    do_intro={x['operation_id']:x['introduction_lesson_id'] for x in data['discourse_operations']}
    graph=defaultdict(set); indeg=defaultdict(int)
    ref_errors=[]; order_errors=[]
    for x in W:
      n=x['world_id']; deps=x['world_prerequisites']+x['point_prerequisites']
      for d in deps:
        if d not in sets['world']|sets['point']: ref_errors.append(f'{n}->{d}')
        graph[d].add(n); indeg[n]+=1
        if d in acq and pos[acq[d]]>pos[acq[n]]: order_errors.append(f'{d} after {n}')
    for x in P:
      n=x['point_id']; deps=x['point_prerequisites']+x['world_prerequisites']
      for d in deps:
        if d not in sets['world']|sets['point']: ref_errors.append(f'{n}->{d}')
        graph[d].add(n); indeg[n]+=1
        if d in acq and pos[acq[d]]>pos[acq[n]]: order_errors.append(f'{d} after {n}')
    q=deque([n for n in sets['world']|sets['point'] if indeg[n]==0]); seen=[]
    while q:
      n=q.popleft(); seen.append(n)
      for m in graph[n]:
        indeg[m]-=1
        if indeg[m]==0:q.append(m)
    cyclic=len(seen)!=len(sets['world']|sets['point'])
    checks += [
      {'check':'referential_integrity','ok':not ref_errors,'details':ref_errors[:50]},
      {'check':'prerequisite_graph_acyclic','ok':not cyclic,'details':{'visited':len(seen),'nodes':len(sets['world']|sets['point'])}},
      {'check':'prerequisites_precede_use','ok':not order_errors,'details':order_errors[:50]},
    ]
    if ref_errors: errors.append(f'Reference errors: {ref_errors[:10]}')
    if cyclic: errors.append('Prerequisite graph contains a cycle')
    if order_errors: errors.append(f'Prerequisite ordering errors: {order_errors[:10]}')
    novelty=[]; staged=[]; surface=[]; transfer=[]; charloc=[]; pb=[]
    char_intro={x['character_id']:x['introduction_lesson_id'] for x in data['character_bindings']}
    loc_intro={x['location_id']:x['introduction_lesson_id'] for x in data['location_bindings']}
    for l in L:
      lid=l['lesson_id']; pf=l['primary_frontier']
      if pf in ('WORLD_FRONTIER','POINT_FRONTIER') and len(l['frontier_lexeme_bundle_ids'])!=1: novelty.append(lid)
      if pf=='TRANSFER' and l['frontier_lexeme_bundle_ids']: novelty.append(lid)
      if pf=='STAGED_EXCEPTION':
        if lid!='L000' or len(l['staged_gates'])!=6 or not all(g.get('independent_probe') for g in l['staged_gates']): staged.append(lid)
      for b in l['required_lexeme_bundle_ids']:
        if b not in bundle_intro or pos[bundle_intro[b]]>=pos[lid]: surface.append(f'{lid}:{b}')
      for r in l['required_response_forms']:
        if r not in rf_intro or pos[rf_intro[r]]>=pos[lid]: surface.append(f'{lid}:{r}')
      for d in l['required_discourse_operations']:
        if d not in do_intro or pos[do_intro[d]]>=pos[lid]: surface.append(f'{lid}:{d}')
      if pf=='TRANSFER':
        for t in l['rehearsal_transfer_targets']:
          if t not in acq or pos[acq[t]]>=pos[lid]: transfer.append(f'{lid}:{t}')
      for c in l['characters']:
        if c not in char_intro or char_intro[c] is None or pos[char_intro[c]]>pos[lid]: charloc.append(f'{lid}:{c}')
      for loc in l['locations']:
        if loc not in loc_intro or loc_intro[loc] is None or pos[loc_intro[loc]]>pos[lid]: charloc.append(f'{lid}:{loc}')
      if l['picture_book_status']=='PB-R' and set(l['grounding_modes'])<={'ABSTRACT'}: pb.append(lid)
    checks += [
      {'check':'one_principal_novelty','ok':not novelty,'details':novelty},
      {'check':'staged_exception_gates','ok':not staged,'details':staged},
      {'check':'surface_language_closure','ok':not surface,'details':surface[:50]},
      {'check':'transfer_after_anchor','ok':not transfer,'details':transfer[:50]},
      {'check':'character_location_chronology','ok':not charloc,'details':charloc[:50]},
      {'check':'picture_book_feasibility','ok':not pb,'details':pb},
    ]
    for label,vals in [('novelty',novelty),('staged',staged),('surface',surface),('transfer',transfer),('character/location',charloc),('picture book',pb)]:
      if vals: errors.append(f'{label} violations: {vals[:10]}')
    first_meeting=[l['lesson_id'] for l in L if l['canonical_first_meeting_pairs']]
    fm_ok=first_meeting==['L000'] and 'noncanonical' in L[0]['exercise_scope'].lower()
    checks.append({'check':'canonical_first_meetings','ok':fm_ok,'details':first_meeting})
    if not fm_ok: errors.append(f'First-meeting violation: {first_meeting}')
    source_expected={f'C{i:03d}' for i in range(1,241)}
    source_ok=sets['source']==source_expected and all(x['target_world_ids'] or x['target_point_ids'] for x in S)
    checks.append({'check':'source_accounting','ok':source_ok,'details':{'count':len(S)}})
    if not source_ok: errors.append('C001-C240 accounting incomplete')
    acquisition_ok=set(acq)==sets['world']|sets['point'] and all(v in sets['lesson'] for v in acq.values())
    checks.append({'check':'active_registry_acquisition','ok':acquisition_ok,'details':{'acquired':len(acq)}})
    if not acquisition_ok: errors.append('Active acquisition coverage incomplete')
    locs={x['location_id']:x for x in data['location_bindings']}
    topo_expected={
      'LOC-MEADOW-PATH':'connects:LOC-GRANS-HOUSE->LOC-POND->LOC-SCHOOL',
      'LOC-POND':'short_walk_from:LOC-OAK', 'LOC-SCHOOL':'far_end_of:LOC-MEADOW-PATH',
      'LOC-VILLAGE-LANE':'connects:LOC-GRANS-HOUSE->LOC-VILLAGE'
    }
    topo_bad=[f'{loc}:{rel}' for loc,rel in topo_expected.items() if loc not in locs or rel not in locs[loc]['topology_relations']]
    names_ok=any(x['canonical_name']=='Gran' for x in data['character_bindings']) and any(x['canonical_name']=="Gran's House" for x in data['location_bindings'])
    checks.append({'check':'world_bible_topology','ok':not topo_bad and names_ok,'details':topo_bad})
    if topo_bad or not names_ok: errors.append(f'World-bible topology/name violations: {topo_bad}')
    raw=json.dumps(data,ensure_ascii=False).lower()
    prohibited=[r'ninereeds is an ai',r'ninereeds is a model',r'ninereeds is a machine',r'ninereeds is conscious',r'ninereeds is sentient',r'ninereeds is an llm']
    hits=[p for p in prohibited if re.search(p,raw)]
    checks.append({'check':'identity_policy_scan','ok':not hits,'details':hits})
    if hits: errors.append(f'Identity-policy prohibited classifications: {hits}')
    points={x['point_id']:x for x in P}
    corrected=(
      'Nice to meet you' in points['P-SOC-002']['form_function'] and
      'Thank' in points['P-SOC-009']['form_function'] and
      'Farewells' in points['P-SOC-010']['form_function'] and
      points['P-SRC-001']['point_prerequisites']==['P-EPI-003'] and
      points['P-SRC-001']['world_prerequisites']==['W-EPI-003'] and
      points['P-LEX-001']['world_prerequisites']==['W-EPI-009'] and
      points['P-CERTAINTY-001']['world_prerequisites']==['W-EPI-008'] and
      'not yet unavailable' not in raw
    )
    checks.append({'check':'known_v3_corrections','ok':corrected,'details':{}})
    if not corrected: errors.append('Known v3 corrections not all present')
    csv_expected={
      'v4_world_registry.csv':157,'v4_point_registry.csv':131,'v4_lexeme_registry.csv':288,
      'v4_lessons.csv':295,'v4_source_accounting.csv':240,
      'v4_response_forms.csv':len(data['response_forms']),'v4_discourse_operations.csv':len(data['discourse_operations']),
      'v4_character_bindings.csv':len(data['character_bindings']),'v4_location_bindings.csv':len(data['location_bindings']),
      'v4_audit.csv':len(data['audit'])
    }
    csv_bad={name:{'expected':n,'actual':csv_count(read(name))} for name,n in csv_expected.items() if name in names and csv_count(read(name))!=n}
    checks.append({'check':'csv_row_counts','ok':not csv_bad,'details':csv_bad})
    if csv_bad: errors.append(f'CSV row-count mismatch: {csv_bad}')
    bob=next((x for x in data['character_bindings'] if x['character_id']=='CHAR-BOB'),None)
    bob_ok=bool(bob and bob['status']=='OPERATOR_APPROVAL_REQUIRED' and all('CHAR-BOB' not in l['characters'] for l in L[1:]))
    checks.append({'check':'bob_resolution','ok':bob_ok,'details':bob})
    if not bob_ok: errors.append('Bob resolution invalid')
    else: warnings.append('Bob canon freeze remains UNRESOLVED by source authority; use is restricted to L000.')
    result={'status':'PASS' if not errors else 'FAIL','error_count':len(errors),'warning_count':len(warnings),'errors':errors,'warnings':warnings,'checks':checks,'counts':actual}
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.json_output: args.json_output.write_text(text+'\n',encoding='utf-8')
    print(text)
    return 0 if not errors else 1

if __name__=='__main__': raise SystemExit(main())
