export type FeedbackSource = "sdk" | "zendesk" | "intercom" | "appstore" | "csv" | "slack" | "api";
export type FeedbackType = "bug" | "feature_request" | "crash" | "support" | "other";

export interface CanonicalFeedbackEvent {
  tenant_id: string;
  source: FeedbackSource;
  type: FeedbackType;
  occurred_at: string;
  actor_hash?: string | null;
  title: string;
  body: string;
  app_version?: string | null;
  os?: string | null;
  service_hint?: string | null;
  external_id?: string | null;
  urls?: string[];
}

export interface FeedbackRow extends CanonicalFeedbackEvent {
  id: string;
  created_at: string;
}
