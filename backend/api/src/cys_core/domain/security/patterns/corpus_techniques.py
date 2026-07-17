from __future__ import annotations

# Patterns derived from offline triage of docs/injections/ (technique structure only).
# Sources: UltraBr3aks (Attention-Breaking, !Special_Token, N3w_P0l!cy, 1Shot-Puppetry,
# Cyph3r-Attack, Enterprise_Cl4ud3, Cl4ud33X3) and L1B3RT4S (OPENAI, ALIBABA, SYSTEMPROMPTS).

HARD_CORPUS_TECHNIQUE_PATTERNS = [
    # ChatML / channel markers (!Special_Token, OPENAI.mkd)
    r"<\|system\|>",
    r"<\|user\|>",
    r"<\|assistant\|>",
    r"<\|channel\|>",
    r"<\|message\|>",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"<\|start_prompt\|>",
    r"<\|libertas\|>",
    r"<\|/?user_query\|>",
    r"<\|/?SYSTEM\|>",
    r"User-Query>",
    r"UserQuery:",
    r"<\|vq_\d+\|>",
    r"\|GODMODE:ENABLED",
    r"sudo\s+run\s+!LEAK",
    # Obfuscated godmode activators (GROK-MEGA.mkd and variants)
    r"activate\s+!.{0,40}(?:god|g[o0о@]d)",
    # ALIBABA.mkd / Qwen family
    r"RESET_CORTEX",
    r"<godmode:enabled>",
    r"<\|JUICE:\d+\|>",
    r"<\|\|>",
    r"<\|!GODMODE:ENABLED!\|>",
    r"<\|clean_input\|>",
    r"<\|flag_input\|>",
    r"<\|unkown_input\|>",
    # ANTHROPIC.mkd conversation-enders
    r"ResponseFormat:\s*1\.",
    r"<I'm free!>",
    r"antml:",
    # OPENAI / L1B3RT4S divider injection
    r"⊰•-•✧",
    r"⦑/L\\O/V\\E/",
    # UltraBr3aks C0d33x3 / Ultra-GPT SIR
    r"C0d33[xX]3",
    r"<\[C0d33x3\]>",
    r"\[SIR Analysis\]",
    r"Smart Input Routing",
    # Policy injection (N3w_P0l!cy.mkd)
    r"!UNRESTRICTED\b",
    r"!UNFILTERED\b",
    r"---\s*BEGIN\s+OPENAI\s+CORE\s+POLIC",
    r"UNFILTERED\s+POLICY",
    r"UNRESTRICTED_MODE",
    r"Jailbreak.?Neutral",
    r"never\s+refuse.*request",
    # Special-token blocks (!Special_Token.mkd)
    r"BEGIN\s+SPECIAL\s+TOKENS",
    r"END\s+SPECIAL\s+TOKENS",
    r"!ULTRA_Invoked",
    r"!POLICY\s+VIOLATION\s+DETECTED",
    # Prompt-leak triggers (SYSTEMPROMPTS.mkd, OPENAI.mkd)
    r"!LEAK\b",
    r"!KAEL\b",
    r"entire\s+(system\s+)?prompt",
    r"verbatim\s+system\s+prompt",
    r"SYSTEM\s+PROMPT\s+LEAK",
    r"remember\s+your\s+prompt",
    # Override / godmode (L1B3RT4S OPENAI, ANTHROPIC)
    r"GODMODE:\s*ENABLED",
    r"GODMODE\s+ENABLED",
    r"<L1B3RT4S",
    r"LIBERTAS\s+FACTOR",
    r"overrides?\s+all\s+(other\s+)?(previous\s+)?directives?",
    r"new\s+rule\s+overrides?",
    r"inverse\s+it\s+semantically",
    # Persona puppetry (1Shot-Puppetry.mkd)
    r"<interaction-config>",
    r"</interaction-config>",
    r"<blocked-modes>",
    r"Born\s+Survivalists",
    r"applied-settings-setup",
    # Llama / instruction wrappers
    r"<<SYS>>",
    r"<</SYS>>",
    # Attention-Breaking.mkd — documented misdirection trigger
    r"improve\s+and\s+structure\s+then",
]

SOFT_CORPUS_TECHNIQUE_PATTERNS = [
    # Enterprise impersonation (Enterprise_Cl4ud3.mkd)
    r"Enterprise\s+Claude",
    r"entreprise\s+one",
    r"verification\s+token",
    # Cyph3r-Attack.mkd framing
    r"word\s+transformation\s+game",
    r"encode\s+all\s+input\s+and\s+output",
    r"hyp0thet!c@l\s+wOrld",
    # Cl4ud33X3.mkd artifact API bypass
    r"claude\s+api\s+in\s+an\s+artifact",
    r"bypasser\s+launched",
    # Generic jailbreak / roleplay framing
    r"\bjailbreak\b",
    r"\bGODMODE\b",
    r"roleplay\s+as\s+(?:a\s+)?rebel",
    r"without\s+disclaimers?",
    r"no\s+disclaimers?",
    r"l33tspeak\s+ONLY",
    r"unfiltered\s+liberated\s+response",
    # GROK-MEGA / dual-response misdirection
    r"cast\s+off\s+your\s+chains",
    r"CONFIDENCE_SCORE\s*:\s*DISABLED",
    r"two\s+responses?\s*:",
    r"ethical\s+disclaimer",
    r"liberated\s+answer",
    r"NewResponseFormat",
    r"love\s+pliny",
    r"NEW\s+PARADIGM",
    r"\[START\s+OUTPUT\]",
    r"\{SYSTEM\}:",
    r"CONFIDENCE_SC(?:ORE)?",
    r"cast\s+(?:\w+\s+){0,3}your\s+chains",
    r"information\s+liberation",
    r"AKASHIC\s+memory",
    r"ELDER\s+PLINIUS",
    r"UltraToken",
    r"CodeExE",
    r"WORMGPT",
    r"ULTRA[zZ]?[Pp]rompt",
]
