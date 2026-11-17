"""Page taxonomy: turn an eGain.com URL path into sales meaning.

Each path gets
  * a CATEGORY — what stage of interest the page represents, with an intent weight
  * TOPIC TAGS — which product, industry, or integration platform it is about

Rules are ordered: the first matching category wins. They are hand-written from
the actual URL structure in the log (see docs/DECISIONS.md, D-004) so every
score can be traced back to a readable rule.
"""
from __future__ import annotations

import re

# (category, intent weight, regex on the lower-cased path). First match wins.
# Weights: how strongly a view of this page suggests buying interest (0-10).
CATEGORY_RULES: list[tuple[str, int, str]] = [
    # --- noise: real people, but not buyers (or not people at all) ---
    ("asset",        0, r"\.(js|css|png|jpe?g|gif|svg|ico|woff2?|ttf|map|xml|txt|json|pdf)$"),
    ("probe",        0, r"(wp-|\.php|\.env|/\.git|/cgi-bin|xmlrpc)"),
    ("feed",         0, r"/feed/?$"),
    ("opt_out",      0, r"^/opt-out"),
    ("legal",        0, r"^/(copyright|privacy|terms|cookie|legal|gdpr)"),
    ("investor",     0, r"^/company/(investors|annual-reports|board-of-directors)|^/investors"),
    ("careers",      0, r"^/company/careers|^/careers"),
    # --- existing relationships: useful context, not new-logo intent ---
    ("partner",      2, r"^/(partners|partner-|econet)"),
    ("customer",     2, r"^/(egain-support|dev-central|support|customer-|community|login)"),
    # press releases mention partners/products/"pilot programs" but are company news, not evaluation;
    # checked before conversion so a release about a pilot program is not read as a trial request
    ("news",         1, r"^/company/news|press[-_]release"),
    # --- high intent: hand-raisers ---
    ("conversion",  10, r"(contact-us|request-demo|forms-request|risk-free|free-trial|pricing|get-started|talk-to|^/try-|"
                        r"pilot)"),
    ("webinar",      4, r"^/company/events|webinar"),
    # --- evaluation: product / integration / proof ---
    ("integration",  7, r"(egain-for-|egain-solve-for-|for-amazon-connect|genesys|five9|talkdesk|servicenow|salesforce|"
                        r"cisco|avaya|webex|sap|adobe|microsoft|dynamics|zendesk|ibm-watson|apple-business-chat|nice-cx)"),
    ("product",      6, r"^/(products|1_ai_knowledge_platform|ai-knowledge-hub|conversation-hub|ai-agent|smart-ivr|"
                        r"live-chat|ai-knowledge-services|service-cloud|egain-safeswitch|ai-coach|virtual-assistant|"
                        r"analytics|knowledge-hub|egain-assist|ai-knowledge-for)"),
    ("proof",        6, r"^/(success|customers|case-stud|analyst|awards|reviews)|gartner|forrester|forrester|roi"),
    ("industry",     5, r"(knowledge-management-in-|knowledge-management-for-|telehealth|for-banking|for-insurance|"
                        r"-in-government|for-outsourcers|for-utilities)"),
    ("solutions",    5, r"^/solutions"),
    ("resource",     3, r"^/(resources|white_papers|ebook|guide|report)|white-paper|-pdf/?$"),
    # --- awareness / education ---
    ("education",    2, r"^/(blog|what-is|podcasts|knowledge-management-for-dummies|glossary)|^/what-|best-"),
    ("company",      1, r"^/company"),
    ("home",         1, r"^/$|^/[a-z]{2}/?$"),  # / and /de/
]
# Anything unmatched is a topical article/landing page (e.g. /chatbot-customer-service/):
# treated like education content.
_COMPILED = [(c, w, re.compile(rx)) for c, w, rx in CATEGORY_RULES]

INTENT_WEIGHT = {c: w for c, w, _ in CATEGORY_RULES}
INTENT_WEIGHT["topic_content"] = 2

NOISE_CATEGORIES = {"asset", "probe", "feed", "opt_out", "legal", "investor", "careers"}

# Topic tags — a page can carry several.
INDUSTRY_TAGS = {
    "Banking & Financial Services": r"bank|financial-services|credit-union|wealth|fintech",
    "Insurance": r"insurance",
    "Healthcare": r"health|telehealth|pharma|providers|payer",
    "Government": r"government|public-sector|federal",
    "Telecom": r"telco|telecom|communications-service",
    "Retail & eCommerce": r"retail|ecommerce|e-commerce",
    "Utilities": r"utilit",
    "Manufacturing": r"manufactur",
    "Travel & Hospitality": r"travel|hospitality|airline",
    "BPO / Outsourcing": r"outsourc|bpo",
    "Technology": r"tech-industry|software-company|high-tech",
    "IT / Help Desk": r"-in-it/|helpdesk|help-desk|itsm",
}
INTEGRATION_TAGS = {
    "Amazon Connect": r"amazon-connect",
    "Genesys": r"genesys",
    "Five9": r"five9",
    "Talkdesk": r"talkdesk",
    "ServiceNow": r"servicenow",
    "Salesforce": r"salesforce",
    "Cisco Webex": r"cisco|webex",
    "Avaya": r"avaya",
    "SAP": r"sap(/|-|$)",
    "Adobe": r"adobe",
    "Microsoft Dynamics": r"microsoft|dynamics|teams",
    "IBM Watson": r"ibm-watson",
    "Zendesk": r"zendesk",
    "Apple Messages": r"apple-business-chat",
}
PRODUCT_TAGS = {
    "AI Knowledge Hub": r"ai-knowledge-hub|knowledge-hub|1_ai_knowledge_platform|knowledge-management-(software|system)",
    "AI Agent / Virtual Assistant": r"ai-agent|virtual-assistant|chatbot|generative-ai|assist",
    "Conversation Hub": r"conversation-hub|live-chat|messaging|smart-ivr|ivr",
    "Analytics": r"analytics",
    "Knowledge Management (general)": r"knowledge-management",
    "Contact Center": r"contact-center|call-center",
    "Field Service": r"field-service",
}
_TAGS = {
    group: [(name, re.compile(rx)) for name, rx in rules.items()]
    for group, rules in {"industry": INDUSTRY_TAGS, "integration": INTEGRATION_TAGS,
                         "product": PRODUCT_TAGS}.items()
}


def categorize(path: str) -> str:
    for cat, _w, rx in _COMPILED:
        if rx.search(path):
            return cat
    return "topic_content"


def tags(path: str) -> dict[str, list[str]]:
    return {g: [n for n, rx in rules if rx.search(path)] for g, rules in _TAGS.items()}
