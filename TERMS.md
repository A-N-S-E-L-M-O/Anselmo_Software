# A.N.S.E.L.M.O — Terms of Use

*Version 1.0 — July 2026 — applies to the official A.N.S.E.L.M.O distribution.*

**In short:** Selmo runs on your computer, under your control. The Author
operates no server, opens no account, and collects nothing — and the source
is available so you can verify that. The software is provided free of charge
and as-is, with no warranty. These Terms are governed by Italian law, with
the Court of Milan as the agreed venue.

---

## 1. Who provides A.N.S.E.L.M.O

**A.N.S.E.L.M.O** — *Algorithm for Neural Synthesis with Emotional-Linguistic
Memory Optimization; "Selmo" for short in these Terms and in the software* —
is developed and distributed by **Fabio Garzetti** (the "Author"), Italy —
contact via GitHub: https://github.com/A-N-S-E-L-M-O (open an issue on the
project repository). A.N.S.E.L.M.O is a personal project connected
to the book *Dialoghi con la lavatrice* (English edition: *The Washing
Machine Dialogues*); it is not a company and the Author operates no online
service.

## 2. Acceptance

By downloading, installing or using Selmo you accept these Terms. If you do
not accept them, do not use the software. If you are a minor, a parent or
guardian must accept these Terms for you.

## 3. These Terms and the source-code license

Selmo's source code is licensed under the **Apache License 2.0 with the
Commons Clause** (see the `LICENSE` and `NOTICE` files): you may use, study,
modify and redistribute the code, but you may not sell it, and attribution
to the Selmo project and the book is required. These Terms govern your *use*
of the official distribution; they do not restrict any right the LICENSE
grants you. If the two conflict about source-code rights, the LICENSE
prevails.

## 4. What Selmo is — and what it is not

Selmo is a local-first interface for running AI language models **on your
own computer**. There is no cloud backend, no account, no subscription. The
Author does not host, relay, store or process any of your data, because
nothing is sent to the Author: Selmo has no server side belonging to anyone.

Because of this, the Author provides **no service** in the legal sense — you
run the software yourself, on your hardware, at your initiative.

## 5. Privacy — no telemetry, no backdoor

Selmo contains **no telemetry, no analytics, no usage tracking, no remote
administration and no hidden network channel**. The Author receives no data
from your installation — not your conversations, not your documents, not
your voice, not even the fact that you installed it. Chats, documents and
settings are stored only on your device.

The complete list of situations in which Selmo's network traffic leaves your
machine is:

- **First launch:** the bundle downloads the inference engine matching your
  hardware (from the sources listed in `installer/downloads.json`). This
  happens once.
- **Page libraries:** the interface loads a small number of published
  open-source libraries and fonts from public CDNs when the page opens.
- **Web search, only when you switch it on:** with the WEB toggle active,
  your query is sent to a search engine — your own local SearXNG instance if
  you installed one, otherwise a public engine. The interface marks which
  one was used. With the toggle off, no search traffic exists.
- **Model downloads you start yourself.**

Nothing else. This list is verifiable: the source code of every component
that touches the network ships with the distribution. Any future feature
that transmits data will be off by default and documented here before it
ships. If you believe you have found behaviour that contradicts this
section, report it to the contact address above; such a report will be
treated as a security issue, not a complaint.

## 6. Your responsibilities

- **Your network.** Selmo can serve its interface to other devices on your
  local network (that is how phone access works). Anyone on the same network
  can reach it. Run Selmo on networks you trust, or restrict access as
  described in the documentation. You are responsible for the exposure of
  your own LAN.
- **Your system.** You are responsible for the security of the computer
  Selmo runs on, for backups of your data, and for keeping your operating
  system and browser updated.
- **Lawful use.** You must not use Selmo to violate any applicable law or
  the rights of others. What you generate and what you do with it is your
  responsibility.
- **Minors.** If you make Selmo available to minors — at home or in a
  classroom — you are responsible for supervising its use. Locally-run
  models have no server-side content filter, and image-generation models in
  particular can easily be misused; the safest configuration for minors is
  not to install an image model at all (see the note for educators in
  `QUICKSTART.md`).

## 7. Third-party components and models

Selmo bundles or relies on third-party open-source components, each under
its own license (see `NOTICE` and the credits in the documentation). AI
model weights — including any model included in the bundle — are third-party
works under their own licenses; the Author did not train them and does not
control them.

## 8. AI-generated content

Output produced by AI models is generated statistically and **can be wrong,
incomplete, biased or inappropriate**, even when it sounds confident. It is
not advice of any kind — medical, legal, financial or otherwise. Verify
anything that matters before relying on it. You are responsible for how you
use the output; rights in the output, where any exist, are yours and/or the
model licensor's, not the Author's.

## 9. No warranty

THE SOFTWARE IS PROVIDED FREE OF CHARGE, "AS IS" AND "AS AVAILABLE", WITHOUT
WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, ACCURACY,
NON-INFRINGEMENT AND UNINTERRUPTED OR ERROR-FREE OPERATION. YOU USE SELMO AT
YOUR OWN RISK.

## 10. Limitation of liability

TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, THE AUTHOR SHALL NOT BE
LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL OR PUNITIVE
DAMAGES, NOR FOR ANY LOSS OF DATA, PROFITS, GOODWILL OR USE, ARISING FROM OR
RELATED TO THE USE OF, OR INABILITY TO USE, THE SOFTWARE — INCLUDING DAMAGE
CAUSED BY AI-GENERATED OUTPUT, THIRD-PARTY COMPONENTS, MODEL WEIGHTS, OR
EXPOSURE OF THE SOFTWARE ON YOUR NETWORK.

Nothing in these Terms excludes or limits liability that cannot be excluded
or limited under applicable law. In particular, under Article 1229 of the
Italian Civil Code liability for wilful misconduct (*dolo*) or gross
negligence (*colpa grave*) cannot be excluded, and mandatory consumer
protections remain unaffected.

## 11. Changes to these Terms

The Author may update these Terms for new versions of the software. The
applicable Terms are the ones shipped with the version you use. Continued
use of a new version after an update constitutes acceptance of the updated
Terms for that version.

## 12. Governing law and venue

These Terms are governed by **Italian law**. For any dispute arising from or
related to these Terms or the use of Selmo, the parties agree on the
exclusive jurisdiction of the **Court of Milan (Tribunale di Milano),
Italy**.

If you use Selmo as a **consumer**, this choice of venue and law does not
deprive you of the mandatory protections of the law of your country of
residence, and where the law so provides (including Article 66-bis of the
Italian Consumer Code and Regulation (EU) 1215/2012) the competent court is
that of your place of residence or domicile.

## 13. Miscellaneous

If any provision of these Terms is found invalid, the remaining provisions
stay in force. Failure to enforce a provision is not a waiver. These Terms,
together with the LICENSE and NOTICE files, are the entire agreement between
you and the Author about the use of Selmo.

---

*A.N.S.E.L.M.O — your AI, on your machine. © 2026 Fabio Garzetti.*
