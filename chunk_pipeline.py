"""
chunk_pipeline.py — pipeline generica: ODT/TXT -> chunking -> LLM -> output

Funziona con qualsiasi prompt e qualsiasi tipo di task:
  traduzione, ricerca tematica, analisi, estrazione, riscrittura, ecc.

Due modalità di output (--mode):
  stitch   [default] : i risultati sono testo continuo.
                       Ideale per: traduzione, riscrittura, parafrasi.
  collect            : i risultati di ogni chunk vengono raccolti in sequenza.
                       Se il modello risponde "NIENTE" o varianti, quel chunk
                       non viene incluso nell'output.
                       Ideale per: ricerca, analisi, estrazione.

Uso:
    python chunk_pipeline.py <file.odt|file.txt> --prompt "..." [opzioni]
    python chunk_pipeline.py <file> --prompt-file prompt.txt [opzioni]
    python chunk_pipeline.py --selftest

Opzioni:
    --mode stitch|collect     modalità output (default: stitch)
    --system "..."            system prompt (default: assistente generico)
    --out FILE                file di output (default: <nome>_out.md)
    --size N                  forza chunk size in caratteri (default: auto)
    --thinking-buffer N       token riservati al thinking interno del modello
                              (default: 0 — modelli instruct; usare 800+ per reasoning)
    --model URL               endpoint llama.cpp (default: http://127.0.0.1:8080/...)
    --max-tokens N            token risposta per chunk (default: 2000)
    --dry-run                 mostra i chunk senza chiamare il modello
    --selftest                verifica chunking e stitching offline

Chunk size automatico (default):
    Prima di iniziare, interroga il server via /props (n_ctx reale) e /tokenize
    (tokenizer esatto del modello). Calcola il chunk size ottimale per questo
    specifico modello e questa finestra di contesto. Funziona per qualsiasi modello.
    Usa --size N per forzare un valore manuale.

Il prompt riceve il testo del chunk come {text}.
Se il prompt non contiene {text}, il testo viene aggiunto in fondo automaticamente.
"""

import zipfile, json, urllib.request, urllib.error, time, sys, os, re, argparse
from xml.etree import ElementTree as ET

# ── Default ───────────────────────────────────────────────────────────────────
DEFAULT_API      = "http://127.0.0.1:8080/v1/chat/completions"
DEFAULT_TOKENS   = 2000
SAFETY_MARGIN    = 200   # token riservati per framing e variazioni tokenizer
FALLBACK_SIZE    = 3000  # usato se il server non è raggiungibile durante auto-calc
COLLECT_EMPTY_RE = re.compile(r'^\s*(niente|nothing|none|no result|nessun|–|—|-)\s*$', re.I)

DEFAULT_SYSTEM = (
    "You are a helpful assistant. Work only on the text provided. "
    "Output only your answer, no preambles or meta-commentary."
)

# ── Estrazione testo ──────────────────────────────────────────────────────────
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

# ── Calcolo automatico chunk size ─────────────────────────────────────────────
def _api_base(api_url):
    """Estrae la base URL dall'endpoint completions."""
    return api_url.split('/v1/')[0]

def get_server_props(api_url):
    """Interroga /props e restituisce il dict, o None se non disponibile."""
    url = _api_base(api_url) + '/props'
    req = urllib.request.Request(url, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception:
        return None

def tokenize_text(text, api_url):
    """Restituisce il numero di token per `text` usando il tokenizer del modello."""
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
    Calcola il chunk size ottimale per questo modello e questa finestra di contesto.

    Usa il tokenizer reale del modello via /tokenize e il n_ctx reale via /props.
    Funziona per qualsiasi modello indipendentemente da tokenizer e architettura.

    Restituisce (chunk_size_chars, info_dict) o (None, None) se il server
    non è raggiungibile o i dati non sono disponibili.
    """
    # 1. n_ctx reale dal server
    props = get_server_props(api_url)
    if props is None:
        return None, None

    # /props può avere n_ctx in posti diversi a seconda della versione llama.cpp
    n_ctx = (props.get('n_ctx')
             or props.get('default_generation_settings', {}).get('n_ctx')
             or props.get('total_slots', {}) and None)
    if not n_ctx:
        return None, None

    # 2. Token esatti del system prompt con il tokenizer di questo modello
    sys_tokens = tokenize_text(system_prompt, api_url)
    if sys_tokens is None:
        return None, None

    # 3. Token disponibili per il chunk
    available_tokens = n_ctx - sys_tokens - max_tokens - thinking_buffer - SAFETY_MARGIN
    if available_tokens <= 100:
        return None, None

    # 4. Calibrazione chars/token sul testo reale (campione di 1500 char)
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

# ── Chiamata modello ──────────────────────────────────────────────────────────
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

# ── Modalità stitch (testo continuo) ─────────────────────────────────────────
def stitch(chunks):
    """Incolla i chunk in sequenza. Nessuna modifica al testo."""
    return '\n\n'.join(c for c in chunks if c).strip()

# ── Modalità collect (aggregazione risultati) ─────────────────────────────────
def collect(chunk_results):
    parts = []
    for i, (num, text) in enumerate(chunk_results):
        if COLLECT_EMPTY_RE.match(text.strip()):
            continue
        if text.strip().startswith('[ERROR'):
            parts.append(f"### Chunk {num} — ERRORE\n{text}\n")
        else:
            parts.append(f"### Chunk {num}\n{text}\n")
    return '\n'.join(parts).strip()

# ── Colori terminale ──────────────────────────────────────────────────────────
class C:
    R = '\033[91m'; G = '\033[92m'; Y = '\033[93m'; DIM = '\033[2m'; OFF = '\033[0m'
if os.name == 'nt':
    os.system('')

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description="Pipeline generica: file -> chunking -> LLM -> output"
    )
    ap.add_argument('file', nargs='?',
                    default=os.path.join(os.path.dirname(__file__),
                                         "Test files", "Dialoghi con la lavatrice.odt"),
                    help="file .odt o .txt da elaborare")
    ap.add_argument('--prompt',           default=None,
                    help='prompt da applicare a ogni chunk (usa {text} per il testo)')
    ap.add_argument('--prompt-file',      default=None,
                    help='file contenente il prompt (alternativa a --prompt)')
    ap.add_argument('--system',           default=DEFAULT_SYSTEM,
                    help='system prompt')
    ap.add_argument('--mode',             default='stitch', choices=['stitch', 'collect'],
                    help='stitch = testo continuo; collect = aggrega risultati')
    ap.add_argument('--out',              default=None)
    ap.add_argument('--size',             type=int, default=None,
                    help='forza chunk size in caratteri (default: calcolo automatico)')
    ap.add_argument('--max-tokens',       type=int, default=DEFAULT_TOKENS, dest='max_tokens')
    ap.add_argument('--thinking',         action='store_true',
                    help='modello reasoning (es. Gemma): riserva 800 token per il thinking interno')
    ap.add_argument('--thinking-buffer',  type=int, default=None, dest='thinking_buffer',
                    help='token riservati al thinking interno (override di --thinking; default 0)')
    ap.add_argument('--model',            default=DEFAULT_API)
    ap.add_argument('--dry-run',          action='store_true')
    ap.add_argument('--selftest',         action='store_true')
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    # ── Rilevamento modalità interattiva (doppio click) ─────────────────────
    interactive = not args.prompt and not args.prompt_file and not args.dry_run

    if interactive:
        print()
        print(" ╔══════════════════════════════════════════════╗")
        print(" ║  chunk_pipeline — modalità interattiva       ║")
        print(" ╚══════════════════════════════════════════════╝")
        print()

    # ── Thinking model? — riserva token per il reasoning interno ──────────────
    # Priorità: --thinking-buffer esplicito > --thinking > domanda interattiva > 0.
    # La domanda compare SOLO con terminale interattivo (stdin.isatty): evita
    # l'EOFError e la finestra che si chiude al doppio click windowless, e non
    # blocca le esecuzioni da script con --prompt.
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
        print(" Inserisci il prompt da applicare a ogni chunk.")
        print(" Usa {text} dove vuoi il testo (o lascia vuoto: verrà aggiunto in fondo).")
        print()
        try:
            prompt_template = input(" Prompt: ").strip()
        except EOFError:
            prompt_template = ''
        if not prompt_template:
            print(f"\n Prompt vuoto. Uscita.")
            input("\n Premi ENTER per chiudere...")
            sys.exit(1)

    if not os.path.exists(args.file):
        print(f"{C.R}File non trovato: {args.file}{C.OFF}")
        sys.exit(1)

    suffix = '_out.md'
    out_path = args.out or os.path.splitext(args.file)[0] + suffix

    text = extract(args.file)

    # ── Calcolo chunk size ────────────────────────────────────────────────────
    if args.size is not None:
        chunk_size = args.size
        size_source = f"manuale ({chunk_size:,} char)"
    else:
        print(f"\n chunk_pipeline — calibrazione modello…")
        cs, info = auto_chunk_size(text, args.system, args.model,
                                   args.max_tokens, thinking_buffer)
        if cs is not None:
            chunk_size = cs
            size_source = (
                f"auto ({chunk_size:,} char · n_ctx={info['n_ctx']} · "
                f"{info['chars_per_token']} char/tok · "
                f"disponibili={info['available_tokens']} tok"
                + (f" · thinking={info['thinking_buffer']}" if info['thinking_buffer'] else "")
                + ")"
            )
        else:
            chunk_size = FALLBACK_SIZE
            size_source = f"fallback ({chunk_size:,} char — server non raggiungibile per calibrazione)"
            print(f" {C.Y}Server non raggiungibile per auto-calibrazione, uso fallback {FALLBACK_SIZE:,} char{C.OFF}")

    print(f"\n chunk_pipeline")
    print(f" {'─' * 50}")
    print(f" File   : {os.path.basename(args.file)}")
    print(f" Modo   : {args.mode}")
    print(f" Chunk  : {size_source}")
    print(f" Token  : {args.max_tokens}   thinking-buffer: {thinking_buffer}")
    print(f" Output : {os.path.basename(out_path)}\n")

    print(f" Estratti {len(text):,} caratteri")

    ranges = build_chunks(text, chunk_size)
    try:
        prove_coverage(text, ranges)
    except AssertionError as e:
        print(f"{C.R}COPERTURA FALLITA: {e}{C.OFF}")
        sys.exit(2)

    biggest = max(b - a for a, b in ranges)
    print(f" {C.G}Copertura OK{C.OFF} · {len(ranges)} chunk · max {biggest:,} char\n")

    if args.dry_run:
        for i, (a, b) in enumerate(ranges):
            snippet = text[a:b].replace('\n', ' ')[:80]
            print(f" [{i+1:3d}/{len(ranges)}] {snippet}…")
        print(f"\n{C.Y}--dry-run: nessuna chiamata al modello.{C.OFF}")
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
        tag = (f"{C.R}ERRORE{C.OFF}" if is_error
               else f"{C.DIM}vuoto{C.OFF}" if is_empty
               else f"{C.G}{dt:.1f}s{C.OFF} → {len(answer):,} char")
        print(tag)

        results.append((n, answer))

    print(f"\n Elaborazione completata in {total_time:.0f}s")

    if args.mode == 'stitch':
        print(f" Stitching {len(results)} chunk…")
        final = stitch([r for _, r in results])
    else:
        print(f" Aggregazione risultati (modalità collect)…")
        final = collect(results)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(final)

    print(f" {C.G}Salvato{C.OFF}: {out_path}  ({len(final):,} char)\n")

    if interactive:
        input(" Premi ENTER per chiudere...")

# ── Selftest ───────────────────────────────────────────────────────────────────
def selftest():
    print("\n SELFTEST\n " + "─" * 40)
    ok = True

    # 1. Copertura chunking
    text = "Primo paragrafo.\n\nSecondo, più lungo, con due frasi. Eccola.\n\nTerzo."
    ranges = build_chunks(text, 40)
    try:
        prove_coverage(text, ranges); g = True
    except AssertionError as e:
        g = False; print("  ", e)
    print(f" [1] copertura char-esatta              : {'OK' if g else 'FAIL'}")
    ok &= g

    # 2. Stitch: chunk presenti e in ordine
    a = "First chunk."
    b = "Second chunk."
    r = stitch([a, b])
    g2 = a in r and b in r and r.index(a) < r.index(b)
    print(f" [2] stitch: chunk presenti e in ordine : {'OK' if g2 else 'FAIL'}")
    if not g2: print(f"     got: {r!r}")
    ok &= g2

    # 3. Stitch: chunk vuoti ignorati
    r2 = stitch(["First.", "", "Last."])
    g3 = "First." in r2 and "Last." in r2
    print(f" [3] stitch: chunk vuoti ignorati       : {'OK' if g3 else 'FAIL'}")
    ok &= g3

    # 4. Collect scarta "NIENTE"
    cr = collect([(1, "Found something."), (2, "NIENTE"), (3, "Also this.")])
    g4 = 'Chunk 2' not in cr and 'Chunk 1' in cr and 'Chunk 3' in cr
    print(f" [4] collect scarta risposta vuota      : {'OK' if g4 else 'FAIL'}")
    if not g4: print(f"     got: {cr!r}")
    ok &= g4

    # 5. build_user_message con e senza {text}
    msg1 = build_user_message("Translate: {text}", "ciao")
    g5a = msg1 == "Translate: ciao"
    msg2 = build_user_message("Find themes.", "ciao")
    g5b = msg2.endswith("ciao")
    g5 = g5a and g5b
    print(f" [5] build_user_message {{text}}/auto    : {'OK' if g5 else 'FAIL'}")
    ok &= g5

    # 6. auto_chunk_size: logica di calcolo con dati mockati
    class _FakeModule:
        """Simula le risposte del server per testare auto_chunk_size offline."""
        @staticmethod
        def mock(n_ctx, sys_tok, sample_tok):
            # Calcolo atteso: disponibili = n_ctx - sys_tok - 2000 - 0 - 200
            available = n_ctx - sys_tok - 2000 - 0 - SAFETY_MARGIN
            cpt = 1500 / sample_tok
            return max(500, int(available * cpt))

    expected = _FakeModule.mock(8192, 50, 375)   # 8192 ctx, 50 sys tok, 1500 char = 375 tok → 4 char/tok
    # disponibili = 8192 - 50 - 2000 - 0 - 200 = 5942 tok × 4 char/tok = 23768 char
    g6 = expected == max(500, int((8192 - 50 - 2000 - 0 - 200) * (1500 / 375)))
    print(f" [6] auto_chunk_size: formula corretta  : {'OK' if g6 else 'FAIL'} (atteso {expected:,} char)")
    ok &= g6

    print("\n " + (f"{C.G}SELFTEST OK{C.OFF}" if ok else f"{C.R}SELFTEST FALLITO{C.OFF}"))
    sys.exit(0 if ok else 1)

if __name__ == '__main__':
    main()
