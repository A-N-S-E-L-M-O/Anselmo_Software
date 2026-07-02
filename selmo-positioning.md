# Selmo — Positioning sheet
*One page. Strategy input, not a promise. July 2026.*

## The honest market reality

Local + private + open is **table stakes** in 2026, not a differentiator. Jan is
already open-source and privacy-first, GPT4All owns "simplest CPU start",
Open WebUI has passed 282M downloads, and LM Studio owns the polished model
browser (though it is proprietary freeware). Launching Selmo as "another ethical
local chat GUI" means disappearing into that crowd. The opportunity is a
**combination** none of them ship, aimed at an audience they don't serve.

## Who we actually compete with

- **LM Studio** — best-in-class GUI, but closed-source, developer/desktop, no
  energy view, US-based, no EU/GDPR framing.
- **Jan / GPT4All** — open and private, but generic chat; no energy, no phone
  access, no document-coverage pipeline, no family-portable story.
- **Open WebUI / LibreChat / AnythingLLM** — powerful, but self-host/server-shaped
  and dev-centric; RAG-style "chat with your PDF", not exhaustive documents.
- **Lumo (Proton) / Langdock** — the "EU/GDPR" names, but **cloud** hosted in
  Europe, not on-device. They do not compete with a truly local tool.

## What Selmo can say that they cannot

1. **Energy transparency (tokens/Wh).** No consumer GUI shows live watts and
   energy-per-token. It is an active research area right now, and Selmo already
   has the power monitor and the efficiency-log design. This is the sharpest,
   least-contested wedge, and it makes "ethical" concrete instead of a slogan.
2. **Genuinely local, GDPR-by-design, EU-flavoured.** On-device by default with
   European model choices (EuroLLM, Mistral, Pixtral) and an EU/Italian voice —
   a real gap, because the "EU AI" brands are cloud.
3. **Your phone talks to your own PC's model.** LAN access with a secure context
   over the front door. Almost every desktop GUI is desktop-only.
4. **Whole-document, provable-coverage pipeline.** Exhaustive translation and
   analysis of an entire file, not retrieve-a-snippet RAG.
5. **Unzip-and-click, family-grade.** A no-install portable bundle for
   non-developers — a different audience from the dev-first tools.

## The one-line positioning to test

> *Selmo — your AI, on your machine, in Europe: private, energy-honest, and
> reachable from your phone. No cloud, no account, no telemetry.*

Lead with **local + energy-honest + EU/GDPR + phone**, not with "private chat".

## Honest risks to hold in view

- **Solo maintainer** against community- and capital-backed projects. Long-term
  upkeep is risk number one.
- **"Ethical" only survives if verifiable** — a genuinely open licence, an explicit
  no-telemetry statement, and the energy numbers on screen. Otherwise it reads as
  marketing.
- **Windows-only** for now (the port is parked), which caps reach.
- **Engine is llama.cpp like everyone else** — the value is the product and the
  values, not the inference.

## Close these before saying "ethical / open" in public

- Confirm the `LICENSE` is genuinely open and state it plainly in the README.
- Add an explicit **"no telemetry, nothing leaves the machine"** claim a user can
  check (and keep it true — the security review already moved the bridges to
  loopback, which supports this).
- Surface the **energy figure in the UI** as a first-class element, not a hidden
  gauge — it is the headline differentiator.
- Decide the LAN-auth posture (security review SEC-3) before promoting phone
  access, so "private" holds on shared networks too.
- Pick the launch audience deliberately: privacy-minded EU users and non-dev
  families, not the Ollama/LM Studio developer crowd.
