import re

from app.core.roles import RelationshipType

RELATIONSHIP_PHRASES: dict[RelationshipType, tuple[str, ...]] = {
    RelationshipType.AMENDS: (
        "amended by",
        "is amended",
        "shall be amended",
        "amendment of section",
        "principal enactment is hereby amended",
    ),
    RelationshipType.REPEALS: (
        "is hereby repealed",
        "shall be repealed",
        "repeal of",
        "is repealed",
    ),
    RelationshipType.INSERTS: (
        "following new section is inserted",
        "inserted immediately after section",
        "there shall be inserted",
        "is inserted",
    ),
    RelationshipType.SUBSTITUTES: (
        "by the substitution for",
        "substitution therefor",
        "is substituted by",
        "following section is substituted",
        "substitute therefor",
        "substituted therefor",
    ),
    RelationshipType.ADDS: (
        "by the addition immediately after",
        "addition immediately after",
        "following new paragraph",
        "following new item",
        "there shall be added",
    ),
    RelationshipType.CROSS_REFERENCE: (
        "referred to in section",
        "subject to section",
        "in accordance with section",
        "under section",
        "for the purposes of section",
        "subject to the provisions of",
    ),
}

ACT_CITATION_RE = re.compile(
    r"(?P<title>[A-Z][A-Za-z0-9\s,&.'()/-]{3,120}?)\s+Act,?\s+No\.?\s*"
    r"(?P<number>\d+)\s+of\s+(?P<year>\d{4})",
    re.I,
)
ACT_TITLE_RE = re.compile(r"(?P<title>[A-Z][A-Za-z0-9\s,&.'()/-]{3,120}?)\s+Act\b", re.I)
AMENDING_ACT_RE = re.compile(
    r"\bAn\s+Act\s+(?:to\s+)?Amend\s+(?:the\s+)?"
    r"(?P<title>[A-Z][A-Za-z0-9\s,&.'()/-]{3,160}?"
    r"(?:Act|Ordinance))"
    r"(?:,?\s+No\.?\s*(?P<number>\d+)\s+of\s+(?P<year>\d{4}))?"
    r"(?:\s*\((?P<chapter>Chapter\s+\d+[A-Z]?)\))?",
    re.I,
)
SECTION_OF_ACT_AMENDED_RE = re.compile(
    r"\bSection\s+(?P<section>\d+[A-Z]*)\s+of\s+the\s+"
    r"(?P<title>[A-Z][A-Za-z0-9\s,&.'()/-]{3,160}?\s+Act)"
    r",?\s+No\.?\s*(?P<number>\d+)\s+of\s+(?P<year>\d{4})"
    r"(?P<trailing>.{0,120}?\bis\s+hereby\s+amended\b)",
    re.I | re.S,
)
PRINCIPAL_SECTION_AMENDED_RE = re.compile(
    r"\bSection\s+(?P<section>\d+[A-Z]*)\s+of\s+the\s+principal\s+enactment"
    r"(?P<trailing>.{0,120}?\bis\s+hereby\s+amended\b)",
    re.I | re.S,
)
NEW_SECTION_INSERT_RE = re.compile(
    r"\bfollowing\s+new\s+section\s+is\s+hereby\s+inserted\s+immediately\s+after\s+"
    r"section\s+(?P<after>\d+[A-Z]*)"
    r"(?P<trailing>.{0,500}?\bshall\s+have\s+effect\s+as\s+section\s+"
    r"(?P<section>\d+[A-Z]*))",
    re.I | re.S,
)
EFFECT_AS_SECTION_RE = re.compile(
    r"\bshall\s+have\s+effect\s+as\s+section\s+(?P<section>\d+[A-Z]*)",
    re.I,
)
REPEAL_PARAGRAPH_RE = re.compile(
    r"\bby\s+the\s+repeal\s+of\s+paragraph\s+\((?P<paragraph>[a-z])\)\s+of\s+"
    r"subsection\s+\((?P<subsection>\d+[A-Z]?)\)",
    re.I,
)
SUBSTITUTION_RE = re.compile(
    r"\b(?:by\s+the\s+substitution\s+for|substitution\s+therefor|substituted\s+therefor)"
    r"(?P<trailing>.{0,180})",
    re.I | re.S,
)
ADDITION_RE = re.compile(
    r"\b(?:by\s+the\s+addition\s+immediately\s+after|addition\s+immediately\s+after)"
    r"\s+(?P<target_type>paragraph|item|section)\s+"
    r"(?P<target>(?:\([a-z0-9]+\)|\d+[A-Z]*))"
    r"(?P<trailing>.{0,180})",
    re.I | re.S,
)
NEW_PARAGRAPH_ITEM_RE = re.compile(
    r"\bof\s+the\s+following\s+new\s+(?P<target_type>paragraph|item)\b"
    r"(?P<trailing>.{0,180})",
    re.I | re.S,
)
SCHEDULE_AMENDMENT_RE = re.compile(
    r"\bThe\s+(?P<schedule>(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|"
    r"Ninth|Tenth)\s+Schedule)\s+to\s+the\s+principal\s+enactment"
    r"(?P<trailing>.{0,120}?\bis\s+hereby\s+amended\b)",
    re.I | re.S,
)
CHAPTER_RE = re.compile(r"\bChapter\s+(?P<chapter>\d+[A-Z]?)\b", re.I)
SECTION_RE = re.compile(
    r"\b(?:section|sections|s\.|sec\.)\s+(?P<section>\d+[A-Z]*(?:\([^)]+\))?)",
    re.I,
)
SUBSECTION_RE = re.compile(r"\bsubsection\s+\((?P<subsection>\d+[A-Z]*)\)", re.I)
PARAGRAPH_RE = re.compile(r"\bparagraph\s+\((?P<paragraph>[a-z])\)", re.I)
ITEM_RE = re.compile(r"\bitem\s+(?P<item>\d+[A-Z]*)\b", re.I)
SCHEDULE_RE = re.compile(
    r"\b(?P<schedule>(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|"
    r"Tenth)?\s*Schedule\s*[IVXLCDM]*)\b",
    re.I,
)
