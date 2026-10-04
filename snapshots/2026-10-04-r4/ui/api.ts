const API_URL =
  process.env.EXPO_PUBLIC_API_URL ??
  "https://llm-holdings-runtime-production.up.railway.app";

const TOKEN_KEY = "llm_holdings_api_token";
let memoryToken = "";

function storage() {
  try {
    return (globalThis as any)?.localStorage ?? null;
  } catch {
    return null;
  }
}

export function getSavedToken(): string {
  if (memoryToken) return memoryToken;
  const value = storage()?.getItem(TOKEN_KEY) ?? "";
  if (value) memoryToken = value;
  return value;
}

export function setSavedToken(value: string) {
  memoryToken = value.trim();
  const target = storage();
  if (target && memoryToken) target.setItem(TOKEN_KEY, memoryToken);
}

export function clearSavedToken() {
  memoryToken = "";
  storage()?.removeItem(TOKEN_KEY);
}

async function request(path: string, init?: RequestInit) {
  const token = getSavedToken();
  const headers: Record<string, string> = {
    "content-type": "application/json",
    ...((init?.headers ?? {}) as Record<string, string>),
  };
  if (token) headers.authorization = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const api = {
  endpoint: API_URL,
  knowledgeRoute: (query: string) => request("/labs/organization/knowledge-route", { method: "POST", body: JSON.stringify({ query }) }),
  discoverMission: (labId: string, missionId: string, query: string) => request(`/labs/${labId}/missions/${missionId}/discovery`, { method: "POST", body: JSON.stringify({ query, route_request: true }) }),
  setMissionOwner: (labId: string, missionId: string, owner: string, authorityLevel = "A1") => request(`/labs/${labId}/missions/${missionId}/owner`, { method: "PUT", body: JSON.stringify({ owner, authority_level: authorityLevel }) }),
  saveCapability: (labId: string, payload: any) => request(`/labs/${labId}/capabilities`, { method: "PUT", body: JSON.stringify(payload) }),
  bootstrapLab: () => request("/labs/bootstrap", { method: "POST" }),
  bootstrapOrganization: () => request("/labs/bootstrap-organization", { method: "POST" }),
  organization: () => request("/labs/organization"),
  runtimeOps: () => request("/runtime/ops"),
  knowledgeTopics: (
    scopeType: "holdings" | "lab" | "employee" = "holdings",
    scopeId = "holdings",
    query = "",
  ) => {
    const params = new URLSearchParams({
      scope_type: scopeType,
      scope_id: scopeId,
      query,
    });
    return request("/knowledge/observatory/topics?" + params.toString());
  },
  knowledgeRecordQueue: () => request("/knowledge/record-writer/queue"),
  semanticReviewKnowledgeRecord: (recordId: string, maxCostUsd = 0.01) =>
    request("/knowledge/reconciliation/records/" + encodeURIComponent(recordId) + "/semantic-resolve", {
      method: "POST",
      body: JSON.stringify({
        max_cost_usd: maxCostUsd,
        created_by: "founder:record-writer",
      }),
    }),
  resolveKnowledgeRecord: (
    recordId: string,
    action: "adopt" | "supersede" | "reject" | "archive",
    disposition?: string,
    targetClaimId?: string | null,
    rationale = "",
  ) =>
    request("/knowledge/record-writer/records/" + encodeURIComponent(recordId) + "/resolve", {
      method: "POST",
      body: JSON.stringify({
        action,
        disposition: disposition || null,
        target_claim_id: targetClaimId || null,
        rationale,
      }),
    }),
  knowledgeTopic: (
    conceptKey: string,
    scopeType: "holdings" | "lab" | "employee" = "holdings",
    scopeId = "holdings",
  ) => {
    const params = new URLSearchParams({
      scope_type: scopeType,
      scope_id: scopeId,
    });
    return request(
      "/knowledge/observatory/topics/" + encodeURIComponent(conceptKey) + "?" + params.toString(),
    );
  },
  quantradePrivateOffice: () => request("/clients/quantrade/private-office"),
  quantradeTradingFloor: () => request("/clients/quantrade/trading-floor"),
  quantradeClientIntelligenceReport: () =>
    request("/clients/quantrade/intelligence/report"),
  dispatchQuanTradeInstitutionalCase: () =>
    request("/clients/quantrade/institutional-case/dispatch", {
      method: "POST",
    }),
  answerQuanTradeClientQuestion: (questionKey: string, value: unknown) =>
    request(
      "/clients/quantrade/intelligence/questions/" + encodeURIComponent(questionKey) + "/answer",
      {
        method: "POST",
        body: JSON.stringify({
          value,
          visibility: "quantrade_internal",
          answered_by: "founder",
        }),
      },
    ),
  waiveQuanTradeClientQuestion: (questionKey: string) =>
    request(
      "/clients/quantrade/intelligence/questions/" + encodeURIComponent(questionKey) + "/waive",
      {
        method: "POST",
        body: JSON.stringify({ waived_by: "founder" }),
      },
    ),
  dispatchFounderCommand: (command: string) =>
    request("/labs/organization/commands", {
      method: "POST",
      body: JSON.stringify({ command, created_by: "founder" }),
    }),
  createFounderNote: (rawText: string) =>
    request("/labs/organization/notes", {
      method: "POST",
      body: JSON.stringify({ raw_text: rawText, created_by: "founder" }),
    }),
  triageFounderNote: (noteId: string) =>
    request(`/labs/organization/notes/${noteId}/triage`, { method: "POST" }),
  approveProposal: (proposalId: string, priority = "normal") =>
    request(`/labs/organization/proposals/${proposalId}/approve`, {
      method: "POST",
      body: JSON.stringify({ reviewed_by: "founder", priority }),
    }),
  runInitiative: (initiativeId: string) =>
    request(`/labs/organization/initiatives/${initiativeId}/run`, { method: "POST" }),
  labMemory: (labId: string) => request(`/labs/${labId}/memory`),
  lab: (id: string) => request(`/labs/${id}`),
  missions: (labId: string) => request(`/labs/${labId}/missions`),
  createMission: (labId: string, payload: any) =>
    request(`/labs/${labId}/missions`, { method: "POST", body: JSON.stringify(payload) }),
  mission: (labId: string, missionId: string) =>
    request(`/labs/${labId}/missions/${missionId}`),
  enqueueMission: (labId: string, missionId: string) =>
    request(`/labs/${labId}/missions/${missionId}/enqueue`, { method: "POST" }),
  missionExecutionJob: (labId: string, missionId: string) =>
    request(`/labs/${labId}/missions/${missionId}/execution-job`),
  runMission: (labId: string, missionId: string) =>
    request(`/labs/${labId}/missions/${missionId}/run`, { method: "POST" }),
  founderAction: (labId: string, missionId: string, action: "approve" | "revise" | "defer" | "cancel", message = "") =>
    request(`/labs/${labId}/missions/${missionId}/founder-action`, {
      method: "POST",
      body: JSON.stringify({ action, message, extra_steps: 2 }),
    }),
  founderActionAsync: (labId: string, missionId: string, action: "approve" | "revise" | "defer" | "cancel", message = "") =>
    request(`/labs/${labId}/missions/${missionId}/founder-action-async`, {
      method: "POST",
      body: JSON.stringify({ action, message, extra_steps: 2 }),
    }),
  agentRequests: (labId: string, missionId?: string) => {
    const suffix = missionId ? `?mission_id=${encodeURIComponent(missionId)}` : "";
    return request(`/labs/${labId}/agent-requests${suffix}`);
  },
  createWork: (labId: string, payload: any) =>
    request(`/labs/${labId}/work`, { method: "POST", body: JSON.stringify(payload) }),
  delegateWork: (labId: string, workId: string, seatId: string) =>
    request(`/labs/${labId}/work/${workId}/delegate`, {
      method: "POST",
      body: JSON.stringify({ seat_id: seatId, assigned_by: "founder" }),
    }),
  runWork: (labId: string, workId: string) =>
    request(`/labs/${labId}/work/${workId}/run`, { method: "POST" }),
  promoteDecision: (labId: string, workId: string, statement: string) =>
    request(`/labs/${labId}/work/${workId}/promote-decision`, {
      method: "POST",
      body: JSON.stringify({ statement }),
    }),
  dashboard: () => request("/dashboard"),
  cases: () => request("/cases"),
  case: (id: string) => request(`/cases/${id}`),
  createCase: (payload: any) => request("/cases", { method: "POST", body: JSON.stringify(payload) }),
  runCase: (id: string) => request(`/cases/${id}/run`, { method: "POST" }),
  agents: () => request("/agents"),
  approvals: () => request("/approvals"),
  approve: (id: string) => request(`/approvals/${id}/approve`, { method: "POST" }),
  reject: (id: string) => request(`/approvals/${id}/reject`, { method: "POST" }),
  stopAll: () => request("/kill-switch/stop", { method: "POST" }),
  startAll: () => request("/kill-switch/start", { method: "POST" }),
  stopCompany: (company: string) =>
    request(`/kill-switch/company/${company}/stop`, { method: "POST" }),
  startCompany: (company: string) =>
    request(`/kill-switch/company/${company}/start`, { method: "POST" }),
  stopCase: (id: string) => request(`/kill-switch/case/${id}/stop`, { method: "POST" }),
  startCase: (id: string) => request(`/kill-switch/case/${id}/start`, { method: "POST" }),
  stopStatus: (company?: string, caseId?: string) => {
    const params = new URLSearchParams();
    if (company) params.set("company", company);
    if (caseId) params.set("case_id", caseId);
    const suffix = params.toString();
    return request(`/kill-switch/status${suffix ? `?${suffix}` : ""}`);
  },
};
