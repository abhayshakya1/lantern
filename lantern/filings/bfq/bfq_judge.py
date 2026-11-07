"""Pinned LLM judge for BharatFinQA.

The judge is pinned by: model id, the exact prompt below (whose SHA-256 is
printed into every result file), temperature 0, and an answer-only input that
is blind to which system produced the candidate. Nothing about the system
under test reaches the judge.

Works against any OpenAI-compatible /chat/completions endpoint: OpenRouter,
DeepSeek, NVIDIA NIM, together, vLLM, or a local ollama server. Standard
library only.
"""
import os, json, hashlib, time, urllib.request, urllib.error, re

JUDGE_PROMPT = """You are grading an answer to a question about an Indian company's annual report.

You are given the QUESTION, the REFERENCE ANSWER (verified by human experts), and a CANDIDATE ANSWER.
Decide whether the CANDIDATE is financially equivalent to the REFERENCE.

Treat as EQUIVALENT:
- the same quantity expressed in a different unit, provided the magnitude is the same
  (1 crore = 100 lakh = 10,000,000; 1 lakh = 100,000)
- Indian 2-2-3 digit grouping versus Western 3-3-3 grouping of the same number
  (6,23,280 and 623,280 are the same number)
- the same direction of change stated in different words (rose / increased / was up)
- Indian regulatory aliases (BRSR, SEBI LODR, Ind AS, CSR under Section 135)
- extra correct context, or a different but valid paraphrase

Treat as NOT EQUIVALENT:
- a different magnitude, including a stated unit that changes the magnitude
  (reporting 9,990 rupees as "1.000 crores" is NOT equivalent)
- a different fiscal year, entity, or line item
- a refusal or a statement that the answer cannot be determined, when the
  REFERENCE gives a substantive answer
- an answer that is only partially right when the question asks for several parts

Reply with exactly one word: EQUIVALENT or DIFFERENT."""

PROMPT_SHA = hashlib.sha256(JUDGE_PROMPT.encode()).hexdigest()

DEFAULTS = {
    'openrouter': ('https://openrouter.ai/api/v1/chat/completions', 'OPENROUTER_API_KEY'),
    'deepseek':   ('https://api.deepseek.com/v1/chat/completions',   'DEEPSEEK_API_KEY'),
    'nim':        ('https://integrate.api.nvidia.com/v1/chat/completions', 'NVIDIA_API_KEY'),
    'openai':     ('https://api.openai.com/v1/chat/completions',     'OPENAI_API_KEY'),
    'ollama':     ('http://localhost:11434/v1/chat/completions',     None),
}

class Judge:
    def __init__(self, model, provider='openrouter', url=None, api_key=None,
                 temperature=0.0, max_retries=4, timeout=120):
        base, envkey = DEFAULTS.get(provider, (None, None))
        self.url = url or base
        if not self.url:
            raise ValueError(f'unknown provider {provider!r}; pass --judge-url')
        self.key = api_key or (os.environ.get(envkey) if envkey else None)
        self.model, self.temperature = model, temperature
        self.max_retries, self.timeout = max_retries, timeout
        self.calls = 0

    def _post(self, payload):
        req = urllib.request.Request(
            self.url, data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json',
                     **({'Authorization': f'Bearer {self.key}'} if self.key else {})})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode())

    def __call__(self, question, reference, candidate):
        user = (f'QUESTION:\n{question}\n\nREFERENCE ANSWER:\n{reference}\n\n'
                f'CANDIDATE ANSWER:\n{candidate}')
        payload = {'model': self.model, 'temperature': self.temperature,
                   'max_tokens': 8,
                   'messages': [{'role': 'system', 'content': JUDGE_PROMPT},
                                {'role': 'user', 'content': user}]}
        last = None
        for i in range(self.max_retries):
            try:
                out = self._post(payload)
                self.calls += 1
                txt = out['choices'][0]['message']['content'].strip().upper()
                if 'EQUIVALENT' in txt and 'NOT' not in txt: return True
                if 'DIFFERENT' in txt: return False
                return None                      # unparseable verdict, recorded as such
            except (urllib.error.HTTPError, urllib.error.URLError, KeyError, TimeoutError) as e:
                last = e; time.sleep(2 ** i)
        raise RuntimeError(f'judge failed after {self.max_retries} attempts: {last}')

    def manifest(self):
        return {'judge_model': self.model, 'judge_url': self.url,
                'temperature': self.temperature, 'prompt_sha256': PROMPT_SHA,
                'blind_to_system': True, 'calls': self.calls}
