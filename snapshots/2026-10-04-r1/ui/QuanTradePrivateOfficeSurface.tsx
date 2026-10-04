import { useEffect, useMemo, useState } from "react";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";

import { api } from "./api";

const mono = Platform.select({ ios: "Menlo", android: "monospace", default: "monospace" });

function moneyKrw(value: any) {
  const number = Number(value);
  return Number.isFinite(number) ? "₩" + Math.round(number).toLocaleString("ko-KR") : "—";
}

function pct(value: any) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return (number >= 0 ? "+" : "") + number.toFixed(2) + "%";
}

function statusKorean(value?: string) {
  const map: Record<string, string> = {
    created: "준비", queued: "대기", running: "진행",
    awaiting_founder: "결재 필요", review_required: "검토 필요",
    budget_blocked: "예산 차단", delivery_blocked: "배포 차단",
    waiting_for_delivery: "배포 대기",
  };
  return map[String(value ?? "").toLowerCase()] ?? String(value ?? "—");
}

function departmentStatus(value?: string) {
  const map: Record<string, string> = {
    READY: "준비",
    INFO_NEEDED: "정보 필요",
    BLOCKED_BY_CLIENT_INFO: "고객정보 대기",
    COMPLETE: "완료",
    SIMULATED: "모의 실행",
    NOT_RUN: "미실행",
    CONNECTED: "연결",
    NOT_CONNECTED: "미연결",
  };
  return map[String(value ?? "").toUpperCase()] ?? String(value ?? "—");
}

function OfficeMetric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return <View style={styles.metric}>
    <Text style={styles.metricLabel}>{label}</Text>
    <Text style={styles.metricValue}>{value}</Text>
    {detail ? <Text style={styles.metricDetail}>{detail}</Text> : null}
  </View>;
}

export function QuanTradePrivateOfficeSurface() {
  const [state, setState] = useState<any>(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  async function load() {
    setRefreshing(true);
    try { setState(await api.quantradePrivateOffice()); setError(""); }
    catch (e: any) { setError(e?.message ?? "Private Investment Office 상태를 불러오지 못했습니다."); }
    finally { setRefreshing(false); }
  }

  useEffect(() => { void load(); }, []);

  const client = state?.client ?? {};
  const portfolio = state?.portfolio ?? {};
  const risk = portfolio?.risk ?? {};
  const report = portfolio?.report ?? {};
  const decision = state?.institutional_decision ?? {};
  const execution = state?.execution ?? {};
  const operations = state?.operations ?? {};
  const learning = state?.learning ?? {};
  const postTrade = learning?.post_trade_review ?? {};
  const performance = learning?.performance_history ?? {};
  const positions = Array.isArray(portfolio?.largest_positions) ? portfolio.largest_positions : [];
  const departments = Array.isArray(state?.departments) ? state.departments : [];
  const active = Array.isArray(operations?.active_missions) ? operations.active_missions : [];
  const decisionPath = Array.isArray(decision?.decision_path) ? decision.decision_path : [];
  const sourceWarnings = useMemo(() => {
    if (!state?.source_health) return [];
    return Object.entries(state.source_health)
      .filter(([, value]) => Boolean(value))
      .map(([key]) => key.replaceAll("_error", "").replaceAll("_", " "));
  }, [state?.source_health]);

  if (!state && !error) return <View style={styles.shell}>
    <Text style={styles.eyebrow}>QUANTRADE / PRIVATE INVESTMENT OFFICE</Text>
    <Text style={styles.muted}>회사 상태 연결 중…</Text>
  </View>;

  return <View style={styles.shell}>
    <View style={styles.header}>
      <View style={styles.flex}>
        <Text style={styles.eyebrow}>QUANTRADE / PRIVATE INVESTMENT OFFICE</Text>
        <Text style={styles.title}>나를 위한 투자회사</Text>
        <Text style={styles.subtitle}>고객 이해 → 전략 → 리서치 → 포트폴리오 → 리스크 → 위원회 → 실행 → 학습</Text>
      </View>
      <Pressable disabled={refreshing} onPress={() => void load()}>
        <Text style={styles.refresh}>{refreshing ? "갱신 중" : "새로고침"}</Text>
      </Pressable>
    </View>

    {error ? <Text style={styles.error}>{error}</Text> : null}

    <View style={styles.metricGrid}>
      <OfficeMetric label="CLIENT / STRATEGY" value={client?.strategy_ready ? "READY" : "INFO NEEDED"}
        detail={client?.information_completion ? String(client.information_completion.resolved ?? 0) + "/" + String(client.information_completion.total ?? 0) + " 확인" : "고객정보 상태 없음"} />
      <OfficeMetric label="PORTFOLIO" value={moneyKrw(portfolio?.total_assets_krw)}
        detail={Number.isFinite(Number(portfolio?.position_count)) ? String(portfolio.position_count) + " positions · cash " + moneyKrw(portfolio?.cash_krw) : "현재 포트폴리오 미연결"} />
      <OfficeMetric label="RISK" value={risk?.available ? (report?.matches_current_portfolio ? "CURRENT" : "STALE REPORT") : "—"}
        detail={risk?.available ? "budget usage " + pct(risk?.budget_usage_pct) + (risk?.provisional ? " · provisional" : "") : "발행된 risk snapshot 없음"} />
      <OfficeMetric label="EXECUTION" value={execution?.live_execution_authorized === false ? "LOCKED" : execution?.live_execution_authorized === true ? "AUTHORIZED" : "—"}
        detail={execution?.paper_experiment_id ? String(execution.mode ?? "PAPER") + " · " + String(execution.paper_experiment_id) : "실행 실험 미연결"} />
    </View>

    {!client?.strategy_ready && client?.next_question ? <View style={styles.notice}>
      <Text style={styles.noticeLabel}>CLIENT INTELLIGENCE</Text>
      <Text style={styles.noticeText}>{String(client.next_question)}</Text>
      <Text style={styles.noticeMeta}>고객 제약이 정리되기 전에는 투자 검토로 자동 승격하지 않습니다.</Text>
    </View> : null}

    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>운용조직</Text>
        <Text style={styles.sectionMeta}>현재 상태 / 검증 범위 분리</Text>
      </View>
      {departments.length ? departments.map((item: any, index: number) => {
        const experimental = item.scope === "PAPER_REPLAY";
        return <View key={String(item.key ?? index)} style={styles.departmentRow}>
          <Text style={styles.departmentIndex}>{String(index + 1).padStart(2, "0")}</Text>
          <View style={styles.flex}>
            <View style={styles.departmentHead}>
              <Text style={styles.departmentName}>{String(item.name ?? "—")}</Text>
              <Text style={experimental ? styles.experimentState : styles.departmentState}>
                {departmentStatus(item.status)}
              </Text>
            </View>
            <Text style={styles.departmentQuestion}>{String(item.question ?? "")}</Text>
            <Text style={styles.departmentScope}>
              {experimental
                ? `실험 검증 · ${String(item.experiment_id ?? "PAPER/REPLAY")} · 실제 투자결정 아님`
                : item.scope === "CURRENT_CLIENT"
                  ? "현재 Client 기준"
                  : item.scope === "CURRENT_RECORDS"
                    ? "현재 기록 기준"
                    : "아직 검증 Case 없음"}
            </Text>
          </View>
        </View>;
      }) : <Text style={styles.muted}>운용조직 상태 projection이 없습니다.</Text>}
      <Text style={styles.muted}>
        부서 상태는 존재하는 Client/Portfolio/Institutional Case/Learning 자료만 투영합니다. PAPER/REPLAY 결과를 실제 운용 판단으로 승격하지 않습니다.
      </Text>
    </View>

    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>실제 포트폴리오</Text>
        <Text style={styles.sectionMeta}>{portfolio?.synced_at ? String(portfolio.synced_at).slice(0, 10) : "source —"}</Text>
      </View>
      {positions.length ? positions.map((item: any) => <View key={String(item.symbol)} style={styles.positionRow}>
        <View style={styles.flex}>
          <Text style={styles.positionName}>{String(item.name ?? item.symbol ?? "—")}</Text>
          <Text style={styles.positionSymbol}>{String(item.symbol ?? "—") + " · " + String(item.market_country ?? "—")}</Text>
        </View>
        <View style={styles.positionRight}>
          <Text style={styles.positionValue}>{moneyKrw(item.eval_amount_krw)}</Text>
          <Text style={styles.positionReturn}>{pct(item.return_pct)}</Text>
        </View>
      </View>) : <Text style={styles.muted}>현재 보유자산 projection이 없습니다.</Text>}
      {report && report.matches_current_portfolio === false ? <Text style={styles.warning}>
        Risk/portfolio_report는 현재 real_portfolio와 같은 시점이 아닙니다. 위험 수치는 참고 상태로만 표시합니다.
      </Text> : null}
    </View>

    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>최근 Institutional Case</Text>
        <Text style={styles.sectionMeta}>{String(decision?.mode ?? "—")}</Text>
      </View>
      {decision?.experiment_id ? <>
        <View style={styles.decisionBar}>
          <View style={styles.flex}>
            <Text style={styles.decisionLabel}>COMMITTEE</Text>
            <Text style={styles.decisionValue}>{String(decision.committee_action ?? "—") + " · " + String(decision.symbol ?? "—")}</Text>
          </View>
          <Text style={styles.paperTag}>PAPER / REPLAY</Text>
        </View>
        <View style={styles.pipeline}>
          {decisionPath.map((item: any, index: number) => <View key={String(item.stage) + "-" + String(index)} style={styles.stage}>
            <Text style={styles.stageName}>{String(item.stage ?? "—")}</Text>
            <Text style={styles.stageState}>{String(item.status ?? "—")}</Text>
          </View>)}
        </View>
        <Text style={styles.muted}>{String(decision.interpretation ?? "실험 read model입니다. 실제 주문 권한을 뜻하지 않습니다.")}</Text>
      </> : <Text style={styles.muted}>발행된 Institutional Case가 없습니다.</Text>}
    </View>

    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>오늘의 회사 업무</Text>
        <Text style={styles.sectionMeta}>{String(operations?.active_count ?? 0) + " active"}</Text>
      </View>
      {active.length ? active.map((item: any) => <View key={item.mission_id} style={styles.operationRow}>
        <Text style={styles.operationStatus}>{statusKorean(item.status)}</Text>
        <Text style={styles.operationTitle} numberOfLines={2}>{String(item.objective ?? "—")}</Text>
      </View>) : <Text style={styles.muted}>현재 QuanTrade Lab의 활성 업무가 없습니다.</Text>}
    </View>

    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Performance & Learning</Text>
        <Text style={styles.sectionMeta}>{String(learning?.status ?? "—")}</Text>
      </View>
      {learning?.status === "CONNECTED" ? <>
        <View style={styles.learningGrid}>
          <View style={styles.learningMetric}>
            <Text style={styles.metricLabel}>POST-TRADE REVIEWS</Text>
            <Text style={styles.learningValue}>{String(postTrade?.report_count ?? "—")}</Text>
            <Text style={styles.metricDetail}>
              {postTrade?.latest_generated_at ? "latest " + String(postTrade.latest_generated_at).slice(0, 10) : "latest —"}
            </Text>
          </View>
          <View style={styles.learningMetric}>
            <Text style={styles.metricLabel}>평가손익</Text>
            <Text style={styles.learningValue}>
              {performance?.latest ? moneyKrw(performance.latest.valuation_pnl_krw) : "—"}
            </Text>
            <Text style={styles.metricDetail}>총손익 아님 · valuation P&L</Text>
          </View>
        </View>
        {postTrade?.latest_findings ? <Text style={styles.muted}>
          {"최근 사후점검 · 집중 " + String(postTrade.latest_findings.concentration_matches ?? 0)
            + " · 상관 사각지대 " + String(postTrade.latest_findings.correlation_blind_spots ?? 0)
            + " · 보유패턴 " + String(postTrade.latest_findings.behavior_patterns ?? 0)}
        </Text> : null}
      </> : null}
      <Text style={styles.muted}>{String(learning?.note ?? "학습 read model이 연결되지 않았습니다.")}</Text>
    </View>

    {sourceWarnings.length ? <Text style={styles.warning}>{"일부 source 연결 실패 · " + sourceWarnings.join(" / ")}</Text> : null}
    <Text style={styles.footer}>이 화면은 기존 검증 데이터를 한 회사의 상태로 투영할 뿐, 투자 추천·주문 권한·누락값 추정을 생성하지 않습니다.</Text>
  </View>;
}

const styles = StyleSheet.create({
  flex: { flex: 1, minWidth: 0 },
  shell: { borderWidth: 1, borderColor: "#3B3B37", backgroundColor: "#11110F", padding: 13, gap: 12 },
  header: { flexDirection: "row", alignItems: "flex-start", gap: 12 },
  eyebrow: { fontFamily: mono, fontSize: 7, letterSpacing: 1.1, color: "#8E8E86", fontWeight: "700" },
  title: { marginTop: 4, fontSize: 19, lineHeight: 24, color: "#F2F2EC", fontWeight: "800" },
  subtitle: { marginTop: 4, fontSize: 9, lineHeight: 14, color: "#96968E" },
  refresh: { fontFamily: mono, fontSize: 7, color: "#BDBDB5", paddingVertical: 3 },
  metricGrid: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  metric: { width: "48%", minHeight: 67, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#4A4A45", paddingTop: 7 },
  metricLabel: { fontFamily: mono, fontSize: 6.5, letterSpacing: 0.5, color: "#777770" },
  metricValue: { marginTop: 4, fontFamily: mono, fontSize: 11, color: "#EEEEEA", fontWeight: "700" },
  metricDetail: { marginTop: 3, fontSize: 7.5, lineHeight: 11, color: "#85857E" },
  notice: { borderLeftWidth: 2, borderLeftColor: "#9B844A", paddingLeft: 9, gap: 4 },
  noticeLabel: { fontFamily: mono, fontSize: 6.5, color: "#A9945B", fontWeight: "700", letterSpacing: 0.7 },
  noticeText: { fontSize: 11, lineHeight: 17, color: "#E8E8E1", fontWeight: "600" },
  noticeMeta: { fontSize: 7.5, lineHeight: 12, color: "#85857E" },
  section: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#3E3E3A", paddingTop: 10, gap: 7 },
  sectionHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", gap: 10 },
  sectionTitle: { fontSize: 11, color: "#E8E8E2", fontWeight: "800" },
  sectionMeta: { fontFamily: mono, fontSize: 6.5, color: "#777770" },
  departmentRow: { flexDirection: "row", gap: 8, paddingVertical: 7, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#292927" },
  departmentIndex: { width: 20, fontFamily: mono, fontSize: 6.5, color: "#666660", paddingTop: 2 },
  departmentHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", gap: 8 },
  departmentName: { flex: 1, fontSize: 9.5, lineHeight: 14, color: "#E2E2DC", fontWeight: "700" },
  departmentState: { fontFamily: mono, fontSize: 6.5, color: "#9F9F97", fontWeight: "700" },
  experimentState: { fontFamily: mono, fontSize: 6.5, color: "#B7A16A", fontWeight: "700" },
  departmentQuestion: { marginTop: 2, fontSize: 7.5, lineHeight: 12, color: "#999991" },
  departmentScope: { marginTop: 2, fontFamily: mono, fontSize: 6, lineHeight: 10, color: "#6F6F69" },
  positionRow: { flexDirection: "row", gap: 10, paddingVertical: 5, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#292927" },
  positionName: { fontSize: 9, color: "#DADAD3", fontWeight: "600" },
  positionSymbol: { marginTop: 2, fontFamily: mono, fontSize: 6.5, color: "#70706A" },
  positionRight: { alignItems: "flex-end" },
  positionValue: { fontFamily: mono, fontSize: 8, color: "#DADAD3" },
  positionReturn: { marginTop: 2, fontFamily: mono, fontSize: 6.5, color: "#888881" },
  decisionBar: { flexDirection: "row", alignItems: "center", gap: 10, borderWidth: StyleSheet.hairlineWidth, borderColor: "#3F3F3B", padding: 8 },
  decisionLabel: { fontFamily: mono, fontSize: 6.5, color: "#777770" },
  decisionValue: { marginTop: 3, fontFamily: mono, fontSize: 9.5, color: "#E8E8E1", fontWeight: "700" },
  paperTag: { fontFamily: mono, fontSize: 6.5, color: "#B9A36C", fontWeight: "700" },
  pipeline: { flexDirection: "row", flexWrap: "wrap", gap: 5 },
  stage: { width: "31%", paddingVertical: 6, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#3C3C38" },
  stageName: { fontFamily: mono, fontSize: 6.5, color: "#C7C7C0", fontWeight: "700" },
  stageState: { marginTop: 2, fontFamily: mono, fontSize: 6, color: "#74746E" },
  operationRow: { flexDirection: "row", gap: 8, paddingVertical: 5, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#292927" },
  operationStatus: { width: 52, fontSize: 7.5, color: "#A5A59D", fontWeight: "700" },
  operationTitle: { flex: 1, fontSize: 9, lineHeight: 14, color: "#D5D5CE" },
  learningGrid: { flexDirection: "row", gap: 7 },
  learningMetric: { flex: 1, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#3B3B37", paddingTop: 6 },
  learningValue: { marginTop: 3, fontFamily: mono, fontSize: 10, color: "#DFDFD8", fontWeight: "700" },
  muted: { fontSize: 7.5, lineHeight: 12, color: "#808078" },
  warning: { fontSize: 7.5, lineHeight: 12, color: "#B5A274" },
  error: { fontSize: 8, lineHeight: 13, color: "#C78B8B" },
  footer: { fontSize: 6.5, lineHeight: 11, color: "#666660" },
});