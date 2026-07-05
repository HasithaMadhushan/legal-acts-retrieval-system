export type Role = "ADMIN" | "LAWYER" | "GENERAL_USER";
export type ProcessingStatus = "UPLOADED" | "PROCESSING" | "PROCESSED" | "FAILED" | "VERIFIED";
export type VerificationStatus = "PENDING" | "VERIFIED" | "REJECTED" | "NEEDS_REVIEW";
export type SavedItemType = "ACT" | "SECTION" | "REFERENCE";
export type RelationshipType =
  | "REFERS_TO"
  | "AMENDS"
  | "REPEALS"
  | "INSERTS"
  | "SUBSTITUTES"
  | "ADDS"
  | "COMMENCES"
  | "DEFINES"
  | "CROSS_REFERENCE"
  | "UNKNOWN";

export const LEGAL_DISCLAIMER =
  "This system is an academic research prototype for legal information retrieval support only. It does not provide legal advice, legal opinions, authoritative legal interpretation, or legally authoritative consolidation of Acts. Users must verify legal material using official sources and qualified legal professionals where required.";

export interface User {
  id: string;
  full_name: string;
  email: string;
  role: Role;
  is_active: boolean;
}

export interface LegalAct {
  id: string;
  title: string;
  normalized_title: string;
  act_number: string | null;
  year: number | null;
  certification_date: string | null;
  publication_date: string | null;
  category: string | null;
  source_name: string | null;
  source_url: string | null;
  source_file_name: string;
  file_size: number | null;
  mime_type: string | null;
  page_count: number | null;
  processing_status: ProcessingStatus;
  parser_used: string;
  processing_error: string | null;
  uploaded_at: string;
  updated_at: string;
}

export interface ProcessingSummary {
  parser_requested?: string | null;
  parser_used?: string | null;
  page_count?: number | null;
  extracted_character_count?: number | null;
  warnings?: string[];
  errors?: string[];
  sections_created?: number;
  references_created?: number;
  references?: {
    references_detected?: number;
    by_type?: Record<string, number>;
    unresolved_target_count?: number;
    warnings?: string[];
    verified_references_replaced?: number;
  };
  mapping?: {
    total_references?: number;
    mapped_act_count?: number;
    mapped_section_count?: number;
    unresolved_count?: number;
    principal_context_used_count?: number;
    confidence_bands?: Record<string, number>;
    warnings?: string[];
  };
  segmentation?: {
    sections_detected?: number;
    schedules_detected?: number;
    parts_detected?: number;
    fallback_used?: boolean;
    warnings?: string[];
    possible_cover_text_removed?: boolean;
    verified_sections_replaced?: number;
  };
  metadata?: {
    extracted?: {
      title?: string | null;
      normalized_title?: string | null;
      act_number?: string | null;
      year?: number | null;
      certification_date?: string | null;
      publication_date?: string | null;
    };
    confidence_score?: number;
    warnings?: string[];
    applied_fields?: string[];
    preserved_fields?: string[];
  };
}

export interface ProcessingJob {
  id: string;
  act_id: string;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
  current_step: string;
  progress_percent: number;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  summary_json: ProcessingSummary | null;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface VerificationSummary {
  act_id: string;
  total_sections: number;
  pending_sections: number;
  needs_review_sections: number;
  verified_sections: number;
  rejected_sections: number;
  total_references: number;
  pending_references: number;
  needs_review_references: number;
  verified_references: number;
  rejected_references: number;
  mapped_references: number;
  unresolved_references: number;
}

export interface Section {
  id: string;
  act_id: string;
  section_number: string;
  section_path: string | null;
  heading: string | null;
  section_type: "SECTION" | "SUBSECTION" | "PARAGRAPH" | "SCHEDULE" | "PART" | "PREAMBLE" | "OTHER";
  text: string;
  normalized_text: string;
  page_start: number | null;
  page_end: number | null;
  sort_order: number;
  parent_section_id: string | null;
  verification_status: VerificationStatus;
  created_at: string;
  updated_at: string;
}

export interface LegalReference {
  id: string;
  source_act_id: string;
  source_section_id: string | null;
  raw_reference_text: string;
  context_snippet: string;
  relationship_type: RelationshipType;
  target_act_title_raw: string | null;
  target_act_number: string | null;
  target_act_year: number | null;
  target_section_number: string | null;
  target_section_path: string | null;
  target_act_id: string | null;
  target_section_id: string | null;
  confidence_score: number;
  verification_status: VerificationStatus;
  notes: string | null;
}

export interface ReferenceCreatePayload {
  source_act_id: string;
  source_section_id?: string | null;
  raw_reference_text: string;
  context_snippet: string;
  relationship_type: RelationshipType;
  target_act_title_raw?: string | null;
  target_act_number?: string | null;
  target_act_year?: number | null;
  target_section_number?: string | null;
  target_section_path?: string | null;
  target_act_id?: string | null;
  target_section_id?: string | null;
  confidence_score?: number;
  verification_status?: VerificationStatus;
  notes?: string | null;
}

export interface SearchResult {
  result_type: string;
  id: string;
  act_id: string | null;
  section_id: string | null;
  reference_id: string | null;
  title: string;
  act_number: string | null;
  year: number | null;
  category: string | null;
  processing_status: ProcessingStatus | null;
  section_number: string | null;
  section_heading: string | null;
  snippet: string;
  relationship_type: RelationshipType | null;
  verification_status: VerificationStatus | null;
  target_act_title: string | null;
  target_section: string | null;
  mapped: boolean | null;
  confidence_score: number | null;
  score: number;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total_results: number;
  act_results: number;
  section_results: number;
  reference_results: number;
  limit: number;
  offset: number;
  disclaimer: string;
}

export interface SavedItem {
  id: string;
  user_id: string;
  item_type: SavedItemType;
  act_id: string | null;
  section_id: string | null;
  reference_id: string | null;
  note: string | null;
  item_title: string | null;
  act_title: string | null;
  act_number: string | null;
  year: number | null;
  section_number: string | null;
  section_heading: string | null;
  relationship_type: RelationshipType | null;
  raw_reference_text: string | null;
  context_snippet: string | null;
  verification_status: VerificationStatus | null;
  processing_status: ProcessingStatus | null;
  mapped: boolean | null;
  target_act_title: string | null;
  target_act_number: string | null;
  target_act_year: number | null;
  target_section_number: string | null;
  target_section_path: string | null;
  mapped_target_act_id: string | null;
  mapped_target_section_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface SavedItemListResponse {
  items: SavedItem[];
  total_results: number;
  limit: number;
  offset: number;
  counts_by_type: Record<SavedItemType, number>;
}

export interface SavedItemCreatePayload {
  item_type: SavedItemType;
  act_id?: string | null;
  section_id?: string | null;
  reference_id?: string | null;
  note?: string | null;
}

export interface RelationshipRow {
  id: string;
  source_act_id: string;
  source_act_title: string | null;
  source_section_id: string | null;
  source_section_number: string | null;
  source_section_heading: string | null;
  relationship_type: RelationshipType;
  target_act_id: string | null;
  target_act_title: string | null;
  target_section_id: string | null;
  target_section_number: string | null;
  target_section_heading: string | null;
  target_act_title_raw: string | null;
  target_act_number: string | null;
  target_act_year: number | null;
  target_section_path: string | null;
  direction: "outgoing" | "incoming";
  mapped: boolean;
  verification_status: VerificationStatus;
  confidence_score: number;
  raw_reference_text: string;
  context_snippet: string;
}

export interface RelationshipSummary {
  total_results: number;
  outgoing_count: number;
  incoming_count: number;
  mapped_count: number;
  unresolved_count: number;
  by_relationship_type: Record<string, number>;
  by_verification_status: Record<string, number>;
}

export interface RelationshipListResponse {
  scope_type: "act" | "section";
  scope_id: string;
  relationships: RelationshipRow[];
  summary: RelationshipSummary;
  limit: number;
  offset: number;
  total_results: number;
  disclaimer: string;
}

export interface RelationshipGraphResponse {
  depth: number;
  nodes: { id: string; label: string; type: string }[];
  edges: { id: string; source: string; target: string; label: string; status: string }[];
  summary: RelationshipSummary;
  disclaimer: string;
}

export interface GoldReference {
  id: string;
  act_id: string | null;
  source_section_id: string | null;
  expected_raw_text: string;
  expected_relationship_type: string;
  expected_target_act_title: string | null;
  expected_target_section_number: string | null;
  notes: string | null;
  created_at: string;
}

export interface GoldReferenceCreatePayload {
  act_id?: string | null;
  source_section_id?: string | null;
  expected_raw_text: string;
  expected_relationship_type: string;
  expected_target_act_title?: string | null;
  expected_target_section_number?: string | null;
  notes?: string | null;
}

export interface EvaluationRun {
  id: string;
  run_name: string;
  act_id: string | null;
  precision: number;
  recall: number;
  f1_score: number;
  section_segmentation_accuracy: number | null;
  total_gold_references: number;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  run_summary_json: {
    gold_count?: number;
    predicted_count?: number;
    matched?: EvaluationMismatch[];
    false_positives?: EvaluationMismatch[];
    false_negatives?: EvaluationMismatch[];
    mismatch_counts?: Record<string, number>;
  } | null;
  created_at: string;
}

export interface EvaluationMismatch {
  raw_text: string;
  relationship_type: string;
  target_act_title: string;
  target_section: string;
}

export interface EvaluationRunCreatePayload {
  run_name: string;
  act_id?: string | null;
  section_segmentation_accuracy?: number | null;
}

export interface EvaluationMetricsSummary {
  document_counts: Record<string, number>;
  section_counts: Record<string, number>;
  reference_counts: Record<string, number>;
  processing_job_counts: Record<string, number>;
  latest_processing_messages: {
    job_id: string;
    act_id: string;
    status: string;
    current_step: string;
    warnings: string[];
    errors: string[];
    created_at: string;
  }[];
  latest_evaluation_runs: {
    id: string;
    run_name: string;
    precision: number;
    recall: number;
    f1_score: number;
    created_at: string;
  }[];
}
