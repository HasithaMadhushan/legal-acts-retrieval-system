from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    LAWYER = "LAWYER"
    GENERAL_USER = "GENERAL_USER"


class ProcessingStatus(str, Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    VERIFIED = "VERIFIED"


class ParserName(str, Enum):
    DOCLING = "DOCLING"
    PYMUPDF = "PYMUPDF"
    OCR = "OCR"
    MANUAL = "MANUAL"
    UNKNOWN = "UNKNOWN"


class SectionType(str, Enum):
    SECTION = "SECTION"
    SUBSECTION = "SUBSECTION"
    PARAGRAPH = "PARAGRAPH"
    SCHEDULE = "SCHEDULE"
    PART = "PART"
    PREAMBLE = "PREAMBLE"
    OTHER = "OTHER"


class VerificationStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class RelationshipType(str, Enum):
    REFERS_TO = "REFERS_TO"
    AMENDS = "AMENDS"
    REPEALS = "REPEALS"
    INSERTS = "INSERTS"
    SUBSTITUTES = "SUBSTITUTES"
    ADDS = "ADDS"
    COMMENCES = "COMMENCES"
    DEFINES = "DEFINES"
    CROSS_REFERENCE = "CROSS_REFERENCE"
    UNKNOWN = "UNKNOWN"


class ExtractionMethod(str, Enum):
    REGEX = "REGEX"
    NLP_RULE = "NLP_RULE"
    MANUAL = "MANUAL"


class ProcessingJobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SavedItemType(str, Enum):
    ACT = "ACT"
    SECTION = "SECTION"
    REFERENCE = "REFERENCE"
