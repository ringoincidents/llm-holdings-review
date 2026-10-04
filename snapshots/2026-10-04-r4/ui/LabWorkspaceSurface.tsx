import { useState } from "react";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";

import { DesignStudioSurface } from "./DesignStudioSurface";
import { QuanTradeDecisionEconomicsSurface } from "./QuanTradeDecisionEconomicsSurface";
import { QuanTradeClientIntelligenceSurface } from "./QuanTradeClientIntelligenceSurface";
import { QuanTradePrivateOfficeSurface } from "./QuanTradePrivateOfficeSurface";
import { RuntimeDevConsoleSurface } from "./RuntimeDevConsoleSurface";

const mono = Platform.select({ ios: "Menlo", android: "monospace", default: "monospace" });

type Props = {
  labKey: string;
  lab: any;
  missions: any[];
  missionState: any;
  organization: any;
  tradingFloor?: any;
  runtimeOps?: any;
  runtimeDashboard?: any;
};

function isInternalVerificationMission(mission: any) {
  const createdBy = String(mission?.created_by ?? "");
  const objective = String(mission?.objective ?? "");
  return (
    createdBy.startsWith("system:e2e-smoke:")
    || objective.startsWith("Production E2E smoke ")
  );
}

function eventMissionId(event: any) {
  try {
    const payload = JSON.parse(event?.payload_json ?? "{}");
    return String(payload?.mission_id ?? "");
  } catch {
    return "";
  }
}

function countOpenWork(work: any[] = []) {
  return work.filter(
    (item) => !["completed", "cancelled", "superseded"].includes(String(item?.status ?? "")),
  ).length;
}

function countBlockedWork(work: any[] = []) {
  return work.filter((item) =>
    ["blocked", "failed", "review_required"].includes(String(item?.status ?? "")),
  ).length;
}

function Tile({
  label,
  value,
  detail,
  inverse = false,
}: {
  label: string;
  value: string;
  detail?: string;
  inverse?: boolean;
}) {
  return (
    <View style={[styles.tile, inverse && styles.tileInverse]}>
      <Text style={[styles.tileLabel, inverse && styles.textInverseMuted]}>{label}</Text>
      <Text style={[styles.tileValue, inverse && styles.textInverse]} numberOfLines={2}>
        {value}
      </Text>
      {detail ? (
        <Text style={[styles.tileDetail, inverse && styles.textInverseMuted]} numberOfLines={2}>
          {detail}
        </Text>
      ) : null}
    </View>
  );
}

function QuanTradeFloor({
  lab,
  missions,
  missionState,
  tradingFloor,
}: Omit<Props, "labKey" | "organization">) {
  const [showMarketLab, setShowMarketLab] = useState(false);
  const work = lab?.work ?? [];
  const runningMissions = missions.filter((mission) =>
    !isInternalVerificationMission(mission)
    && ["queued", "running"].includes(String(mission?.status ?? "")),
  ).length;
  const founderRequired = Boolean(missionState?.founder_brief?.founder_decision_required);
  const floor = tradingFloor?.payload ?? tradingFloor ?? null;
  const paperCapital = Number(floor?.starting_capital_usd);
  const marketPrice = Number(floor?.market_observation?.price);
  const paperEquity = Number(floor?.paper_account?.equity_usd);
  const paperReturn = Number(floor?.paper_account?.total_return_pct);
  const benchmarkValue = Number(floor?.benchmark?.current_value_usd_before_costs);
  const benchmarkReturn = Number(floor?.benchmark?.return_pct_before_costs);
  const experimentId = String(floor?.experiment_id ?? "—");
  const symbol = String(floor?.market_observation?.symbol ?? "—");
  const validation = String(floor?.current_validation ?? "UNCONNECTED");
  const signal = String(floor?.trend_control?.signal ?? "—");
  const episodeCount = Array.isArray(floor?.trade_episodes) ? floor.trade_episodes.length : 0;
  const paperPosition = floor?.paper_account?.position ?? null;
  const executionLocked = floor?.live_execution_authorized === false;
  const sourceTime = floor?.market_observation?.observed_at
    ? String(floor.market_observation.observed_at).replace("T", " ").replace("+00:00", "Z")
    : "source unavailable";

  return (
    <View style={styles.tradingFloor}>
      <QuanTradePrivateOfficeSurface />

      <Pressable
        style={styles.marketLabToggle}
        onPress={() => setShowMarketLab((value) => !value)}
      >
        <View style={styles.flex}>
          <Text style={styles.marketLabToggleTitle}>시장 실험실 · PAPER / REPLAY</Text>
          <Text style={styles.marketLabToggleMeta}>
            BTC 등 시장 실험은 QuanTrade의 정체성이 아니라 검증용 laboratory입니다.
          </Text>
        </View>
        <Text style={styles.marketLabToggleAction}>
          {showMarketLab ? "닫기 ▲" : "열기 ▼"}
        </Text>
      </Pressable>

      {showMarketLab ? (
        <>
      <View style={styles.surfaceHeader}>
        <View style={styles.flex}>
          <Text style={styles.tradingEyebrow}>QUANTRADE / TRADING FLOOR</Text>
          <Text style={styles.tradingTitle}>운용 현황</Text>
        </View>
        <Text style={styles.liveTag}>{runningMissions > 0 ? "● LIVE" : "○ IDLE"}</Text>
      </View>

      <View style={styles.tileGrid}>
        <Tile
          label="PAPER EQUITY"
          value={Number.isFinite(paperEquity) ? `${paperEquity.toFixed(2)}` : Number.isFinite(paperCapital) ? `${paperCapital.toFixed(2)}` : "—"}
          detail={Number.isFinite(paperReturn) ? `return ${paperReturn >= 0 ? "+" : ""}${paperReturn.toFixed(2)}%` : floor ? experimentId : "실험 projection 연결 전"}
          inverse
        />
        <Tile
          label="MARKET"
          value={symbol}
          detail={Number.isFinite(marketPrice) ? `${marketPrice.toLocaleString("en-US", { maximumFractionDigits: 2 })} · ${String(floor?.market_scope?.timeframe ?? "—")}` : "시장 관측 없음"}
          inverse
        />
        <Tile
          label="SIGNAL"
          value={signal}
          detail={`${validation} · ${String(floor?.trend_control?.state ?? floor?.mode ?? "—")}`}
          inverse
        />
        <Tile
          label="BENCHMARK"
          value={Number.isFinite(benchmarkValue) ? `${benchmarkValue.toFixed(2)}` : "—"}
          detail={Number.isFinite(benchmarkReturn) ? `B&H ${benchmarkReturn >= 0 ? "+" : ""}${benchmarkReturn.toFixed(2)}%` : "benchmark 미연결"}
          inverse
        />
      </View>

      <View style={styles.tradingStrip}>
        <Text style={styles.tradingStripLabel}>POSITION</Text>
        <Text style={styles.tradingStripValue}>
          {paperPosition
            ? `${Number(paperPosition.quantity).toFixed(8)} ${String(paperPosition.symbol ?? symbol)} · entry ${Number(paperPosition.entry_fill_price).toLocaleString("en-US", { maximumFractionDigits: 2 })}`
            : `FLAT · closed ${episodeCount}`}
        </Text>
      </View>
      <View style={styles.tradingStrip}>
        <Text style={styles.tradingStripLabel}>EXECUTION</Text>
        <Text style={styles.tradingStripValue}>
          {executionLocked ? "LOCKED · PAPER ONLY" : floor ? "CHECK AUTHORITY" : "UNCONNECTED"}
        </Text>
      </View>
      <View style={styles.tradingStrip}>
        <Text style={styles.tradingStripLabel}>RUNTIME</Text>
        <Text style={styles.tradingStripValue}>
          {runningMissions} mission · {countOpenWork(work)} open · {countBlockedWork(work)} blocked
        </Text>
      </View>
      <View style={styles.tradingStrip}>
        <Text style={styles.tradingStripLabel}>FOUNDER GATE</Text>
        <Text style={styles.tradingStripValue}>{founderRequired ? "DECISION REQUIRED" : "CLEAR"}</Text>
      </View>
      <Text style={styles.tradingNotice}>
        {floor
          ? `source · ${sourceTime} · Knowledge may transfer across markets. Validation does not.`
          : "시장·수익·포지션 숫자는 실제 QuanTrade projection이 연결되기 전까지 표시하지 않습니다."}
      </Text>

      <QuanTradeClientIntelligenceSurface />

      <QuanTradeDecisionEconomicsSurface
        institutionalDecision={tradingFloor?.institutional_decision}
        error={tradingFloor?.institutional_decision_error}
      />
        </>
      ) : null}
    </View>
  );
}

function LlmResearchConsole({ lab, missions, missionState }: Omit<Props, "labKey" | "organization">) {
  const work = lab?.work ?? [];
  const experiments = work.filter((item: any) => item.work_type === "experiment");
  const operationalMissions = missions.filter((mission) => !isInternalVerificationMission(mission));
  const internalMissionIds = new Set(
    missions.filter(isInternalVerificationMission).map((mission) => String(mission?.id ?? "")),
  );
  const running = operationalMissions.filter((mission) =>
    ["queued", "running"].includes(String(mission?.status ?? "")),
  ).length;
  const provider = missionState?.budget?.last_provider;
  const model = missionState?.budget?.last_model;
  const spent = Number(missionState?.budget?.spent_usd ?? 0);
  const history = (Array.isArray(lab?.history) ? lab.history : []).filter((item: any) => {
    const missionId = eventMissionId(item);
    return !missionId || !internalMissionIds.has(missionId);
  });
  const modelCalls = history.filter((item: any) => item?.type === "MODEL_CALLED").length;
  const toolCalls = history.filter((item: any) => item?.type === "TOOL_EXECUTED").length;
  const failures = history.filter((item: any) =>
    ["TOOL_FAILED", "LAB_WORK_FAILED"].includes(String(item?.type ?? "")),
  ).length;
  const recentActivity = [...history]
    .filter((item: any) =>
      ["MODEL_CALLED", "TOOL_EXECUTED", "TOOL_FAILED", "LAB_WORK_COMPLETED", "LAB_WORK_FAILED"].includes(
        String(item?.type ?? ""),
      ),
    )
    .slice(-5)
    .reverse();
  const recentExperiments = [...experiments].slice(-3).reverse();

  function activityLabel(type?: string) {
    const labels: Record<string, string> = {
      MODEL_CALLED: "MODEL",
      TOOL_EXECUTED: "TOOL",
      TOOL_FAILED: "TOOL FAIL",
      LAB_WORK_COMPLETED: "WORK DONE",
      LAB_WORK_FAILED: "WORK FAIL",
    };
    return labels[String(type ?? "")] ?? String(type ?? "EVENT");
  }

  return (
    <View style={styles.researchConsole}>
      <View style={styles.surfaceHeader}>
        <View style={styles.flex}>
          <Text style={styles.researchEyebrow}>LLM LAB / RESEARCH CONSOLE</Text>
          <Text style={styles.surfaceTitle}>모델 · 실험 · 평가</Text>
        </View>
        <Text style={styles.researchStatus}>{running > 0 ? "● ACTIVE" : "○ IDLE"}</Text>
      </View>

      <View style={styles.researchGrid}>
        <Tile
          label="CURRENT ROUTE"
          value={provider && model ? `${provider}/${model}` : "아직 호출 없음"}
          detail="최근 Mission telemetry"
        />
        <Tile label="MISSION SPEND" value={`${spent.toFixed(4)}`} detail="현재 미션 기준" />
        <Tile label="MODEL CALLS" value={String(modelCalls)} detail="Lab history 기준" />
        <Tile label="TOOL CALLS" value={String(toolCalls)} detail={failures ? `실패 기록 ${failures}` : "실패 기록 없음"} />
      </View>

      <View style={styles.researchBand}>
        <View style={styles.researchBandItem}>
          <Text style={styles.researchBandLabel}>ACTIVE MISSIONS</Text>
          <Text style={styles.researchBandValue}>{running}</Text>
        </View>
        <View style={styles.researchBandItem}>
          <Text style={styles.researchBandLabel}>EXPERIMENTS</Text>
          <Text style={styles.researchBandValue}>{experiments.length}</Text>
        </View>
        <View style={styles.researchBandItem}>
          <Text style={styles.researchBandLabel}>AI SEATS</Text>
          <Text style={styles.researchBandValue}>{Array.isArray(lab?.seats) ? lab.seats.length : 0}</Text>
        </View>
      </View>

      <View style={styles.consoleLine}>
        <Text style={styles.consolePrompt}>research://</Text>
        <Text style={styles.consoleText}>
          {missionState?.mission?.objective ?? "활성 미션이 없습니다."}
        </Text>
      </View>

      <View style={styles.researchSection}>
        <Text style={styles.researchSectionTitle}>RECENT EXPERIMENTS</Text>
        {recentExperiments.length ? (
          recentExperiments.map((item: any) => (
            <View key={item.id} style={styles.researchRow}>
              <View style={styles.flex}>
                <Text style={styles.researchRowTitle} numberOfLines={1}>{item.title}</Text>
                <Text style={styles.researchRowSub}>{String(item.status ?? "unknown")}</Text>
              </View>
              <Text style={styles.researchRowTag}>EXP</Text>
            </View>
          ))
        ) : (
          <Text style={styles.surfaceMuted}>기록된 Experiment Work가 없습니다.</Text>
        )}
      </View>

      <View style={styles.researchSection}>
        <Text style={styles.researchSectionTitle}>LIVE ACTIVITY</Text>
        {recentActivity.length ? (
          recentActivity.map((item: any) => (
            <View key={item.id} style={styles.researchRow}>
              <View style={styles.flex}>
                <Text style={styles.researchRowTitle}>{activityLabel(item.type)}</Text>
                <Text style={styles.researchRowSub} numberOfLines={1}>
                  {item.created_at ? String(item.created_at).replace("T", " ").slice(0, 19) : "시간 미상"}
                </Text>
              </View>
              <Text style={styles.researchRowTag}>{String(item.id ?? "").slice(-6)}</Text>
            </View>
          ))
        ) : (
          <Text style={styles.surfaceMuted}>아직 표시할 Runtime activity가 없습니다.</Text>
        )}
      </View>

      <Text style={styles.researchFootnote}>
        모든 수치는 canonical Mission / Work / Event telemetry의 읽기 전용 projection입니다. benchmark 결과는 실제 Eval artifact가 연결되기 전까지 표시하지 않습니다.
      </Text>
    </View>
  );
}

export function LabWorkspaceSurface(props: Props) {
  if (!props.lab) return null;

  if (props.labKey === "quantrade") {
    return (
      <QuanTradeFloor
        lab={props.lab}
        missions={props.missions}
        missionState={props.missionState}
        tradingFloor={props.tradingFloor}
      />
    );
  }
  if (props.labKey === "llm") {
    return <LlmResearchConsole lab={props.lab} missions={props.missions} missionState={props.missionState} />;
  }
  if (props.labKey === "design") {
    return <DesignStudioSurface lab={props.lab} missions={props.missions} missionState={props.missionState} />;
  }
  if (props.labKey === "runtime") {
    return (
      <RuntimeDevConsoleSurface
        lab={props.lab}
        missions={props.missions}
        missionState={props.missionState}
        runtimeOps={props.runtimeOps}
        runtimeDashboard={props.runtimeDashboard}
      />
    );
  }
  return null;
}

const styles = StyleSheet.create({
  flex: { flex: 1, minWidth: 0 },
  surfaceHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", gap: 12 },
  surfaceTitle: { fontSize: 20, lineHeight: 25, fontWeight: "700", color: "#11110F", marginTop: 3 },
  surfaceMuted: { fontSize: 11, lineHeight: 17, color: "#77776F" },
  tileGrid: { flexDirection: "row", flexWrap: "wrap", gap: 7 },
  tile: {
    width: "48%",
    minHeight: 82,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "#CFCFC7",
    padding: 10,
    justifyContent: "space-between",
  },
  tileInverse: { borderColor: "#454541", backgroundColor: "#181816" },
  tileLabel: { fontFamily: mono, fontSize: 8, lineHeight: 12, letterSpacing: 0.8, color: "#77776F", fontWeight: "700" },
  tileValue: { fontFamily: mono, fontSize: 16, lineHeight: 20, color: "#11110F", fontWeight: "700", marginTop: 6 },
  tileDetail: { fontFamily: mono, fontSize: 8, lineHeight: 12, color: "#77776F", marginTop: 6 },
  textInverse: { color: "#F4F4EF" },
  textInverseMuted: { color: "#A7A79F" },

  tradingFloor: { backgroundColor: "#11110F", padding: 14, gap: 10, borderWidth: 1, borderColor: "#282824" },
  marketLabToggle: { flexDirection: "row", alignItems: "center", gap: 10, borderTopWidth: StyleSheet.hairlineWidth, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: "#3E3E39", paddingVertical: 10 },
  marketLabToggleTitle: { fontSize: 10, lineHeight: 15, color: "#D8D8D1", fontWeight: "700" },
  marketLabToggleMeta: { marginTop: 2, fontSize: 7.5, lineHeight: 12, color: "#7E7E77" },
  marketLabToggleAction: { fontFamily: mono, fontSize: 7, color: "#A2A29A", fontWeight: "700" },
  tradingEyebrow: { fontFamily: mono, fontSize: 8, letterSpacing: 1.2, color: "#9A9A92", fontWeight: "700" },
  tradingTitle: { fontSize: 22, lineHeight: 27, color: "#F4F4EF", fontWeight: "700", marginTop: 4 },
  liveTag: { fontFamily: mono, fontSize: 8, color: "#E8E8E0", fontWeight: "700", paddingTop: 2 },
  tradingStrip: { flexDirection: "row", justifyContent: "space-between", borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#454541", paddingTop: 9 },
  tradingStripLabel: { fontFamily: mono, fontSize: 8, color: "#9A9A92", letterSpacing: 0.8 },
  tradingStripValue: { fontFamily: mono, fontSize: 9, color: "#F4F4EF", fontWeight: "700" },
  tradingNotice: { fontSize: 9, lineHeight: 14, color: "#8F8F87" },

  researchConsole: { borderWidth: 1, borderColor: "#BDBDB5", padding: 14, gap: 10, backgroundColor: "#F8F8F4" },
  researchEyebrow: { fontFamily: mono, fontSize: 8, letterSpacing: 1.2, color: "#5F5F59", fontWeight: "700" },
  researchStatus: { fontFamily: mono, fontSize: 8, color: "#41413C", fontWeight: "700", paddingTop: 2 },
  researchGrid: { flexDirection: "row", flexWrap: "wrap", gap: 7 },
  researchBand: { flexDirection: "row", borderTopWidth: StyleSheet.hairlineWidth, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: "#CFCFC7", paddingVertical: 8 },
  researchBandItem: { flex: 1 },
  researchBandLabel: { fontFamily: mono, fontSize: 7, color: "#77776F", letterSpacing: 0.5 },
  researchBandValue: { fontFamily: mono, fontSize: 14, color: "#11110F", fontWeight: "700", marginTop: 3 },
  consoleLine: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#CFCFC7", paddingTop: 9, flexDirection: "row", gap: 7 },
  consolePrompt: { fontFamily: mono, fontSize: 9, color: "#11110F", fontWeight: "700" },
  consoleText: { flex: 1, fontSize: 10, lineHeight: 15, color: "#55554F" },
  researchSection: { gap: 3 },
  researchSectionTitle: { fontFamily: mono, fontSize: 8, color: "#5F5F59", letterSpacing: 0.8, fontWeight: "700", marginBottom: 2 },
  researchRow: { flexDirection: "row", alignItems: "center", gap: 8, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#D7D7D0", paddingVertical: 6 },
  researchRowTitle: { fontSize: 10, lineHeight: 14, color: "#22221F", fontWeight: "600" },
  researchRowSub: { fontFamily: mono, fontSize: 7, lineHeight: 11, color: "#77776F", marginTop: 1 },
  researchRowTag: { fontFamily: mono, fontSize: 7, color: "#5F5F59", fontWeight: "700" },
  researchFootnote: { fontSize: 8, lineHeight: 13, color: "#77776F" },

});
