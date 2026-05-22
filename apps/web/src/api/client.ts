const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export const TOKEN_STORAGE_KEY = "comic-os-access-token";

export type SortBy =
  | "title"
  | "publisher"
  | "purchase_date"
  | "acquisition_cost"
  | "current_fmv"
  | "gain_loss"
  | "star_rating";

export type OrderSortBy = "order_date" | "retailer" | "total_amount" | "created_at";
export type ImportSortBy = "created_at" | "updated_at" | "confidence_score" | "status";

export interface RegisterPayload {
  email: string;
  password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface User {
  id: number;
  email: string;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface AiParseOrderPayload {
  raw_text: string;
}

export interface AiDraftOrderItem {
  publisher: string | null;
  title: string | null;
  issue_number: string | null;
  cover_name: string | null;
  printing: string | null;
  ratio: string | null;
  variant_type: string | null;
  cover_artist: string | null;
  quantity: number | null;
  raw_item_price: string | null;
}

export type DraftSourceType = "ai_draft" | "manual_draft";

export interface AiParseOrderResponse {
  retailer: string | null;
  order_date: string | null;
  source_type: DraftSourceType;
  shipping_amount: string;
  tax_amount: string;
  items: AiDraftOrderItem[];
  warnings: string[];
  confidence_score: number;
}

export type DraftImportStatus = "draft" | "confirmed" | "discarded";

export interface DraftImport {
  id: number;
  raw_text: string;
  parsed_payload_json: AiParseOrderResponse;
  confidence_score: string;
  status: DraftImportStatus;
  order_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface DraftImportListResponse {
  page: number;
  page_size: number;
  total: number;
  items: DraftImport[];
}

export interface ImportQueryParams {
  page: number;
  page_size: number;
  status?: DraftImportStatus;
  search?: string;
  sort_by?: ImportSortBy;
  sort_dir?: "asc" | "desc";
}

export interface DraftImportCreatePayload {
  raw_text: string;
}

export interface ManualDraftImportCreatePayload extends AiParseOrderResponse {
  raw_text?: string | null;
  source_type: "manual_draft";
}

export interface DraftImportUpdatePayload {
  raw_text?: string;
  parsed_payload_json?: AiParseOrderResponse;
  confidence_score?: number;
}

export interface DraftImportConfirmResponse {
  import_id: number;
  status: DraftImportStatus;
  order_id: number;
  total_items: number;
  total_copies_created: number;
  all_in_total: string;
}

export type ImportParseJobStatus =
  | "queued"
  | "started"
  | "finished"
  | "failed"
  | "scheduled"
  | "deferred";

export interface ImportParseJobEnqueueResponse {
  job_id: string;
  status: ImportParseJobStatus;
}

export interface ImportParseJobStatusResponse {
  job_id: string;
  job_type: string;
  status: ImportParseJobStatus;
  import_id: number | null;
  import_record: DraftImport | null;
  error: string | null;
  enqueued_at: string | null;
  started_at: string | null;
  ended_at: string | null;
}

export interface GmailStatusResponse {
  configured: boolean;
  connected: boolean;
  gmail_email: string | null;
  token_expires_at: string | null;
}

export interface GmailConnectStartResponse {
  authorization_url: string;
}

export interface GmailDisconnectResponse {
  disconnected: boolean;
}

export interface GmailSyncEnqueueResponse {
  job_id: string;
  status: string;
}

export interface GmailSyncStatusResponse {
  auto_sync_enabled: boolean;
  last_sync_started_at: string | null;
  last_sync_completed_at: string | null;
  last_sync_status: string | null;
  last_sync_error: string | null;
}

export interface GmailSyncSettingsUpdatePayload {
  auto_sync_enabled: boolean;
}

export interface GmailImportedDraft {
  external_message_id: string;
  imported_at: string;
  draft_import: DraftImport;
}

export interface OpsQueueSnapshot {
  queue_name: string;
  queued_jobs: number;
  started_jobs: number;
  failed_jobs: number;
  most_recent_job_result: string | null;
}

export interface OpsJobRow {
  job_id: string;
  job_type: string;
  queue_name: string;
  status: string;
  user_id: number | null;
  user_email: string | null;
  started_at: string | null;
  ended_at: string | null;
  result_summary: string | null;
  error: string | null;
}

export interface OpsDraftImportRow {
  draft_id: number;
  user_id: number;
  user_email: string;
  retailer: string | null;
  status: string;
  confidence: string;
  warning_count: number;
  created_at: string;
  linked_order_id: number | null;
}

export interface OpsGmailSyncRow {
  gmail_account_id: number;
  user_id: number;
  user_email: string;
  gmail_email: string;
  auto_sync_enabled: boolean;
  last_sync_status: string | null;
  last_sync_started_at: string | null;
  last_sync_completed_at: string | null;
  processed_messages: number | null;
  created_draft_imports: number | null;
  skipped_duplicates: number | null;
  last_error_message: string | null;
}

export interface OpsEventRow {
  id: number;
  event_type: string;
  status: string;
  created_at: string;
  user_id: number | null;
  user_email: string | null;
  draft_import_id: number | null;
  order_id: number | null;
  external_message_id: string | null;
  message: string | null;
  details: Record<string, unknown>;
}

export interface OpsDashboardResponse {
  recent_gmail_sync_jobs: OpsJobRow[];
  recent_ai_parse_jobs: OpsJobRow[];
  gmail_sync_statuses: OpsGmailSyncRow[];
  recent_draft_imports: OpsDraftImportRow[];
  parser_failures: OpsEventRow[];
  duplicate_skip_events: OpsEventRow[];
  confirm_events: OpsEventRow[];
  queue_health: OpsQueueSnapshot[];
}

export interface InventoryItem {
  inventory_copy_id: number;
  title: string;
  publisher: string;
  issue_number: string;
  cover_name: string | null;
  printing: string | null;
  ratio: string | null;
  variant_type: string | null;
  cover_artist: string | null;
  retailer: string;
  order_date: string;
  acquisition_cost: string;
  current_fmv: string | null;
  gain_loss: string | null;
  grade_status: "raw" | "submitted" | "graded";
  hold_status: "hold" | "sell" | "sold";
  star_rating: number | null;
  condition_notes: string | null;
}

export interface InventoryDetail extends InventoryItem {
  copy_number: number;
  source_type: string | null;
  order_id: number;
  order_item_id: number;
  variant_id: number;
  created_at: string;
}

export interface InventoryFmvSnapshot {
  id: number;
  previous_fmv: string | null;
  new_fmv: string;
  changed_at: string;
  source: string;
}

export interface InventoryResponse {
  page: number;
  page_size: number;
  total: number;
  items: InventoryItem[];
}

export interface InventorySummary {
  total_copies: number;
  total_cost_basis: string;
  total_current_fmv: string;
  total_unrealized_gain_loss: string;
  raw_count: number;
  graded_count: number;
  hold_count: number;
  sell_count: number;
}

export interface PortfolioPerformanceItem {
  inventory_copy_id: number;
  title: string;
  publisher: string;
  issue_number: string;
  cover_name: string | null;
  current_fmv: string | null;
  gain_loss: string | null;
}

export interface PortfolioPerformance {
  total_cost_basis: string;
  total_current_fmv: string;
  total_unrealized_gain_loss: string;
  top_gainers: PortfolioPerformanceItem[];
  top_losers: PortfolioPerformanceItem[];
  highest_value_books: PortfolioPerformanceItem[];
}

export interface InventoryUpdatePayload {
  current_fmv?: string | null;
  hold_status?: "hold" | "sell" | "sold";
  star_rating?: number | null;
  grade_status?: "raw" | "submitted" | "graded";
  condition_notes?: string | null;
}

export interface BulkInventoryUpdatePayload {
  inventory_copy_ids: number[];
  updates: InventoryUpdatePayload;
}

export interface BulkInventoryUpdateResponse {
  updated_count: number;
}

export interface OrderItemPayload {
  publisher: string;
  title: string;
  issue_number: string;
  cover_name?: string | null;
  printing?: string | null;
  ratio?: string | null;
  variant_type?: string | null;
  cover_artist?: string | null;
  quantity: number;
  raw_item_price: number;
}

export interface OrderCreatePayload {
  retailer: string;
  order_date: string;
  source_type?: string | null;
  shipping_amount: number;
  tax_amount: number;
  items: OrderItemPayload[];
}

export interface OrderCreateResponse {
  order_id: number;
  total_items: number;
  total_copies_created: number;
  all_in_total: string;
}

export interface OrderListItem {
  order_id: number;
  retailer: string;
  order_date: string;
  source_type: string | null;
  shipping_amount: string;
  tax_amount: string;
  total_amount: string;
  total_items: number;
  total_copies: number;
  created_at: string;
}

export interface OrderListResponse {
  page: number;
  page_size: number;
  total: number;
  items: OrderListItem[];
}

export interface OrderDetailItem {
  order_item_id: number;
  publisher: string;
  title: string;
  issue_number: string;
  cover_name: string | null;
  printing: string | null;
  ratio: string | null;
  variant_type: string | null;
  cover_artist: string | null;
  quantity: number;
  raw_item_price: string;
  allocated_shipping: string;
  allocated_tax: string;
  all_in_unit_cost: string;
  inventory_copy_ids: number[];
}

export interface OrderDetail {
  order_id: number;
  retailer: string;
  order_date: string;
  source_type: string | null;
  shipping_amount: string;
  tax_amount: string;
  total_amount: string;
  created_at: string;
  items: OrderDetailItem[];
}

export interface InventoryQueryParams {
  page: number;
  page_size: number;
  search?: string;
  publisher?: string;
  hold_status?: string;
  grade_status?: string;
  sort_by?: SortBy;
  sort_dir?: "asc" | "desc";
}

export interface OrderQueryParams {
  page: number;
  page_size: number;
  retailer?: string;
  search?: string;
  sort_by?: OrderSortBy;
  sort_dir?: "asc" | "desc";
}

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(init?.headers);

  if (!headers.has("Content-Type") && init?.body) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

  if (response.status === 401) {
    clearStoredToken();
    if (window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    throw new ApiError("Authentication required", 401);
  }

  if (!response.ok) {
    let message = "Request failed";

    try {
      const data = (await response.json()) as { detail?: string };
      if (typeof data.detail === "string") {
        message = data.detail;
      }
    } catch {
      // Ignore invalid error payloads.
    }

    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

function buildQueryString(
  params:
    | Record<string, string | number | undefined>
    | InventoryQueryParams
    | OrderQueryParams
    | ImportQueryParams,
): string {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  });

  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

export const apiClient = {
  register(payload: RegisterPayload): Promise<User> {
    return request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  login(payload: LoginPayload): Promise<TokenResponse> {
    return request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getCurrentUser(): Promise<User> {
    return request<User>("/auth/me");
  },

  getGmailConnectStart(): Promise<GmailConnectStartResponse> {
    return request<GmailConnectStartResponse>("/gmail/connect/start");
  },

  getGmailStatus(): Promise<GmailStatusResponse> {
    return request<GmailStatusResponse>("/gmail/status");
  },

  getGmailSyncSummary(): Promise<GmailSyncStatusResponse> {
    return request<GmailSyncStatusResponse>("/gmail/sync/status");
  },

  updateGmailSyncSettings(
    payload: GmailSyncSettingsUpdatePayload,
  ): Promise<GmailSyncStatusResponse> {
    return request<GmailSyncStatusResponse>("/gmail/sync/settings", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  disconnectGmail(): Promise<GmailDisconnectResponse> {
    return request<GmailDisconnectResponse>("/gmail/disconnect", {
      method: "POST",
    });
  },

  syncGmail(): Promise<GmailSyncEnqueueResponse> {
    return request<GmailSyncEnqueueResponse>("/gmail/sync", {
      method: "POST",
    });
  },

  getGmailSyncStatus(jobId: string): Promise<ImportParseJobStatusResponse> {
    return request<ImportParseJobStatusResponse>(`/gmail/sync/${jobId}`);
  },

  getGmailImports(): Promise<GmailImportedDraft[]> {
    return request<GmailImportedDraft[]>("/gmail/imports");
  },

  getOpsDashboard(): Promise<OpsDashboardResponse> {
    return request<OpsDashboardResponse>("/ops/dashboard");
  },

  getInventory(params: InventoryQueryParams): Promise<InventoryResponse> {
    const query = buildQueryString(params);
    return request<InventoryResponse>(`/inventory${query}`);
  },

  getInventorySummary(): Promise<InventorySummary> {
    return request<InventorySummary>("/inventory/summary");
  },

  getPortfolioPerformance(): Promise<PortfolioPerformance> {
    return request<PortfolioPerformance>("/portfolio/performance");
  },

  getInventoryCopy(inventoryCopyId: number): Promise<InventoryDetail> {
    return request<InventoryDetail>(`/inventory/${inventoryCopyId}`);
  },

  getInventoryFmvHistory(inventoryCopyId: number): Promise<InventoryFmvSnapshot[]> {
    return request<InventoryFmvSnapshot[]>(`/inventory/${inventoryCopyId}/fmv-history`);
  },

  updateInventoryCopy(
    inventoryCopyId: number,
    updates: InventoryUpdatePayload,
  ): Promise<InventoryItem> {
    return request<InventoryItem>(`/inventory/${inventoryCopyId}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    });
  },

  bulkUpdateInventory(payload: BulkInventoryUpdatePayload): Promise<BulkInventoryUpdateResponse> {
    return request<BulkInventoryUpdateResponse>("/inventory/bulk", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  createOrder(payload: OrderCreatePayload): Promise<OrderCreateResponse> {
    return request<OrderCreateResponse>("/orders", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getOrders(params: OrderQueryParams): Promise<OrderListResponse> {
    const query = buildQueryString(params);
    return request<OrderListResponse>(`/orders${query}`);
  },

  getOrder(orderId: number): Promise<OrderDetail> {
    return request<OrderDetail>(`/orders/${orderId}`);
  },

  parseOrder(payload: AiParseOrderPayload): Promise<AiParseOrderResponse> {
    return request<AiParseOrderResponse>("/ai/parse-order", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getImports(params: ImportQueryParams): Promise<DraftImportListResponse> {
    const query = buildQueryString(params);
    return request<DraftImportListResponse>(`/imports${query}`);
  },

  getImport(importId: number): Promise<DraftImport> {
    return request<DraftImport>(`/imports/${importId}`);
  },

  createImport(payload: DraftImportCreatePayload): Promise<DraftImport> {
    return request<DraftImport>("/imports", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  createManualImport(payload: ManualDraftImportCreatePayload): Promise<DraftImport> {
    return request<DraftImport>("/imports/manual", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  enqueueImportParseJob(
    payload: DraftImportCreatePayload,
  ): Promise<ImportParseJobEnqueueResponse> {
    return request<ImportParseJobEnqueueResponse>("/imports/parse-jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getImportParseJobStatus(jobId: string): Promise<ImportParseJobStatusResponse> {
    return request<ImportParseJobStatusResponse>(`/imports/parse-jobs/${jobId}`);
  },

  updateImport(importId: number, payload: DraftImportUpdatePayload): Promise<DraftImport> {
    return request<DraftImport>(`/imports/${importId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  confirmImport(importId: number): Promise<DraftImportConfirmResponse> {
    return request<DraftImportConfirmResponse>(`/imports/${importId}/confirm`, {
      method: "POST",
    });
  },

  discardImport(importId: number): Promise<DraftImport> {
    return request<DraftImport>(`/imports/${importId}/discard`, {
      method: "POST",
    });
  },
};

export { ApiError, getStoredToken };
