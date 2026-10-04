import { useEffect, useMemo, useState } from "react";
import {
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { api } from "./api";

const mono = Platform.select({ ios: "Menlo", android: "monospace", default: "monospace" });

type Props = {
  labId?: string | null;
  labTitle?: string | null;
};

function statusLabel(value?: string) {
  const labels: Record<string, string> = {
    current: "현재",
    contested: "충돌",
    empty: "비어 있음",
    no_action: "미실행",
    planned: "계획",
    in_progress: "진행 중",
    implemented: "구현",
    verified: "검증",
    deployed: "배포",
    superseded: "대체됨",
    candidate: "후보",
    historical: "과거",
  };
  return labels[String(value ?? "")] ?? String(value ?? "—");
}

function shortId(value?: string) {
  if (!value) return "—";
  return value.length > 12 ? value.slice(0, 12) : value;
}

export function FounderKnowledgeObservatory({ labId, labTitle }: Props) {
  const [scope, setScope] = useState<"holdings" | "lab">("holdings");
  const [query, setQuery] = useState("");
  const [topics, setTopics] = useState<any[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const scopeId = scope === "holdings" ? "holdings" : String(labId ?? "");

  async function loadTopics(nextQuery = query) {
    if (scope === "lab" && !labId) return;
    setLoading(true);
    setError("");
    try {
      const result = await api.knowledgeTopics(
        scope,
        scopeId,
        nextQuery.trim(),
      );
      const next = (Array.isArray(result?.topics) ? result.topics : []).filter(
        (item: any) => !String(item?.key ?? "").startsWith("e2e-memory-smoke-"),
      );
      setTopics(next);
      if (selectedKey && !next.some((item: any) => item.key === selectedKey)) {
        setSelectedKey(null);
        setDetail(null);
      }
    } catch (e: any) {
      setError(e?.message ?? "지식 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function openTopic(key: string) {
    setLoading(true);
    setError("");
    try {
      const next = await api.knowledgeTopic(key, scope, scopeId);
      setSelectedKey(key);
      setDetail(next);
    } catch (e: any) {
      setError(e?.message ?? "지식 주제를 열지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setSelectedKey(null);
    setDetail(null);
    void loadTopics("");
  }, [scope, labId]);

  const currentClaims = detail?.current_knowledge ?? [];
  const timeline = useMemo(
    () => [...(detail?.timeline ?? [])].reverse().slice(0, 8),
    [detail],
  );
  const belief = detail?.why_believe_this ?? [];
  const gaps = detail?.open_gaps ?? [];

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <View style={styles.flex}>
          <Text style={styles.eyebrow}>FOUNDER / KNOWLEDGE OBSERVATORY</Text>
          <Text style={styles.title}>조직 지식</Text>
        </View>
        <Text style={styles.readOnly}>READ ONLY</Text>
      </View>

      <View style={styles.scopeRow}>
        <Pressable
          onPress={() => setScope("holdings")}
          style={[styles.scopeButton, scope === "holdings" && styles.scopeButtonActive]}
        >
          <Text style={[styles.scopeText, scope === "holdings" && styles.scopeTextActive]}>
            HOLDINGS
          </Text>
        </Pressable>
        <Pressable
          disabled={!labId}
          onPress={() => setScope("lab")}
          style={[
            styles.scopeButton,
            scope === "lab" && styles.scopeButtonActive,
            !labId && styles.disabled,
          ]}
        >
          <Text style={[styles.scopeText, scope === "lab" && styles.scopeTextActive]}>
            {labTitle ? "LAB · " + labTitle : "CURRENT LAB"}
          </Text>
        </Pressable>
      </View>

      <View style={styles.searchRow}>
        <TextInput
          value={query}
          onChangeText={setQuery}
          onSubmitEditing={() => void loadTopics()}
          placeholder="주제 검색"
          placeholderTextColor="#92928A"
          style={styles.search}
          autoCorrect={false}
        />
        <Pressable onPress={() => void loadTopics()} style={styles.searchButton}>
          <Text style={styles.searchButtonText}>{loading ? "…" : "검색"}</Text>
        </Pressable>
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      {!selectedKey ? (
        <View style={styles.topicList}>
          {topics.length ? topics.slice(0, 12).map((item: any) => (
            <Pressable
              key={item.id}
              onPress={() => void openTopic(item.key)}
              style={styles.topicRow}
            >
              <View style={styles.flex}>
                <Text style={styles.topicTitle}>{item.title}</Text>
                <Text style={styles.topicSummary} numberOfLines={2}>
                  {item.current_summary || item.description || "현재 요약 없음"}
                </Text>
                <Text style={styles.meta}>
                  {statusLabel(item.projection_status)}
                  {" · "}{statusLabel(item.action_state)}
                  {" · "}gap {item.open_gap_count ?? 0}
                </Text>
              </View>
              <Text style={styles.arrow}>›</Text>
            </Pressable>
          )) : (
            <Text style={styles.empty}>
              {loading ? "불러오는 중…" : "이 scope에 표시할 지식 주제가 없습니다."}
            </Text>
          )}
        </View>
      ) : (
        <View style={styles.detail}>
          <Pressable
            onPress={() => {
              setSelectedKey(null);
              setDetail(null);
            }}
          >
            <Text style={styles.back}>‹ 주제 목록</Text>
          </Pressable>

          <View style={styles.detailHeader}>
            <View style={styles.flex}>
              <Text style={styles.detailTitle}>{detail?.topic?.title ?? selectedKey}</Text>
              <Text style={styles.meta}>
                {statusLabel(detail?.projection_status)}
                {" · "}{statusLabel(detail?.action_state)}
                {" · "}{shortId(detail?.topic?.id)}
              </Text>
            </View>
            {gaps.length ? (
              <Text style={styles.gapBadge}>GAP {gaps.length}</Text>
            ) : (
              <Text style={styles.clearBadge}>CLEAR</Text>
            )}
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>CURRENT KNOWLEDGE</Text>
            {currentClaims.length ? currentClaims.map((claim: any) => (
              <View key={claim.id} style={styles.claim}>
                <Text style={styles.claimText}>{claim.content}</Text>
                <Text style={styles.meta}>
                  {claim.trust_class} · {claim.authority_level} · {claim.source_type}:{shortId(claim.source_id)}
                </Text>
              </View>
            )) : <Text style={styles.empty}>현재 유효 Claim이 없습니다.</Text>}
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>WHY DO WE BELIEVE THIS?</Text>
            {belief.length ? belief.map((item: any) => (
              <View key={item.claim?.id} style={styles.evidenceRow}>
                <Text style={styles.evidenceTitle}>
                  {item.provenance?.trust_class ?? "unknown"} / {item.provenance?.authority_level ?? "—"}
                </Text>
                <Text style={styles.meta}>
                  source {item.provenance?.source_type ?? "—"}:{shortId(item.provenance?.source_id)}
                  {" · "}support {item.supporting_relations?.length ?? 0}
                  {" · "}verify {item.verification_actions?.length ?? 0}
                </Text>
              </View>
            )) : <Text style={styles.empty}>현재 Claim provenance가 없습니다.</Text>}
          </View>

          <View style={styles.band}>
            <View style={styles.bandCell}>
              <Text style={styles.bandLabel}>ACTION</Text>
              <Text style={styles.bandValue}>{statusLabel(detail?.action_state)}</Text>
            </View>
            <View style={styles.bandCell}>
              <Text style={styles.bandLabel}>HISTORY</Text>
              <Text style={styles.bandValue}>{detail?.history?.length ?? 0}</Text>
            </View>
            <View style={styles.bandCell}>
              <Text style={styles.bandLabel}>GRAPH</Text>
              <Text style={styles.bandValue}>
                {detail?.graph?.nodes?.length ?? 0}/{detail?.graph?.edges?.length ?? 0}
              </Text>
            </View>
          </View>

          {gaps.length ? (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>OPEN GAPS</Text>
              {gaps.map((gap: any, index: number) => (
                <View key={String(gap.kind) + "-" + String(index)} style={styles.gapRow}>
                  <Text style={styles.gapKind}>{gap.kind}</Text>
                  <Text style={styles.gapText}>{gap.message}</Text>
                </View>
              ))}
            </View>
          ) : null}

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>TIMELINE</Text>
            {timeline.length ? timeline.map((item: any, index: number) => (
              <View key={String(item.kind) + "-" + String(item.id) + "-" + String(index)} style={styles.timelineRow}>
                <Text style={styles.timelineKind}>{String(item.kind ?? "event").toUpperCase()}</Text>
                <View style={styles.flex}>
                  <Text style={styles.timelineText} numberOfLines={2}>{item.summary}</Text>
                  <Text style={styles.meta}>{item.at ? String(item.at).replace("T", " ").slice(0, 19) : "시간 없음"}</Text>
                </View>
              </View>
            )) : <Text style={styles.empty}>표시할 변화 이력이 없습니다.</Text>}
          </View>

          <Text style={styles.footnote}>
            이 화면은 canonical KnowledgeConcept / Claim / Relation / ActionBinding의 읽기 전용 projection입니다. 여기서 지식을 직접 덮어쓰지 않습니다.
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    borderWidth: 1,
    borderColor: "#BEBEB6",
    backgroundColor: "#FAFAF6",
    padding: 12,
    gap: 10,
  },
  flex: { flex: 1, minWidth: 0 },
  header: { flexDirection: "row", alignItems: "flex-start", gap: 12 },
  eyebrow: { fontFamily: mono, fontSize: 8, letterSpacing: 1.1, color: "#6A6A64", fontWeight: "700" },
  title: { fontSize: 20, lineHeight: 25, color: "#11110F", fontWeight: "700", marginTop: 3 },
  readOnly: { fontFamily: mono, fontSize: 7, color: "#77776F", paddingTop: 2 },
  scopeRow: { flexDirection: "row", gap: 5 },
  scopeButton: { borderWidth: StyleSheet.hairlineWidth, borderColor: "#C7C7C0", paddingHorizontal: 8, paddingVertical: 6, flex: 1 },
  scopeButtonActive: { backgroundColor: "#1A1A18", borderColor: "#1A1A18" },
  scopeText: { fontFamily: mono, fontSize: 7, color: "#676761", fontWeight: "700" },
  scopeTextActive: { color: "#F4F4EF" },
  disabled: { opacity: 0.35 },
  searchRow: { flexDirection: "row", gap: 5 },
  search: { flex: 1, minHeight: 36, borderWidth: StyleSheet.hairlineWidth, borderColor: "#C7C7C0", paddingHorizontal: 9, fontSize: 11, color: "#181816" },
  searchButton: { minWidth: 52, alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: "#22221F" },
  searchButtonText: { fontSize: 10, color: "#22221F", fontWeight: "700" },
  error: { fontSize: 9, lineHeight: 14, color: "#7A2C24" },
  topicList: { gap: 0 },
  topicRow: { flexDirection: "row", gap: 8, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#D5D5CE", paddingVertical: 9 },
  topicTitle: { fontSize: 11, lineHeight: 15, color: "#1B1B18", fontWeight: "700" },
  topicSummary: { fontSize: 9, lineHeight: 14, color: "#55554F", marginTop: 2 },
  meta: { fontFamily: mono, fontSize: 7, lineHeight: 11, color: "#7B7B74", marginTop: 3 },
  arrow: { fontSize: 18, color: "#77776F", alignSelf: "center" },
  empty: { fontSize: 9, lineHeight: 14, color: "#77776F", paddingVertical: 8 },
  detail: { gap: 10 },
  back: { fontSize: 9, color: "#55554F", fontWeight: "600" },
  detailHeader: { flexDirection: "row", gap: 10, alignItems: "flex-start" },
  detailTitle: { fontSize: 16, lineHeight: 21, color: "#171714", fontWeight: "700" },
  gapBadge: { fontFamily: mono, fontSize: 7, color: "#6D2B22", borderWidth: 1, borderColor: "#9B5B52", paddingHorizontal: 6, paddingVertical: 3 },
  clearBadge: { fontFamily: mono, fontSize: 7, color: "#484842", borderWidth: 1, borderColor: "#909089", paddingHorizontal: 6, paddingVertical: 3 },
  section: { gap: 5 },
  sectionTitle: { fontFamily: mono, fontSize: 8, color: "#5D5D57", letterSpacing: 0.8, fontWeight: "700" },
  claim: { borderLeftWidth: 2, borderLeftColor: "#33332F", paddingLeft: 8, paddingVertical: 3 },
  claimText: { fontSize: 10, lineHeight: 16, color: "#22221F" },
  evidenceRow: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#D7D7D0", paddingVertical: 6 },
  evidenceTitle: { fontFamily: mono, fontSize: 8, color: "#2F2F2B", fontWeight: "700" },
  band: { flexDirection: "row", borderTopWidth: StyleSheet.hairlineWidth, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: "#CFCFC7", paddingVertical: 8 },
  bandCell: { flex: 1 },
  bandLabel: { fontFamily: mono, fontSize: 7, color: "#77776F" },
  bandValue: { fontFamily: mono, fontSize: 12, color: "#1A1A18", fontWeight: "700", marginTop: 2 },
  gapRow: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#D7D7D0", paddingVertical: 6 },
  gapKind: { fontFamily: mono, fontSize: 7, color: "#75362D", fontWeight: "700" },
  gapText: { fontSize: 9, lineHeight: 14, color: "#4E4E48", marginTop: 2 },
  timelineRow: { flexDirection: "row", gap: 8, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#D7D7D0", paddingVertical: 6 },
  timelineKind: { width: 52, fontFamily: mono, fontSize: 7, color: "#686862", fontWeight: "700" },
  timelineText: { fontSize: 9, lineHeight: 14, color: "#33332F" },
  footnote: { fontSize: 8, lineHeight: 13, color: "#77776F" },
});
