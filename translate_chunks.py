"""
translate_chunks.py — pipeline ODT -> chunking -> translation -> stitching

Three responsibilities, each isolated:
  1. CHUNKING   : cuts at paragraph/sentence boundary; full coverage guaranteed.
  2. TRANSLATION: sends each chunk to the model with a clean prompt (zero CONTEXT).
  3. STITCHING  : pastes the outputs in sequence with a double newline. No modification to the text.
                  Post-processing happens on the output file, not here.

Usage:
    python translate_chunks.py [path.odt] [--selftest] [--dry-run]

    --selftest          verify chunking without calling the model
    --dry-run           show the chunks without translating
    --out FILE          output file (default: <odt_name>_EN.md)
    --size N            force chunk size in characters (default: automatic calculation)
    --thinking-buffer N tokens reserved for the model's thinking (default: 0)
    --model URL         llama.cpp server url (default: http://127.0.0.1:8080/...)

Automatic chunk size (default):
    Queries /props (real n_ctx) and /tokenize (exact tokenizer) before starting.
    Computes the optimal chunk size for any model. Use --size N to force.
"""

import zipfile, json, urllib.request, urllib.error, time, sys, os, re, argparse
from xml.etree import ElementTree as ET

# ── Config default ────────────────────────────────────────────────────────────
DEFAULT_API    = "http://127.0.0.1:8080/v1/chat/completions"
MAX_TOKENS     = 2000
SAFETY_MARGIN  = 200
FALLBACK_SIZE  = 3000

SYSTEM_PROMPT = (
    "You are a literary translator. Translate the Italian text given to you into English. "
    "Preserve tone, voice, style, and every narrative element. "
    "Output only the translated text — no preambles, no comments, no explanations."
)

TRANSLATE_PROMPT = (
    "Translate the following Italian text into English.\n\n"
    "Rules:\n"
    "- Preserve tone, style, and every narrative element without exception.\n"
    "- Replace dialogue em-dashes (—) with American double quotes: "
    '  "Dialogue text," character said.\n'
    "- Use italics (*word*) only where the original uses them.\n"
    "- Scene breaks use *** only.\n"
    "- Do NOT add chapter headers, fragment numbers, preambles, or any meta-commentary.\n"
    "- Do NOT omit any sentence or paragraph.\n\n"
    "Text to translate:\n\n"
    "{text}"
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
            lines.append(t)   # keep empty lines too: they are separator paragraphs
            return
        for child in node:
            walk(child)
    walk(tree)
    return '\n'.join(lines)

# ── Chunking ──────────────────────────────────────────────────────────────────
def _find_break(text, start, size):
    """Break point: prefers paragraph boundary, then sentence, then space."""
    n = len(text)
    if start + size >= n:
        return n
    hi = start + size
    nl = text.rfind('\n', start, hi)
    if nl > start:
        return nl + 1
    last = None
    for m in re.finditer(r'[.!?…»"]\s', text[start:hi]):
        last = m
    if last is not None:
        return start + last.end()
    sp = text.rfind(' ', start, hi)
    if sp > start:
        return sp + 1
    return hi

def build_chunks(text, size):
    """Return a list of contiguous, non-overlapping (start, end) tuples."""
    n, ranges, i = len(text), [], 0
    while i < n:
        e = _find_break(text, i, size)
        if e <= i:
            e = min(i + size, n)
        ranges.append((i, e))
        i = e
    return ranges

def prove_coverage(text, ranges):
    assert ranges and ranges[0][0] == 0 and ranges[-1][1] == len(text)
    for (a, b), (c, d) in zip(ranges, ranges[1:]):
        assert b == c and b > a
    assert ''.join(text[a:b] for a, b in ranges) == text
    return True

# ── Translation ───────────────────────────────────────────────────────────────
def translate_chunk(text_fragment, api_url, chunk_num, total):
    prompt = TRANSLATE_PROMPT.format(text=text_fragment)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]
    payload = json.dumps({
        "model": "local",
        "messages": messages,
        "stream": False,
        "temperature": 0.2,
        "max_tokens": MAX_TOKENS,
        "repeat_penalty": 1.05,
    }).encode('utf-8')
    req = urllib.request.Request(
        api_url, data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data['choices'][0]['message']['content'].strip()
    except urllib.error.URLError as e:
        return f"[TRANSLATION ERROR chunk {chunk_num}: {e}]"

# ── Automatic chunk size calculation ──────────────────────────────────────────
def _api_base(api_url):
    return api_url.split('/v1/')[0]

def get_server_props(api_url):
    url = _api_base(api_url) + '/props'
    req = urllib.request.Request(url, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception:
        return None

def tokenize_text(text, api_url):
    url = _api_base(api_url) + '/tokenize'
    payload = json.dumps({'content': text}).encode('utf-8')
    req = urllib.request.Request(url, data=payload,
                                  headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return len(data.get('tokens', []))
    except Exception:
        return None

def auto_chunk_size(text, system_prompt, api_url, max_tokens, thinking_buffer):
    props = get_server_props(api_url)
    if props is None:
        return None, None
    n_ctx = (props.get('n_ctx')
             or props.get('default_generation_settings', {}).get('n_ctx'))
    if not n_ctx:
        return None, None
    sys_tokens = tokenize_text(system_prompt, api_url)
    if sys_tokens is None:
        return None, None
    available_tokens = n_ctx - sys_tokens - max_tokens - thinking_buffer - SAFETY_MARGIN
    if available_tokens <= 100:
        return None, None
    sample = text[:1500] if len(text) >= 1500 else text
    sample_tokens = tokenize_text(sample, api_url)
    if not sample_tokens:
        return None, None
    chars_per_token = len(sample) / sample_tokens
    chunk_size = max(500, int(available_tokens * chars_per_token))
    info = {
        'n_ctx': n_ctx, 'sys_tokens': sys_tokens,
        'available_tokens': available_tokens,
        'chars_per_token': round(chars_per_token, 2),
        'chunk_size': chunk_size, 'thinking_buffer': thinking_buffer,
    }
    return chunk_size, info

# ── Stitching ─────────────────────────────────────────────────────────────────
def stitch(translated_chunks):
    """Paste the translated chunks in sequence. No modification to the text."""
    return '\n\n'.join(c for c in translated_chunks if c).strip()

# ── Terminal colors ───────────────────────────────────────────────────────────
class C:
    R = '\033[91m'; G = '\033[92m'; Y = '\033[93m'; DIM = '\033[2m'; OFF = '\033[0m'
if os.name == 'nt':
    os.system('')

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Translates an ODT into English via llama.cpp")
    ap.add_argument('odt', nargs='?',
                    default=os.path.join(os.path.dirname(__file__),
                                         "Test files", "Dialoghi con la lavatrice.odt"))
    ap.add_argument('--selftest',         action='store_true')
    ap.add_argument('--dry-run',          action='store_true')
    ap.add_argument('--out',              default=None)
    ap.add_argument('--size',             type=int, default=None,
                    help='force chunk size in characters (default: automatic calculation)')
    ap.add_argument('--model',            default=DEFAULT_API)
    ap.add_argument('--thinking',         action='store_true',
                    help='reasoning model (e.g. Gemma): reserve 800 tokens for internal thinking')
    ap.add_argument('--thinking-buffer',  type=int, default=None, dest='thinking_buffer',
                    help='tokens reserved for internal thinking (overrides --thinking; default 0)')
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    # ── Thinking model? — reserve tokens for internal reasoning ───────────────
    # Priority: explicit --thinking-buffer > --thinking > interactive prompt > 0.
    # The prompt appears ONLY on an interactive terminal (stdin.isatty): this avoids
    # the EOFError and the window closing on a windowless double click.
    if args.thinking_buffer is not None:
        thinking_buffer = args.thinking_buffer
    elif args.thinking:
        thinking_buffer = 800
    elif sys.stdin.isatty() and not args.dry_run:
        try:
            ans = input(" Is this a thinking model? (e.g. Gemma) [y/N]: ").strip().lower()
        except EOFError:
            ans = ''
        thinking_buffer = 800 if ans == 'y' else 0
    else:
        thinking_buffer = 0

    if not os.path.exists(args.odt):
        print(f"{C.R}File not found: {args.odt}{C.OFF}")
        sys.exit(1)

    out_path = args.out or os.path.splitext(args.odt)[0] + '_EN.md'

    print(f"\n Selmo — chunked translation")
    print(f" {'─' * 50}")
    text = extract_odt(args.odt)

    # ── Calcolo chunk size ────────────────────────────────────────────────────
    if args.size is not None:
        chunk_size = args.size
        size_source = f"manual ({chunk_size:,} char)"
    else:
        print(f"\n translate_chunks — calibrating model…")
        cs, info = auto_chunk_size(text, SYSTEM_PROMPT, args.model,
                                   MAX_TOKENS, thinking_buffer)
        if cs is not None:
            chunk_size = cs
            size_source = (
                f"auto ({chunk_size:,} char · n_ctx={info['n_ctx']} · "
                f"{info['chars_per_token']} char/tok"
                + (f" · thinking={info['thinking_buffer']}" if info['thinking_buffer'] else "")
                + ")"
            )
        else:
            chunk_size = FALLBACK_SIZE
            size_source = f"fallback ({chunk_size:,} char)"
            print(f" {C.Y}Server unreachable, using fallback {FALLBACK_SIZE:,} char{C.OFF}")

    print(f" Source   : {os.path.basename(args.odt)}")
    print(f" Output   : {os.path.basename(out_path)}")
    print(f" Chunk    : {size_source}\n")

    print(f" Extracted {len(text):,} characters")

    ranges = build_chunks(text, chunk_size)
    try:
        prove_coverage(text, ranges)
    except AssertionError as e:
        print(f"{C.R}COVERAGE FAILED: {e}{C.OFF}")
        sys.exit(2)

    biggest = max(b - a for a, b in ranges)
    print(f" {C.G}Coverage OK{C.OFF} · {len(ranges)} chunk · max {biggest:,} char\n")

    if args.dry_run:
        for i, (a, b) in enumerate(ranges):
            snippet = text[a:b].replace('\n', ' ')[:80]
            print(f" [{i+1:3d}/{len(ranges)}] {snippet}…")
        print(f"\n{C.Y}--dry-run: no call to the model.{C.OFF}")
        return

    translated = []
    total_time = 0.0
    for i, (a, b) in enumerate(ranges):
        n = i + 1
        fragment = text[a:b]
        snippet = fragment.replace('\n', ' ')[:55]
        print(f" [{n:3d}/{len(ranges)}] '{snippet}'…  ", end='', flush=True)

        t0 = time.time()
        result = translate_chunk(fragment, args.model, n, len(ranges))
        dt = time.time() - t0
        total_time += dt

        if result.startswith('[TRANSLATION ERROR'):
            print(f"{C.R}{result}{C.OFF}")
        else:
            chars_out = len(result)
            print(f"{C.G}{dt:.1f}s{C.OFF}  → {chars_out:,} char")

        translated.append(result)

    print(f"\n {C.G}Translation completed{C.OFF} in {total_time:.0f}s total")
    print(f" Stitching {len(translated)} chunk…")

    final = stitch(translated)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(final)

    print(f" {C.G}Saved{C.OFF}: {out_path}  ({len(final):,} char)\n")

# ── Selftest ───────────────────────────────────────────────────────────────────
def selftest():
    print("\n SELFTEST\n " + "─" * 40)
    ok = True

    # Chunking: char-exact coverage
    text = "First paragraph.\n\nSecond, longer paragraph, with two sentences. Here it is.\n\nThird."
    ranges = build_chunks(text, 40)
    try:
        prove_coverage(text, ranges); g = True
    except AssertionError as e:
        g = False; print("  ", e)
    print(f" [1] char-exact coverage           : {'OK' if g else 'FAIL'}")
    ok &= g

    # Stitch: all chunks present, in order, no losses
    chunk_a = "She walked into the room."
    chunk_b = "Nobody moved at all."
    result = stitch([chunk_a, chunk_b])
    g2 = chunk_a in result and chunk_b in result and result.index(chunk_a) < result.index(chunk_b)
    print(f" [2] stitch: chunks present and ordered: {'OK' if g2 else 'FAIL'}")
    if not g2:
        print(f"     got: {result!r}")
    ok &= g2

    # Stitch: empty chunks ignored
    result2 = stitch(["First.", "", "Last."])
    g3 = "First." in result2 and "Last." in result2
    print(f" [3] stitch: empty chunks ignored  : {'OK' if g3 else 'FAIL'}")
    ok &= g3

    print("\n " + (f"\033[92mSELFTEST OK\033[0m" if ok else f"\033[91mSELFTEST FAILED\033[0m"))
    sys.exit(0 if ok else 1)

if __name__ == '__main__':
    main()
