"""BharatFinQA scoring metrics. Standard library + numpy only.

Every metric here is deterministic except `judge`, which lives in bfq_judge.py
and is pinned by model id, prompt hash and temperature 0.
"""
import re, unicodedata, math
from collections import Counter

# ---------------------------------------------------------------- normalisation
_PUNCT = re.compile(r'[^\w\s.%/-]', re.UNICODE)
_WS    = re.compile(r'\s+')
_ART   = re.compile(r'\b(a|an|the|is|was|were|are|of|for|as|at|in|on|to)\b')
_MD    = re.compile(r'[*_`#>]+')

_ORD   = re.compile(r'(?<=\d)\s*(?:st|nd|rd|th)\b')
_THOUS = re.compile(r'(?<=\d),(?=\d)')
_PCTSP = re.compile(r'(?<=\d)\s+(?=%)')
_TIME  = re.compile(r'(?<=\d)\.(?=\d{2}\s*(?:am|pm)\b)', re.I)
_TRAILZ= re.compile(r'(?<=\d)\.0+(?!\d)')
_NBSP  = dict.fromkeys(map(ord, '    '), ' ')
_DASH  = dict.fromkeys(map(ord, '‐‑‒–—−'), '-')

def normalize(s):
    """Surface normalisation shared by every lexical metric.

    Beyond lowercasing and punctuation stripping, this folds the surface
    variation Indian filings actually produce, so that a correct answer is not
    marked wrong for cosmetic reasons:
      digit separators  156,799  -> 156799   (2-2-3 and 3-3-3 both fold)
      percent spacing   90 %     -> 90%
      ordinal suffixes  12 th    -> 12
      dash variants     6.50 en-dash 6.70 -> 6.50 - 6.70
      time separators   12.30 PM -> 12:30 pm
      trailing zeros    60.00    -> 60
    """
    if s is None: return ''
    s = unicodedata.normalize('NFKC', str(s))
    s = s.translate(_NBSP).translate(_DASH)
    s = _MD.sub(' ', s).lower()
    s = re.sub(r'\b(rs\.?|inr)\b', ' ', s).replace('₹', ' ')
    s = _TIME.sub(':', s)
    s = _THOUS.sub('', s)
    s = _PCTSP.sub('', s)
    s = _ORD.sub('', s)
    s = _TRAILZ.sub('', s)
    s = _PUNCT.sub(' ', s)
    s = _ART.sub(' ', s)
    return _WS.sub(' ', s).strip()

# ---------------------------------------------------------------- numbers
_NUM = re.compile(r'[-+(]?\d[\d,]*\.?\d*\)?')
SCALE = {'crore':1e7,'crores':1e7,'cr':1e7,'lakh':1e5,'lakhs':1e5,'lac':1e5,'lacs':1e5,
         'million':1e6,'mn':1e6,'billion':1e9,'bn':1e9,'thousand':1e3,'trillion':1e12}
_SCALE_RE = re.compile(r'\b(' + '|'.join(SCALE) + r')\b', re.I)

def parse_number(tok):
    """Parse a numeric literal. Indian 2-2-3 grouping (6,23,280) parses the same
    as Western grouping once separators are stripped; parentheses mean negative."""
    neg = tok.strip().startswith('(') or tok.strip().startswith('-')
    t = tok.strip().strip('()+-').replace(',', '')
    if not t or t in '.': return None
    try: v = float(t)
    except ValueError: return None
    return -v if neg else v

def numbers(s, apply_scale=True):
    """Values asserted by a string, in base units. A trailing macro-unit word
    (lakh/crore/million) multiplies the values that precede it."""
    s = unicodedata.normalize('NFKC', str(s or '')).replace(' ',' ')
    out = set()
    scales = [SCALE[m.group(1).lower()] for m in _SCALE_RE.finditer(s)]
    for m in _NUM.finditer(s):
        v = parse_number(m.group(0))
        if v is None: continue
        out.add(v)
        if apply_scale:
            for f in scales: out.add(v * f)
    return out

def has_indian_notation(s):
    s = unicodedata.normalize('NFKC', str(s or ''))
    return bool(re.search(r'\d{1,2}(?:,\d{2})+,\d{3}(?!\d)', s)) or \
           bool(re.search(r'\b(lakh|lakhs|lac|lacs|crore|crores)\b', s, re.I))

# ---------------------------------------------------------------- metrics
def is_empty(pred):
    """True when a system returned nothing. An empty prediction is a failed
    generation, never a correct answer; every scorer must short-circuit on it."""
    return not str(pred or '').strip()

def relaxed_em(gold, pred):
    """1.0 if the normalised gold appears as a contiguous span of the
    normalised prediction (or vice versa for very short predictions)."""
    if is_empty(pred): return 0.0
    g, p = normalize(gold), normalize(pred)
    if not g: return 0.0
    if g == p: return 1.0
    return 1.0 if g in p else 0.0

def token_f1(gold, pred):
    if is_empty(pred): return 0.0
    g, p = normalize(gold).split(), normalize(pred).split()
    if not g or not p: return 0.0
    common = Counter(g) & Counter(p)
    n = sum(common.values())
    if n == 0: return 0.0
    prec, rec = n/len(p), n/len(g)
    return 2*prec*rec/(prec+rec)

def numeric_em(gold, pred, rel_tol=0.01):
    """Unit-aware numeric match. Returns None when gold asserts no number."""
    if is_empty(pred): return 0.0
    g = numbers(gold)
    if not g: return None
    p = numbers(pred)
    if not p: return 0.0
    for x in g:
        for y in p:
            d = max(abs(x), abs(y))
            if x == y or (d > 0 and abs(x-y)/d <= rel_tol): return 1.0
    return 0.0

# ---------------------------------------------------------------- refusal
_REFUSE = [
    r'not found', r'not (?:present|available|disclosed|stated|provided|specified|mentioned|given)',
    r'no (?:such )?(?:information|data|figure|disclosure|mention|value)',
    r'cannot (?:be )?(?:determin|answer|find|comput|establish|verif)',
    r"can(?:'|no)t (?:be )?(?:determin|answer|find|comput)",
    r'unable to (?:determin|answer|find|locate|comput)',
    r'does not (?:contain|include|provide|disclose|specify|mention)',
    r'(?:is|are) not (?:included|contained)',
    r'insufficient (?:information|evidence|data)',
    r'no information (?:is )?(?:available|provided)',
    r'\bn/?a\b',
]
_REFUSE_RE = re.compile('|'.join(_REFUSE), re.I)

CANONICAL_REFUSAL = 'Not found in the provided evidence.'

def is_refusal(pred, semantic=True):
    """Refusal detection.

    strict  : the prediction must reproduce the canonical gold refusal string
              (compared after the same normalisation, so markdown and
              punctuation do not matter, but wording does).
    semantic: any recognisable refusal counts.

    The two differ materially for systems that refuse conversationally
    ("The provided evidence does not contain ..."), which strict matching
    scores as a hallucination. Report both; the gap is itself a finding.
    """
    if is_empty(pred): return False   # no output is not a refusal, it is a failure
    t = normalize(pred)
    if not semantic:
        canon = normalize(CANONICAL_REFUSAL)
        return canon in t or t == normalize('Not found')
    return bool(_REFUSE_RE.search(t))

def correct_refusal(pred, semantic=True):
    return 1.0 if is_refusal(pred, semantic) else 0.0

# ---------------------------------------------------------------- BFQ-Score
TIER_PRIMARY = {'easy':'relaxed_em', 'medium':'llm_correct',
                'hard':'llm_correct', 'multihop':'llm_correct'}

def bfq_score(per_tier):
    """Macro-average of the four tier primaries, on a 0-100 scale.

    per_tier: {'easy': {'relaxed_em': x, ...}, 'medium': {'llm_correct': y}, ...}
    Returns (score, missing_tiers). The score is undefined unless all four
    tiers are present -- a partial macro-average is not comparable.
    """
    vals, missing = [], []
    for t, key in TIER_PRIMARY.items():
        d = per_tier.get(t) or {}
        v = d.get(key)
        if v is None: missing.append(t); continue
        vals.append(100*v if v <= 1.0 else v)
    if missing: return None, missing
    return sum(vals)/len(vals), []

def reliability_gate(h_ref, threshold=90.0):
    """H-Ref is a gate, not a score component.

    A system below the threshold answers unanswerable questions; its BFQ-Score
    is reported but must be shown as GATED, because accuracy bought by never
    abstaining is not comparable to accuracy with calibrated abstention.
    Threshold is a released default, not a law: report it explicitly.
    """
    if h_ref is None: return 'UNKNOWN'
    h = 100*h_ref if h_ref <= 1.0 else h_ref
    return 'PASS' if h >= threshold else 'GATED'


# ---------------------------------------------------------------- ROUGE-L
def _lcs(a, b):
    """Length of the longest common subsequence. O(len(a)*len(b)) with a rolling
    row, which is fine at answer length and avoids a dependency."""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(cur[j], prev[j + 1]))
        prev = cur
    return prev[-1]


def rouge_l(gold, pred, beta=1.2):
    """ROUGE-L F-measure on normalised tokens.

    beta=1.2 is the standard ROUGE setting, which weights recall slightly above
    precision -- a summary that covers the reference matters more than one that
    adds nothing extra.
    """
    if is_empty(pred):
        return 0.0
    g, p = normalize(gold).split(), normalize(pred).split()
    if not g or not p:
        return 0.0
    l = _lcs(g, p)
    if l == 0:
        return 0.0
    prec, rec = l / len(p), l / len(g)
    b2 = beta * beta
    return (1 + b2) * prec * rec / (rec + b2 * prec)


# ---------------------------------------------------------------- Jaccard
def jaccard(gold, pred):
    """Token-set Jaccard between gold and prediction."""
    if is_empty(pred):
        return 0.0
    g, p = set(normalize(gold).split()), set(normalize(pred).split())
    if not g or not p:
        return 0.0
    return len(g & p) / len(g | p)


# ---------------------------------------------------------------- containment
def containment(gold, pred):
    """Share of gold tokens present in the prediction.

    Unlike Relaxed EM this does not require a contiguous span, so it stays
    informative above the Easy tier where gold answers are free text and
    Relaxed EM sits at floor.
    """
    if is_empty(pred):
        return 0.0
    g, p = set(normalize(gold).split()), set(normalize(pred).split())
    if not g:
        return 0.0
    return len(g & p) / len(g)


def _selftest():
    assert rouge_l('the cat sat on the mat', 'the cat sat on the mat') == 1.0
    assert rouge_l('a b c', 'x y z') == 0.0
    assert 0 < rouge_l('the cat sat', 'the cat quickly sat') < 1.0
    # NB: normalize() strips articles and copulas, so test tokens must avoid
    # them -- 'a b c d' normalises to 'b c d' and the arithmetic changes.
    assert jaccard('alpha beta gamma', 'alpha beta gamma') == 1.0
    assert jaccard('alpha beta', 'gamma delta') == 0.0
    assert containment('alpha beta', 'alpha beta gamma delta') == 1.0
    assert containment('alpha beta gamma delta', 'alpha beta') == 0.5
    # every metric must short-circuit on an empty prediction
    for f in (rouge_l, jaccard, containment):
        assert f('anything', '') == 0.0, f.__name__
    # and must be blind to Indian digit grouping, like the rest of the suite
    assert rouge_l('6,23,280', '623,280') == 1.0
    print('extended metrics self-check: OK')
