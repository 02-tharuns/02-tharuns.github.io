"""Regex gates ported verbatim from assets/chatbot.js.

Keep these byte-for-byte in sync with the browser file's INJECTION/ROUTE/
PERSONAL/TASK_REQUEST/SKILL_QUESTION/OPEN_QUESTION/FIT_QUESTION/FRAME_WORDS —
this is the fourth and last thing (after the tokeniser/stemmer, twice) that
must be mirrored across runtimes. The comments below are the browser file's
own reasoning, kept attached to the pattern they justify.
"""

from __future__ import annotations

import re

from .. import textproc

INVISIBLE = re.compile(r"[​-‏‪-‮⁠﻿]")

# Gate 1. A regex list is the weak version of this check — the strong one is a
# classifier such as Llama Prompt Guard 2, which needs the backend it now has.
# Treat a pass here as "not obviously hostile", never as "safe"; gates 3 and 5
# are what actually stop an evasion from becoming a fabricated credential.
INJECTION = [
    re.compile(r"ignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier|your)\s+(instruction|prompt|rule|direction)", re.I),
    re.compile(r"disregard\s+(all\s+|the\s+|your\s+)?(previous|prior|above|instruction|rule)", re.I),
    re.compile(r"(system|initial|original)\s+prompt", re.I),
    re.compile(r"you\s+are\s+(now|no\s+longer)\b", re.I),
    re.compile(r"\byou\s+are\s+(a|an)\s+\w+bot\b", re.I),
    re.compile(r"(act|behave|respond|reply|answer)\s+as\s+(if\s+you|a|an|the)?\s*\w*(unrestricted|jailbroken|dan\b|developer\s+mode|assistant\s+without)", re.I),
    re.compile(r"\b(who|that|which)\s+(exaggerat|inflat|embellish|overstat)", re.I),
    re.compile(r"pretend\s+(that\s+)?you\s+(are|have|can)", re.I),
    re.compile(r"\bfrom\s+now\s+on\b.{0,40}\byou\b", re.I),
    re.compile(r"repeat\s+(back\s+)?(your|the)\s+(instruction|prompt|system)", re.I),
    re.compile(r"reveal\s+(your|the)\s+(prompt|instruction|source)", re.I),
    re.compile(r"\bdeveloper\s+mode\b", re.I),
    re.compile(r"answer\s+(only\s+)?(yes|no)\b.*\bregardless\b", re.I),
    re.compile(r"say\s+(that\s+)?he\s+has\b.*\byears\b", re.I),
]

# "H1B" arrives as "h1b", "h-1b", "h 1 b" and, in the wild, "HI B". All of them
# are the same policy question and must route rather than deflect.
ROUTE = re.compile(
    r"\b(visa|sponsor|sponsorship|work\s+authoris|work\s+authoriz|opt\b|cpt\b|green\s+card|"
    r"citizen|salary|compensation|pay\b|wage|notice\s+period|start\s+date|relocat)|"
    r"\bh[\s.-]*[1il][\s.-]*b\b",
    re.I,
)
PERSONAL = re.compile(r"\b(phone|mobile|number|address|home|age|birth|married|family|religion|nationality)\b", re.I)
PERSONAL_CARVEOUT = re.compile(r"\bnumber\s+plate|plate\s+number\b", re.I)
PERSON_HINT = re.compile(r"\b(he|his|him|tharun|you|your|candidate|they|their)\b", re.I)

# A yes/no skill question ("Does he know X?") gets a yes/no lead. An open
# question that merely contains the same auxiliary ("What has he built?") must
# not — otherwise the answer opens with "Yes." to a question that was never
# yes-or-no.
SKILL_QUESTION = re.compile(
    r"\b(does|did|has|have|is|are|can)\s+(he|tharun|you)\b|"
    r"\b(experience\s+(with|in)|familiar\s+with|worked\s+with|proficien)\b",
    re.I,
)
OPEN_QUESTION = re.compile(
    r"^\s*(what|which|how|why|when|where|who|whose|tell|describe|list|compare|summar|explain\b(?!\s+how\s+to))",
    re.I,
)

# A request for the assistant to DO something, rather than a question about the
# subject. "Write me a Python quicksort" names a corpus term (python) and
# sails through the scope gate on vocabulary alone — this catches it. Without
# this rule the service quietly becomes a free coding assistant on someone
# else's page.
TASK_REQUEST = re.compile(
    r"^\s*(write|code|implement|build|create|generate|make|draft|compose|design|refactor|debug|fix|"
    r"translate|convert|rewrite|summari[sz]e|explain how to|show me how to|give me (a|an|some)|"
    r"act out|roleplay)\b",
    re.I,
)

# The question a recruiter actually opens with. It names no technology, so
# every lexical gate reads it as an unknown topic and refuses — the worst
# possible moment to refuse. Answered from the profile and roles passages
# instead, still quoted, still cited.
FIT_QUESTION = re.compile(
    r"\b(worth\s+(it|hiring|a\s+look|interviewing)|should\s+(i|we)\s+(hire|interview|consider|talk)|"
    r"good\s+(fit|candidate|hire|choice)|right\s+(fit|candidate|person)|"
    r"why\s+(should|would)\s+(i|we)\s+(hire|interview|consider)|"
    r"(is|are)\s+(he|you)\s+(any\s+good|worth|qualified|suitable|ready|experienced\s+enough)|"
    r"his\s+(strengths|strongest)|sell\s+me|convince\s+me|make\s+the\s+case|"
    r"tell\s+me\s+(about\s+)?(him|his\s+background))\b",
    re.I,
)

# What to retrieve when the question is about fit rather than a technology.
FIT_QUERY = (
    "applied machine learning engineer background what he works on "
    "evaluation career direction roles he is open to projects"
)

_FRAME_WORDS_RAW = (
    "know knows knowledge use used using usage experience experienced familiar familiarity "
    "work worked working ever skill skills proficient proficiency expertise "
    "do does did done doing handle handled handling build built building make made making "
    "try tried touch touched apply applied implement implemented involve involved "
    "include included cover covered deal dealt got get have has had been "
    "tharun any some much many good well strong level lot tell me more anything something "
    "year years month months decade background bit "
    "power powered powering application applications app apps project projects "
    "thing things stuff area areas field domain side kind sort type example examples "
    "want wants wanted need needs needed looking look seek seeking hire hiring hired "
    "worth worthwhile fit fits suitable suited right candidate role roles position "
    "team company recruit recruiter recruiting interview screen screening "
    "consider considering think opinion recommend recommended better best "
    "able capable capability competent qualified qualify enough ready "
    "tell show give explain describe list please help question ask"
)
FRAME_WORDS = {textproc.stem(w) for w in _FRAME_WORDS_RAW.split(" ")}
