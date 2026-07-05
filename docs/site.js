/* A.N.S.E.L.M.O landing — shared config, i18n scaffold, content.
   Multilingual-ready: add an `it` block with the same keys to I18N and the
   language button turns on automatically. */

/* ---- Links: fill these in ---- */
var LINKS = {
  github: "https://github.com/A-N-S-E-L-M-O/Anselmo_Software/releases/latest",
  amazon: "https://www.amazon.com/",        // TODO: Amazon book URL (once the book is up)
  kobo:   "https://www.kobo.com/",          // TODO: Kobo book URL (once the book is up)
  quick:  "quickstart.html",                 // in-site quick start page
  terms:  "https://github.com/A-N-S-E-L-M-O/Anselmo_Software/blob/main/TERMS.md",
  notice: "https://github.com/A-N-S-E-L-M-O/Anselmo_Software/blob/main/NOTICE"
};

/* ---- language ---- */
var LANG = 'en';

/* ---- dictionary ---- */
var I18N = {
  en: {
    'brand.mini': 'A.N.S.E.L.M.O · <b>local AI</b>',
    'nav.back': '← Back',

    /* home */
    'hero.tag': "The easy way into local AI models, stigma not included.",
    'hero.sub': 'Algorithm for Neural Synthesis with Emotional-Linguistic Memory Optimization. Selmo, to friends.',
    'entry.app.k': 'The software', 'entry.app.t': 'Want to talk to A.N.S.E.L.M.O from your PC?',
    'entry.app.d': 'For the washing machine, we are not quite there yet.',
    'entry.app.go': 'Enter →',
    'entry.book.k': 'The book', 'entry.book.t': 'The Washing Machine Dialogues',
    'entry.book.d': 'The novel A.N.S.E.L.M.O was born from.',
    'entry.book.go': 'Enter →',

    /* software page */
    'sw.title': 'A.N.S.E.L.M.O', 'sw.sub': 'The easy way into local AI models, stigma not included.',
    'fw.title': 'A.N.S.E.L.M.O — live interface', 'fw.hint': 'drag me',
    'fw.ph': 'Drop the interface screenshot at assets/anselmo-ui.png',
    'faq.h': 'About the software',
    'cta.github': 'Get it on GitHub', 'cta.github.s': 'Download · source available',
    'cta.quickstart': 'Quick start — up and running in 3 steps →',
    'cta.readbook': 'Read the book', 'cta.readbook.s': 'The Washing Machine Dialogues',
    'cta.note': 'Windows for now. Unzip and click — no install, no account.',

    /* book page */
    'book.title': 'The Washing Machine Dialogues', 'book.sub': 'Dialoghi con la lavatrice — the novel behind A.N.S.E.L.M.O.',
    'book.pitch': "Selmo's &ldquo;father&rdquo; is called to answer a question no algorithm can settle on its own: what is the right thing to do. From the Ortica district to the corridors of financial power, from underground theatres to humanitarian field camps, Arx takes shape &mdash; a project that hopes to intervene without dominating. But every choice has consequences, and not all of them can be undone. <i>The Washing Machine Dialogues</i> is a lucid, deeply human solarpunk novel about power once it gives up on heroism, and technology once it is forced to reckon with responsibility.",
    'book.avail': 'The book is available here:',
    'cta.amazon': 'Amazon', 'cta.amazon.s': 'Paperback · eBook',
    'cta.kobo': 'Kobo', 'cta.kobo.s': 'eBook',
    'book.it.note': 'The Italian edition (Dialoghi con la lavatrice) is already out; the English edition ships with the app.',

    /* footer */
    'foot.quick': 'Quick guide', 'foot.terms': 'Terms of Use', 'foot.notice': 'Notice & license',
    'foot.cw': '© 2026 Fabio Garzetti — A.N.S.E.L.M.O is source-available (Apache 2.0 + Commons Clause).'
  },
  es: {
    'brand.mini': 'A.N.S.E.L.M.O · <b>IA local</b>',
    'nav.back': '← Volver',
    'hero.tag': "La forma fácil de entrar en los modelos de IA locales, sin estigma incluido.",
    'hero.sub': 'Algorithm for Neural Synthesis with Emotional-Linguistic Memory Optimization. Selmo, para los amigos.',
    'entry.app.k': 'El software', 'entry.app.t': '¿Quieres hablar con A.N.S.E.L.M.O desde tu PC?',
    'entry.app.d': 'Para la lavadora, todavía no hemos llegado.',
    'entry.app.go': 'Entrar →',
    'entry.book.k': 'El libro', 'entry.book.t': 'The Washing Machine Dialogues',
    'entry.book.d': 'La novela de la que nació A.N.S.E.L.M.O.',
    'entry.book.go': 'Entrar →',
    'sw.title': 'A.N.S.E.L.M.O', 'sw.sub': 'La forma fácil de entrar en los modelos de IA locales, sin estigma incluido.',
    'fw.title': 'A.N.S.E.L.M.O — interfaz en vivo', 'fw.hint': 'arrástrame',
    'fw.ph': 'Coloca la captura de la interfaz en assets/anselmo-ui.png',
    'faq.h': 'Sobre el software',
    'cta.github': 'Descárgalo en GitHub', 'cta.github.s': 'Descarga · código disponible',
    'cta.quickstart': 'Guía rápida — en marcha en 3 pasos →',
    'cta.readbook': 'Lee el libro', 'cta.readbook.s': 'The Washing Machine Dialogues',
    'cta.note': 'Windows por ahora. Descomprime y haz clic — sin instalación, sin cuenta.',
    'book.title': 'The Washing Machine Dialogues', 'book.sub': 'Dialoghi con la lavatrice — la novela detrás de A.N.S.E.L.M.O.',
    'book.pitch': "El &laquo;padre&raquo; de Selmo es llamado a responder una pregunta que ningún algoritmo puede resolver por sí solo: qué es lo correcto. Del barrio de la Ortica a los pasillos del poder financiero, de los teatros clandestinos a los campos de ayuda humanitaria, Arx toma forma &mdash; un proyecto que aspira a intervenir sin dominar. Pero cada decisión tiene consecuencias, y no todas pueden deshacerse. <i>The Washing Machine Dialogues</i> es una novela solarpunk lúcida y profundamente humana sobre el poder cuando renuncia al heroísmo, y la tecnología cuando se ve obligada a responder por sus actos.",
    'book.avail': 'El libro está disponible aquí:',
    'cta.amazon': 'Amazon', 'cta.amazon.s': 'Tapa blanda · eBook',
    'cta.kobo': 'Kobo', 'cta.kobo.s': 'eBook',
    'book.it.note': 'La edición italiana (Dialoghi con la lavatrice) ya está a la venta; la edición inglesa viene con la app.',
    'foot.quick': 'Guía rápida', 'foot.terms': 'Términos de uso', 'foot.notice': 'Aviso y licencia',
    'foot.cw': '© 2026 Fabio Garzetti — A.N.S.E.L.M.O es de código disponible (Apache 2.0 + Commons Clause).'
  },
  zh: {
    'brand.mini': 'A.N.S.E.L.M.O · <b>本地 AI</b>',
    'nav.back': '← 返回',
    'hero.tag': "轻松上手本地 AI 模型，不带偏见。",
    'hero.sub': 'Algorithm for Neural Synthesis with Emotional-Linguistic Memory Optimization。朋友们叫它 Selmo。',
    'entry.app.k': '软件', 'entry.app.t': '想在自己的电脑上和 A.N.S.E.L.M.O 对话吗？',
    'entry.app.d': '至于洗衣机，我们还没做到。',
    'entry.app.go': '进入 →',
    'entry.book.k': '这本书', 'entry.book.t': 'The Washing Machine Dialogues',
    'entry.book.d': 'A.N.S.E.L.M.O 由这本小说而生。',
    'entry.book.go': '进入 →',
    'sw.title': 'A.N.S.E.L.M.O', 'sw.sub': '轻松上手本地 AI 模型，不带偏见。',
    'fw.title': 'A.N.S.E.L.M.O — 实时界面', 'fw.hint': '拖动我',
    'fw.ph': '把界面截图放到 assets/anselmo-ui.png',
    'faq.h': '关于软件',
    'cta.github': '在 GitHub 获取', 'cta.github.s': '下载 · 源码可用',
    'cta.quickstart': '快速开始 — 三步即可运行 →',
    'cta.readbook': '阅读本书', 'cta.readbook.s': 'The Washing Machine Dialogues',
    'cta.note': '目前支持 Windows。解压即点即用 — 无需安装，无需账户。',
    'book.title': 'The Washing Machine Dialogues', 'book.sub': 'Dialoghi con la lavatrice — A.N.S.E.L.M.O 背后的小说。',
    'book.pitch': "Selmo 的「父亲」被召唤去回答一个任何算法都无法独自解决的问题：什么才是正确的事。从奥尔提卡（Ortica）街区到金融权力的走廊，从地下剧场到人道主义营地，Arx 逐渐成形&mdash;&mdash;一个希望介入而不支配的计划。但每个选择都有后果，而并非所有后果都能挽回。<i>The Washing Machine Dialogues</i> 是一部清醒而深切人性的太阳朋克小说，写的是放弃英雄主义之后的权力，以及被迫直面责任之后的技术。",
    'book.avail': '本书可在这里获取：',
    'cta.amazon': 'Amazon', 'cta.amazon.s': '平装 · 电子书',
    'cta.kobo': 'Kobo', 'cta.kobo.s': '电子书',
    'book.it.note': '意大利语版（Dialoghi con la lavatrice）已上市；英文版随应用一同发布。',
    'foot.quick': '快速指南', 'foot.terms': '使用条款', 'foot.notice': '声明与许可',
    'foot.cw': '© 2026 Fabio Garzetti — A.N.S.E.L.M.O 源码可用（Apache 2.0 + Commons Clause）。'
  },
  ar: {
    'brand.mini': 'A.N.S.E.L.M.O · <b>ذكاء اصطناعي محلي</b>',
    'nav.back': '→ رجوع',
    'hero.tag': "الطريق السهل إلى نماذج الذكاء الاصطناعي المحلية، بلا وصمة.",
    'hero.sub': 'Algorithm for Neural Synthesis with Emotional-Linguistic Memory Optimization. سِلمو، لأصدقائه.',
    'entry.app.k': 'البرنامج', 'entry.app.t': 'هل تريد التحدث إلى A.N.S.E.L.M.O من حاسوبك؟',
    'entry.app.d': 'أما الغسالة، فلم نصل إليها بعد.',
    'entry.app.go': 'ادخل →',
    'entry.book.k': 'الكتاب', 'entry.book.t': 'The Washing Machine Dialogues',
    'entry.book.d': 'الرواية التي وُلد منها A.N.S.E.L.M.O.',
    'entry.book.go': 'ادخل →',
    'sw.title': 'A.N.S.E.L.M.O', 'sw.sub': 'الطريق السهل إلى نماذج الذكاء الاصطناعي المحلية، بلا وصمة.',
    'fw.title': 'A.N.S.E.L.M.O — الواجهة الحية', 'fw.hint': 'اسحبني',
    'fw.ph': 'ضع لقطة الواجهة في assets/anselmo-ui.png',
    'faq.h': 'عن البرنامج',
    'cta.github': 'احصل عليه من GitHub', 'cta.github.s': 'تنزيل · المصدر متاح',
    'cta.quickstart': 'البدء السريع — جاهز في 3 خطوات →',
    'cta.readbook': 'اقرأ الكتاب', 'cta.readbook.s': 'The Washing Machine Dialogues',
    'cta.note': 'ويندوز حاليًا. فك الضغط وانقر — بلا تثبيت، بلا حساب.',
    'book.title': 'The Washing Machine Dialogues', 'book.sub': 'Dialoghi con la lavatrice — الرواية وراء A.N.S.E.L.M.O.',
    'book.pitch': "&laquo;أبو&raquo; سِلمو مدعوٌّ للإجابة عن سؤال لا تستطيع أي خوارزمية أن تحسمه وحدها: ما هو الصواب. من حيّ أورتيكا إلى أروقة السلطة المالية، ومن المسارح السرّية إلى مخيّمات الإغاثة الإنسانية، يتشكّل Arx &mdash; مشروع يأمل أن يتدخّل دون أن يهيمن. لكن لكل اختيار عواقب، وليست كلها قابلة للتراجع. <i>The Washing Machine Dialogues</i> رواية سولاربَنك صافية وإنسانية عميقة عن السلطة حين تتخلّى عن البطولة، وعن التقنية حين تُجبَر على تحمّل المسؤولية.",
    'book.avail': 'الكتاب متاح هنا:',
    'cta.amazon': 'Amazon', 'cta.amazon.s': 'غلاف ورقي · كتاب إلكتروني',
    'cta.kobo': 'Kobo', 'cta.kobo.s': 'كتاب إلكتروني',
    'book.it.note': 'النسخة الإيطالية (Dialoghi con la lavatrice) صدرت بالفعل؛ والنسخة الإنجليزية تأتي مع التطبيق.',
    'foot.quick': 'دليل سريع', 'foot.terms': 'شروط الاستخدام', 'foot.notice': 'إشعار وترخيص',
    'foot.cw': '© 2026 Fabio Garzetti — A.N.S.E.L.M.O مصدره متاح (Apache 2.0 + Commons Clause).'
  }
};

/* ---- FAQ content (per language) ---- */
var FAQ = {
  en: [
    { q:'What is A.N.S.E.L.M.O?',
      body:"<p>First, what it is <b>not</b>: A.N.S.E.L.M.O is not an AI, and it trains no models of its own. It's a <b>graphical interface</b> — one clean page — that drives third-party open-source engines and models on <b>your own computer</b>. The intelligence lives in the models you load (llama.cpp for language, Whisper for speech, Kokoro for voice, stable-diffusion.cpp for images); Selmo is the cockpit that makes them usable together.</p><p>Through that one interface you get chat, vision and OCR, whole-document analysis, optional web search, voice, and image generation — all from one machine.</p><p>The name is a backronym: <i>Algorithm for Neural Synthesis with Emotional-Linguistic Memory Optimization</i>. Selmo, to friends. It comes from the novel <i>The Washing Machine Dialogues</i>, where Selmo is a character before it's a product.</p>" },
    { q:'Why A.N.S.E.L.M.O?',
      body:"<p>Because your conversations shouldn't have to leave your desk. No cloud, no account, no telemetry — and because the source is available, you can check that it's true.</p><p>It also shows you an estimate of the energy it draws: watts and energy-per-token. \"Ethical\" becomes a number on your screen instead of a slogan. Made in Europe, private by design.</p>" },
    { q:'Who is it for?',
      body:"<p>Anyone who wants a real AI on their own hardware without handing anything to a cloud: privacy-minded people, families, students, professionals working with sensitive documents.</p><p>It's unzip-and-click — you don't need to be a developer. Developers are welcome too, but they're not who we built it for first.</p>" },
    { q:'What does it do?',
      body:"<p>Runs any open-source model (permissive license) on top of <code>llama.cpp</code>, behind one clean page. It gives you:</p><p>• Chat with three switchable profiles (Selmo, Mizan, Custom).<br>• Whole-document reading and analysis (docx, pdf, xlsx, pptx, odt…) with exhaustive coverage, not snippet-RAG.<br>• Vision and OCR on images and PDFs.<br>• Optional web search, off by default.<br>• Voice in and out (Whisper + Kokoro), hands-free.<br>• Local image generation.<br>• Your phone talking to your own PC's model over your home network.</p>" },
    { q:'How much energy does it use — and can I see it?',
      body:"<p>Yes — and this is the part no other local-AI app gives you. A.N.S.E.L.M.O shows an <b>estimate</b> of the power your machine draws while it works (CPU plus GPU plus the rest), the watt-hours spent this session and overall, the speed in tokens per second, and the running cost in your own currency, from the price you pay per kWh.</p><p>It's an estimate, not a certified meter: the GPU draw is read from the card, the CPU and the rest are approximated from load. It's accurate enough to compare a lean model against a heavy one on the same hardware. For the exact figure, a wall power meter or a smart plug with energy metering reads what the PC really pulls from the socket, and you can calibrate Selmo against it.</p>" },
    { q:'Wait — from my phone?',
      body:"<p>Yes. Selmo runs on your PC, but it serves its interface over your home network, so any device on the same Wi-Fi — your phone, a tablet — can open it in a browser. On the phone go to <code>https://YOUR-PC-IP:8443/chat.html</code> (the PC's address is shown in the tray icon), accept the certificate warning once, and you're talking to your own PC's model. That one-time warning is normal — it's what lets the phone use the microphone over a secure connection.</p><p>Nothing touches a cloud; it stays on your own network. To reach Selmo when you're away from home, don't expose the PC to the open internet — instead run a VPN into your own router (WireGuard or OpenVPN on the router, or a mesh VPN like Tailscale), then use the same PC address as if you were sitting at home.</p>" },
    { q:'I tried Selmo and it talks about \"chunking\" — what does that mean?',
      body:"<p>A model can only hold so much text in its working memory at once (its context window). When you give Selmo a long document that doesn't fit, <b>chunking</b> is how it splits the file into pieces that do fit, works through every one, and stitches the results back together with a final summary.</p><p>The point is coverage: Selmo goes through the <b>whole</b> document, passage by passage, instead of grabbing a few snippets it guessed were relevant (the shortcut most tools take). So a translation or an analysis of a long file is exhaustive, with nothing quietly skipped. When Selmo says it's chunking, it's telling you a big file is being handled in full rather than truncated.</p>" },
    { q:'Do I need a monster PC to run it? What should I expect?',
      body:"<p>No. A.N.S.E.L.M.O runs whatever model your machine can fit — the bigger and faster your GPU, the bigger the model and the more tokens per second you get. On a mid-range gaming GPU with 12 GB of VRAM it runs 24-billion-parameter models comfortably; on lighter hardware it runs smaller models, more slowly.</p><p><b>A tip that stretches modest hardware: Mixture-of-Experts (MoE) models.</b> An MoE is large in total but activates only a few billion parameters per token, so a 30B MoE with about 3B active runs fast even when the whole thing doesn't fit in VRAM — Selmo keeps the core on the GPU and pushes the idle experts out to system RAM. On a small GPU it's usually the best choice, giving you much of a big model's quality without the VRAM a dense model of the same size would need. We recommend them.</p><p>There's no minimum \"monster PC\": you trade model size and speed for whatever you have. And since it all runs locally, electricity is the only running cost — which is exactly why A.N.S.E.L.M.O keeps an estimate of the watts and energy-per-token on screen.</p>" },
    { q:'What does it NOT do?',
      body:"<p>It doesn't phone home. No telemetry, no analytics, no account, no hidden network channel — nothing reaches the author, not even the fact that you installed it.</p><p>It isn't a cloud service: there's no server that belongs to anyone. It isn't a guarantee of correctness — AI output can be wrong, so verify what matters.</p>" },
    { q:'Is it dangerous?',
      body:"<p>Not to your privacy: nothing leaves your machine, there's no account and no telemetry, and the source is available so you can verify it.</p><p>Two honest caveats. It can serve its interface to other devices on your home network — that's how phone access works — so run it on networks you trust. And a local model has no cloud content filter, so what it generates is your responsibility; with children around, the safe setup is to skip the image model and supervise. The AI can also be confidently wrong, so check anything that matters. Beyond that, it's a normal program running on your own computer.</p>" },
    { q:'Can I use it for my projects?',
      body:"<p>Yes. The source is available under <b>Apache 2.0 with the Commons Clause</b>: use it, study it, modify it, redistribute it. The one limit — you may not <b>sell</b> it. Attribution to the A.N.S.E.L.M.O project and the book is required.</p><p>If you build something on top of it, it has to carry a different name: the A.N.S.E.L.M.O / Selmo / Mizan names stay with the project. Full details in the Terms of Use and the NOTICE file.</p>" },
    { q:'I\'m a teacher, I live somewhere remote, and my language is spoken by 3,000 people. Can I have Selmo in my language?',
      body:"<p>Please do — this is one of the reasons Selmo exists. A cloud company will never localise its product for a language spoken by three thousand people; there is no market in it. A local, open tool has no such excuse: the interface is just text in a file, and a speaker like you can translate it.</p><p>Here is how. The interface strings live in one language file, <code>selmo-i18n.js</code> — a list of short keys, each with its English text. You copy the English block, leave the keys exactly as they are, and translate the text into your language. Selmo then offers your language in the globe menu, so the interface itself becomes yours.</p><p>One honest limit: the conversation depends on the model you load, not on Selmo. Selmo is the interface; the language ability lives in the model. So you'll want a model that actually knows your language — and for a tongue spoken by a few thousand people, a strong one may not exist yet. The interface, though, is entirely in your hands.</p><p>And once Selmo and a model are on the PC, it needs no internet at all — it runs fully offline, on your own hardware, which is exactly the spirit of the project. Where the connection is thin or absent, that's the difference between being able to run these models and not.</p>" },
    { q:'Bah, it looks a marketing trick to sell the book.',
      body:"<p>You are absolutely correct. The app and the book promote each other, and I won't pretend otherwise.</p><p>But A.N.S.E.L.M.O is free and source-available, and I use it for real, every day, on a 12 GB VRAM GPU.</p>" },
    { q:'Resources, credits and thanks',
      body:"<p>A.N.S.E.L.M.O stands on open-source work — it is a thin interface, the hard engineering is theirs. Thank you to everyone who builds and maintains:</p><p><b>Engines and runtimes:</b> llama.cpp (MIT), stable-diffusion.cpp (MIT), onnxruntime / onnxruntime-web (MIT).</p><p><b>Speech and voice:</b> faster-whisper + CTranslate2 + Whisper (MIT), Kokoro / kokoro-onnx (Apache 2.0), @ricky0123/vad-web (ISC), Silero VAD (MIT), soundfile (BSD-3), langdetect (Apache 2.0).</p><p><b>Web, documents and server:</b> Flask (BSD-3), requests (Apache 2.0), trafilatura (Apache 2.0), SearXNG (AGPL-3.0, separate process), Podman (Apache 2.0), JSZip (MIT/GPL), SheetJS (Apache 2.0), PDF.js (Apache 2.0), marked (MIT).</p><p><b>Hardware and power:</b> pynvml (BSD-3), psutil (BSD-3), LibreHardwareMonitor (optional).</p><p><b>Models and weights:</b> the open-weight LLMs you load — EuroLLM, Mistral, Gemma and others, each under its own license — plus Z-Image-Turbo (Apache 2.0), the Qwen3-4B text encoder (Apache 2.0) and the FLUX VAE (Apache 2.0).</p><p><b>Type:</b> Share Tech Mono (SIL OFL).</p><p>Full licenses and attribution live in the project's NOTICE file and the Credits section of the docs.</p>" }
  ],
  es: [
    { q:'¿Qué es A.N.S.E.L.M.O?',
      body:"<p>Primero, lo que <b>no</b> es: A.N.S.E.L.M.O no es una IA, y no entrena ningún modelo propio. Es una <b>interfaz gráfica</b> — una sola página limpia — que maneja motores y modelos de código abierto de terceros en <b>tu propio ordenador</b>. La inteligencia vive en los modelos que cargas (llama.cpp para el lenguaje, Whisper para el habla, Kokoro para la voz, stable-diffusion.cpp para las imágenes); Selmo es la cabina que los hace utilizables juntos.</p><p>A través de esa única interfaz tienes chat, visión y OCR, análisis de documentos completos, búsqueda web opcional, voz y generación de imágenes — todo desde una sola máquina.</p><p>El nombre es un acrónimo: <i>Algorithm for Neural Synthesis with Emotional-Linguistic Memory Optimization</i>. Selmo, para los amigos. Viene de la novela <i>The Washing Machine Dialogues</i>, donde Selmo es un personaje antes de ser un producto.</p>" },
    { q:'¿Por qué A.N.S.E.L.M.O?',
      body:"<p>Porque tus conversaciones no deberían tener que salir de tu escritorio. Sin nube, sin cuenta, sin telemetría — y como el código está disponible, puedes comprobar que es cierto.</p><p>También te muestra una estimación de la energía que consume: vatios y energía por token. «Ético» se convierte en un número en tu pantalla en lugar de un eslogan. Hecho en Europa, privado por diseño.</p>" },
    { q:'¿Para quién es?',
      body:"<p>Para cualquiera que quiera una IA real en su propio hardware sin entregar nada a una nube: personas que valoran su privacidad, familias, estudiantes, profesionales que trabajan con documentos sensibles.</p><p>Es descomprimir y hacer clic — no necesitas ser programador. Los desarrolladores también son bienvenidos, pero no son para quienes lo construimos primero.</p>" },
    { q:'¿Qué hace?',
      body:"<p>Ejecuta cualquier modelo de código abierto (licencia permisiva) sobre <code>llama.cpp</code>, tras una sola página limpia. Te ofrece:</p><p>• Chat con tres perfiles conmutables (Selmo, Mizan, Custom).<br>• Lectura y análisis de documentos completos (docx, pdf, xlsx, pptx, odt…) con cobertura exhaustiva, no RAG por fragmentos.<br>• Visión y OCR en imágenes y PDF.<br>• Búsqueda web opcional, desactivada por defecto.<br>• Voz de entrada y salida (Whisper + Kokoro), manos libres.<br>• Generación de imágenes local.<br>• Tu teléfono hablando con el modelo de tu propio PC por tu red doméstica.</p>" },
    { q:'¿Cuánta energía consume — y puedo verlo?',
      body:"<p>Sí — y esta es la parte que ninguna otra app de IA local te da. A.N.S.E.L.M.O muestra una <b>estimación</b> de la potencia que consume tu máquina mientras trabaja (CPU más GPU más el resto), los vatios-hora gastados en esta sesión y en total, la velocidad en tokens por segundo, y el coste en tu propia moneda, a partir del precio que pagas por kWh.</p><p>Es una estimación, no un medidor certificado: el consumo de la GPU se lee de la tarjeta, la CPU y el resto se aproximan por la carga. Es lo bastante precisa para comparar un modelo ligero con uno pesado en el mismo hardware. Para la cifra exacta, un medidor de enchufe o un enchufe inteligente con medición de energía lee lo que el PC realmente consume de la toma, y puedes calibrar Selmo con ello.</p>" },
    { q:'Espera — ¿desde mi teléfono?',
      body:"<p>Sí. Selmo se ejecuta en tu PC, pero sirve su interfaz por tu red doméstica, así que cualquier dispositivo en la misma Wi-Fi — tu teléfono, una tableta — puede abrirlo en un navegador. En el teléfono ve a <code>https://IP-DE-TU-PC:8443/chat.html</code> (la dirección del PC aparece en el icono de la bandeja), acepta el aviso de certificado una vez, y estarás hablando con el modelo de tu propio PC. Ese aviso único es normal — es lo que permite al teléfono usar el micrófono por una conexión segura.</p><p>Nada toca una nube; se queda en tu propia red. Para llegar a Selmo cuando estés fuera de casa, no expongas el PC a la internet abierta — en su lugar levanta una VPN hacia tu propio router (WireGuard u OpenVPN en el router, o una VPN de malla como Tailscale), y usa la misma dirección del PC como si estuvieras en casa.</p>" },
    { q:'Probé Selmo y habla de «chunking» — ¿qué significa?',
      body:"<p>Un modelo solo puede retener cierta cantidad de texto en su memoria de trabajo a la vez (su ventana de contexto). Cuando le das a Selmo un documento largo que no cabe, el <b>chunking</b> (troceado) es cómo divide el archivo en piezas que sí caben, procesa cada una, y vuelve a coser los resultados con un resumen final.</p><p>El objetivo es la cobertura: Selmo recorre el documento <b>entero</b>, pasaje por pasaje, en vez de tomar unos pocos fragmentos que supuso relevantes (el atajo que toman la mayoría de las herramientas). Así una traducción o un análisis de un archivo largo es exhaustivo, sin nada omitido en silencio. Cuando Selmo dice que está troceando, te está diciendo que un archivo grande se está tratando por completo en lugar de truncarse.</p>" },
    { q:'¿Necesito un PC monstruoso? ¿Qué debo esperar?',
      body:"<p>No. A.N.S.E.L.M.O ejecuta el modelo que quepa en tu máquina — cuanto más grande y rápida sea tu GPU, más grande el modelo y más tokens por segundo. En una GPU de gama media para juegos con 12 GB de VRAM ejecuta cómodamente modelos de 24 000 millones de parámetros; en hardware más ligero ejecuta modelos más pequeños, más despacio.</p><p><b>Un truco que estira el hardware modesto: los modelos Mixture-of-Experts (MoE).</b> Un MoE es grande en total pero activa solo unos pocos miles de millones de parámetros por token, así que un MoE de 30B con unos 3B activos va rápido incluso cuando el conjunto no cabe en la VRAM — Selmo mantiene el núcleo en la GPU y empuja los expertos inactivos a la RAM del sistema. En una GPU pequeña suele ser la mejor opción, dándote gran parte de la calidad de un modelo grande sin la VRAM que necesitaría un modelo denso del mismo tamaño. Los recomendamos.</p><p>No hay un mínimo de «PC monstruoso»: cambias tamaño y velocidad del modelo por lo que tengas. Y como todo corre en local, la electricidad es el único coste continuo — que es exactamente por qué A.N.S.E.L.M.O mantiene en pantalla una estimación de los vatios y la energía por token.</p>" },
    { q:'¿Qué NO hace?',
      body:"<p>No llama a casa. Sin telemetría, sin analíticas, sin cuenta, sin canal de red oculto — nada llega al autor, ni siquiera el hecho de que lo instalaste.</p><p>No es un servicio en la nube: no hay ningún servidor que pertenezca a nadie. No es una garantía de exactitud — la salida de la IA puede estar equivocada, así que verifica lo que importe.</p>" },
    { q:'¿Es peligroso?',
      body:"<p>No para tu privacidad: nada sale de tu máquina, no hay cuenta ni telemetría, y el código está disponible para que lo verifiques.</p><p>Dos advertencias honestas. Puede servir su interfaz a otros dispositivos de tu red doméstica — así funciona el acceso desde el teléfono — así que ejecútalo en redes de confianza. Y un modelo local no tiene filtro de contenido en la nube, así que lo que genera es tu responsabilidad; con niños cerca, la configuración segura es no instalar el modelo de imágenes y supervisar. La IA también puede equivocarse con seguridad, así que comprueba lo que importe. Más allá de eso, es un programa normal ejecutándose en tu propio ordenador.</p>" },
    { q:'¿Puedo usarlo para mis proyectos?',
      body:"<p>Sí. El código está disponible bajo <b>Apache 2.0 con la Commons Clause</b>: úsalo, estúdialo, modifícalo, redistribúyelo. El único límite — no puedes <b>venderlo</b>. Es obligatorio atribuir al proyecto A.N.S.E.L.M.O y al libro.</p><p>Si construyes algo encima, debe llevar otro nombre: los nombres A.N.S.E.L.M.O / Selmo / Mizan se quedan con el proyecto. Todos los detalles en los Términos de uso y en el archivo NOTICE.</p>" },
    { q:'Soy profesor, vivo en un lugar remoto y mi lengua la hablan 3000 personas. ¿Puedo tener Selmo en mi idioma?',
      body:"<p>Por favor, hazlo — esta es una de las razones por las que Selmo existe. Una empresa de nube nunca localizará su producto para una lengua que hablan tres mil personas; no hay mercado en ello. Una herramienta local y abierta no tiene esa excusa: la interfaz es solo texto en un archivo, y un hablante como tú puede traducirla.</p><p>Así se hace. Los textos de la interfaz viven en un archivo de idioma, <code>selmo-i18n.js</code> — una lista de claves cortas, cada una con su texto en inglés. Copias el bloque en inglés, dejas las claves exactamente como están, y traduces el texto a tu idioma. Selmo entonces ofrece tu idioma en el menú del globo, y la interfaz se vuelve tuya.</p><p>Un límite honesto: la conversación depende del modelo que cargues, no de Selmo. Selmo es la interfaz; la capacidad lingüística vive en el modelo. Así que querrás un modelo que de verdad conozca tu lengua — y para una lengua hablada por unos pocos miles de personas, quizá aún no exista uno fuerte. La interfaz, en cambio, está por completo en tus manos.</p><p>Y una vez que Selmo y un modelo están en el PC, no necesita internet en absoluto — funciona totalmente sin conexión, en tu propio hardware, que es exactamente el espíritu del proyecto. Donde la conexión es escasa o inexistente, esa es la diferencia entre poder usar estos modelos o no.</p>" },
    { q:'Bah, parece un truco de marketing para vender el libro.',
      body:"<p>Tienes toda la razón. La app y el libro se promocionan mutuamente, y no lo voy a fingir de otro modo.</p><p>Pero A.N.S.E.L.M.O es gratuito y de código disponible, y lo uso de verdad, cada día, en una GPU con 12 GB de VRAM.</p>" },
    { q:'Recursos, créditos y agradecimientos',
      body:"<p>A.N.S.E.L.M.O se apoya en trabajo de código abierto — es una interfaz ligera, la ingeniería difícil es de ellos. Gracias a todos los que construyen y mantienen:</p><p><b>Motores y runtimes:</b> llama.cpp (MIT), stable-diffusion.cpp (MIT), onnxruntime / onnxruntime-web (MIT).</p><p><b>Habla y voz:</b> faster-whisper + CTranslate2 + Whisper (MIT), Kokoro / kokoro-onnx (Apache 2.0), @ricky0123/vad-web (ISC), Silero VAD (MIT), soundfile (BSD-3), langdetect (Apache 2.0).</p><p><b>Web, documentos y servidor:</b> Flask (BSD-3), requests (Apache 2.0), trafilatura (Apache 2.0), SearXNG (AGPL-3.0, proceso separado), Podman (Apache 2.0), JSZip (MIT/GPL), SheetJS (Apache 2.0), PDF.js (Apache 2.0), marked (MIT).</p><p><b>Hardware y energía:</b> pynvml (BSD-3), psutil (BSD-3), LibreHardwareMonitor (opcional).</p><p><b>Modelos y pesos:</b> los LLM de pesos abiertos que cargas — EuroLLM, Mistral, Gemma y otros, cada uno bajo su propia licencia — más Z-Image-Turbo (Apache 2.0), el codificador de texto Qwen3-4B (Apache 2.0) y el VAE de FLUX (Apache 2.0).</p><p><b>Tipografía:</b> Share Tech Mono (SIL OFL).</p><p>Las licencias completas y la atribución están en el archivo NOTICE del proyecto y en la sección de Créditos de la documentación.</p>" }
  ],
  zh: [
    { q:'A.N.S.E.L.M.O 是什么？',
      body:"<p>首先，它<b>不是</b>什么：A.N.S.E.L.M.O 不是人工智能，也不训练任何自己的模型。它是一个<b>图形界面</b>——一个干净的页面——在<b>你自己的电脑</b>上驱动第三方开源引擎和模型。智能存在于你加载的模型里（llama.cpp 负责语言，Whisper 负责语音识别，Kokoro 负责语音合成，stable-diffusion.cpp 负责图像）；Selmo 是让它们协同可用的驾驶舱。</p><p>通过这一个界面，你可以进行对话、视觉与 OCR、整篇文档分析、可选的网络搜索、语音，以及图像生成——全部在一台机器上完成。</p><p>这个名字是一个首字母缩写：<i>Algorithm for Neural Synthesis with Emotional-Linguistic Memory Optimization</i>。朋友们叫它 Selmo。它来自小说 <i>The Washing Machine Dialogues</i>，在那里 Selmo 先是一个角色，然后才是一个产品。</p>" },
    { q:'为什么选择 A.N.S.E.L.M.O？',
      body:"<p>因为你的对话不该离开你的书桌。没有云、没有账户、没有遥测——而且因为源码是公开的，你可以自己核实这一点。</p><p>它还会向你显示能耗的估算：瓦特和每个 token 的能量。「有道德」变成了你屏幕上的一个数字，而不是一句口号。欧洲制造，隐私为本。</p>" },
    { q:'它是给谁用的？',
      body:"<p>给任何想在自己硬件上拥有真正 AI、又不把任何东西交给云的人：重视隐私的人、家庭、学生、处理敏感文档的专业人士。</p><p>解压即点即用——你不需要是程序员。开发者也欢迎，但他们不是我们最先为之打造的人。</p>" },
    { q:'它能做什么？',
      body:"<p>在 <code>llama.cpp</code> 之上运行任何开源模型（宽松许可），背后是一个干净的页面。它为你提供：</p><p>• 三个可切换配置的对话（Selmo、Mizan、Custom）。<br>• 整篇文档的阅读与分析（docx、pdf、xlsx、pptx、odt…），覆盖详尽，而非按片段的 RAG。<br>• 图像和 PDF 的视觉与 OCR。<br>• 可选的网络搜索，默认关闭。<br>• 语音输入与输出（Whisper + Kokoro），免手操作。<br>• 本地图像生成。<br>• 你的手机通过家庭网络与你自己电脑上的模型对话。</p>" },
    { q:'它耗多少电——我能看到吗？',
      body:"<p>能——而且这是其他本地 AI 应用都不给你的部分。A.N.S.E.L.M.O 显示你机器工作时功耗的<b>估算</b>（CPU 加 GPU 加其余部分）、本次会话与总计的瓦时、每秒 token 的速度，以及按你所付每度电价格换算的运行成本。</p><p>这是估算，不是经认证的计量：GPU 的功耗从显卡读取，CPU 和其余部分按负载近似。它足够精确，可在同一硬件上比较轻量模型与重型模型。要精确数字，插座功率计或带电量计量的智能插座能读出电脑真正从插座取用的功率，你可以据此校准 Selmo。</p>" },
    { q:'等等——从我的手机？',
      body:"<p>是的。Selmo 在你的电脑上运行，但它把界面通过你的家庭网络提供出来，所以同一 Wi-Fi 上的任何设备——你的手机、平板——都可以在浏览器里打开它。在手机上访问 <code>https://你的电脑IP:8443/chat.html</code>（电脑地址显示在托盘图标里），接受一次证书警告，你就在和自己电脑上的模型对话了。那次一次性的警告是正常的——它让手机能通过安全连接使用麦克风。</p><p>什么都不经过云；一切留在你自己的网络里。想在离家时访问 Selmo，不要把电脑暴露到公网——而是通过 VPN 连入你自己的路由器（路由器上的 WireGuard 或 OpenVPN，或像 Tailscale 这样的网状 VPN），然后像在家一样使用相同的电脑地址。</p>" },
    { q:'我试了 Selmo，它提到「chunking（分块）」——那是什么意思？',
      body:"<p>一个模型一次只能在它的工作记忆（上下文窗口）里容纳有限的文本。当你给 Selmo 一个放不下的长文档时，<b>分块（chunking）</b>就是它把文件切成放得下的片段、逐一处理、再用一个最终摘要把结果缝合起来的方式。</p><p>重点在于覆盖：Selmo 会逐段走完<b>整篇</b>文档，而不是抓取它猜测相关的少数片段（大多数工具走的捷径）。所以对长文件的翻译或分析是详尽的，不会悄悄漏掉任何东西。当 Selmo 说它在分块时，是在告诉你一个大文件正被完整处理，而不是被截断。</p>" },
    { q:'我需要一台怪兽级电脑吗？我该期待什么？',
      body:"<p>不需要。A.N.S.E.L.M.O 运行你的机器装得下的任何模型——你的 GPU 越大越快，模型就能越大、每秒 token 越多。在一块 12 GB 显存的中端游戏 GPU 上，它能轻松运行 240 亿参数的模型；在更轻的硬件上，它运行更小的模型，速度更慢。</p><p><b>一个能榨出普通硬件潜力的小窍门：混合专家（MoE）模型。</b>MoE 总量很大，但每个 token 只激活几十亿参数，所以一个约 3B 激活的 30B MoE 即使整体装不进显存也能跑得快——Selmo 把核心留在 GPU 上，把闲置的专家推到系统内存。在小显存 GPU 上它通常是最佳选择，让你获得接近大模型的质量，而不需要同等规模稠密模型所需的显存。我们推荐它们。</p><p>没有「怪兽级电脑」的最低门槛：你用手头的硬件去换模型的大小和速度。而且因为一切都在本地运行，电费是唯一的持续成本——这正是 A.N.S.E.L.M.O 在屏幕上保留瓦特和每 token 能量估算的原因。</p>" },
    { q:'它不会做什么？',
      body:"<p>它不会「回家报告」。没有遥测、没有分析统计、没有账户、没有隐藏的网络通道——什么都不会到达作者那里，连你安装过它这件事都不会。</p><p>它不是云服务：没有属于任何人的服务器。它不是正确性的保证——AI 的输出可能出错，所以重要的事情要自己核实。</p>" },
    { q:'它危险吗？',
      body:"<p>对你的隐私不危险：什么都不离开你的机器，没有账户也没有遥测，而且源码公开可供你核实。</p><p>两点诚实的提醒。它可以把界面提供给你家庭网络里的其他设备——手机访问就是这样实现的——所以请在你信任的网络上运行它。而且本地模型没有云端内容过滤，所以它生成什么由你负责；有孩子在场时，安全的做法是不安装图像模型并加以监督。AI 也可能自信地出错，所以重要的事要核对。除此之外，它就是一个在你自己电脑上运行的普通程序。</p>" },
    { q:'我能把它用于我的项目吗？',
      body:"<p>可以。源码以 <b>Apache 2.0 加 Commons Clause</b> 提供：使用、研究、修改、再分发都可以。唯一的限制——你不能<b>出售</b>它。必须署名 A.N.S.E.L.M.O 项目和那本书。</p><p>如果你在它之上构建东西，必须使用不同的名字：A.N.S.E.L.M.O / Selmo / Mizan 这些名字归项目所有。完整细节见使用条款和 NOTICE 文件。</p>" },
    { q:'我是一名教师，住在偏远地区，我的语言只有 3000 人使用。我能有我语言版本的 Selmo 吗？',
      body:"<p>请一定要做——这正是 Selmo 存在的原因之一。云公司永远不会为一门只有三千人使用的语言做本地化；那里没有市场。而一个本地、开放的工具没有这个借口：界面只是一个文件里的文本，像你这样的母语者就能翻译它。</p><p>方法如下。界面文字都在一个语言文件里，<code>selmo-i18n.js</code>——一串短键，每个都带着它的英文文本。你复制英文块，让键保持原样，把文本翻译成你的语言。然后 Selmo 会在地球图标菜单里提供你的语言，界面就成了你的。</p><p>一个诚实的限制：对话取决于你加载的模型，而非 Selmo。Selmo 是界面；语言能力在模型里。所以你会想要一个真正懂你语言的模型——而对于只有几千人使用的语言，强大的模型也许还不存在。但界面完全在你手中。</p><p>而且一旦 Selmo 和一个模型在电脑上，它完全不需要互联网——它在你自己的硬件上全离线运行，这正是这个项目的精神。在连接微弱或没有连接的地方，这就是能不能用上这些模型的区别。</p>" },
    { q:'切，看起来就是为卖书搞的营销把戏。',
      body:"<p>你完全说对了。应用和书互相推广，我不会假装不是这样。</p><p>但 A.N.S.E.L.M.O 是免费且源码可用的，而且我真的每天在一块 12 GB 显存的 GPU 上使用它。</p>" },
    { q:'资源、致谢与鸣谢',
      body:"<p>A.N.S.E.L.M.O 站在开源工作的肩膀上——它是一层轻薄的界面，困难的工程是他们的。感谢每一位构建和维护以下项目的人：</p><p><b>引擎与运行时：</b> llama.cpp (MIT)、stable-diffusion.cpp (MIT)、onnxruntime / onnxruntime-web (MIT)。</p><p><b>语音与嗓音：</b> faster-whisper + CTranslate2 + Whisper (MIT)、Kokoro / kokoro-onnx (Apache 2.0)、@ricky0123/vad-web (ISC)、Silero VAD (MIT)、soundfile (BSD-3)、langdetect (Apache 2.0)。</p><p><b>网络、文档与服务器：</b> Flask (BSD-3)、requests (Apache 2.0)、trafilatura (Apache 2.0)、SearXNG (AGPL-3.0，独立进程)、Podman (Apache 2.0)、JSZip (MIT/GPL)、SheetJS (Apache 2.0)、PDF.js (Apache 2.0)、marked (MIT)。</p><p><b>硬件与功耗：</b> pynvml (BSD-3)、psutil (BSD-3)、LibreHardwareMonitor（可选）。</p><p><b>模型与权重：</b> 你加载的开源权重 LLM——EuroLLM、Mistral、Gemma 等，各自遵循其许可——以及 Z-Image-Turbo (Apache 2.0)、Qwen3-4B 文本编码器 (Apache 2.0) 和 FLUX VAE (Apache 2.0)。</p><p><b>字体：</b> Share Tech Mono (SIL OFL)。</p><p>完整许可与署名见项目的 NOTICE 文件和文档的致谢部分。</p>" }
  ],
  ar: [
    { q:'ما هو A.N.S.E.L.M.O؟',
      body:"<p>أولًا، ما <b>ليس</b> عليه: A.N.S.E.L.M.O ليس ذكاءً اصطناعيًا، ولا يدرّب أي نماذج خاصة به. إنه <b>واجهة رسومية</b> — صفحة واحدة نظيفة — تُشغّل محرّكات ونماذج مفتوحة المصدر من أطراف أخرى على <b>حاسوبك أنت</b>. الذكاء يكمن في النماذج التي تُحمّلها (llama.cpp للّغة، وWhisper للكلام، وKokoro للصوت، وstable-diffusion.cpp للصور)؛ وSelmo هو قمرة القيادة التي تجعلها قابلة للاستخدام معًا.</p><p>عبر هذه الواجهة الواحدة تحصل على المحادثة، والرؤية وقراءة النصوص من الصور، وتحليل المستندات كاملةً، والبحث على الويب اختياريًا، والصوت، وتوليد الصور — كل ذلك من جهاز واحد.</p><p>الاسم اختصار: <i>Algorithm for Neural Synthesis with Emotional-Linguistic Memory Optimization</i>. سِلمو، لأصدقائه. جاء من رواية <i>The Washing Machine Dialogues</i>، حيث كان سِلمو شخصيةً قبل أن يكون منتجًا.</p>" },
    { q:'لماذا A.N.S.E.L.M.O؟',
      body:"<p>لأن محادثاتك لا ينبغي أن تغادر مكتبك. بلا سحابة، بلا حساب، بلا تتبّع — ولأن المصدر متاح، يمكنك التحقق من أن هذا صحيح.</p><p>كما يعرض لك تقديرًا للطاقة التي يستهلكها: واط وطاقة لكل توكن. تصبح «الأخلاقية» رقمًا على شاشتك بدل أن تكون شعارًا. صُنع في أوروبا، خاص بالتصميم.</p>" },
    { q:'لِمَن هو؟',
      body:"<p>لأي شخص يريد ذكاءً اصطناعيًا حقيقيًا على عتاده الخاص دون تسليم أي شيء إلى سحابة: من يهتمون بخصوصيتهم، والعائلات، والطلاب، والمحترفون الذين يتعاملون مع مستندات حساسة.</p><p>فُكّ الضغط وانقر — لست بحاجة لأن تكون مبرمجًا. المطوّرون مُرحّب بهم أيضًا، لكنهم ليسوا من بنيناه لأجلهم أولًا.</p>" },
    { q:'ماذا يفعل؟',
      body:"<p>يُشغّل أي نموذج مفتوح المصدر (رخصة متساهلة) فوق <code>llama.cpp</code>، خلف صفحة واحدة نظيفة. يمنحك:</p><p>• محادثة بثلاثة ملفات تعريف قابلة للتبديل (Selmo وMizan وCustom).<br>• قراءة وتحليل المستندات كاملةً (docx وpdf وxlsx وpptx وodt…) بتغطية شاملة، لا بأسلوب RAG المقتطع.<br>• الرؤية وقراءة النصوص من الصور وملفات PDF.<br>• بحث على الويب اختياري، معطّل افتراضيًا.<br>• صوت دخْلًا وخرْجًا (Whisper + Kokoro)، دون استخدام اليدين.<br>• توليد صور محلي.<br>• هاتفك يتحدث إلى نموذج حاسوبك عبر شبكة منزلك.</p>" },
    { q:'كم يستهلك من طاقة — وهل يمكنني رؤية ذلك؟',
      body:"<p>نعم — وهذا هو الجزء الذي لا يمنحك إياه أي تطبيق ذكاء اصطناعي محلي آخر. يعرض A.N.S.E.L.M.O <b>تقديرًا</b> للطاقة التي يسحبها جهازك أثناء العمل (المعالج زائد كرت الرسوم زائد الباقي)، وواط-ساعة هذه الجلسة والإجمالي، والسرعة بالتوكن في الثانية، والتكلفة الجارية بعملتك أنت، انطلاقًا من سعر الكيلوواط-ساعة الذي تدفعه.</p><p>إنه تقدير، لا قياس معتمد: يُقرأ استهلاك كرت الرسوم من الكرت نفسه، أما المعالج والباقي فيُقدَّران من الحِمل. وهو دقيق بما يكفي لمقارنة نموذج خفيف بنموذج ثقيل على العتاد نفسه. وللرقم الدقيق، يقرأ مقياس طاقة على المقبس أو قابس ذكي مزوّد بقياس للطاقة ما يسحبه الحاسوب فعلًا من المقبس، ويمكنك معايرة Selmo وفقًا له.</p>" },
    { q:'مهلًا — من هاتفي؟',
      body:"<p>نعم. يعمل Selmo على حاسوبك، لكنه يقدّم واجهته عبر شبكة منزلك، فيمكن لأي جهاز على شبكة الـWi-Fi نفسها — هاتفك أو جهازك اللوحي — أن يفتحه في المتصفح. على الهاتف اذهب إلى <code>https://YOUR-PC-IP:8443/chat.html</code> (يظهر عنوان الحاسوب في أيقونة شريط النظام)، واقبل تحذير الشهادة مرة واحدة، وستكون تتحدث إلى نموذج حاسوبك أنت. ذلك التحذير لمرة واحدة أمر طبيعي — فهو ما يتيح للهاتف استخدام الميكروفون عبر اتصال آمن.</p><p>لا شيء يمرّ بسحابة؛ يبقى كله على شبكتك أنت. وللوصول إلى Selmo وأنت خارج المنزل، لا تُعرّض الحاسوب للإنترنت المفتوح — بل أقِم شبكة VPN إلى موجّهك الخاص (WireGuard أو OpenVPN على الموجّه، أو شبكة VPN مترابطة مثل Tailscale)، ثم استخدم عنوان الحاسوب نفسه كأنك في المنزل.</p>" },
    { q:'جرّبت Selmo فتحدّث عن «التقطيع (chunking)» — ماذا يعني ذلك؟',
      body:"<p>لا يستطيع النموذج أن يحتفظ إلا بقدر محدود من النص في ذاكرته العاملة دفعةً واحدة (نافذة السياق). حين تعطي Selmo مستندًا طويلًا لا يتّسع، فإن <b>التقطيع (chunking)</b> هو الطريقة التي يقسّم بها الملف إلى أجزاء تتّسع، ويعالج كل جزء، ثم يخيط النتائج معًا بملخّص نهائي.</p><p>الهدف هو التغطية: يمرّ Selmo على المستند <b>كاملًا</b>، مقطعًا مقطعًا، بدل انتقاء بضع مقتطفات ظنّها ذات صلة (الاختصار الذي تسلكه معظم الأدوات). وهكذا تكون ترجمة ملف طويل أو تحليله شاملةً، دون أن يُغفَل شيء بصمت. وحين يقول Selmo إنه يقطّع، فهو يخبرك أن ملفًا كبيرًا يُعالَج بالكامل بدل أن يُبتَر.</p>" },
    { q:'هل أحتاج إلى حاسوب وحشي لتشغيله؟ وماذا أتوقّع؟',
      body:"<p>لا. يُشغّل A.N.S.E.L.M.O أي نموذج يتّسع له جهازك — فكلما كان كرت الرسوم أكبر وأسرع، كبُر النموذج وزاد عدد التوكن في الثانية. على كرت رسوم ألعاب متوسط بذاكرة 12 غيغابايت يُشغّل نماذج بحجم 24 مليار وسيط بأريحية؛ وعلى عتاد أخف يُشغّل نماذج أصغر وأبطأ.</p><p><b>حيلة تمدّ العتاد المتواضع: نماذج مزيج الخبراء (MoE).</b> نموذج MoE كبير في مجموعه لكنه يُفعّل بضعة مليارات من الأوساط فقط لكل توكن، فنموذج MoE بحجم 30B وبنحو 3B نشطة يعمل بسرعة حتى حين لا يتّسع كله في ذاكرة كرت الرسوم — إذ يبقي Selmo النواة على الكرت ويدفع الخبراء الخاملين إلى ذاكرة النظام. على كرت رسوم صغير يكون عادةً الخيار الأفضل، إذ يمنحك جانبًا كبيرًا من جودة نموذج كبير دون الذاكرة التي يحتاجها نموذج كثيف بالحجم نفسه. نحن نوصي بها.</p><p>لا حدّ أدنى من «حاسوب وحشي»: تُبادل حجم النموذج وسرعته بما لديك. ولأن كل شيء يعمل محليًا، فالكهرباء هي التكلفة الجارية الوحيدة — ولهذا بالضبط يُبقي A.N.S.E.L.M.O على الشاشة تقديرًا للواط وللطاقة لكل توكن.</p>" },
    { q:'ماذا لا يفعل؟',
      body:"<p>لا يتّصل بصانعه في الخفاء. بلا تتبّع، بلا تحليلات، بلا حساب، بلا قناة شبكية خفية — لا شيء يصل إلى المؤلف، ولا حتى واقعة أنك ثبّتّه.</p><p>ليس خدمة سحابية: لا يوجد خادم يملكه أحد. وليس ضمانًا للصحّة — فمُخرَج الذكاء الاصطناعي قد يكون خاطئًا، لذا تحقّق مما يهمّك.</p>" },
    { q:'هل هو خطير؟',
      body:"<p>ليس على خصوصيتك: لا شيء يغادر جهازك، لا حساب ولا تتبّع، والمصدر متاح لتتحقّق منه.</p><p>تنبيهان صادقان. يمكنه تقديم واجهته لأجهزة أخرى على شبكة منزلك — هكذا يعمل الوصول من الهاتف — فشغّله على شبكات تثق بها. والنموذج المحلي لا يملك مرشّح محتوى سحابيًا، فما يولّده مسؤوليتك أنت؛ ومع وجود أطفال، الإعداد الآمن هو عدم تثبيت نموذج الصور والإشراف على الاستخدام. وقد يخطئ الذكاء الاصطناعي بثقة، فتحقّق مما يهمّ. وفيما عدا ذلك، هو برنامج عادي يعمل على حاسوبك أنت.</p>" },
    { q:'هل يمكنني استخدامه في مشاريعي؟',
      body:"<p>نعم. المصدر متاح بموجب <b>Apache 2.0 مع شرط Commons Clause</b>: استخدمه، وادرسه، وعدّله، وأعِد توزيعه. القيد الوحيد — لا يمكنك <b>بيعه</b>. ويجب نسب العمل إلى مشروع A.N.S.E.L.M.O وإلى الكتاب.</p><p>وإن بنيت شيئًا فوقه، فعليه أن يحمل اسمًا مختلفًا: أسماء A.N.S.E.L.M.O / Selmo / Mizan تبقى للمشروع. التفاصيل الكاملة في شروط الاستخدام وملف NOTICE.</p>" },
    { q:'أنا معلّم أعيش في مكان نائٍ، ولغتي يتحدّثها 3000 شخص. هل يمكنني الحصول على Selmo بلغتي؟',
      body:"<p>أرجوك افعل — فهذا أحد أسباب وجود Selmo. لن تُوطِّن شركةُ سحابةٍ منتجَها للغة يتحدّثها ثلاثة آلاف شخص؛ لا سوق في ذلك. أما أداة محلية ومفتوحة فلا عذر لها: الواجهة مجرّد نص في ملف، ومتحدّث مثلك يستطيع ترجمتها.</p><p>وإليك الطريقة. نصوص الواجهة تعيش في ملف لغة واحد، <code>selmo-i18n.js</code> — قائمة من مفاتيح قصيرة، لكلٍّ نصُّه الإنجليزي. تنسخ الكتلة الإنجليزية، وتترك المفاتيح كما هي تمامًا، وتترجم النص إلى لغتك. عندها يعرض Selmo لغتك في قائمة الكرة الأرضية، فتصبح الواجهة لك.</p><p>حدٌّ صادق واحد: المحادثة تعتمد على النموذج الذي تُحمّله، لا على Selmo. فSelmo هو الواجهة؛ والقدرة اللغوية تعيش في النموذج. لذا ستريد نموذجًا يعرف لغتك حقًّا — وللغة يتحدّثها بضعة آلاف قد لا يوجد نموذج قوي بعد. لكن الواجهة بين يديك بالكامل.</p><p>وبمجرد أن يصبح Selmo ونموذجٌ على الحاسوب، فإنه لا يحتاج إلى إنترنت البتّة — يعمل دون اتصال تمامًا، على عتادك أنت، وهذا بالضبط روح المشروع. وحيث يكون الاتصال ضعيفًا أو غائبًا، هذا هو الفرق بين أن تستطيع تشغيل هذه النماذج أو لا.</p>" },
    { q:'بحّ، يبدو حيلة تسويقية لبيع الكتاب.',
      body:"<p>أنت محقّ تمامًا. التطبيق والكتاب يروّج كلٌّ منهما للآخر، ولن أتظاهر بغير ذلك.</p><p>لكن A.N.S.E.L.M.O مجاني ومصدره متاح، وأنا أستخدمه فعليًا، كل يوم، على كرت رسوم بذاكرة 12 غيغابايت.</p>" },
    { q:'المصادر والاعتمادات والشكر',
      body:"<p>يقف A.N.S.E.L.M.O على أكتاف عمل مفتوح المصدر — فهو واجهة رقيقة، والهندسة الصعبة لهم. شكرًا لكل من يبني ويصون:</p><p><b>المحرّكات وبيئات التشغيل:</b> llama.cpp (MIT)، stable-diffusion.cpp (MIT)، onnxruntime / onnxruntime-web (MIT).</p><p><b>الكلام والصوت:</b> faster-whisper + CTranslate2 + Whisper (MIT)، Kokoro / kokoro-onnx (Apache 2.0)، @ricky0123/vad-web (ISC)، Silero VAD (MIT)، soundfile (BSD-3)، langdetect (Apache 2.0).</p><p><b>الويب والمستندات والخادم:</b> Flask (BSD-3)، requests (Apache 2.0)، trafilatura (Apache 2.0)، SearXNG (AGPL-3.0، عملية منفصلة)، Podman (Apache 2.0)، JSZip (MIT/GPL)، SheetJS (Apache 2.0)، PDF.js (Apache 2.0)، marked (MIT).</p><p><b>العتاد والطاقة:</b> pynvml (BSD-3)، psutil (BSD-3)، LibreHardwareMonitor (اختياري).</p><p><b>النماذج والأوزان:</b> نماذج اللغة مفتوحة الأوزان التي تُحمّلها — EuroLLM وMistral وGemma وغيرها، كلٌّ برخصته — إضافة إلى Z-Image-Turbo (Apache 2.0)، ومُرمّز النص Qwen3-4B (Apache 2.0)، وFLUX VAE (Apache 2.0).</p><p><b>الخط:</b> Share Tech Mono (SIL OFL).</p><p>الرخص الكاملة والنسب موجودة في ملف NOTICE للمشروع وقسم الاعتمادات في الوثائق.</p>" }
  ]
};

/* ---- helpers ---- */
function t(k){ return (I18N[LANG] && I18N[LANG][k]) || I18N.en[k] || k; }
function getFAQ(){ return FAQ[LANG] || FAQ.en; }

function applyI18n(){
  document.querySelectorAll('[data-i18n]').forEach(function(el){
    el.innerHTML = t(el.getAttribute('data-i18n'));
  });
}
function wireLinks(){
  document.querySelectorAll('[data-link]').forEach(function(el){
    var key = el.getAttribute('data-link');
    if(LINKS[key]) el.href = LINKS[key];
  });
}
var SELMO_LANGS = [
  {code:'en', name:'English'},
  {code:'es', name:'Español'},
  {code:'zh', name:'中文'},
  {code:'ar', name:'العربية'}
];
function setLang(code){
  LANG = I18N[code] ? code : 'en';
  var rtl = (LANG === 'ar');
  document.documentElement.setAttribute('lang', LANG);
  document.documentElement.setAttribute('dir', rtl ? 'rtl' : 'ltr');
  try{ localStorage.setItem('selmo_lang', LANG); }catch(e){}
  var btn = document.getElementById('langbtn');
  if(btn){
    var m = SELMO_LANGS.filter(function(l){ return l.code === LANG; })[0];
    btn.textContent = (m ? m.name : LANG.toUpperCase()) + ' ▾';
  }
  applyI18n();
  if(window.onLangChange) window.onLangChange();
}
function initLang(){
  var btn = document.getElementById('langbtn');
  if(!btn) return;
  var saved; try{ saved = localStorage.getItem('selmo_lang'); }catch(e){}
  if(saved && I18N[saved]) LANG = saved;
  var menu = document.createElement('div');
  menu.className = 'langmenu';
  SELMO_LANGS.forEach(function(l){
    if(!I18N[l.code]) return;
    var it = document.createElement('button');
    it.className = 'langitem'; it.textContent = l.name;
    it.addEventListener('click', function(e){ e.stopPropagation(); setLang(l.code); menu.classList.remove('on'); });
    menu.appendChild(it);
  });
  document.body.appendChild(menu);
  btn.addEventListener('click', function(e){
    e.stopPropagation();
    var r = btn.getBoundingClientRect();
    menu.style.top = (r.bottom + 6) + 'px';
    menu.style.right = Math.max(8, window.innerWidth - r.right) + 'px';
    menu.classList.toggle('on');
  });
  document.addEventListener('click', function(){ menu.classList.remove('on'); });
}

/* ---- capability matrix ---- */
var CAPS = [
  { icon:'<path d="M13 2L3 14h9l-1 8 10-12h-9z"/>',
    ct:'Energy monitoring',
    cd:'Real-time watts + Wh per session' },
  { icon:'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 8h10M7 12h7M7 16h4"/><path d="M17 14l2 2-2 2"/>',
    ct:'Reasoning / THINK',
    cd:'Dedicated panel for reasoning models' },
  { icon:'<rect x="7" y="2" width="10" height="20" rx="2"/><circle cx="12" cy="18" r="1"/>',
    ct:'Mobile access',
    cd:'Phone access via HTTPS on local network' },
  { icon:'<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/><path d="M9 13h6M9 17h4"/>',
    ct:'Documents & chunking',
    cd:'Full-file analysis, auto-chunking, vision & OCR' },
  { icon:'<rect x="9" y="2" width="6" height="9" rx="3"/><path d="M5.5 10a6.5 6.5 0 0013 0"/><path d="M12 16V20M9.5 20h5"/>',
    ct:'Voice loop',
    cd:'Whisper STT + Kokoro TTS, hands-free' },
  { icon:'<circle cx="11" cy="11" r="7"/><path d="M16.5 16.5L21 21"/>',
    ct:'Web search',
    cd:'Optional, off by default, privacy-first' },
  { icon:'<rect x="3" y="6" width="11" height="9" rx="1.5"/><rect x="10" y="9" width="11" height="9" rx="1.5"/><path d="M14 3l4 4-4 4"/>',
    ct:'Image-to-image',
    cd:'Generate from text or existing image' },
  { icon:'<path d="M4 4h16v11H9l-4 4v-4H4z"/>',
    ct:'Chat',
    cd:'Local conversation, zero cloud' }
];

function buildCaps(){
  var el = document.querySelector('.caps');
  if(!el) return;
  el.innerHTML = CAPS.map(function(c){
    return '<div class="cap">'+
      '<div class="ic"><svg viewBox="0 0 24 24">'+c.icon+'</svg></div>'+
      '<div class="ct">'+c.ct+'</div>'+
      '<div class="cd">'+c.cd+'</div>'+
      '</div>';
  }).join('');
}

document.addEventListener('DOMContentLoaded', function(){
  wireLinks(); initLang(); setLang(LANG);
  buildCaps();
  if(window.onPageReady) window.onPageReady();
});
