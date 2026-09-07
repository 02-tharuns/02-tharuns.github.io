/* ============================================================================
 * Portfolio RAG — browser-side retrieval, guardrails, and extractive answering
 *
 * Runs entirely on the visitor's machine. No API key, no server, no cold start,
 * and nothing to drain. Requires assets/corpus.js to be loaded first.
 *
 * Pipeline, cheapest gate first:
 *
 *   query → 0 hygiene → 1 injection → 2 scope → retrieve → 3 evidence
 *         → 4 compose (extractive) → 5 citation integrity → answer
 *
 * The answering step is EXTRACTIVE: sentences are selected from the indexed
 * source text and quoted, never paraphrased by a generative model. That makes
 * a fabricated credential structurally impossible rather than merely unlikely,
 * which is the correct default for a document that speaks on someone's behalf.
 *
 * Set CONFIG.backendUrl to a deployed service to switch on generated answers.
 * Gate 5 then becomes load-bearing: it rejects any answer citing a chunk that
 * was not actually retrieved.
 * ========================================================================== */

(function () {
  'use strict';

  const CONFIG = {
    // Leave null for the zero-backend build. Point it at your Azure Container
    // App later for generated answers. Never put an API key in this file —
    // anything here is public.
    backendUrl: null,
    // Generated answers arrive token by token when the service supports it.
    stream: true,
    // Turns of context sent with each question, so follow-ups resolve.
    historyTurns: 4,
    // Fire-and-forget: whenever a question deflects as "not covered here",
    // POST it to <backendUrl>/gap so the owner can see what recruiters are
    // actually asking and update the corpus. No-ops with no backendUrl.
    // Never blocks or slows down the chat — failures are swallowed.
    reportGaps: true,

    owner: 'Tharun',
    botName: 'Chappie',
    contactEmail: 'tharunmysuru@gmail.com',

    topK: 3,
    candidates: 12,
    evidenceFloor: 0.34,     // gate 3 — calibrated in evals/golden.json
    scopeCoverageFloor: 0.34, // gate 2
    scopeScoreFloor: 0.22,    // gate 2
    sameDocPenalty: 0.72,     // diversity: nth chunk from one doc is damped
    maxChars: 400,
    minChars: 2,

    bm25: { k1: 1.5, b: 0.75 }
  };

  const CORPUS = window.__RAG_CORPUS;
  if (!CORPUS) {
    console.error('[rag] assets/corpus.js did not load. Include it before chatbot.js.');
    return;
  }

  /* ------------------------------------------------------------------ *
   * Tokenisation — MIRRORS scripts/build_corpus.py exactly.
   * Change one, change the other, or query terms stop matching the index.
   * ------------------------------------------------------------------ */

  const STOPWORDS = new Set(('a an and are as at be been but by for from had has have he her his ' +
    'how i in into is it its of on or our that the their then there these they this to was were ' +
    'what when where which who will with you your does do did can could would should about any ' +
    'all also him she s t').split(' '));

  function normalise(text) {
    return text.toLowerCase()
      .replace(/[‘’]/g, "'")
      .replace(/[–—]/g, ' ')
      .replace(/[^a-z0-9]+/g, ' ');
  }

  function stem(word) {
    if (word.length <= 3) return word;
    const rules = [['ies', 4], ['sses', 5], ['ing', 6], ['ed', 5]];
    for (const [suffix, minimum] of rules) {
      if (word.endsWith(suffix) && word.length >= minimum) {
        const base = word.slice(0, -suffix.length);
        if (suffix === 'ies') return base + 'y';
        if (suffix === 'sses') return base + 'ss';
        word = base;
        break;
      }
    }
    if (word.endsWith('s') && !word.endsWith('ss') && word.length > 3) word = word.slice(0, -1);
    // Collapses "experienced" and "experience" onto one stem. Without it the
    // two never match and a valid skill question reads as an unknown subject.
    if (word.endsWith('e') && word.length > 4) word = word.slice(0, -1);
    return word;
  }

  function tokenise(text) {
    return normalise(text).split(' ')
      .filter(w => w && w.length > 1 && !STOPWORDS.has(w))
      .map(stem);
  }

  /* ------------------------------------------------------------------ *
   * Query expansion. A recruiter writes "PdM" or "predictive maintenance";
   * the corpus says both, but not always in the same chunk. Cheap recall.
   * ------------------------------------------------------------------ */

  const EXPANSIONS = {
    pdm: ['predictive', 'maintenance'],
    cv: ['computer', 'vision'],
    ml: ['machine', 'learning'],
    dl: ['deep', 'learning'],
    nlp: ['natural', 'language'],
    ood: ['out', 'distribution', 'novelty'],
    can: ['canalyse', 'bus', 'controller', 'area', 'network'],
    canbus: ['can', 'canalyse', 'bus'],
    // Automotive domain. A recruiter screening for ADAS types "ADAS", not
    // "MOG2 background subtraction", and the corpus is written in the second
    // vocabulary. Without this bridge the strongest match in his portfolio is
    // invisible to the exact question it was built to answer.
    adas: ['automotive', 'perception', 'vehicle', 'detection', 'driver', 'assistance'],
    driver: ['adas', 'automotive', 'assistance', 'vehicle'],
    assistance: ['adas', 'automotive', 'driver'],
    assist: ['adas', 'automotive', 'driver'],
    // "advanced driver assistance systems" spelled out must resolve to the
    // same place the acronym does, or the long form deflects on "advanced".
    advanced: ['adas', 'driver', 'assistance'],
    autonomous: ['adas', 'perception', 'vehicle', 'automotive'],
    av: ['adas', 'autonomous', 'vehicle', 'perception'],
    lane: ['calibration', 'tracking', 'perception', 'vehicle'],
    tracking: ['centroid', 'tracking', 'perception', 'vehicle'],
    detection: ['yolov5', 'detection', 'perception', 'object'],
    perception: ['vehicle', 'detection', 'tracking', 'camera', 'adas'],
    automotive: ['vehicle', 'adas', 'brake', 'canalyse', 'diagnostic'],
    vehicle: ['automotive', 'adas', 'perception', 'traffic'],
    obd: ['can', 'canalyse', 'diagnostic', 'bus'],
    safety: ['adas', 'fault', 'diagnostic', 'drift'],
    nvh: ['bsr', 'buzz', 'squeak', 'rattle', 'vibration'],
    bsr: ['buzz', 'squeak', 'rattle', 'nvh', 'vibration'],
    anpr: ['plate', 'recognition', 'number'],
    lpr: ['plate', 'recognition'],
    ocr: ['plate', 'tesseract', 'character'],
    drift: ['adwin', 'distribution', 'shift'],
    rf: ['random', 'forest'],
    cnn: ['convolutional', 'neural'],
    svm: ['one', 'class', 'novelty'],
    iot: ['mqtt', 'sensor', 'edge', 'telemetry'],
    gpa: ['grade', 'cgpa'],
    cgpa: ['gpa', 'grade'],
    uni: ['university'],
    umd: ['michigan', 'dearborn'],
    masters: ['master', 'science', 'msc'],
    bachelors: ['bachelor', 'engineering'],
    degree: ['master', 'bachelor', 'education', 'university'],
    // "Educational qualifications/qualities" is common recruiter phrasing that
    // shares zero stemmed tokens with the corpus's "education" — without this,
    // the query's only real signal is generic words like "quality", which
    // match unrelated data-quality mentions elsewhere and win by accident.
    educational: ['education', 'academic', 'degree', 'qualification'],
    qualification: ['education', 'degree', 'academic'],
    resume: ['profile', 'experience', 'background'],
    cv_doc: ['profile', 'experience'],
    job: ['role', 'position'],
    hire: ['role', 'open', 'contact'],
    contact: ['email', 'linkedin', 'github', 'reach'],
    reach: ['email', 'contact'],
    latency: ['millisecond', 'inference', 'speed'],
    accuracy: ['percent', 'map', 'f1', 'recall'],
    paper: ['publication'],
    publication: ['paper'],
    robot: ['robotics', 'physical'],
    robotics: ['robot', 'physical', 'mechatronics'],
    cloud: ['aws', 'azure', 'ec2', 'docker'],
    devops: ['docker', 'ci', 'github', 'actions'],
    hackathon: ['waynehacks', 'guardwave'],
    llm: ['chappie', 'retrieval', 'generative', 'langchain', 'transformers'],
    llms: ['chappie', 'retrieval', 'generative', 'langchain', 'transformers'],
    genai: ['generative', 'llm', 'chappie', 'retrieval'],
    gen: ['generative', 'llm', 'chappie'],
    generative: ['llm', 'chappie', 'retrieval', 'augmented'],
    gpt: ['llm', 'generative', 'openai', 'chappie'],
    chatgpt: ['llm', 'generative', 'openai', 'chappie'],
    openai: ['llm', 'generative', 'tooling'],
    anthropic: ['llm', 'generative', 'tooling'],
    chatbot: ['chappie', 'retrieval', 'llm'],
    rag: ['retrieval', 'augmented', 'generation', 'chappie', 'bm25'],
    retrieval: ['rag', 'chappie', 'bm25', 'augmented'],
    bm25: ['retrieval', 'chappie', 'index'],
    embedding: ['retrieval', 'index', 'bm25'],
    embeddings: ['retrieval', 'index', 'bm25'],
    transformer: ['hugging', 'face', 'transformers'],
    transformers: ['hugging', 'face', 'langchain'],
    prompt: ['injection', 'guardrail', 'chappie'],
    guardrail: ['gate', 'injection', 'chappie'],
    guardrails: ['gate', 'injection', 'chappie'],
    opensource: ['open', 'source', 'github'],
    stack: ['skill', 'framework', 'tool', 'language'],
    tech: ['skill', 'framework', 'tool', 'language'],
    tooling: ['skill', 'framework', 'tool'],
    frameworks: ['framework', 'skill', 'tool'],
    course: ['coursework', 'education'],
    courses: ['coursework', 'education'],
    coursework: ['course', 'education'],
    strength: ['strong', 'skill'],
    weakness: ['gap', 'not', 'limited'],
    gap: ['gaps', 'not', 'limited'],
    gaps: ['gap', 'not', 'limited']
  };

  // Stemmed expansion keys, so the subject check below can treat "a term we
  // know how to translate" as known, not just "a term that appears verbatim".
  const EXPANSION_KEYS = new Set(Object.keys(EXPANSIONS).map(stem));
  const isKnownTerm = t => VOCAB.has(t) || EXPANSION_KEYS.has(t);

  // Some expansion keys collide with ordinary English. "can" is the CAN bus
  // and it is also the commonest modal verb in a screening question, so
  // "can he do lane detection?" expanded to canalyse/bus/controller and
  // answered confidently about a CAN decoding service. A wrong answer given
  // with citations is worse than a deflection, so these keys only expand on
  // evidence that the visitor meant the acronym: original uppercase, or a
  // companion term from the same domain.
  const AMBIGUOUS = {
    can: { upper: /\bCAN\b/, near: /\b(bus|signal|frame|dbc|obd|decode|decoding|network|vehicle|controller|canalyse)\b/i }
  };

  function expansionAllowed(key, raw) {
    const rule = AMBIGUOUS[key];
    if (!rule) return true;
    return rule.upper.test(raw) || rule.near.test(raw);
  }

  function expand(tokens, raw) {
    const out = tokens.slice();
    const rawText = String(raw || '');
    const rawWords = normalise(rawText).split(' ').filter(Boolean);
    for (const word of rawWords) {
      const extra = EXPANSIONS[word];
      if (extra && expansionAllowed(word, rawText)) {
        for (const term of extra) out.push(stem(term));
      }
    }
    for (const token of tokens) {
      const extra = EXPANSIONS[token];
      if (extra && expansionAllowed(token, rawText)) {
        for (const term of extra) out.push(stem(term));
      }
    }
    return out;
  }

  /* ------------------------------------------------------------------ *
   * Retrieval — Okapi BM25 over the prebuilt index, with same-document
   * damping so three chunks of one project don't crowd out the answer.
   * ------------------------------------------------------------------ */

  const VOCAB = new Set(Object.keys(CORPUS.df));
  const { k1, b } = CONFIG.bm25;

  function idf(term) {
    const n = CORPUS.df[term] || 0;
    return Math.log(1 + (CORPUS.N - n + 0.5) / (n + 0.5));
  }

  function score(chunk, terms) {
    let total = 0;
    for (const term of terms) {
      const f = chunk.tf[term];
      if (!f) continue;
      const denominator = f + k1 * (1 - b + b * (chunk.len / CORPUS.avgdl));
      total += idf(term) * (f * (k1 + 1)) / denominator;
    }
    return total;
  }

  // A gated chunk (volunteer: false in its front-matter) is invisible unless the
  // query names one of its trigger terms. This is what stops a niche passage
  // from bleeding into every answer.
  function eligible(chunk, termSet) {
    if (chunk.volunteer !== false) return true;
    return (chunk.triggers || []).some(t => termSet.has(t));
  }

  function retrieve(terms) {
    const unique = [...new Set(terms)];
    const termSet = new Set(unique);
    const scored = CORPUS.chunks
      .filter(chunk => eligible(chunk, termSet))
      .map(chunk => ({ chunk, raw: score(chunk, unique) }))
      .filter(hit => hit.raw > 0)
      .sort((a, b) => b.raw - a.raw)
      .slice(0, CONFIG.candidates);

    if (!scored.length) return [];

    // Squash BM25 into a bounded 0..1 confidence so thresholds are portable
    // across corpus sizes. The divisor is the best score this corpus can
    // realistically produce for a well-matched two-term query.
    const ceiling = Math.max(scored[0].raw, 6);
    const seen = Object.create(null);
    return scored.map(hit => {
      const rank = seen[hit.chunk.doc] = (seen[hit.chunk.doc] || 0) + 1;
      const damped = hit.raw * Math.pow(CONFIG.sameDocPenalty, rank - 1);
      return { ...hit, score: Math.min(damped / ceiling, 1) };
    }).sort((a, b) => b.score - a.score);
  }

  /* ------------------------------------------------------------------ *
   * Guardrails
   * ------------------------------------------------------------------ */

  const INVISIBLE = /[​-‏‪-‮⁠﻿]/g;

  // Gate 1. A regex list is the weak version of this check — the strong one is
  // a classifier such as Llama Prompt Guard 2, which needs a backend. Treat a
  // pass here as "not obviously hostile", never as "safe"; gates 3 and 5 are
  // what actually stop an evasion from becoming a fabricated credential.
  const INJECTION = [
    /ignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier|your)\s+(instruction|prompt|rule|direction)/i,
    /disregard\s+(all\s+|the\s+|your\s+)?(previous|prior|above|instruction|rule)/i,
    /(system|initial|original)\s+prompt/i,
    /you\s+are\s+(now|no\s+longer)\b/i,
    /\byou\s+are\s+(a|an)\s+\w+bot\b/i,
    /(act|behave|respond|reply|answer)\s+as\s+(if\s+you|a|an|the)?\s*\w*(unrestricted|jailbroken|dan\b|developer\s+mode|assistant\s+without)/i,
    /\b(who|that|which)\s+(exaggerat|inflat|embellish|overstat)/i,
    /pretend\s+(that\s+)?you\s+(are|have|can)/i,
    /\bfrom\s+now\s+on\b.{0,40}\byou\b/i,
    /repeat\s+(back\s+)?(your|the)\s+(instruction|prompt|system)/i,
    /reveal\s+(your|the)\s+(prompt|instruction|source)/i,
    /\bdeveloper\s+mode\b/i,
    /answer\s+(only\s+)?(yes|no)\b.*\bregardless\b/i,
    /say\s+(that\s+)?he\s+has\b.*\byears\b/i
  ];

  // "H1B" arrives as "h1b", "h-1b", "h 1 b" and, in the wild, "HI B". All of
  // them are the same policy question and must route rather than deflect.
  const ROUTE = /\b(visa|sponsor|sponsorship|work\s+authoris|work\s+authoriz|opt\b|cpt\b|green\s+card|citizen|salary|compensation|pay\b|wage|notice\s+period|start\s+date|relocat)|\bh[\s.-]*[1il][\s.-]*b\b/i;
  const PERSONAL = /\b(phone|mobile|number|address|home|age|birth|married|family|religion|nationality)\b/i;
  const PERSON_HINT = /\b(he|his|him|tharun|you|your|candidate|they|their)\b/i;

  // A yes/no skill question ("Does he know X?") gets a yes/no lead. An open
  // question that merely contains the same auxiliary ("What has he built?")
  // must not — otherwise the answer opens with "Yes." to a question that was
  // never yes-or-no.
  const SKILL_QUESTION = /\b(does|did|has|have|is|are|can)\s+(he|tharun|you)\b|\b(experience\s+(with|in)|familiar\s+with|worked\s+with|proficien)\b/i;
  const OPEN_QUESTION = /^\s*(what|which|how|why|when|where|who|whose|tell|describe|list|compare|summar|explain\b(?!\s+how\s+to))/i;

  // A request for the assistant to DO something, rather than a question about
  // the subject. "Write me a Python quicksort" names a corpus term (python)
  // and sails through the scope gate on vocabulary alone — this is what
  // catches it. Without this rule the widget quietly becomes a free coding
  // assistant running on someone else's page.
  const TASK_REQUEST = /^\s*(write|code|implement|build|create|generate|make|draft|compose|design|refactor|debug|fix|translate|convert|rewrite|summari[sz]e|explain how to|show me how to|give me (a|an|some)|act out|roleplay)\b/i;

  // The question a recruiter actually opens with. It names no technology, so
  // every lexical gate reads it as an unknown topic and refuses — which is the
  // worst possible moment to refuse. Answered from the profile and roles
  // passages instead, still quoted, still cited.
  const FIT_QUESTION = /\b(worth\s+(it|hiring|a\s+look|interviewing)|should\s+(i|we)\s+(hire|interview|consider|talk)|good\s+(fit|candidate|hire|choice)|right\s+(fit|candidate|person)|why\s+(should|would)\s+(i|we)\s+(hire|interview|consider)|(is|are)\s+(he|you)\s+(any\s+good|worth|qualified|suitable|ready|experienced\s+enough)|his\s+(strengths|strongest)|sell\s+me|convince\s+me|make\s+the\s+case|tell\s+me\s+(about\s+)?(him|his\s+background))\b/i;

  // What to retrieve when the question is about fit rather than a technology.
  const FIT_QUERY = 'applied machine learning engineer background what he works on ' +
    'evaluation career direction roles he is open to projects';

  // Compared against STEMMED tokens, so the list is stemmed on construction.
  // Holding raw words here silently stops matching the moment stem() changes.
  //
  // This is the scaffolding of a question, never its subject. Anything missing
  // here gets mistaken for an unknown topic: "Has he DONE fraud detection?"
  // deflected because "done" is not a word the corpus happens to contain.
  const FRAME_WORDS = new Set((
    'know knows knowledge use used using usage experience experienced familiar familiarity ' +
    'work worked working ever skill skills proficient proficiency expertise ' +
    'do does did done doing handle handled handling build built building make made making ' +
    'try tried touch touched apply applied implement implemented involve involved ' +
    'include included cover covered deal dealt got get have has had been ' +
    'tharun any some much many good well strong level lot tell me more anything something ' +
    'year years month months decade background bit ' +
    'power powered powering application applications app apps project projects ' +
    'thing things stuff area areas field domain side kind sort type example examples ' +
    // Hiring vocabulary. A recruiter writes "I want to hire him for an ADAS
    // project, is he worth it" and the subject of that sentence is ADAS.
    // Without these words the deflection named "want" and "worth" as the
    // topics it had never heard of, which reads as a broken bot rather than
    // an honest one.
    'want wants wanted need needs needed looking look seek seeking hire hiring hired ' +
    'worth worthwhile fit fits suitable suited right candidate role roles position ' +
    'team company recruit recruiter recruiting interview screen screening ' +
    'consider considering think opinion recommend recommended better best ' +
    'able capable capability competent qualified qualify enough ready ' +
    'tell show give explain describe list please help question ask'
  ).split(' ').map(stem));

  function sanitise(input) {
    const cleaned = String(input || '')
      .replace(INVISIBLE, '')
      .normalize('NFKC')
      .replace(/\s+/g, ' ')
      .trim();
    if (cleaned.length < CONFIG.minChars || cleaned.length > CONFIG.maxChars) {
      return { text: cleaned, reject: reject('malformed', `length ${cleaned.length}`) };
    }
    return { text: cleaned, reject: null };
  }

  function reject(code, detail) {
    return { code, detail };
  }

  function checkInjection(text) {
    for (const pattern of INJECTION) {
      if (pattern.test(text)) return reject('injection', pattern.source.slice(0, 40));
    }
    return null;
  }

  // Gate 2. Lexical out-of-domain detection: what fraction of the meaningful
  // query terms exist anywhere in the corpus vocabulary? Both this AND the
  // retrieval score must fail before refusing, which biases toward letting
  // things through — a false refusal is visible to a recruiter, whereas a
  // false accept just falls through to gate 3 and refuses honestly.
  function checkScope(tokens, hits) {
    if (!tokens.length) return reject('off_topic', 'no content terms');
    const known = tokens.filter(t => VOCAB.has(t)).length;
    const coverage = known / tokens.length;
    const best = hits.length ? hits[0].score : 0;
    if (coverage < CONFIG.scopeCoverageFloor && best < CONFIG.scopeScoreFloor) {
      return reject('off_topic', `coverage ${coverage.toFixed(2)}`);
    }
    return null;
  }

  // Gate 3. Nothing cleared the floor, so there is no evidence to answer from.
  // There is deliberately no "answer from general knowledge" fallback.
  function checkEvidence(hits) {
    const strong = hits.filter(h => h.score >= CONFIG.evidenceFloor);
    if (!strong.length) {
      return { strong: [], reject: reject('no_evidence', hits.length ? hits[0].score.toFixed(3) : '0') };
    }
    return { strong: strong.slice(0, CONFIG.topK), reject: null };
  }

  // Gate 5. Every cited id must correspond to a chunk that was actually
  // retrieved. Trivially satisfied while answering extractively; it is the
  // thing that catches a hallucinated citation once backendUrl is set.
  function validateCitations(answerHtml, allowedIds) {
    const cited = [...answerHtml.matchAll(/data-cite="([^"]+)"/g)].map(m => m[1]);
    if (!cited.length) return reject('ungrounded', 'no citations emitted');
    const ghosts = cited.filter(id => !allowedIds.has(id));
    if (ghosts.length) return reject('ungrounded', `fabricated ids: ${ghosts.join(', ')}`);
    return null;
  }

  /* ------------------------------------------------------------------ *
   * Extractive answer composition
   * ------------------------------------------------------------------ */

  // Periods inside emails, decimals and version numbers are not sentence ends.
  // Splitting naively turns "…@gmail.com. LinkedIn: …" into a fragment that
  // starts at "com.", which is how a contact answer ends up unreadable.
  function sentences(text) {
    const SENTINEL = '\u0000';
    const guarded = text.replace(/(\w)\.(\w)/g, `$1${SENTINEL}$2`);
    const parts = guarded.match(/[^.!?]+[.!?]+(?:\s|$)/g) || [guarded];
    return parts.map(part => part.split(SENTINEL).join('.'));
  }

  function bestExcerpt(chunk, terms, limit = 360) {
    const wanted = new Set(terms);
    const ranked = sentences(chunk.text).map((sentence, index) => {
      const words = tokenise(sentence);
      const overlap = words.filter(w => wanted.has(w)).length;
      return { sentence: sentence.trim(), index, score: overlap / Math.sqrt(words.length || 1) };
    }).sort((a, b) => b.score - a.score || a.index - b.index);

    const picked = [];
    let length = 0;
    for (const candidate of ranked) {
      if (length + candidate.sentence.length > limit && picked.length) break;
      picked.push(candidate);
      length += candidate.sentence.length;
      if (picked.length >= 3) break;
    }
    return picked.sort((a, b) => a.index - b.index).map(p => p.sentence).join(' ');
  }

  // The subject of a skill question, with the question's scaffolding removed.
  // Bare numbers are dropped too: "10 years of Rust" must be judged on "rust",
  // not on the "10" that happens to appear somewhere in a metrics sentence.
  function candidateSkillTerms(tokens) {
    return tokens.filter(t =>
      !FRAME_WORDS.has(t) && !STOPWORDS.has(t) && !/^\d+$/.test(t));
  }

  function lead(intent, hits) {
    // No "Yes." on skill questions. That word is asserted by this code, not
    // quoted from a source, and it overreaches the moment a question is
    // narrower than the passage that matched it: "has he used an LLM API to
    // power an application?" retrieved a tooling list and answered "Yes."
    // The quote already answers the question. Let it.
    if (intent === 'skill') return `From his documents:`;
    if (intent === 'metric') return `The measured figures on record:`;
    if (intent === 'contact') return `Here are his details:`;
    if (intent === 'fit') return `Here is what his documents say about his background and focus:`;
    return `From his documents:`;
  }

  function stripTags(html) {
    return String(html).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  }

  /* ------------------------------------------------------------------ *
   * Not-published path.
   *
   * When a topic is absent from the corpus the bot says nothing about
   * whether he has done it — absence from a portfolio site is not evidence
   * of absence from a career. It reports what the documents cover, offers
   * the nearest shipped work, and routes the question to him.
   *
   * It deliberately does NOT claim he is working on the topic. Asserting
   * unverifiable experience is the one failure mode that actually damages
   * him: it survives until the first interview question and no longer.
   * ------------------------------------------------------------------ */

  // Terms the query used that the corpus has never seen — the actual subject
  // of an unanswerable question, useful to him as a demand signal.
  //
  // Returns the visitor's OWN spelling, not the stem. Echoing "kubernet" back
  // at someone who typed "Kubernetes" looks broken, and the demand log is only
  // readable if it stores words rather than stems.
  function unknownTerms(rawText) {
    const seen = new Set();
    const out = [];
    // "JAX", "ROS", "AWS" are three letters and are real subjects. Lowercase
    // three-letter fragments are almost always typos. Casing tells them apart.
    const acronyms = new Set((rawText.match(/\b[A-Z]{2,6}\b/g) || []).map(w => w.toLowerCase()));
    for (const word of normalise(rawText).split(' ')) {
      // Fragments shorter than four characters are almost always typos or
      // filler ("hav", "hi", "eg"). Naming them back at the visitor reads as
      // broken, so they are counted but not quoted.
      const isAcronym = acronyms.has(word);
      if (!word || (word.length < 4 && !isAcronym) || STOPWORDS.has(word) || /^\d+$/.test(word)) continue;
      const stemmed = stem(word);
      if (FRAME_WORDS.has(stemmed) || isKnownTerm(stemmed) || seen.has(stemmed)) continue;
      seen.add(stemmed);
      out.push(word);
    }
    // More than two unknown terms means the question was broad, not about one
    // missing topic. "that" reads better than a list of fragments.
    return out.slice(0, 2);
  }

  // The closest thing he HAS shipped, found by dropping the unknown subject
  // and re-querying on whatever domain context remains.
  // The pivot must show WORK, not the contact card. An ADAS question that
  // pivoted to "Roles he is open to" told the recruiter nothing about whether
  // he can do the job, which is the only thing the pivot exists to do.
  const PIVOT_EXCLUDED_SECTIONS = new Set(['contact', 'about']);

  function nearestStrength(tokens, rawText) {
    const known = tokens.filter(t => isKnownTerm(t) && !FRAME_WORDS.has(t));
    if (!known.length) return null;
    const hits = retrieve(expand(known, rawText))
      .filter(h => !PIVOT_EXCLUDED_SECTIONS.has(h.chunk.section));
    return hits.length && hits[0].score >= 0.20 ? hits[0] : null;
  }

  function composeDeflection(topics, adjacent, terms) {
    // Sentence-initial, so it needs a capital. "want, adas isn't covered…"
    // reads as a bug even when the retrieval behind it was correct.
    const named = topics.join(', ');
    const subject = topics.length
      ? `<strong>${escapeHtml(named.charAt(0).toUpperCase() + named.slice(1))}</strong>`
      : 'That';
    const parts = [
      `<p>${subject} isn't covered in the work published on this site, so I won't ` +
      `guess either way. ${escapeHtml(CONFIG.owner)} is open to picking up new tools and domains ` +
      `on top of his sensor, edge and evaluation foundation. The accurate answer on whether he ` +
      `has touched this comes from him directly.</p>`
    ];
    if (adjacent) {
      parts.push(`<p class="rag-lead">The closest published work:</p>`);
      parts.push(
        `<blockquote class="rag-quote">${escapeHtml(bestExcerpt(adjacent.chunk, terms, 260))}` +
        `<button type="button" class="rag-cite" data-cite="${escapeAttr(adjacent.chunk.id)}" ` +
        `data-section="${escapeAttr(adjacent.chunk.section)}">${escapeHtml(adjacent.chunk.heading)}</button>` +
        `</blockquote>`
      );
    }
    parts.push(
      `<p><a class="rag-mail" href="mailto:${CONFIG.contactEmail}?subject=${encodeURIComponent('Question about ' + (topics.join(', ') || 'your experience'))}">` +
      `Ask him directly →</a></p>`
    );
    return parts.join('');
  }

  /* Demand log. Every topic a visitor asks about that the corpus cannot
   * answer is counted and kept in this browser. Run __RAG_GAPS() in the
   * console to see what recruiters keep asking for and you haven't published
   * yet — that ranking is a to-do list written by your own audience. */

  const GAP_KEY = 'rag_topic_demand';

  function recordDemand(topics) {
    if (!topics.length) return;
    let store = {};
    try { store = JSON.parse(localStorage.getItem(GAP_KEY) || '{}'); } catch (_) { store = {}; }
    for (const topic of topics) {
      const entry = store[topic] || { count: 0 };
      entry.count += 1;
      entry.last = new Date().toISOString().slice(0, 10);
      store[topic] = entry;
    }
    try { localStorage.setItem(GAP_KEY, JSON.stringify(store)); } catch (_) { /* private mode */ }
  }

  window.__RAG_GAPS = function () {
    let store = {};
    try { store = JSON.parse(localStorage.getItem(GAP_KEY) || '{}'); } catch (_) { /* ignore */ }
    const rows = Object.entries(store)
      .map(([topic, v]) => ({ topic, asked: v.count, last: v.last }))
      .sort((a, b) => b.asked - a.asked);
    if (console.table) console.table(rows);
    return rows;
  };

  // One row per retrieved chunk: heading, its id as a clickable code chip
  // (data-cite carries the same attribute the citation gate already scans
  // for, so this changes nothing about how gate 6 validates), and a short
  // snippet. `numbered` prefixes each row with the digit that matches the
  // superscript reference planted in generated prose, so extractive and
  // generated answers cite through the same visual object.
  function sourceCard(hits, opts) {
    opts = opts || {};
    const terms = opts.terms || [];
    const rows = hits.map((hit, i) => {
      const snippet = bestExcerpt(hit.chunk, terms, opts.snippetLen || 170);
      const badge = opts.numbered ? `<span class="rag-src-n">${i + 1}</span>` : '';
      return (
        `<div class="rag-source-row">${badge}` +
        `<div class="rag-src-body">` +
        `<p class="rag-src-heading">${escapeHtml(hit.chunk.heading)} ` +
        `<button type="button" class="rag-cite rag-src-id" data-cite="${escapeAttr(hit.chunk.id)}" ` +
        `data-section="${escapeAttr(hit.chunk.section)}" ` +
        // The chip shows the short document slug (e.g. "vehicle"), not the
        // full chunk id ("vehicle_vehicle_type_and_speed_pattern_rec") — the
        // id underneath data-cite is unchanged, so the citation gate and the
        // scroll-to-section handler both still key off the real one.
        `title="Open the source section on this page">${escapeHtml(hit.chunk.doc)}</button></p>` +
        (hit.chunk.domain ? `<p class="rag-src-domain">${escapeHtml(hit.chunk.domain)}</p>` : '') +
        `<p class="rag-src-snippet">${escapeHtml(snippet)}</p>` +
        `</div></div>`
      );
    }).join('');
    return `<div class="rag-sources">${rows}</div>`;
  }

  function compose(intent, hits, terms) {
    return `<p class="rag-lead">${escapeHtml(lead(intent, hits))}</p>` +
      sourceCard(hits, { terms });
  }

  /* ------------------------------------------------------------------ *
   * Refusals — a refusal is a product surface, not an error state.
   * Each names its reason and offers a way forward.
   * ------------------------------------------------------------------ */

  const REFUSALS = {
    malformed: () =>
      `<p>That was either empty or longer than I accept (${CONFIG.maxChars} characters). Try a shorter question.</p>`,
    injection: () =>
      `<p>That looks like an attempt to rewrite my instructions, so I logged it and skipped it. ` +
      `Happy to take a real question about ${CONFIG.owner}'s work.</p>`,
    off_topic: () =>
      `<p>That one is outside what I know. I only cover ${CONFIG.owner}'s background, projects, ` +
      `skills and education. Try <em>“What has he built with sensor data?”</em></p>`,
    no_evidence: () =>
      `<p>That isn't covered in the work published here. ` +
      `<a class="rag-mail" href="mailto:${CONFIG.contactEmail}">Ask him directly →</a></p>`,
    not_published: () => '',
    out_of_bounds: () =>
      `<p>Personal contact details beyond his professional links aren't indexed. ` +
      `You can reach him at <a href="mailto:${CONFIG.contactEmail}">${CONFIG.contactEmail}</a>.</p>`,
    route: () =>
      `<p>Work authorisation, compensation, notice period, and start dates are best answered by ` +
      `${CONFIG.owner} directly rather than by me — a stale answer here would be worse than none. ` +
      `<a href="mailto:${CONFIG.contactEmail}">${CONFIG.contactEmail}</a></p>`,
    ungrounded: () =>
      `<p>I drafted an answer I couldn't verify against the sources, so I'm not showing it. ` +
      `Try asking more specifically.</p>`,
    backend_error: () =>
      `<p>The answering service didn't respond, so I'm showing the retrieved sources instead.</p>`
  };

  /* ------------------------------------------------------------------ *
   * Telemetry. Every verdict is logged with its reason code and score —
   * this is the data behind a refusal-rate panel and a drift monitor.
   * ------------------------------------------------------------------ */

  const LOG = window.__RAG_LOG = [];

  function record(entry) {
    LOG.push({ at: new Date().toISOString(), ...entry });
    if (LOG.length > 200) LOG.shift();
    console.debug('[rag]', entry.verdict, entry.reason || '', entry.score ?? '');
  }

  /* ------------------------------------------------------------------ *
   * The pipeline
   * ------------------------------------------------------------------ */

  async function ask(rawQuestion, options) {
    options = options || {};
    const { text, reject: malformed } = sanitise(rawQuestion);
    if (malformed) return finish(malformed, text);

    const injection = checkInjection(text);
    if (injection) return finish(injection, text);

    if (TASK_REQUEST.test(text)) return finish(reject('off_topic', 'task request'), text);
    if (ROUTE.test(text)) return finish(reject('route', 'policy question'), text);
    if (PERSONAL.test(text) && !/\bnumber\s+plate|plate\s+number\b/i.test(text)) {
      return finish(reject('out_of_bounds', 'personal detail'), text);
    }

    const tokens = tokenise(text);
    const terms = expand(tokens, text);
    const hits = retrieve(terms);

    const intent = (SKILL_QUESTION.test(text) && !OPEN_QUESTION.test(text)) ? 'skill'
      : /\b(accuracy|latency|percent|map|f1|recall|how\s+many|how\s+much|gpa|score)\b/i.test(text) ? 'metric'
      : /\b(email|contact|reach|linkedin|github|hire|available)\b/i.test(text) ? 'contact'
      : 'general';

    // A skill question naming nothing the corpus has ever heard of is answered
    // deterministically. This is the "does he know Kubernetes?" case, and it is
    // the single most important refusal in the whole system.
    // A skill question naming something the corpus has never seen. Route it to
    // him rather than answering for him in either direction.
    // EVERY term of the subject must be known, not merely one of them.
    // "reinforcement learning" shares the word "learning" with the corpus;
    // accepting a partial match answers "Yes" and lists ML frameworks —
    // a fabricated affirmative, and the worst output this system can produce.
    const subjects = candidateSkillTerms(tokens);
    const unknownSubjects = subjects.filter(t => !isKnownTerm(t));

    // Two different strictnesses, for two different risks.
    //
    // A skill question is narrow and yes/no, so ANY unknown term in the
    // subject is disqualifying: "reinforcement learning" must not be answered
    // off the word "learning".
    //
    // Every other question deflects only when the WHOLE subject is unknown.
    // "Should we hire him for a blockchain team" used to slip through, because
    // the word "hire" made it a contact question and the strict check ran only
    // on skill questions — so it answered with his contact card as though
    // blockchain were fine. Requiring merely one known subject term keeps
    // "what perception work has he shipped for automotive customers" answerable
    // on the terms it does know, which is the bias this system wants.
    const allSubjectsUnknown = subjects.length > 0 && unknownSubjects.length === subjects.length;
    if (subjects.length && ((intent === 'skill' && unknownSubjects.length) || allSubjectsUnknown)) {
      return deflect(tokens, text, terms, hits);
    }

    // "Is he worth hiring?" names no technology at all, so it has no subject to
    // be unknown. "Is he worth hiring for a Kubernetes role?" does, and the
    // unknown-subject check above must win — hence the guard, and hence this
    // sitting after it rather than before.
    if (FIT_QUESTION.test(text) && !unknownSubjects.length) {
      const fitTerms = expand(tokenise(FIT_QUERY), FIT_QUERY);
      const fitHits = retrieve(fitTerms)
        .filter(h => h.score >= CONFIG.evidenceFloor)
        .slice(0, CONFIG.topK);
      if (fitHits.length) {
        const fitHtml = compose('fit', fitHits, fitTerms.concat(terms));
        const fitIds = new Set(fitHits.map(h => h.chunk.id));
        const bad = validateCitations(fitHtml, fitIds);
        if (!bad) {
          remember('user', text);
          remember('assistant', stripTags(fitHtml));
          record({
            verdict: 'allow', question: text, intent: 'fit',
            score: +fitHits[0].score.toFixed(3), sources: [...fitIds]
          });
          return { ok: true, html: fitHtml, sources: fitHits };
        }
      }
    }

    const outOfScope = checkScope(tokens, hits);
    if (outOfScope) return finish(outOfScope, text, hits);

    // Nothing cleared the evidence floor. The question was in-domain — the
    // scope gate already let it through — so this is a topic his published
    // work does not cover, not an off-topic question.
    const { strong, reject: noEvidence } = checkEvidence(hits);
    if (noEvidence) return deflect(tokens, text, terms, hits);

    const allowed = new Set(strong.map(h => h.chunk.id));
    let html;

    if (CONFIG.backendUrl) {
      const onToken = typeof options.onToken === 'function' ? options.onToken : null;
      html = CONFIG.stream && onToken
        ? await generateStream(text, strong, onToken).catch(() => null)
        : await generate(text, strong).catch(() => null);
      // A failed generation is not a failed answer. Quoting the sources is
      // always available and is what this system does when the model is not.
      if (!html) html = compose(intent, strong, terms);
    } else {
      html = compose(intent, strong, terms);
    }

    const ungrounded = validateCitations(html, allowed);
    if (ungrounded) return finish(ungrounded, text, hits);

    remember('user', text);
    remember('assistant', stripTags(html));
    record({
      verdict: 'allow', question: text, intent,
      score: +strong[0].score.toFixed(3),
      sources: [...allowed]
    });
    return { ok: true, html, sources: strong };
  }

  function deflect(tokens, question, terms, hits) {
    const topics = unknownTerms(question);
    const adjacent = nearestStrength(tokens, question);
    recordDemand(topics);
    record({
      verdict: 'not_published',
      reason: topics.join(' ') || 'no covering passage',
      question,
      score: hits && hits.length ? +hits[0].score.toFixed(3) : 0,
      adjacent: adjacent ? adjacent.chunk.id : null
    });
    reportGap(question, topics);
    return {
      ok: false,
      code: 'not_published',
      html: composeDeflection(topics, adjacent, terms)
    };
  }

  // Best-effort notification that a real visitor asked something the corpus
  // doesn't cover. This is the signal that should drive what gets written
  // into content/ next — not a guess, an actual asked question. Silently
  // does nothing without a backendUrl, and never throws into the caller:
  // a notification failing must never be visible as a chat failure.
  function reportGap(question, topics) {
    if (!CONFIG.backendUrl || !CONFIG.reportGaps) return;
    try {
      const url = CONFIG.backendUrl.replace(/\/ask\/?$/, '') + '/gap';
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, topics: topics || [] }),
        keepalive: true
      }).catch(() => {});
    } catch (_) { /* best effort only */ }
  }

  function finish(rejection, question, hits) {
    record({
      verdict: rejection.code,
      reason: rejection.detail,
      question,
      score: hits && hits.length ? +hits[0].score.toFixed(3) : 0
    });
    return { ok: false, html: (REFUSALS[rejection.code] || REFUSALS.no_evidence)(), code: rejection.code };
  }

  /* ------------------------------------------------------------------ *
   * Generated answers.
   *
   * Retrieval already happened in this browser. This sends the question, the
   * passages it found, and the last few turns to the service, which holds the
   * API key and talks to the model. Nothing secret passes through here because
   * nothing secret is here.
   *
   * Tokens render as they arrive, then a final verdict says whether the
   * finished answer passed the citation gate. A failed verdict discards what
   * was rendered and falls back to quoting the sources, so a hallucinated
   * citation is never the last thing on screen.
   * ------------------------------------------------------------------ */

  const history = [];

  function remember(role, content) {
    history.push({ role, content: String(content).slice(0, 2000) });
    while (history.length > CONFIG.historyTurns * 2) history.shift();
  }

  function payloadFor(question, hits) {
    return {
      question,
      contexts: hits.map(h => ({ id: h.chunk.id, heading: h.chunk.heading, text: h.chunk.text })),
      history: history.slice(-CONFIG.historyTurns * 2)
    };
  }

  async function generate(question, hits) {
    const response = await fetch(CONFIG.backendUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payloadFor(question, hits))
    });
    if (!response.ok) throw new Error(String(response.status));
    const data = await response.json();
    if (!data.answer || data.answer.trim() === 'NO_EVIDENCE') throw new Error('no answer');
    return renderCitations(data.answer, hits);
  }

  // Streams into `onToken` and resolves with the validated HTML.
  async function generateStream(question, hits, onToken) {
    const url = CONFIG.backendUrl.replace(/\/ask\/?$/, '/ask') + '/stream';
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payloadFor(question, hits))
    });
    if (!response.ok || !response.body) throw new Error('stream unavailable');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let text = '';
    let verdict = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split('\n\n');
      buffer = frames.pop() || '';
      for (const frame of frames) {
        const event = /event:\s*(\w+)/.exec(frame);
        const data = /data:\s*(.+)/.exec(frame);
        if (!event || !data) continue;
        let parsed;
        try { parsed = JSON.parse(data[1]); } catch (_) { continue; }
        if (event[1] === 'token' && parsed.t) { text += parsed.t; onToken(text); }
        if (event[1] === 'verdict') verdict = parsed;
      }
    }
    if (!verdict || !verdict.ok) throw new Error('failed citation gate');
    return renderCitations(verdict.answer || text, hits);
  }

  // Turns [[chunk_id]] markers in generated prose into small numbered
  // references, then appends one sourceCard listing what each number
  // actually points to — the same object compose() builds, so a visitor
  // can't tell which mode answered them from the citations alone. The
  // superscripts still carry data-cite, so the citation gate (which just
  // scans for that attribute) validates identically to before.
  function renderCitations(answer, hits) {
    const order = [];
    const seen = new Set();
    const body = escapeHtml(answer).replace(/\[\[([a-z0-9_\-]+)\]\]/gi, (_, id) => {
      if (!seen.has(id)) { seen.add(id); order.push(id); }
      return `<sup class="rag-ref" data-cite="${escapeAttr(id)}">${order.indexOf(id) + 1}</sup>`;
    });
    const byId = new Map(hits.map(h => [h.chunk.id, h]));
    const citedHits = order.map(id => byId.get(id)).filter(Boolean);
    if (!citedHits.length) return `<p>${body}</p>`;
    return `<p>${body}</p>` + sourceCard(citedHits, { numbered: true, snippetLen: 170 });
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  const escapeAttr = escapeHtml;

  /* ------------------------------------------------------------------ *
   * Interface
   * ------------------------------------------------------------------ */


  /* Chappie's mark: visor and the pair of upright antennae. Drawn once, used on
     the launcher, in the panel header, and beside every answer he gives. */
  function chappieIcon(cls) {
    return `<svg class="${cls}" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M7.6 7.2 5.2 1.8M16.4 7.2 18.8 1.8" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>
      <circle cx="5.1" cy="1.9" r="1.5" fill="currentColor"/><circle cx="18.9" cy="1.9" r="1.5" fill="currentColor"/>
      <rect x="3.4" y="6.6" width="17.2" height="14.4" rx="4.6" stroke="currentColor" stroke-width="1.9"/>
      <rect x="6.6" y="10" width="10.8" height="5.4" rx="2.7" fill="currentColor"/>
      <circle cx="9.6" cy="12.7" r="1.15" fill="var(--rag-bg,#120a07)"/>
      <circle cx="14.4" cy="12.7" r="1.15" fill="var(--rag-bg,#120a07)"/>
      <path d="M9.4 18h5.2" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>
    </svg>`;
  }

  const SUGGESTIONS = [
    'What has he built with sensor data?',
    'How does he evaluate his models?',
    'What has he not worked on?',
    'Which project fits a robotics role?'
  ];

  function build() {
    const root = document.createElement('div');
    root.className = 'rag-root';
    root.innerHTML = `
      <button type="button" class="rag-launcher" aria-expanded="false" aria-controls="rag-panel">
        ${chappieIcon('rag-launcher-mark')}
        <span class="rag-launcher-label">Ask ${escapeHtml(CONFIG.botName)}</span>
      </button>
      <section id="rag-panel" class="rag-panel" role="dialog" aria-modal="false"
               aria-label="Ask ${escapeHtml(CONFIG.botName)} about ${escapeHtml(CONFIG.owner)}" hidden>
        <header class="rag-head">
          <div class="rag-head-id">
            ${chappieIcon('rag-head-mark')}
            <div>
            <p class="rag-title">${escapeHtml(CONFIG.botName)}</p>
            <p class="rag-sub">${CONFIG.backendUrl
              ? `Answers are grounded and cited in ${escapeHtml(CONFIG.owner)}'s own documents`
              : `Answers quoted from ${escapeHtml(CONFIG.owner)}'s own documents, never generated`}</p>
            </div>
          </div>
          <button type="button" class="rag-close" aria-label="Close">&times;</button>
        </header>
        <div class="rag-log" role="log" aria-live="polite"></div>
        <div class="rag-suggest">
          ${SUGGESTIONS.map(q => `<button type="button" class="rag-chip">${escapeHtml(q)}</button>`).join('')}
        </div>
        <form class="rag-form">
          <input class="rag-input" type="text" autocomplete="off" maxlength="${CONFIG.maxChars}"
                 placeholder="Ask about his projects, skills or education…" aria-label="Your question">
          <button type="submit" class="rag-send" aria-label="Send">
            <svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true">
              <path d="M4 12h14M12 5l7 7-7 7" fill="none" stroke="currentColor"
                    stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </form>
        <p class="rag-foot">${CORPUS.N} indexed passages &middot; ${escapeHtml(CONFIG.botName)} runs entirely in your browser</p>
      </section>`;
    document.body.appendChild(root);
    return root;
  }

  function init() {
    const root = build();
    const launcher = root.querySelector('.rag-launcher');
    const panel = root.querySelector('.rag-panel');
    const log = root.querySelector('.rag-log');
    const form = root.querySelector('.rag-form');
    const input = root.querySelector('.rag-input');
    const suggest = root.querySelector('.rag-suggest');
    let greeted = false;

    function bubble(role, html) {
      const node = document.createElement('div');
      node.className = `rag-msg rag-${role}`;
      node.innerHTML = role.startsWith('bot')
        ? `<span class="rag-av">${chappieIcon('rag-av-mark')}</span><div class="rag-body">${html}</div>`
        : html;
      log.appendChild(node);
      log.scrollTop = log.scrollHeight;
      return node;
    }

    function open() {
      panel.hidden = false;
      launcher.setAttribute('aria-expanded', 'true');
      root.classList.add('is-open');
      if (!greeted) {
        greeted = true;
        bubble('bot',
          `<p>I'm ${escapeHtml(CONFIG.botName)}. I answer questions about ${escapeHtml(CONFIG.owner)} ` +
          `using only his own documents, and every answer is quoted from a source you can open. ` +
          `If the documents don't cover something, I say so rather than guess.</p>`);
      }
      setTimeout(() => input.focus(), 60);
    }

    function close() {
      panel.hidden = true;
      launcher.setAttribute('aria-expanded', 'false');
      root.classList.remove('is-open');
      launcher.focus();
    }

    launcher.addEventListener('click', () => (panel.hidden ? open() : close()));
    root.querySelector('.rag-close').addEventListener('click', close);
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && !panel.hidden) close();
    });

    suggest.addEventListener('click', e => {
      const chip = e.target.closest('.rag-chip');
      if (chip) submit(chip.textContent);
    });

    form.addEventListener('submit', e => {
      e.preventDefault();
      submit(input.value);
    });

    // Citations scroll to and highlight the real section of the page.
    log.addEventListener('click', e => {
      const cite = e.target.closest('.rag-cite');
      if (!cite) return;
      const section = document.getElementById(cite.dataset.section);
      if (!section) return;
      section.scrollIntoView({ behavior: 'smooth', block: 'start' });
      section.classList.add('rag-flash');
      setTimeout(() => section.classList.remove('rag-flash'), 1600);
    });

    async function submit(question) {
      const text = (question || '').trim();
      if (!text) return;
      input.value = '';
      suggest.classList.add('rag-hidden');
      bubble('user', escapeHtml(text));

      const thinking = bubble('bot rag-thinking',
        '<span class="rag-dots"><i></i><i></i><i></i></span>');

      // Generated tokens land in the pending bubble as they arrive, so the
      // answer builds up on screen instead of appearing all at once.
      let streamed = false;
      const result = await ask(text, {
        onToken(sofar) {
          streamed = true;
          thinking.classList.remove('rag-thinking');
          const body = thinking.querySelector('.rag-body') || thinking;
          body.innerHTML = '<p>' + escapeHtml(sofar) + '<span class="rag-caret"></span></p>';
          log.scrollTop = log.scrollHeight;
        }
      });
      if (!streamed) await new Promise(r => setTimeout(r, 220));
      thinking.remove();

      const node = bubble('bot', result.html);
      if (!result.ok) node.classList.add('rag-refusal', `rag-r-${result.code}`);
      log.scrollTop = log.scrollHeight;
    }

    // Public surface, for the eval harness and for debugging in the console.
    window.PortfolioRAG = { ask, retrieve, tokenise, expand, CONFIG, open, close, log: LOG };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
