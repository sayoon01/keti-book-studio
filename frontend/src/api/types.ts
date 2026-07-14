// backend/storage/models.py 의 실제 필드와 1:1로 맞춘 타입.
// status 값도 실제 상태 전이(draft -> edited -> approved -> generating ->
// generated -> reviewed -> finalized)를 그대로 반영한다 - 목업 때 썼던
// 4단계 단순화(완료/작성중/검토중/대기)가 아니라 실제 백엔드 상태값 기준.

export type UnitStatus =
  | "draft"
  | "edited"
  | "approved"
  | "generating"
  | "generated"
  | "reviewed"
  | "finalized";

export type OutlineStatus = "draft" | "edited" | "approved";

export type ApprovalMode = "safe" | "balanced" | "auto";

export interface BookUnit {
  unit_id: string;
  outline_id: string;
  parent_id: string | null;
  order: number;
  title: string;
  description: string;
  target_characters: number;
  persona_id: string | null;
  source_ids: string[];
  must_cover: string[];
  status: UnitStatus;
  custom_instructions: string | null;
  body_md: string | null;
  body_version: number;
  updated_at: string;
}

export interface BookUnitUpdatePayload {
  title?: string;
  description?: string;
  target_characters?: number;
  must_cover?: string[];
  custom_instructions?: string;
}

export interface BookOutline {
  outline_id: string;
  book_id: string;
  status: OutlineStatus;
  version: number;
  updated_at: string;
}

export interface BookConfig {
  config_id: string;
  book_id: string;
  document_type: string;
  target_reader: string;
  purpose: string;
  tone: string;
  expertise_level: string;
  chapter_count: number;
  default_chars_per_chapter: number;
  total_target_characters: number;
  citation_policy: string;
  visual_density: string;
  output_formats: string[];
  approval_mode: ApprovalMode;
  version: number;
  updated_at: string;
}

export interface BookProject {
  book_id: string;
  workspace_id: string;
  title: string;
  status: string;
  persona_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface OutlineWithUnits {
  outline: BookOutline;
  units: BookUnit[];
}

export interface Persona {
  persona_id: string;
  scope: "system" | "custom";
  name: string;
  base_persona_id: string | null;
  files: Record<string, string>;
  defaults: { description?: string; [key: string]: unknown };
  created_by: string | null;
}

export interface BookConfigUpdatePayload {
  document_type?: string;
  target_reader?: string;
  purpose?: string;
  tone?: string;
  expertise_level?: string;
  default_chars_per_chapter?: number;
  citation_policy?: string;
  visual_density?: string;
  approval_mode?: ApprovalMode;
}

export interface ConfigSuggestResult {
  config: BookConfig;
  suggested_chapter_count: number;
  recommended_persona_id: string | null;
  recommendation_reason: string;
  alternative_persona_ids: string[];
  book_persona_id: string | null;
}

export type SourceType =
  | "pdf"
  | "docx"
  | "hwp"
  | "hwpx"
  | "xlsx"
  | "csv"
  | "md"
  | "txt"
  | "url";

export type SourceStatus = "uploaded" | "analyzing" | "analyzed" | "failed";

export interface SourceDocument {
  source_id: string;
  workspace_id: string;
  book_id: string | null;
  source_type: SourceType;
  title: string;
  content_hash: string | null;
  file_path: string | null;
  url: string | null;
  raw_text: string | null;
  status: SourceStatus;
  created_at: string;
}

export interface SourceProfile {
  profile_id: string;
  source_id: string;
  summary: string;
  main_topics: string[];
  key_findings: string[];
  tables: Record<string, unknown>[];
  limitations: string[];
  recommended_uses: string[];
  analysis_purpose: string | null;
}
