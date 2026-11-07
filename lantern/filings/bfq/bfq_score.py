#!/usr/bin/env python3
"""BharatFinQA scoring harness.

  # deterministic metrics only (no API key needed)
  python3 bfq_score.py --pred preds.jsonl --gold human_evaluation_benchmark.jsonl

  # with the pinned LLM judge (required for the headline BFQ-Score)
  python3 bfq_score.py --pred preds.jsonl --gold gold.jsonl \
      --judge deepseek-ai/DeepSeek-V4-Pro --provider openrouter

  # judge-sensitivity: score the same predictions under a second judge
  python3 bfq_score.py --pred preds.jsonl --gold gold.jsonl \
      --judge openai/gpt-5 --provider openrouter --out out_gpt5.json

Prediction file: JSONL, one object per item, with at least
  {"question": ..., "predicted_answer": ...}
plus either "company" or "item_id" so it can be joined to the gold set.
"""
import argparse, json, sys, os, collections, hashlib
import bfq_metrics as M

def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pred', required=True)
    ap.add_argument('--gold', required=True)
    ap.add_argument('--judge', default='', help='judge model id; omit to skip judged metrics')
    ap.add_argument('--provider', default='openrouter', choices=list(__import__('bfq_judge').DEFAULTS))
    ap.add_argument('--judge-url', default='')
    ap.add_argument('--refusal', default='semantic', choices=['semantic','strict','both'])
    ap.add_argument('--gate', type=float, default=90.0, help='H-Ref reliability-gate threshold')
    ap.add_argument('--out', default='bfq_results.json')
    a = ap.parse_args()

    gold = load_jsonl(a.gold)
    gidx = {}
    for i, g in enumerate(gold):
        gidx[('id', g.get('item_id', f'R{i:05d}'))] = g
        gidx[('q', (g.get('company'), (g.get('question') or '').strip()))] = g
        gidx[('q', (None, (g.get('question') or '').strip()))] = g

    preds = load_jsonl(a.pred)
    judge = None
    if a.judge:
        from bfq_judge import Judge
        judge = Judge(a.judge, a.provider, a.judge_url or None)

    rows, unmatched = [], 0
    for p in preds:
        g = (gidx.get(('id', p.get('item_id'))) or
             gidx.get(('q', (p.get('company'), (p.get('question') or '').strip()))) or
             gidx.get(('q', (None, (p.get('question') or '').strip()))))
        if g is None:
            unmatched += 1; continue
        pred = p.get('predicted_answer') or p.get('prediction') or p.get('actual') or ''
        probe = bool(p.get('unanswerable') or p.get('sabotage'))
        ref = g.get('answer')
        r = dict(item_id=g.get('item_id'), company=g.get('company'),
                 difficulty=(g.get('difficulty') or '').lower(),
                 question_type=g.get('question_type'), model=p.get('model', 'system'),
                 unanswerable=probe,
                 relaxed_em=M.relaxed_em(ref, pred) if not probe else None,
                 token_f1=M.token_f1(ref, pred) if not probe else None,
                 numeric_em=M.numeric_em(ref, pred) if not probe else None,
                 refusal_semantic=M.correct_refusal(pred, True) if probe else None,
                 refusal_strict=M.correct_refusal(pred, False) if probe else None,
                 llm_correct=None)
        if judge and not probe:
            r['llm_correct'] = judge(g.get('question'), ref, pred)
        rows.append(r)

    if unmatched:
        print(f'WARNING: {unmatched} predictions did not join to the gold set', file=sys.stderr)

    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        k = (r['model'], r['difficulty'])
        for m in ('relaxed_em','token_f1','numeric_em','llm_correct',
                  'refusal_semantic','refusal_strict'):
            if r[m] is not None: by[k][m].append(float(r[m]))

    models = sorted({r['model'] for r in rows})
    report = {'manifest': {'pred_file': os.path.basename(a.pred),
                           'pred_sha256': hashlib.sha256(open(a.pred,'rb').read()).hexdigest()[:16],
                           'gold_n': len(gold), 'scored_n': len(rows),
                           'refusal_mode': a.refusal, 'gate_threshold': a.gate,
                           **(judge.manifest() if judge else {'judge_model': None})},
              'models': {}}

    print(f'\n{"model":28s} {"tier":9s} {"n":>5s} {"Rel.EM":>7s} {"F1":>6s} '
          f'{"NumEM":>6s} {"LLM-J":>6s} {"H-Ref":>6s}')
    print('-'*80)
    for mdl in models:
        per_tier = {}
        for t in ['easy','medium','hard','multihop']:
            d = by.get((mdl, t))
            if not d: continue
            avg = lambda k: (sum(d[k])/len(d[k])) if d.get(k) else None
            per_tier[t] = {'n': len([r for r in rows if r['model']==mdl and r['difficulty']==t]),
                           'relaxed_em': avg('relaxed_em'), 'token_f1': avg('token_f1'),
                           'numeric_em': avg('numeric_em'), 'llm_correct': avg('llm_correct'),
                           'h_ref_semantic': avg('refusal_semantic'),
                           'h_ref_strict': avg('refusal_strict')}
            f = lambda v: f'{100*v:6.1f}' if v is not None else '     -'
            pt = per_tier[t]
            print(f'{mdl:28s} {t:9s} {pt["n"]:5d} {f(pt["relaxed_em"])} {f(pt["token_f1"])} '
                  f'{f(pt["numeric_em"])} {f(pt["llm_correct"])} '
                  f'{f(pt["h_ref_semantic"] if a.refusal!="strict" else pt["h_ref_strict"])}')
        score, missing = M.bfq_score(per_tier)
        href = [v['h_ref_semantic'] for v in per_tier.values() if v['h_ref_semantic'] is not None]
        href = sum(href)/len(href) if href else None
        gate = M.reliability_gate(href, a.gate)
        if score is None:
            print(f'{mdl:28s} {"BFQ-Score":9s}   n/a  (missing tiers: {", ".join(missing)})')
        else:
            print(f'{mdl:28s} {"BFQ-Score":9s} {score:8.1f}   H-Ref {100*href:.1f}%  [{gate}]'
                  if href is not None else
                  f'{mdl:28s} {"BFQ-Score":9s} {score:8.1f}   H-Ref unavailable  [UNKNOWN]')
        report['models'][mdl] = {'per_tier': per_tier, 'bfq_score': score,
                                 'missing_tiers': missing, 'h_ref': href, 'gate': gate}
        print('-'*80)

    json.dump({'report': report, 'items': rows}, open(a.out,'w'), indent=1)
    print(f'\nwrote {a.out}')
    print(f'judge prompt sha256: {report["manifest"].get("prompt_sha256","(no judge)")}')

if __name__ == '__main__':
    main()
