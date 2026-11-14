export type Status = "verified" | "needs_review";
export interface Entry { source_page?: number | null; source_text?: string | null; confidence?: number; status?: Status; [k: string]: unknown }
export interface Trace { value: unknown; source_page: number | null; source_text: string | null; rule: string | null; confidence: number; status: Status }
export interface ResumeResult {
  document: { filename: string | null; file_type: string | null; document_type: string | null; total_pages: number; extraction_method: string | null; ocr_used: boolean; processing_time_ms: number | null };
  personal_information: Record<string, string | null>;
  social_profiles: Record<string, string | string[] | null>;
  education: Entry[]; experience: Entry[]; projects: Entry[]; certifications: Entry[]; achievements: Entry[];
  publications: Entry[]; languages: Entry[]; volunteer_experience: Entry[]; training: Entry[]; awards: Entry[];
  skills: Record<string, string[]>;
  interests: string[];
  additional_information: { section: string; text: string; source_page?: number | null }[];
  unclassified_text: { text: string; source_page?: number | null; reason?: string | null }[];
  extraction_metadata: { pages_processed: number; ocr_pages: number[]; ocr_mean_confidence: number | null; warnings: string[]; missing_fields: string[]; needs_review: string[]; extracted_field_count: number; field_traces: Record<string, Trace> };
}
export interface Stage { index: number; name: string; state: "pending" | "running" | "done" | "failed" }
export interface StatusPayload { status: "uploaded" | "processing" | "completed" | "failed"; progress: number; current_stage_name: string | null; detail: string | null; stages: Stage[]; error: { code: string; message: string } | null }
export interface UploadResponse { resume_id: string; owner_token: string; filename: string; size_bytes: number; page_count: number }
