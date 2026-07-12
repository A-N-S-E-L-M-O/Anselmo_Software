# Selmo — Agent mode (file-access tool loop) plan
*Analysis + plan only. Nothing applied. July 2026. Successor to RAG (v0.932).*

## 1. Why this exists (the distinction that started it)

RAG does **not** give the model access to the folder — it is the opposite of
access. The indexer reads the tree once, turns it into vectors, and at query
time the model only ever sees the handful of chunks retrieval injects. It cannot
open a file, list a directory, or grep the tree, so "I can't access that" is
honest. **Agent mode gives it the keys**: instead of receiving snippets, the
model *asks* ("read selmo-core.js", "list the folder", "grep setOdo") and a
bridge executes each request against the real folder and hands the result back,
looping until the model has what it needs. This is how Cowork / Claude Code
work, and it is the "agent loop" flagged at the very start of the RAG arc.

RAG and agent are complementary, not rivals: RAG is best at *finding* the
relevant bit in a huge corpus; agent tools are best at *reading this exact file,
grepping the tree, and (later) editing*. The end state wants both — agent uses a
`rag_search` tool to find, then reads the file in full.

## 2. Fit with Selmo's architecture (verified)

- **Retrieval already owns the folder.** `selmo_rag.py` (port 8088) knows
  `corpus_dir`, the `exclude_dirs`, and the `formats`, and already walks/reads
  the tree. The file tools belong here as new endpoints — no new bridge needed.
- **The send loop already has the branch pattern.** `selmo-send.js` has the
  `if(isWebSearch||isRagSearch){...}` branch that rewrites → retrieves → injects
  → streams. Agent mode is a *loop* around the generation call instead of a
  single pass.
- **The LLM is llama.cpp on `/proxy/8089`.** Native tool calling is served with
  `--jinja` + tool definitions; Qwen3.6-35B-A3B is strong at it (~96% well-formed
  tool calls). Use the model's native tool protocol, NOT regex on the text (the
  `[SEARCH:]`/`QUERY:` fragility lesson).
- **Selmo philosophy: you always see what it's doing.** Every tool call is shown
  in the transcript ("📖 reading selmo-core.js", "📂 listing …", "🔎 grep setOdo")
  so the loop is never a black box. Bare-bones, transparent.

## 3. Bridge — file tools on `selmo_rag.py` (port 8088)

Read-only first. Every path is resolved against `corpus_dir` and **rejected if it
escapes the root** (`os.path.realpath` prefix check) — the single most important
guard. Honor `exclude_dirs`; skip `_SELF_PATHS`; cap read size.

- `GET /fs/list?dir=<relpath>` → `{entries:[{name,type,size}]}` (one level).
- `GET /fs/read?path=<relpath>[&start&end]` → `{path, text, truncated}` (whole
  file, or a line range; cap ~200 KB, report truncation).
- `GET /fs/grep?q=<regex>[&glob=]` → `[{path, line, text}]` (ripgrep if present,
  else a Python walk; cap N hits).
- Reuse `extract_any` so pdf/docx/odt are readable too, not just text.

Later (phase 3, opt-in): `POST /fs/write` / `/fs/patch` — gated behind an
explicit "allow writes" flag + a per-call confirmation in the UI. Never on by
default.

## 4. Client — the tool-calling loop (`selmo-send.js`)

An **AGENT** header toggle (twin of WEB/RAG, mutually exclusive with them). When
on, `sendMsg` runs a loop instead of one generation:

1. Build the OpenAI-style tool schemas (`read_file`, `list_dir`, `search_text`,
   and a `rag_search` that calls the existing `/search`). Send them with the
   chat request (`tools`, `tool_choice:auto`) to `/proxy/8089` with `--jinja`.
2. Stream the reply. If it ends in `tool_calls`, for each call: render a
   transparent line in the transcript, execute it via the matching `/fs/*` (or
   `/search`) endpoint, push a `role:"tool"` message with the result.
3. Loop back to (1) with the growing message list until the model answers with
   no tool calls — capped at `MAX_STEPS` (e.g. 8) and a wall-clock timeout, so a
   confused model can't spin forever.
4. Finalise like the normal path (markdown, download bar, session save).

Guards: cap tool-output size fed back (the 32k/150k window fills fast — paginate
big reads); a visible step counter; a STOP that aborts the loop.

## 5. Server / tray

- llama-server must run with **`--jinja`** and a model whose chat template
  declares tools (Qwen3 does). Add `--jinja` to the Qwen sections' `srv` flags in
  `selmo-models.ini` (the tray forwards `srv` verbatim). Verify with a one-shot
  `tools` request before wiring the UI.
- No new port: file tools live on 8088 (already proxied via `/proxy/8088`);
  generation stays on `/proxy/8089`.

## 6. Phasing

1. **Read-only agent.** `/fs/list|read|grep` (root-scoped) + the loop + AGENT
   toggle + transparent tool trace. This alone delivers "full read access": the
   model can open any file, list, and grep — no more "I can't".
2. **Find-then-read.** Add the `rag_search` tool so the agent uses retrieval to
   locate, then `read_file` to see the whole thing. RAG becomes a tool the agent
   calls, closing the loop between the two systems.
3. **Write/edit (careful).** `POST /fs/write|patch`, opt-in flag + per-edit
   confirmation in the UI, root-scoped, with a diff shown before applying. This
   is the step that turns Selmo into a real coding co-worker — do it last and
   guarded.

## 7. Risks & notes

- **Path escape is the whole ballgame** — realpath + root-prefix check on every
  `/fs/*` call, tested with `..`, symlinks, absolute paths, UNC.
- **Native tool calls, not regex** — parse llama.cpp's structured `tool_calls`;
  a plain retry without tools if the server rejects the field.
- **Loop safety** — MAX_STEPS + timeout + STOP; a per-turn budget so tool output
  can't blow the context.
- **Transparency is a feature, not a debug aid** — the tool trace stays in the
  final transcript so the user (and the exported log) always shows what Selmo
  read and searched.

## 8. Where to start next session

Phase 1, read-only, in this order: (a) `/fs/read` + `/fs/list` + `/fs/grep` on
`selmo_rag.py` with the root-scope guard, provable from `curl`; (b) add `--jinja`
to the Qwen `srv` flags and confirm a one-shot tool call works; (c) the AGENT
toggle + the loop in `selmo-send.js` with the transparent trace. That gives the
model real read access to the folder — the thing RAG deliberately withholds.
