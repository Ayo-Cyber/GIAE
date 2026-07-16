// Keep in sync with JobStatus enum in src/giae_api/models.py
export type JobStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";

export interface Evidence {
  label: string;
  source: string;
  conf: number;
}

export interface CompetingHypothesis {
  hypothesis: string;
  confidence: number;
  reason_not_preferred: string;
}

export interface GeneDomain {
  start: number;   // amino-acid coordinate (0-based)
  end: number;     // amino-acid coordinate (exclusive)
  label: string;
  source: string;  // tool name (prosite / hmmer / …)
  kind?: string;   // evidence_type (motif_match / domain_hit / …)
}

export interface GeneRow {
  id: string;
  name: string;
  locus: string;
  start?: number | null;
  end?: number | null;
  strand?: number | null;
  length?: number | null;
  is_dark: boolean;
  confidence: "HIGH" | "MODERATE" | "LOW" | "SPECULATIVE" | null;
  score: number | null;
  // Calibrated P(correct) from post-hoc isotonic recalibration; present only
  // for homology-backed calls (null otherwise). See ConfidenceCalibrator.
  calibrated_confidence?: number | null;
  calibration_model?: string | null;
  function: string | null;
  normalized_product?: string | null;
  cog_category?: string | null;
  cog_name?: string | null;
  cog_source?: string | null;
  go_terms?: string[];
  ec_number?: string | null;
  pfam_id?: string | null;
  category?: string | null;
  reasoning: string | null;
  reasoning_steps?: string[];
  competing_hypotheses?: CompetingHypothesis[];
  uncertainty_sources?: string[];
  evidence: Evidence[];
  aa_sequence?: string | null;
  aa_length?: number | null;
  domains?: GeneDomain[];
}

export interface Job {
  job_id: string;
  filename: string;
  status: JobStatus;
  report_url: string | null;
  error_message: string | null;
  total_genes: number | null;
  interpreted_genes: number | null;
  high_confidence_count: number | null;
  dark_count: number | null;
  processing_time_seconds: number | null;
  created_at: string | null;
  genes: GeneRow[];
}

export interface CreateJobResponse {
  job_id: string;
  status: "PENDING";
  filename: string;
}

export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
}

export interface CreatedApiKey extends ApiKey {
  key: string; // raw — shown once only
}

export interface Notification {
  id: string;
  type: "completed" | "failed" | "cancelled" | "watch_hit";
  job_id: string;
  filename: string;
  message: string;
  created_at: string | null;
}

export interface WatchlistEntry {
  id: string;
  locus: string;
  gene_name: string;
  created_at: string;
}

export interface DarkGene {
  id: string;
  name: string;
  locus: string;
  organism: string;
  job_id: string;
}
