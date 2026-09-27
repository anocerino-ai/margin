import { ref } from 'vue'
export const apiToken = ref('')
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}
export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch('/api/v1' + path, {
    method,
    headers: {
      "X-Requested-With": "Margin",
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...(apiToken.value ? { Authorization: 'Bearer ' + apiToken.value } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    let message = 'API unavailable'
    try {
      const data = await response.json()
      message = data.error?.message ?? message
    } catch {}
    throw new ApiError(response.status, message)
  }
  return response.status === 204 ? (undefined as T) : await response.json()
}
export interface Topic {
  id: string
  name: string
  description: string
  is_active: boolean
}
export interface Source {
  id: string
  name: string
  feed_url: string | null
  website_url: string
  is_active: boolean
}
export interface Match {
  topic_name: string
  confidence: number
  topic_type: string
}
export interface Article {
  id: string
  title: string
  url: string
  source_id: string
  source_name: string
  published_at: string | null
  discovered_at: string
  classification: {
    status: string
    is_target: boolean | null
    model_used: string | null
    prompt_version: string
    prompt_hash: string
    attempts?: { model: string; attempt_number: number; status: string; error_code: string | null; started_at: string; completed_at: string }[]
    topics: Match[]
  } | null
}
export interface Run {
  id: string
  created_at: string
  status: string
  new_articles: number
  target_count: number
  failed_count: number
  classified_count: number
  topics: Record<string, unknown>[]
  articles: Article[]
  events: EventRow[]
  emails: Email[]
}
export interface EventRow {
  id: string
  created_at: string
  stage: string
  status: string
  error_code: string | null
}
export interface Email {
  id: string
  status: string
  recipient: string
  subject: string
  error_code: string | null
}
export interface Version {
  id: string
  version: number
  title: string
  content_markdown: string
  status: string
  model_used: string
  prompt_version: string
  prompt_hash: string
  additional_instructions: string
  dependencies: { depends_on_version_id: string; version: number; output_type: string }[]
  sources: { original_url: string; content_hash: string; context_mode: string }[]
}
export interface Output {
  id: string
  output_type: 'BLOG' | 'LINKEDIN'
  versions: Version[]
}
export interface Generation {
  id: string
  status: string
  created_at: string
  generate_blog: boolean
  generate_linkedin: boolean
  sources: {
    id: string
    article_title: string
    original_url: string
    crawl_status: string
    crawls: { status: string; crawled_at: string; error_code: string | null }[]
  }[]
  outputs: Output[]
  events: EventRow[]
  jobs: { id: string; kind: string; status: string; error_code: string | null }[]
}
export interface Model {
  id: string
  model: string
  position: number
  enabled: boolean
}
export interface Settings {
  openrouter_auto_resume: boolean
  openrouter_requests_per_minute: number
  openrouter_requests_per_day: number
  email_enabled: boolean
  discovery: {
    enabled: boolean
    frequency: 'DAILY' | 'WEEKLY'
    day_of_week: number
    hour: number
    minute: number
    timezone: string
  }
  classification_threshold: number
  crawl_cache_days: number
}
export interface SystemStatus {
  quota_pause?: { until: number; reason: string; auto_resume: boolean } | null
  storage: string
  openrouter: boolean
  firecrawl: boolean
  resend: boolean
  models: number
  active_sources: number
  worker_online: boolean
}
export interface Page<T> {
  items: T[]
  pagination: { page: number; pages: number; total: number; page_size: number }
}
