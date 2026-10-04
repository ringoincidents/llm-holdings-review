import { Platform, StyleSheet, Text, View } from "react-native";

const mono = Platform.select({ ios: "Menlo", android: "monospace", default: "monospace" });

type Props = {
  lab: any;
  missions: any[];
  missionState: any;
  runtimeOps?: any;
  runtimeDashboard?: any;
};

function shortSha(value: any) {
  const text = String(value ?? "").trim();
  return text ? text.slice(0, 10) : "—";
}

function statusText(value: any) {
  return String(value ?? "unknown").replaceAll("_", " ").toUpperCase();
}

function openStatus(value: any) {
  return !["completed", "cancelled", "superseded"].includes(String(value ?? ""));
}

function Tile({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <View style={styles.tile}>
      <Text style={styles.tileLabel}>{label}</Text>
      <Text style={styles.tileValue} numberOfLines={2}>{value}</Text>
      {detail ? <Text style={styles.tileDetail} numberOfLines={2}>{detail}</Text> : null}
    </View>
  );
}

export function RuntimeDevConsoleSurface({
  lab,
  missions,
  missionState,
  runtimeOps,
  runtimeDashboard,
}: Props) {
  const work = Array.isArray(lab?.work) ? lab.work : [];
  const assignments = Array.isArray(lab?.assignments) ? lab.assignments : [];
  const seats = Array.isArray(lab?.seats) ? lab.seats : [];
  const history = Array.isArray(lab?.history) ? lab.history : [];
  const evidence = Array.isArray(missionState?.execution_evidence)
    ? missionState.execution_evidence
    : [];
  const delivery = missionState?.delivery ?? {};

  const developerSeatIds = new Set(
    seats
      .filter((seat: any) =>
        ["developer", "maintainer", "release_engineer"].includes(String(seat?.seat_key ?? "")),
      )
      .map((seat: any) => seat.id),
  );
  const developerWorkIds = new Set(
    assignments
      .filter(
        (item: any) =>
          item?.object_type === "work" && developerSeatIds.has(item?.seat_id),
      )
      .map((item: any) => item.object_id),
  );
  const developerWork = work.filter((item: any) => developerWorkIds.has(item?.id));
  const openDeveloperWork = developerWork.filter((item: any) => openStatus(item?.status));

  const passedChecks = evidence.reduce(
    (total: number, item: any) => total + (Array.isArray(item?.passed_checks) ? item.passed_checks.length : 0),
    0,
  );
  const evidenceBlockers = evidence.filter((item: any) =>
    ["blocked", "failed"].includes(String(item?.status ?? "")),
  );
  const workBlockers = work.filter((item: any) =>
    ["blocked", "failed", "review_required"].includes(String(item?.status ?? "")),
  );
  const blockerCount =
    evidenceBlockers.length +
    workBlockers.length +
    (delivery?.blocker ? 1 : 0);

  const opsRuntime = runtimeOps?.runtime ?? {};
  const repo = runtimeOps?.repository ?? {};
  const ci = repo?.ci ?? {};
  const productionState =
    repo?.deployment_matches_main === true
      ? "SYNCED"
      : repo?.deployment_matches_main === false
        ? "DRIFT"
        : opsRuntime?.ok
          ? "RUNNING"
          : "UNKNOWN";

  const activeMissions = missions.filter((mission: any) =>
    ["queued", "running", "review_required", "awaiting_founder", "delivery_blocked", "waiting_for_delivery"].includes(
      String(mission?.status ?? ""),
    ),
  ).length;

  const recentActivity = [...history]
    .filter((item: any) =>
      [
        "LAB_WORK_STARTED",
        "LAB_WORK_COMPLETED",
        "LAB_WORK_FAILED",
        "LAB_MISSION_DELIVERY_CREATED",
        "LAB_MISSION_DELIVERY_MERGED",
        "LAB_MISSION_DELIVERY_HELD",
        "TOOL_EXECUTED",
        "TOOL_FAILED",
      ].includes(String(item?.type ?? "")),
    )
    .slice(-6)
    .reverse();

  const blockerTitle =
    delivery?.blocker_help?.title ??
    (delivery?.blocker ? statusText(delivery.blocker) : null);
  const blockerSummary =
    delivery?.blocker_help?.summary ??
    (workBlockers.length ? "Runtime Work에 검토가 필요한 상태가 있습니다." : null);

  return (
    <View style={styles.console}>
      <View style={styles.header}>
        <View style={styles.flex}>
          <Text style={styles.eyebrow}>RUNTIME ENGINEERING / DEV CONSOLE</Text>
          <Text style={styles.title}>shared OS operations</Text>
        </View>
        <Text style={styles.live}>{opsRuntime?.ok ? "● RUNTIME UP" : "○ UNKNOWN"}</Text>
      </View>

      <View style={styles.releaseBar}>
        <View style={styles.releaseMain}>
          <Text style={styles.releaseLabel}>MAIN</Text>
          <Text style={styles.releaseSha}>{shortSha(repo?.main_sha)}</Text>
        </View>
        <Text style={styles.releaseArrow}>→</Text>
        <View style={styles.releaseMain}>
          <Text style={styles.releaseLabel}>PRODUCTION</Text>
          <Text style={styles.releaseSha}>{shortSha(opsRuntime?.deployed_sha)}</Text>
        </View>
        <Text style={styles.releaseState}>{productionState}</Text>
      </View>

      <View style={styles.grid}>
        <Tile
          label="MAIN CI"
          value={statusText(ci?.status)}
          detail={Number.isFinite(Number(ci?.check_count)) ? `${ci.check_count} check runs` : "GitHub 상태 미확인"}
        />
        <Tile
          label="DELIVERY"
          value={delivery?.stage ? statusText(delivery.stage) : "—"}
          detail={delivery?.pr_number ? `PR #${delivery.pr_number} · target ${delivery?.target ?? "—"}` : "활성 PR 없음"}
        />
        <Tile
          label="DEV WORK"
          value={String(openDeveloperWork.length)}
          detail={developerWork.length ? `${developerWork.length} assigned total` : "Developer 배정 없음"}
        />
        <Tile
          label="BLOCKERS"
          value={String(blockerCount)}
          detail={blockerCount ? "조치/검토 필요" : "clear"}
        />
      </View>

      <View style={styles.pipeline}>
        <View style={styles.pipelineStep}>
          <Text style={styles.pipelineLabel}>IMPLEMENT</Text>
          <Text style={styles.pipelineValue}>{passedChecks > 0 ? `${passedChecks} CHECKS` : "WAIT"}</Text>
        </View>
        <View style={styles.pipelineStep}>
          <Text style={styles.pipelineLabel}>CI</Text>
          <Text style={styles.pipelineValue}>{statusText(ci?.status)}</Text>
        </View>
        <View style={styles.pipelineStep}>
          <Text style={styles.pipelineLabel}>MERGE</Text>
          <Text style={styles.pipelineValue}>{delivery?.merged_sha ? shortSha(delivery.merged_sha) : delivery?.pr_number ? "PR READY" : "—"}</Text>
        </View>
        <View style={styles.pipelineStep}>
          <Text style={styles.pipelineLabel}>DEPLOY</Text>
          <Text style={styles.pipelineValue}>{productionState}</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>DEVELOPER WORK</Text>
        {developerWork.length ? (
          [...developerWork].slice(-5).reverse().map((item: any) => (
            <View key={item.id} style={styles.row}>
              <View style={styles.flex}>
                <Text style={styles.rowTitle} numberOfLines={2}>{item?.title ?? "Untitled Work"}</Text>
                <Text style={styles.rowSub}>{String(item?.work_type ?? "work").toUpperCase()} · {String(item?.id ?? "").slice(-7)}</Text>
              </View>
              <Text style={styles.rowTag}>{statusText(item?.status)}</Text>
            </View>
          ))
        ) : (
          <Text style={styles.muted}>현재 Developer/Runtime Maintainer에 배정된 Work가 없습니다.</Text>
        )}
      </View>

      <View style={styles.opsBand}>
        <View style={styles.opsMetric}>
          <Text style={styles.opsLabel}>ACTIVE MISSIONS</Text>
          <Text style={styles.opsValue}>{activeMissions}</Text>
        </View>
        <View style={styles.opsMetric}>
          <Text style={styles.opsLabel}>RUNNING AGENTS</Text>
          <Text style={styles.opsValue}>{runtimeDashboard?.agents_running ?? "—"}</Text>
        </View>
        <View style={styles.opsMetric}>
          <Text style={styles.opsLabel}>TODAY COST</Text>
          <Text style={styles.opsValue}>
            {Number.isFinite(Number(runtimeDashboard?.today_cost_usd))
              ? `$${Number(runtimeDashboard.today_cost_usd).toFixed(4)}`
              : "—"}
          </Text>
        </View>
      </View>

      {blockerTitle ? (
        <View style={styles.blocker}>
          <Text style={styles.blockerLabel}>BLOCKER</Text>
          <Text style={styles.blockerTitle}>{blockerTitle}</Text>
          {blockerSummary ? <Text style={styles.blockerSummary}>{blockerSummary}</Text> : null}
        </View>
      ) : null}

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>OPERATIONS LOG</Text>
        {recentActivity.length ? (
          recentActivity.map((item: any) => (
            <View key={item.id} style={styles.logRow}>
              <Text style={styles.logType}>{String(item?.type ?? "EVENT").replace("LAB_", "")}</Text>
              <Text style={styles.logTime}>
                {item?.created_at ? String(item.created_at).replace("T", " ").slice(0, 19) : "시간 미상"}
              </Text>
            </View>
          ))
        ) : (
          <Text style={styles.muted}>표시할 최근 delivery/runtime activity가 없습니다.</Text>
        )}
      </View>

      <View style={styles.shellLine}>
        <Text style={styles.prompt}>runtime $</Text>
        <Text style={styles.shellText}>
          {opsRuntime?.environment ?? "environment ?"} / {opsRuntime?.service ?? "service ?"} · GitHub {repo?.github_status ?? "unavailable"} · canonical read-only ops projection
        </Text>
      </View>

      <Text style={styles.footnote}>
        GitHub main/CI는 읽기 전용 실시간 조회이며, production SHA는 실행 중 Runtime 환경에서 가져옵니다. 변경·merge·배포 권한은 기존 Mission governance를 그대로 따릅니다.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, minWidth: 0 },
  console: {
    borderWidth: 1,
    borderColor: "#252522",
    backgroundColor: "#E6E6E1",
    padding: 14,
    gap: 10,
  },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", gap: 12 },
  eyebrow: { fontFamily: mono, fontSize: 8, color: "#5B5B55", letterSpacing: 1.1, fontWeight: "700" },
  title: { fontFamily: mono, fontSize: 18, lineHeight: 23, color: "#11110F", fontWeight: "700", marginTop: 4 },
  live: { fontFamily: mono, fontSize: 8, color: "#33332F", fontWeight: "700", paddingTop: 2 },

  releaseBar: {
    backgroundColor: "#11110F",
    padding: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  releaseMain: { minWidth: 0 },
  releaseLabel: { fontFamily: mono, fontSize: 6.5, color: "#777770", letterSpacing: 0.7 },
  releaseSha: { fontFamily: mono, fontSize: 10, color: "#F2F2ED", fontWeight: "700", marginTop: 2 },
  releaseArrow: { fontFamily: mono, fontSize: 10, color: "#71716B" },
  releaseState: { marginLeft: "auto", fontFamily: mono, fontSize: 8, color: "#F2F2ED", fontWeight: "700" },

  grid: { flexDirection: "row", flexWrap: "wrap", gap: 7 },
  tile: { width: "48%", minHeight: 82, borderWidth: StyleSheet.hairlineWidth, borderColor: "#BEBEB7", backgroundColor: "#F2F2ED", padding: 10, justifyContent: "space-between" },
  tileLabel: { fontFamily: mono, fontSize: 7, lineHeight: 11, color: "#73736C", letterSpacing: 0.6, fontWeight: "700" },
  tileValue: { fontFamily: mono, fontSize: 14, lineHeight: 18, color: "#141412", fontWeight: "700", marginTop: 6 },
  tileDetail: { fontFamily: mono, fontSize: 7, lineHeight: 11, color: "#777770", marginTop: 6 },

  pipeline: { flexDirection: "row", borderTopWidth: StyleSheet.hairlineWidth, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: "#BEBEB7", paddingVertical: 8 },
  pipelineStep: { flex: 1 },
  pipelineLabel: { fontFamily: mono, fontSize: 6.5, color: "#777770", letterSpacing: 0.5 },
  pipelineValue: { fontFamily: mono, fontSize: 8, color: "#22221F", fontWeight: "700", marginTop: 3 },

  section: { gap: 3 },
  sectionTitle: { fontFamily: mono, fontSize: 8, color: "#55554F", letterSpacing: 0.8, fontWeight: "700", marginBottom: 2 },
  row: { flexDirection: "row", alignItems: "center", gap: 8, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#C8C8C1", paddingVertical: 7 },
  rowTitle: { fontSize: 10, lineHeight: 15, color: "#22221F", fontWeight: "600" },
  rowSub: { fontFamily: mono, fontSize: 6.5, lineHeight: 10, color: "#7D7D75", marginTop: 2 },
  rowTag: { fontFamily: mono, fontSize: 7, color: "#484843", fontWeight: "700" },
  muted: { fontSize: 9, lineHeight: 14, color: "#777770" },

  opsBand: { flexDirection: "row", backgroundColor: "#DADAD4", paddingVertical: 8, paddingHorizontal: 9 },
  opsMetric: { flex: 1 },
  opsLabel: { fontFamily: mono, fontSize: 6.5, color: "#73736C" },
  opsValue: { fontFamily: mono, fontSize: 12, color: "#1E1E1B", fontWeight: "700", marginTop: 3 },

  blocker: { borderLeftWidth: 3, borderLeftColor: "#343430", paddingLeft: 9, paddingVertical: 2 },
  blockerLabel: { fontFamily: mono, fontSize: 6.5, color: "#7A7A73", letterSpacing: 0.7 },
  blockerTitle: { fontSize: 11, lineHeight: 16, color: "#242421", fontWeight: "700", marginTop: 3 },
  blockerSummary: { fontSize: 9, lineHeight: 14, color: "#65655F", marginTop: 2 },

  logRow: { flexDirection: "row", justifyContent: "space-between", gap: 8, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#CBCBC4", paddingVertical: 6 },
  logType: { flex: 1, fontFamily: mono, fontSize: 7, color: "#44443F", fontWeight: "700" },
  logTime: { fontFamily: mono, fontSize: 6.5, color: "#85857E" },

  shellLine: { backgroundColor: "#11110F", paddingHorizontal: 10, paddingVertical: 8, flexDirection: "row", gap: 7 },
  prompt: { fontFamily: mono, fontSize: 8, color: "#F2F2ED", fontWeight: "700" },
  shellText: { flex: 1, fontFamily: mono, fontSize: 7, lineHeight: 12, color: "#A7A7A0" },
  footnote: { fontSize: 8, lineHeight: 13, color: "#777770" },
});
