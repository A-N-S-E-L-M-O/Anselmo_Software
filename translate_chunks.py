"""
translate_chunks.py — pipeline ODT -> chunking -> traduzione -> stitching

Tre responsabilità, ognuna isolata:
  1. CHUNKING  : taglia al confine di paragrafo/frase; garanzia di copertura completa.
  2. TRADUZIONE: manda ogni chunk al modello con un prompt pulito (zero CONTESTO).
  3. STITCHING : incolla gli output in sequenza con doppio newline. Nessuna modifica al testo.
                 Il postprocessing si fa sul file di output, non qui.

Uso:
    python translate_chunks.py [percorso.odt] [--selftest] [--dry-run]

    --selftest  verifica chunking senza chiamare il modello
    --dry-run   mostra i chunk senza tradurre
    --out FILE  file di output (default: <nome_odt>_EN.md)
    --size N    caratteri per chunk (default: 3000)
    --model URL url del server llama.cpp (default: http://127.0.0.1:8080/v1/chat/completions)
"""

import zipfile, json, urllib.request, urllib.error, time, sys, os, re, argparse
from xml.etree import ElementTree as ET

# ── Config default ────────────────────────────────────────────────────────────
DEFAULT_API    = "http://127.0.0.1:8080/v1/chat/completions"
DEFAULT_SIZE   = 3000   # caratteri per chunk; lascia ampio spazio in ctx 16k
MAX_TOKENS     = 2000

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

# ── Estrazione ODT ────────────────────────────────────────────────────────────
def extract_odt(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read('content.xml').decode('utf-8')
    tree = ET.fromstring(xml)
    NS = 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'
    lines = []
    def walk(node):
        if node.tag in (f'{{{NS}}}p', f'{{{NS}}}h'):
            t = ''.join(node.itertext()).strip()
            lines.append(t)   # mantieni anche le righe vuote: sono paragrafi separatori
            return
        for child in node:
            walk(child)
    walk(tree)
    return '\n'.join(lines)

# ── Chunking ──────────────────────────────────────────────────────────────────
def _find_break(text, start, size):
    """Punto di taglio: preferisce confine di paragrafo, poi frase, poi spazio."""
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
    """Restituisce lista di (start, end) contigui e non sovrapposti."""
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

# ── Traduzione ────────────────────────────────────────────────────────────────
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

# ── Stitching ─────────────────────────────────────────────────────────────────
def stitch(translated_chunks):
    """Incolla i chunk tradotti in sequenza. Nessuna modifica al testo."""
    return '\n\n'.join(c for c in translated_chunks if c).strip()

# ── Colori terminale ──────────────────────────────────────────────────────────
class C:
    R = '\033[91m'; G = '\033[92m'; Y = '\033[93m'; DIM = '\033[2m'; OFF = '\033[0m'
if os.name == 'nt':
    os.system('')

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Traduce un ODT in inglese via llama.cpp")
    ap.add_argument('odt', nargs='?',
                    default=os.path.join(os.path.dirname(__file__),
                                         "Test files", "Dialoghi con la lavatrice.odt"))
    ap.add_argument('--selftest',  action='store_true')
    ap.add_argument('--dry-run',   action='store_true')
    ap.add_argument('--out',       default=None)
    ap.add_argument('--size', type=int, default=DEFAULT_SIZE)
    ap.add_argument('--model',     default=DEFAULT_API)
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return

    if not os.path.exists(args.odt):
        print(f"{C.R}File non trovato: {args.odt}{C.OFF}")
        sys.exit(1)

    out_path = args.out or os.path.splitext(args.odt)[0] + '_EN.md'

    print(f"\n Selmo — traduzione chunked")
    print(f" {'─' * 50}")
    print(f" Sorgente : {os.path.basename(args.odt)}")
    print(f" Output   : {os.path.basename(out_path)}")
    print(f" Chunk    : {args.size:,} char\n")

    text = extract_odt(args.odt)
    print(f" Estratti {len(text):,} caratteri")

    ranges = build_chunks(text, args.size)
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

    print(f"\n {C.G}Traduzione completata{C.OFF} in {total_time:.0f}s totali")
    print(f" Stitching {len(translated)} chunk…")

    final = stitch(translated)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(final)

    print(f" {C.G}Salvato{C.OFF}: {out_path}  ({len(final):,} char)\n")

# ── Selftest ───────────────────────────────────────────────────────────────────
def selftest():
    print("\n SELFTEST\n " + "─" * 40)
    ok = True

    # Chunking: copertura char-esatta
    text = "Primo paragrafo.\n\nSecondo paragrafo più lungo, con due frasi. Eccola.\n\nTerzo."
    ranges = build_chunks(text, 40)
    try:
        prove_coverage(text, ranges); g = True
    except AssertionError as e:
        g = False; print("  ", e)
    print(f" [1] copertura char-esatta         : {'OK' if g else 'FAIL'}")
    ok &= g

    # Stitch: tutti i chunk presenti, in ordine, senza perdite
    chunk_a = "She walked into the room."
    chunk_b = "Nobody moved at all."
    result = stitch([chunk_a, chunk_b])
    g2 = chunk_a in result and chunk_b in result and result.index(chunk_a) < result.index(chunk_b)
    print(f" [2] stitch: chunk presenti e in ordine: {'OK' if g2 else 'FAIL'}")
    if not g2:
        print(f"     got: {result!r}")
    ok &= g2

    # Stitch: chunk vuoti ignorati
    result2 = stitch(["First.", "", "Last."])
    g3 = "First." in result2 and "Last." in result2
    print(f" [3] stitch: chunk vuoti ignorati  : {'OK' if g3 else 'FAIL'}")
    ok &= g3

    print("\n " + (f"{C.G}SELFTEST OK{C.OFF}" if ok else f"{C.R}SELFTEST FALLITO{C.OFF}"))
    sys.exit(0 if ok else 1)

if __name__ == '__main__':
    main()
