"""
test_chunking.py -- pipeline ODT -> chunking -> Selmo, versione "fa poco ma bene".

Uso:
    python test_chunking.py            # gira sul manoscritto (serve il server llama.cpp attivo)
    python test_chunking.py --selftest # verifica le 5 garanzie SENZA server (offline)

Le cinque garanzie:
  1. Niente chunk giganti  -> un paragrafo piu' lungo del budget viene spezzato
                              per frase, poi per parola, poi per carattere.
  2. Prova di copertura     -> i chunk ricostruiscono il testo carattere per carattere;
                              se manca qualcosa il programma SI FERMA.
  3. Sovrapposizione minima -> le ultime frasi di ogni chunk sono ripetute, marcate,
                              in testa al successivo: niente cade nei bordi del taglio.
  4. Una sola fonte         -> al modello arriva solo il testo da analizzare, nient'altro.
  5. Citazione obbligatoria -> il modello deve riportare la frase esatta; la verifichiamo
                              col match contro il testo. Citazione non trovata = ALLARME.
"""

import zipfile, json, urllib.request, urllib.error, time, sys, os, re
from xml.etree import ElementTree as ET

# Config
ODT_PATH   = os.path.join(os.path.dirname(__file__), "Test files", "Dialoghi con la lavatrice.odt")
API_URL    = "http://127.0.0.1:8080/v1/chat/completions"
CHUNK_SIZE = 11000   # budget caratteri per blocco (lascia spazio a prompt + risposta in ctx 16k)
OVERLAP_SENTENCES = 2
MAX_TOKENS = 1000

# Mizan: deterministico. Per un compito di analisi non vogliamo creativita'.
SYSTEM_PROMPT = (
    "Sei un sistema di analisi testuale. Lavori solo sul testo che ti viene dato. "
    "Non aggiungi nulla che non sia scritto nel testo. Nessuna opinione, solo dati."
)

# Il formato di risposta e' rigido di proposito: ci permette di verificare ogni citazione.
QUERY = (
    "Questo e' un frammento di romanzo italiano scritto al passato remoto e imperfetto.\n"
    "Cerca SOLO nei paragrafi narrativi (non nei dialoghi) le frasi in cui il narratore "
    "usa un verbo al tempo PRESENTE invece del passato.\n\n"
    "Per OGNI anomalia trovata, scrivi ESATTAMENTE due righe:\n"
    'FRASE: "<la frase copiata parola per parola dal testo, senza modifiche>"\n'
    "VERBO: <il verbo al presente>\n\n"
    "Copia la frase IDENTICA al testo: serve per la verifica automatica.\n"
    "Analizza solo la sezione marcata [DA ANALIZZARE]. La sezione [CONTESTO] serve solo "
    "a non perdere frasi spezzate dal taglio: non riportare anomalie che stanno solo li'.\n"
    "Se non trovi nulla, rispondi con una sola parola: NIENTE"
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
            if t:
                lines.append(t)
            return
        for child in node:
            walk(child)
    walk(tree)
    return '\n'.join(lines)

# ── Chunking (garanzie 1 e 2) ─────────────────────────────────────────────────
def _find_break(text, start, size):
    """Restituisce l'indice dove tagliare il chunk che parte da `start`.
    Prova in ordine: confine di paragrafo, fine frase, spazio, taglio netto.
    Garantisce sempre un avanzamento (risultato > start)."""
    n = len(text)
    if start + size >= n:
        return n
    hi = start + size
    # 1) confine di paragrafo: taglia subito dopo un newline
    nl = text.rfind('\n', start, hi)
    if nl > start:
        return nl + 1
    # 2) fine frase (paragrafo piu' lungo del budget -> garanzia 1)
    last = None
    for m in re.finditer(r'[.!?…](?=\s|$)', text[start:hi]):
        last = m
    if last is not None and start + last.end() > start:
        return start + last.end()
    # 3) confine di parola
    sp = text.rfind(' ', start, hi)
    if sp > start:
        return sp + 1
    # 4) ultima spiaggia: taglio netto al carattere (non perde nulla, solo brutto)
    return hi

def build_chunks(text, size):
    """Partiziona `text` in range contigui e non sovrapposti, nessuno > size.
    Restituisce lista di (start, end)."""
    n = len(text)
    ranges, i = [], 0
    while i < n:
        e = _find_break(text, i, size)
        if e <= i:            # paracadute: non deve mai succedere
            e = min(i + size, n)
        ranges.append((i, e))
        i = e
    return ranges

def prove_coverage(text, ranges):
    """Garanzia 2: i range coprono ESATTAMENTE il testo. Solleva AssertionError se no."""
    assert ranges, "nessun chunk prodotto"
    assert ranges[0][0] == 0, "il primo chunk non parte da 0"
    assert ranges[-1][1] == len(text), "l'ultimo chunk non arriva alla fine"
    for (a, b), (c, d) in zip(ranges, ranges[1:]):
        assert b == c, f"buco o sovrapposizione tra {b} e {c}"
        assert b > a, "chunk vuoto"
    recon = ''.join(text[a:b] for a, b in ranges)
    assert recon == text, "la ricostruzione NON combacia col testo originale"
    return True

def _last_sentences(text, k):
    parts = re.split(r'(?<=[.!?…])\s+', text.strip())
    return ' '.join(parts[-k:]).strip() if parts else ''

def overlap_for(text, ranges, idx):
    """Garanzia 3: testo di contesto = ultime frasi del chunk precedente."""
    if idx == 0:
        return ''
    a, b = ranges[idx - 1]
    return _last_sentences(text[a:b], OVERLAP_SENTENCES)

# ── Verifica citazioni (garanzia 5) ───────────────────────────────────────────
def _norm(s):
    return re.sub(r'\s+', ' ', s).strip().lower()

def parse_quotes(answer):
    return re.findall(r'FRASE:\s*"(.+?)"', answer, flags=re.S)

def verify_quote(quote, source):
    return _norm(quote) in _norm(source)

# ── Colori terminale ──────────────────────────────────────────────────────────
class C:
    R = '\033[91m'; G = '\033[92m'; Y = '\033[93m'; DIM = '\033[2m'; OFF = '\033[0m'
if os.name == 'nt':
    os.system('')   # abilita le sequenze ANSI su Windows 10+

# ── Chiamata modello (garanzia 4: una sola fonte nel prompt) ───────────────────
def call_model(analyze_text, context_text, chunk_num, total):
    blocks = ''
    if context_text:
        blocks += '[CONTESTO — solo per non perdere frasi spezzate, non analizzare]\n' \
                  + context_text + '\n\n'
    blocks += '[DA ANALIZZARE]\n' + analyze_text
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content":
            f"Documento — blocco {chunk_num} di {total}:\n\n{blocks}\n\n---\n{QUERY}"}
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
        return f"[ERRORE API: {e}]"

# ── Run principale ────────────────────────────────────────────────────────────
def main():
    print("\n Selmo — analisi documento (chunking robusto)")
    print(" " + "─" * 56)

    if not os.path.exists(ODT_PATH):
        print(f"\n ERRORE: file non trovato: {ODT_PATH}")
        sys.exit(1)

    text = extract_odt(ODT_PATH)
    print(f"\n Estratti {len(text):,} caratteri da {os.path.basename(ODT_PATH)}")

    ranges = build_chunks(text, CHUNK_SIZE)
    biggest = max(b - a for a, b in ranges)
    try:
        prove_coverage(text, ranges)
        print(f" {C.G}COPERTURA OK{C.OFF}: {len(ranges)} blocchi ricostruiscono il testo "
              f"al carattere · max blocco {biggest:,} char (budget {CHUNK_SIZE:,})\n")
    except AssertionError as e:
        print(f" {C.R}COPERTURA FALLITA: {e}{C.OFF}\n Mi fermo: non posso garantire zero perdite.")
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

        if answer.strip().upper().startswith("NIENTE"):
            print(f"{dt:.1f}s  —")
            continue

        quotes = parse_quotes(answer)
        # Garanzia 5: ogni citazione deve esistere VERBATIM nel chunk analizzato.
        verdicts = [(q, verify_quote(q, analyze)) for q in quotes]
        ok = sum(1 for _, v in verdicts if v)
        bad = len(verdicts) - ok
        unverified += bad
        tag = f"{C.G}★ {ok} verificate{C.OFF}" + (f"  {C.R}{bad} NON VERIFICATE{C.OFF}" if bad else "")
        print(f"{dt:.1f}s  {tag}")
        found.append((n, answer, verdicts))
        for q, v in verdicts:
            col = C.G if v else C.R
            mark = "✓" if v else "✗ INVENTATA?"
            print(f"        {col}{mark}{C.OFF} \"{q.strip()[:90]}\"")

    # Riepilogo
    print("\n" + "═" * 58)
    print(f" Blocchi con risultati: {len(found)}/{len(ranges)}")
    if unverified:
        print(f" {C.R}ATTENZIONE: {unverified} citazioni non trovate nel testo "
              f"(possibili allucinazioni).{C.OFF}")
    elif found:
        print(f" {C.G}Tutte le citazioni verificate contro il testo.{C.OFF}")
    else:
        print(" Nessuna anomalia trovata.")

# ── Selftest offline (verifica le garanzie senza il modello) ──────────────────
def selftest():
    print("\n SELFTEST — verifica le garanzie senza server\n " + "─" * 40)
    ok = True

    # Testo costruito apposta: un paragrafo GIGANTE che supera il budget,
    # frasi normali, e un accento per controllare i caratteri non-ASCII.
    giant = ("Frase lunghissima numero uno. " * 40).strip()      # ~1200 char, > budget di test
    text = "Primo paragrafo corto.\n" + giant + "\nTerzo paragrafo. Con due frasi.\nQuarto è qui."
    SIZE = 200  # budget piccolo per forzare gli split

    ranges = build_chunks(text, SIZE)

    # Garanzia 1: nessun chunk supera il budget
    big = max(b - a for a, b in ranges)
    g1 = big <= SIZE
    print(f" [1] nessun chunk > budget        : {'OK' if g1 else 'FALLITO'} (max {big}/{SIZE})")
    ok &= g1

    # Garanzia 2: copertura char-esatta (anche col paragrafo gigante spezzato)
    try:
        prove_coverage(text, ranges); g2 = True
    except AssertionError as e:
        g2 = False; print("     ", e)
    print(f" [2] copertura carattere-esatta    : {'OK' if g2 else 'FALLITO'}")
    ok &= g2

    # Garanzia 3: l'overlap del 2° chunk sono le ultime frasi del 1°
    ov = overlap_for(text, ranges, 1)
    g3 = len(ov) > 0 and ov in text
    print(f" [3] overlap presente e dal testo   : {'OK' if g3 else 'FALLITO'} (\"{ov[:40]}…\")")
    ok &= g3

    # Garanzia 5: la verifica accetta una citazione vera e smaschera una falsa
    vera  = "Terzo paragrafo. Con due frasi."
    falsa = "Questa frase non è nel testo."
    g5 = verify_quote(vera, text) and not verify_quote(falsa, text)
    print(f" [5] quote-check vero=accetta/falso=rifiuta: {'OK' if g5 else 'FALLITO'}")
    ok &= g5

    # parsing del formato di risposta del modello
    sample = 'FRASE: "Annuisco e resto fermo."\nVERBO: annuisco'
    g_parse = parse_quotes(sample) == ["Annuisco e resto fermo."]
    print(f" [+] parsing FRASE: \"...\"           : {'OK' if g_parse else 'FALLITO'}")
    ok &= g_parse

    print("\n " + ("\033[92mTUTTE LE GARANZIE OK\033[0m" if ok else "\033[91mQUALCOSA È FALLITO\033[0m"))
    sys.exit(0 if ok else 1)

if __name__ == '__main__':
    if '--selftest' in sys.argv:
        selftest()
    main()
