"""
test_chunking.py -- pipeline ODT -> chunking -> Selmo, the "does little but does it well" version.

Usage:
    python test_chunking.py            # runs on the manuscript (needs the llama.cpp server running)
    python test_chunking.py --selftest # verifies the 5 guarantees WITHOUT a server (offline)

The five guarantees:
  1. No giant chunks      -> a paragraph longer than the budget is split
                             by sentence, then by word, then by character.
  2. Coverage proof       -> the chunks reconstruct the text character by character;
                             if anything is missing the program STOPS.
  3. Minimal overlap      -> the last sentences of each chunk are repeated, marked,
                             at the head of the next one: nothing falls through the cut edges.
  4. A single source      -> the model receives only the text to analyze, nothing else.
  5. Mandatory citation   -> the model must report the exact sentence; we verify it
                             by matching against the text. Citation not found = ALARM.
"""

import zipfile, json, urllib.request, urllib.error, time, sys, os, re
from xml.etree import ElementTree as ET

# Config
ODT_PATH   = os.path.join(os.path.dirname(__file__), "Test files", "Dialoghi con la lavatrice.odt")
API_URL    = "http://127.0.0.1:8080/v1/chat/completions"
CHUNK_SIZE = 11000   # character budget per block (leaves room for prompt + response in ctx 16k)
OVERLAP_SENTENCES = 2
MAX_TOKENS = 1000

# Mizan: deterministic. For an analysis task we don't want creativity.
SYSTEM_PROMPT = (
    "You are a text analysis system. You work only on the text you are given. "
    "You add nothing that is not written in the text. No opinions, only data."
)

# The response format is rigid on purpose: it lets us verify every citation.
QUERY = (
    "This is a fragment of an Italian novel written in the passato remoto and imperfetto tenses.\n"
    "Look ONLY in the narrative paragraphs (not in the dialogue) for the sentences where the narrator "
    "uses a verb in the PRESENT tense instead of the past.\n\n"
    "For EACH anomaly found, write EXACTLY two lines:\n"
    'SENTENCE: "<the sentence copied word for word from the text, without changes>"\n'
    "VERB: <the present-tense verb>\n\n"
    "Copy the sentence IDENTICAL to the text: it is needed for automatic verification.\n"
    "Analyze only the section marked [TO ANALYZE]. The [CONTEXT] section is only there "
    "to avoid losing sentences cut by the split: do not report anomalies that exist only there.\n"
    "If you find nothing, reply with a single word: NOTHING"
)

# ── ODT extraction ────────────────────────────────────────────────────────────
def extract_odt(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read('content.xml').decode('utf-8')
    tree = ET.fromstring(xml)
    NS = 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'
    lines = []
    def walk(node):
        if node.tag in (f'{{{NS}}}p', f'{{{NS}}}h'):
            t = ''.join(node.itertext()).strip()
            if t:
                lines.append(t)
            return
        for child in node:
            walk(child)
    walk(tree)
    return '\n'.join(lines)

# ── Chunking (guarantees 1 and 2) ─────────────────────────────────────────────
def _find_break(text, start, size):
    """Return the index where to cut the chunk starting at `start`.
    Tries in order: paragraph boundary, sentence end, space, hard cut.
    Always guarantees progress (result > start)."""
    n = len(text)
    if start + size >= n:
        return n
    hi = start + size
    # 1) paragraph boundary: cut right after a newline
    nl = text.rfind('\n', start, hi)
    if nl > start:
        return nl + 1
    # 2) sentence end (paragraph longer than budget -> guarantee 1)
    last = None
    for m in re.finditer(r'[.!?…](?=\s|$)', text[start:hi]):
        last = m
    if last is not None and start + last.end() > start:
        return start + last.end()
    # 3) word boundary
    sp = text.rfind(' ', start, hi)
    if sp > start:
        return sp + 1
    # 4) last resort: hard character cut (loses nothing, just ugly)
    return hi

def build_chunks(text, size):
    """Partition `text` into contiguous, non-overlapping ranges, none > size.
    Returns a list of (start, end)."""
    n = len(text)
    ranges, i = [], 0
    while i < n:
        e = _find_break(text, i, size)
        if e <= i:            # safety net: this must never happen
            e = min(i + size, n)
        ranges.append((i, e))
        i = e
    return ranges

def prove_coverage(text, ranges):
    """Guarantee 2: the ranges cover the text EXACTLY. Raises AssertionError if not."""
    assert ranges, "no chunk produced"
    assert ranges[0][0] == 0, "the first chunk does not start at 0"
    assert ranges[-1][1] == len(text), "the last chunk does not reach the end"
    for (a, b), (c, d) in zip(ranges, ranges[1:]):
        assert b == c, f"gap or overlap between {b} and {c}"
        assert b > a, "empty chunk"
    recon = ''.join(text[a:b] for a, b in ranges)
    assert recon == text, "the reconstruction does NOT match the original text"
    return True

def _last_sentences(text, k):
    parts = re.split(r'(?<=[.!?…])\s+', text.strip())
    return ' '.join(parts[-k:]).strip() if parts else ''

def overlap_for(text, ranges, idx):
    """Guarantee 3: context text = last sentences of the previous chunk."""
    if idx == 0:
        return ''
    a, b = ranges[idx - 1]
    return _last_sentences(text[a:b], OVERLAP_SENTENCES)

# ── Citation verification (guarantee 5) ───────────────────────────────────────
def _norm(s):
    return re.sub(r'\s+', ' ', s).strip().lower()

def parse_quotes(answer):
    return re.findall(r'SENTENCE:\s*"(.+?)"', answer, flags=re.S)

def verify_quote(quote, source):
    return _norm(quote) in _norm(source)

# ── Terminal colors ───────────────────────────────────────────────────────────
class C:
    R = '\033[91m'; G = '\033[92m'; Y = '\033[93m'; DIM = '\033[2m'; OFF = '\033[0m'
if os.name == 'nt':
    os.system('')   # enable ANSI sequences on Windows 10+

# ── Model call (guarantee 4: a single source in the prompt) ────────────────────
def call_model(analyze_text, context_text, chunk_num, total):
    blocks = ''
    if context_text:
        blocks += '[CONTEXT — only to avoid losing split sentences, do not analyze]\n' \
                  + context_text + '\n\n'
    blocks += '[TO ANALYZE]\n' + analyze_text
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content":
            f"Document — block {chunk_num} of {total}:\n\n{blocks}\n\n---\n{QUERY}"}
    ]
    payload = json.dumps({
        "model": "local", "messages": messages, "stream": False,
        "temperature": 0.01, "max_tokens": MAX_TOKENS, "repeat_penalty": 1.1
    }).encode('utf-8')
    req = urllib.request.Request(API_URL, data=payload,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data['choices'][0]['message']['content'].strip()
    except urllib.error.URLError as e:
        return f"[API ERROR: {e}]"

# ── Main run ──────────────────────────────────────────────────────────────────
def main():
    print("\n Selmo — document analysis (robust chunking)")
    print(" " + "─" * 56)

    if not os.path.exists(ODT_PATH):
        print(f"\n ERROR: file not found: {ODT_PATH}")
        sys.exit(1)

    text = extract_odt(ODT_PATH)
    print(f"\n Extracted {len(text):,} characters from {os.path.basename(ODT_PATH)}")

    ranges = build_chunks(text, CHUNK_SIZE)
    biggest = max(b - a for a, b in ranges)
    try:
        prove_coverage(text, ranges)
        print(f" {C.G}COVERAGE OK{C.OFF}: {len(ranges)} blocks reconstruct the text "
              f"to the character · max block {biggest:,} char (budget {CHUNK_SIZE:,})\n")
    except AssertionError as e:
        print(f" {C.R}COVERAGE FAILED: {e}{C.OFF}\n Stopping: I cannot guarantee zero losses.")
        sys.exit(2)

    found, unverified = [], 0
    for i, (a, b) in enumerate(ranges):
        n = i + 1
        analyze = text[a:b]
        context = overlap_for(text, ranges, i)
        head = analyze.split('\n')[0][:60]
        print(f" [{n:2d}/{len(ranges)}] '{head}' … ", end='', flush=True)

        t0 = time.time()
        answer = call_model(analyze, context, n, len(ranges))
        dt = time.time() - t0

        if answer.strip().upper().startswith("NOTHING"):
            print(f"{dt:.1f}s  —")
            continue

        quotes = parse_quotes(answer)
        # Guarantee 5: every citation must exist VERBATIM in the analyzed chunk.
        verdicts = [(q, verify_quote(q, analyze)) for q in quotes]
        ok = sum(1 for _, v in verdicts if v)
        bad = len(verdicts) - ok
        unverified += bad
        tag = f"{C.G}★ {ok} verified{C.OFF}" + (f"  {C.R}{bad} NOT VERIFIED{C.OFF}" if bad else "")
        print(f"{dt:.1f}s  {tag}")
        found.append((n, answer, verdicts))
        for q, v in verdicts:
            col = C.G if v else C.R
            mark = "✓" if v else "✗ INVENTED?"
            print(f"        {col}{mark}{C.OFF} \"{q.strip()[:90]}\"")

    # Summary
    print("\n" + "═" * 58)
    print(f" Blocks with results: {len(found)}/{len(ranges)}")
    if unverified:
        print(f" {C.R}WARNING: {unverified} citations not found in the text "
              f"(possible hallucinations).{C.OFF}")
    elif found:
        print(f" {C.G}All citations verified against the text.{C.OFF}")
    else:
        print(" No anomalies found.")

# ── Offline selftest (verifies the guarantees without the model) ──────────────
def selftest():
    print("\n SELFTEST — verifies the guarantees without a server\n " + "─" * 40)
    ok = True

    # Text built on purpose: a GIANT paragraph that exceeds the budget,
    # normal sentences, and an accent to check non-ASCII characters.
    giant = ("Very long sentence number one. " * 40).strip()      # ~1200 char, > test budget
    text = "Short first paragraph.\n" + giant + "\nThird paragraph. With two sentences.\nFourth is here."
    SIZE = 200  # small budget to force the splits

    ranges = build_chunks(text, SIZE)

    # Guarantee 1: no chunk exceeds the budget
    big = max(b - a for a, b in ranges)
    g1 = big <= SIZE
    print(f" [1] no chunk > budget            : {'OK' if g1 else 'FAILED'} (max {big}/{SIZE})")
    ok &= g1

    # Guarantee 2: char-exact coverage (even with the giant paragraph split)
    try:
        prove_coverage(text, ranges); g2 = True
    except AssertionError as e:
        g2 = False; print("     ", e)
    print(f" [2] char-exact coverage           : {'OK' if g2 else 'FAILED'}")
    ok &= g2

    # Guarantee 3: the overlap of the 2nd chunk is the last sentences of the 1st
    ov = overlap_for(text, ranges, 1)
    g3 = len(ov) > 0 and ov in text
    print(f" [3] overlap present and from text  : {'OK' if g3 else 'FAILED'} (\"{ov[:40]}…\")")
    ok &= g3

    # Guarantee 5: the verification accepts a real citation and unmasks a false one
    real  = "Third paragraph. With two sentences."
    fake  = "This sentence is not in the text."
    g5 = verify_quote(real, text) and not verify_quote(fake, text)
    print(f" [5] quote-check real=accept/fake=reject: {'OK' if g5 else 'FAILED'}")
    ok &= g5

    # parsing of the model's response format
    sample = 'SENTENCE: "I nod and stay still."\nVERB: nod'
    g_parse = parse_quotes(sample) == ["I nod and stay still."]
    print(f" [+] parsing SENTENCE: \"...\"        : {'OK' if g_parse else 'FAILED'}")
    ok &= g_parse

    print("\n " + ("\033[92mALL GUARANTEES OK\033[0m" if ok else "\033[91mSOMETHING FAILED\033[0m"))
    sys.exit(0 if ok else 1)

if __name__ == '__main__':
    if '--selftest' in sys.argv:
        selftest()
    main()
