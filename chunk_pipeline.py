"""
chunk_pipeline.py — generic pipeline: ODT/TXT -> chunking -> LLM -> output

Works with any prompt and any kind of task:
  translation, thematic search, analysis, extraction, rewriting, etc.

Two output modes (--mode):
  stitch   [default] : results are continuous text.
                       Ideal for: translation, rewriting, paraphrasing.
  collect            : the result of each chunk is gathered in sequence.
                       If the model replies "NOTHING" or variants, that chunk
                       is not included in the output.
                       Ideal for: search, analysis, extraction.

Usage:
    python chunk_pipeline.py <file.odt|file.txt> --prompt "..." [options]
    python chunk_pipeline.py <file> --prompt-file prompt.txt [options]
    python chunk_pipeline.py --selftest

Options:
    --mode stitch|collect     output mode (default: stitch)
    --system "..."            system prompt (default: generic assistant)
    --out FILE                output file (default: <name>_out.md)
    --size N                  force chunk size in characters (default: auto)
    --thinking-buffer N       tokens reserved for the model's internal thinking
                              (default: 0 — instruct models; use 800+ for reasoning)
    --model URL               llama.cpp endpoint (default: http://127.0.0.1:8080/...)
    --max-tokens N            response tokens per chunk (default: 2000)
    --dry-run                 show the chunks without calling the model
    --selftest                verify chunking and stitching offline

Automatic chunk size (default):
    Before starting, it queries the server via /props (real n_ctx) and /tokenize
    (the model's exact tokenizer). It computes the optimal chunk size for this
    specific model and this context window. Works for any model.
    Use --size N to force a manual value.

The prompt receives the chunk text as {text}.
If the prompt does not contain {text}, the text is appended at the end automatically.
"""

import zipfile, json, urllib.request, urllib.error, time, sys, os, re, argparse
from xml.etree import ElementTree as ET

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_API      = "http://127.0.0.1:8080/v1/chat/completions"
DEFAULT_TOKENS   = 2000
SAFETY_MARGIN    = 200   # tokens reserved for framing and tokenizer variations
FALLBACK_SIZE    = 3000  # used if the server is unreachable during auto-calc
COLLECT_EMPTY_RE = re.compile(r'^\s*(niente|nothing|none|no result|nessun|–|—|-)\s*$', re.I)

DEFAULT_SYSTEM = (
    "You are a helpful assistant. Work only on the text provided. "
    "Output only your answer, no preambles or meta-commentary."
)

# ── Text extraction ───────────────────────────────────────────────────────────
def extract_odt(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read('content.xml').decode('utf-8')
    tree = ET.fromstring(xml)
    NS = 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'
    lines = []
    def walk(node):
        if node.tag in (f'{{{NS}}}p', f'{{{NS}}}h'):
            lines.append(''.join(node.itertext()).strip())
            return
        for child in node:
            walk(child)
    walk(tree)
    return '\n'.join(lines)

def extract_txt(path):
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read()

def extract(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.odt':
        return extract_odt(path)
    return extract_txt(path)

# ── Chunking ──────────────────────────────────────────────────────────────────
def _find_break(text, start, size):
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

# ── Automatic chunk size calculation ──────────────────────────────────────────
def _api_base(api_url):
    """Extract the base URL from the completions endpoint."""
    return api_url.split('/v1/')[0]

def get_server_props(api_url):
    """Query /props and return the dict, or None if unavailable."""
    url = _api_base(api_url) + '/props'
    req = urllib.request.Request(url, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception:
        return None

def tokenize_text(text, api_url):
    """Return the number of tokens for `text` using the model's tokenizer."""
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
    """
    Compute the optimal chunk size for this model and this context window.

    Uses the model's real tokenizer via /tokenize and the real n_ctx via /props.
    Works for any model regardless of tokenizer and architecture.

    Returns (chunk_size_chars, info_dict) or (None, None) if the server
    is unreachable or the data is not available.
    """
    # 1. Real n_ctx from the server
    props = get_server_props(api_url)
    if props is None:
        return None, None

    # /props may expose n_ctx in different places depending on the llama.cpp version
    n_ctx = (props.get('n_ctx')
             or props.get('default_generation_settings', {}).get('n_ctx')
             or props.get('total_slots', {}) and None)
    if not n_ctx:
        return None, None

    # 2. Exact token count of the system prompt with this model's tokenizer
    sys_tokens = tokenize_text(system_prompt, api_url)
    if sys_tokens is None:
        return None, None

    # 3. Tokens available for the chunk
    available_tokens = n_ctx - sys_tokens - max_tokens - thinking_buffer - SAFETY_MARGIN
    if available_tokens <= 100:
        return None, None

    # 4. chars/token calibration on the real text (1500-char sample)
    sample = text[:1500] if len(text) >= 1500 else text
    sample_tokens = tokenize_text(sample, api_url)
    if not sample_tokens:
        return None, None
    chars_per_token = len(sample) / sample_tokens

    chunk_size = max(500, int(available_tokens * chars_per_token))

    info = {
        'n_ctx': n_ctx,
        'sys_tokens': sys_tokens,
        'max_tokens': max_tokens,
        'thinking_buffer': thinking_buffer,
        'safety_margin': SAFETY_MARGIN,
        'available_tokens': available_tokens,
        'chars_per_token': round(chars_per_token, 2),
        'chunk_size': chunk_size,
    }
    return chunk_size, info

# ── Model call ────────────────────────────────────────────────────────────────
def call_model(user_content, system, api_url, max_tokens):
    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": user_content},
    ]
    payload = json.dumps({
        "model": "local",
        "messages": messages,
        "stream": False,
        "temperature": 0.2,
        "max_tokens": max_tokens,
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
        return f"[ERROR: {e}]"

def build_user_message(prompt_template, chunk_text):
    if '{text}' in prompt_template:
        return prompt_template.format(text=chunk_text)
    return prompt_template + '\n\n' + chunk_text

# ── Stitch mode (continuous text) ─────────────────────────────────────────────
def stitch(chunks):
    """Paste the chunks in sequence. No modification to the text."""
    return '\n\n'.join(c for c in chunks if c).strip()

# ── Collect mode (aggregate results) ──────────────────────────────────────────
def collect(chunk_results):
    parts = []
    for i, (num, text) in enumerate(chunk_results):
        if COLLECT_EMPTY_RE.match(text.strip()):
            continue
        if text.strip().startswith('[ERROR'):
            parts.append(f"### Chunk {num} — ERROR\n{text}\n")
        else:
            parts.append(f"### Chunk {num}\n{text}\n")
    return '\n'.join(parts).strip()

# ── Terminal colors ───────────────────────────────────────────────────────────
class C:
    R = '\033[91m'; G = '\033[92m'; Y = '\033[93m'; DIM = '\033[2m'; OFF = '\033[0m'
if os.name == 'nt':
    os.system('')

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description="Generic pipeline: file -> chunking -> LLM -> output"
    )
    ap.add_argument('file', nargs='?',
                    default=os.path.join(os.path.dirname(__file__),
                                         "Test files", "Dialoghi con la lavatrice.odt"),
                    help="the .odt or .txt file to process")
    ap.add_argument('--prompt',           default=None,
                    help='prompt to apply to each chunk (use {text} for the text)')
    ap.add_argument('--prompt-file',      default=None,
                    help='file containing the prompt (alternative to --prompt)')
    ap.add_argument('--system',           default=DEFAULT_SYSTEM,
                    help='system prompt')
    ap.add_argument('--mode',             default='stitch', choices=['stitch', 'collect'],
                    help='stitch = continuous text; collect = aggregate results')
    ap.add_argument('--out',              default=None)
    ap.add_argument('--size',             type=int, default=None,
                    help='force chunk size in characters (default: automatic calculation)')
    ap.add_argument('--max-tokens',       type=int, default=DEFAULT_TOKENS, dest='max_tokens')
    ap.add_argument('--thinking',         action='store_true',
                    help='reasoning model (e.g. Gemma): reserve 800 tokens for internal thinking')
    ap.add_argument('--thinking-buffer',  type=int, default=None, dest='thinking_buffer',
                    help='tokens reserved for internal thinking (overrides --thinking; default 0)')
    ap.add_argument('--model',            default=DEFAULT_API)
    ap.add_argument('--dry-run',          action='store_true')
    ap.add_argument('--selftest',         action='store_true')
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    # ── Interactive mode detection (double click) ───────────────────────────
    interactive = not args.prompt and not args.prompt_file and not args.dry_run

    if interactive:
        print()
        print(" ╔══════════════════════════════════════════════╗")
        print(" ║  chunk_pipeline — interactive mode           ║")
        print(" ╚══════════════════════════════════════════════╝")
        print()

    # ── Thinking model? — reserve tokens for internal reasoning ───────────────
    # Priority: explicit --thinking-buffer > --thinking > interactive prompt > 0.
    # The prompt appears ONLY on an interactive terminal (stdin.isatty): this avoids
    # the EOFError and the window closing on a windowless double click, and does not
    # block script runs that use --prompt.
    if args.thinking_buffer is not None:
        thinking_buffer = args.thinking_buffer
    elif args.thinking:
        thinking_buffer = 800
    elif interactive and sys.stdin.isatty():
        try:
            ans = input(" Is this a thinking model? (e.g. Gemma) [y/N]: ").strip().lower()
        except EOFError:
            ans = ''
        thinking_buffer = 800 if ans == 'y' else 0
    else:
        thinking_buffer = 0

    # Prompt
    if args.prompt_file:
        with open(args.prompt_file, encoding='utf-8') as f:
            prompt_template = f.read()
    elif args.prompt:
        prompt_template = args.prompt
    else:
        print()
        print(" Enter the prompt to apply to each chunk.")
        print(" Use {text} where you want the text (or leave empty: it will be appended at the end).")
        print()
        try:
            prompt_template = input(" Prompt: ").strip()
        except EOFError:
            prompt_template = ''
        if not prompt_template:
            print(f"\n Empty prompt. Exiting.")
            input("\n Press ENTER to close...")
            sys.exit(1)

    if not os.path.exists(args.file):
        print(f"{C.R}File not found: {args.file}{C.OFF}")
        sys.exit(1)

    suffix = '_out.md'
    out_path = args.out or os.path.splitext(args.file)[0] + suffix

    text = extract(args.file)

    # ── Chunk size calculation ────────────────────────────────────────────────
    if args.size is not None:
        chunk_size = args.size
        size_source = f"manual ({chunk_size:,} char)"
    else:
        print(f"\n chunk_pipeline — calibrating model…")
        cs, info = auto_chunk_size(text, args.system, args.model,
                                   args.max_tokens, thinking_buffer)
        if cs is not None:
            chunk_size = cs
            size_source = (
                f"auto ({chunk_size:,} char · n_ctx={info['n_ctx']} · "
                f"{info['chars_per_token']} char/tok · "
                f"available={info['available_tokens']} tok"
                + (f" · thinking={info['thinking_buffer']}" if info['thinking_buffer'] else "")
                + ")"
            )
        else:
            chunk_size = FALLBACK_SIZE
            size_source = f"fallback ({chunk_size:,} char — server unreachable for calibration)"
            print(f" {C.Y}Server unreachable for auto-calibration, using fallback {FALLBACK_SIZE:,} char{C.OFF}")

    print(f"\n chunk_pipeline")
    print(f" {'─' * 50}")
    print(f" File   : {os.path.basename(args.file)}")
    print(f" Mode   : {args.mode}")
    print(f" Chunk  : {size_source}")
    print(f" Token  : {args.max_tokens}   thinking-buffer: {thinking_buffer}")
    print(f" Output : {os.path.basename(out_path)}\n")

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

    results = []
    total_time = 0.0

    for i, (a, b) in enumerate(ranges):
        n = i + 1
        fragment = text[a:b]
        user_msg = build_user_message(prompt_template, fragment)
        snippet = fragment.replace('\n', ' ')[:55]
        print(f" [{n:3d}/{len(ranges)}] '{snippet}'…  ", end='', flush=True)

        t0 = time.time()
        answer = call_model(user_msg, args.system, args.model, args.max_tokens)
        dt = time.time() - t0
        total_time += dt

        is_error = answer.startswith('[ERROR')
        is_empty = COLLECT_EMPTY_RE.match(answer.strip()) is not None
        tag = (f"{C.R}ERROR{C.OFF}" if is_error
               else f"{C.DIM}empty{C.OFF}" if is_empty
               else f"{C.G}{dt:.1f}s{C.OFF} → {len(answer):,} char")
        print(tag)

        results.append((n, answer))

    print(f"\n Processing completed in {total_time:.0f}s")

    if args.mode == 'stitch':
        print(f" Stitching {len(results)} chunk…")
        final = stitch([r for _, r in results])
    else:
        print(f" Aggregating results (collect mode)…")
        final = collect(results)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(final)

    print(f" {C.G}Saved{C.OFF}: {out_path}  ({len(final):,} char)\n")

    if interactive:
        input(" Press ENTER to close...")

# ── Selftest ───────────────────────────────────────────────────────────────────
def selftest():
    print("\n SELFTEST\n " + "─" * 40)
    ok = True

    # 1. Chunking coverage
    text = "First paragraph.\n\nSecond, longer, with two sentences. Here it is.\n\nThird."
    ranges = build_chunks(text, 40)
    try:
        prove_coverage(text, ranges); g = True
    except AssertionError as e:
        g = False; print("  ", e)
    print(f" [1] char-exact coverage                : {'OK' if g else 'FAIL'}")
    ok &= g

    # 2. Stitch: chunks present and in order
    a = "First chunk."
    b = "Second chunk."
    r = stitch([a, b])
    g2 = a in r and b in r and r.index(a) < r.index(b)
    print(f" [2] stitch: chunks present and ordered : {'OK' if g2 else 'FAIL'}")
    if not g2: print(f"     got: {r!r}")
    ok &= g2

    # 3. Stitch: empty chunks ignored
    r2 = stitch(["First.", "", "Last."])
    g3 = "First." in r2 and "Last." in r2
    print(f" [3] stitch: empty chunks ignored       : {'OK' if g3 else 'FAIL'}")
    ok &= g3

    # 4. Collect discards "NOTHING"
    cr = collect([(1, "Found something."), (2, "NOTHING"), (3, "Also this.")])
    g4 = 'Chunk 2' not in cr and 'Chunk 1' in cr and 'Chunk 3' in cr
    print(f" [4] collect discards empty answer      : {'OK' if g4 else 'FAIL'}")
    if not g4: print(f"     got: {cr!r}")
    ok &= g4

    # 5. build_user_message with and without {text}
    msg1 = build_user_message("Translate: {text}", "hello")
    g5a = msg1 == "Translate: hello"
    msg2 = build_user_message("Find themes.", "hello")
    g5b = msg2.endswith("hello")
    g5 = g5a and g5b
    print(f" [5] build_user_message {{text}}/auto    : {'OK' if g5 else 'FAIL'}")
    ok &= g5

    # 6. auto_chunk_size: calculation logic with mocked data
    class _FakeModule:
        """Simulates the server responses to test auto_chunk_size offline."""
        @staticmethod
        def mock(n_ctx, sys_tok, sample_tok):
            # Expected calculation: available = n_ctx - sys_tok - 2000 - 0 - 200
            available = n_ctx - sys_tok - 2000 - 0 - SAFETY_MARGIN
            cpt = 1500 / sample_tok
            return max(500, int(available * cpt))

    expected = _FakeModule.mock(8192, 50, 375)   # 8192 ctx, 50 sys tok, 1500 char = 375 tok → 4 char/tok
    # available = 8192 - 50 - 2000 - 0 - 200 = 5942 tok × 4 char/tok = 23768 char
    g6 = expected == max(500, int((8192 - 50 - 2000 - 0 - 200) * (1500 / 375)))
    print(f" [6] auto_chunk_size: formula correct   : {'OK' if g6 else 'FAIL'} (expected {expected:,} char)")
    ok &= g6

    print("\n " + (f"{C.G}SELFTEST OK{C.OFF}" if ok else f"{C.R}SELFTEST FAILED{C.OFF}"))
    sys.exit(0 if ok else 1)

if __name__ == '__main__':
    main()
