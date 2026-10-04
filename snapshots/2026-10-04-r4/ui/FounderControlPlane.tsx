import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { api } from "./api";

type Props = {
  organization: any;
  busy?: boolean;
  onDispatched: (result: any) => Promise<void>;
  onOpenMission: (labId: string, missionId: string) => Promise<void>;
};

const ACTIVE = new Set([
  "created",
  "queued",
  "running",
  "awaiting_founder",
  "review_required",
  "budget_blocked",
  "waiting_for_delivery",
  "delivery_blocked",
]);

function statusLabel(value?: string) {
  const map: Record<string, string> = {
    created: "준비 중",
    queued: "대기",
    running: "진행 중",
    awaiting_founder: "내 결정 필요",
    review_required: "검토 필요",
    budget_blocked: "예산 확인 필요",
    waiting_for_delivery: "배포 대기",
    delivery_blocked: "배포 확인 필요",
    completed: "완료",
    deferred: "보류",
    cancelled: "폐기",
    failed: "중단됨",
  };
  return map[String(value ?? "").toLowerCase()] ?? String(value ?? "—");
}

function recordClassification(value?: string) {
  const map: Record<string, string> = {
    extends: "기존 방향 확장",
    possible_extends: "기존 방향 확장 가능",
    narrows: "범위 구체화",
    possible_narrows: "범위 구체화 가능",
    conflict: "기존 방향과 충돌",
    supersession_candidate: "기존 방향 변경 가능",
    possible_conflict_or_supersession: "기존 방향 변경 가능",
    new_concept: "새 개념 제안",
    related: "관련 기록",
    supports: "기존 방향 지지",
    duplicate: "기존 기록과 동일",
    unresolved: "판단 필요",
  };
  return map[String(value ?? "").toLowerCase()] ?? "기록 검토";
}

function recordSuggestion(disposition?: string, action?: string) {
  const dispositions: Record<string, string> = {
    reference_only: "참고 기록",
    watch: "관찰",
    experiment: "실험",
    implement: "구현 후보",
    propose_policy: "정책 제안",
    supersede: "기존 방향 대체 후보",
    archive: "보관",
  };
  const actions: Record<string, string> = {
    review: "Founder 검토",
    adopt: "현재 지식 반영 검토",
    supersede: "대체 검토",
    archive: "보관 검토",
    reject: "반려 검토",
  };
  const d = dispositions[String(disposition ?? "")] ?? "참고 기록";
  const a = actions[String(action ?? "")] ?? "Founder 검토";
  return `${d} · ${a}`;
}


export function FounderControlPlane({
  organization,
  busy = false,
  onDispatched,
  onOpenMission,
}: Props) {
  const [command, setCommand] = useState("");
  const [sending, setSending] = useState(false);
  const [receipt, setReceipt] = useState<any>(null);
  const [error, setError] = useState("");
  const [recordQueue, setRecordQueue] = useState<any[]>([]);
  const [recordBusy, setRecordBusy] = useState("");
  const [recordError, setRecordError] = useState("");

  const labById = useMemo(() => {
    const map = new Map<string, any>();
    for (const item of organization?.labs ?? []) {
      if (item?.lab?.id) map.set(item.lab.id, item);
    }
    return map;
  }, [organization]);

  const active = useMemo(
    () => (organization?.ledger ?? [])
      .filter((item: any) => item.mission_id && ACTIVE.has(String(item.status ?? "")))
      .slice()
      .reverse()
      .slice(0, 5),
    [organization],
  );

  const completed = useMemo(
    () => (organization?.ledger ?? [])
      .filter((item: any) => item.mission_id && String(item.status ?? "") === "completed")
      .slice()
      .reverse()
      .slice(0, 4),
    [organization],
  );

  const decisions = organization?.exception_inbox ?? [];
  const deferred = organization?.deferred_inbox ?? [];

  async function loadRecordQueue() {
    try {
      const result = await api.knowledgeRecordQueue();
      setRecordQueue(Array.isArray(result?.records) ? result.records : []);
      setRecordError("");
    } catch (e: any) {
      setRecordError(e?.message ?? "기록 검토함을 불러오지 못했습니다.");
    }
  }

  useEffect(() => {
    void loadRecordQueue();
  }, [organization?.updated_at]);

  async function semanticReviewRecord(item: any) {
    if (!item?.id || recordBusy) return;
    setRecordBusy(String(item.id));
    setRecordError("");
    try {
      await api.semanticReviewKnowledgeRecord(String(item.id), 0.01);
      await loadRecordQueue();
    } catch (e: any) {
      setRecordError(e?.message ?? "AI 기록 정리를 완료하지 못했습니다.");
    } finally {
      setRecordBusy("");
    }
  }

  async function resolveRecord(
    item: any,
    action: "adopt" | "supersede" | "reject" | "archive",
    disposition?: string,
  ) {
    if (!item?.id || recordBusy) return;
    setRecordBusy(String(item.id));
    setRecordError("");
    try {
      await api.resolveKnowledgeRecord(
        String(item.id),
        action,
        disposition,
        action === "supersede" ? item.target_claim_id : null,
        "",
      );
      await loadRecordQueue();
    } catch (e: any) {
      setRecordError(e?.message ?? "기록 처분을 저장하지 못했습니다.");
    } finally {
      setRecordBusy("");
    }
  }

  async function send() {
    const value = command.trim();
    if (!value || sending || busy) return;
    setSending(true);
    setError("");
    try {
      const result = await api.dispatchFounderCommand(value);
      setReceipt(result);
      setCommand("");
      await onDispatched(result);
    } catch (e: any) {
      setError(e?.message ?? "지시를 전달하지 못했습니다.");
    } finally {
      setSending(false);
    }
  }

  return (
    <View style={styles.shell}>
      <View style={styles.header}>
        <Text style={styles.eyebrow}>FOUNDER DESK</Text>
        <Text style={styles.title}>무엇을 시킬까요?</Text>
        <Text style={styles.subtitle}>
          내부 구조는 회사가 처리합니다. 원하는 결과만 자연어로 지시하세요.
        </Text>
      </View>

      <View style={styles.commandCard}>
        <TextInput
          value={command}
          onChangeText={setCommand}
          placeholder="예: QuanTrade가 내 현금 필요 시점을 파악하고 필요한 질문을 보고하게 해줘"
          placeholderTextColor="#8A8A82"
          multiline
          maxLength={4000}
          style={styles.commandInput}
        />
        <Pressable
          disabled={sending || busy || !command.trim()}
          onPress={() => void send()}
          style={[
            styles.commandButton,
            (sending || busy || !command.trim()) && styles.disabled,
          ]}
        >
          <Text style={styles.commandButtonText}>
            {sending ? "전달 중…" : "지시 보내기"}
          </Text>
        </Pressable>
      </View>

      {receipt ? (
        <Pressable
          style={styles.receipt}
          onPress={() => void onOpenMission(receipt.routed_lab_id, receipt.mission.id)}
        >
          <Text style={styles.receiptTitle}>지시를 맡겼습니다.</Text>
          <Text style={styles.receiptBody}>
            {receipt.routed_lab_title} · {statusLabel(receipt.mission?.status)}
          </Text>
          <Text style={styles.receiptLink}>진행 상황 보기</Text>
        </Pressable>
      ) : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <View style={styles.rule} />

      <View style={styles.sectionHead}>
        <Text style={styles.sectionTitle}>내 결정</Text>
        <Text style={styles.count}>{decisions.length}</Text>
      </View>
      {decisions.length === 0 ? (
        <Text style={styles.empty}>지금 내가 결정할 일은 없습니다.</Text>
      ) : decisions.slice(0, 4).map((item: any) => (
        <Pressable
          key={item.mission_id}
          style={styles.row}
          onPress={() => void onOpenMission(item.lab_id, item.mission_id)}
        >
          <Text style={styles.rowTitle} numberOfLines={2}>
            {item.question || item.objective || "Founder 판단이 필요합니다."}
          </Text>
          <Text style={styles.rowMeta}>
            {labById.get(item.lab_id)?.lab?.title ?? "Holdings"} · 보고서 열기
          </Text>
        </Pressable>
      ))}

      <View style={styles.rule} />

      <View style={styles.sectionHead}>
        <Text style={styles.sectionTitle}>기록 검토</Text>
        <Text style={styles.count}>{recordQueue.length}</Text>
      </View>
      {recordQueue.length === 0 ? (
        <Text style={styles.empty}>방향을 바꿀 가능성이 있는 새 기록은 없습니다.</Text>
      ) : recordQueue.slice(0, 3).map((item: any) => {
        const isBusy = recordBusy === String(item.id);
        const needsSemantic = String(item.status ?? "") === "needs_semantic_resolution";
        const classification = needsSemantic ? "AI 정리 필요" : recordClassification(item.classification);
        const canSupersede = Boolean(item.target_claim_id)
          && (String(item.classification ?? "").includes("supersession")
            || String(item.classification ?? "").includes("conflict"));
        return (
          <View key={item.id} style={styles.recordCard}>
            <Text style={styles.recordKind}>{classification}</Text>
            <Text style={styles.rowTitle} numberOfLines={3}>
              {item.source_preview || item.candidate_claim?.content || "새로운 조직 기록 후보"}
            </Text>
            <Text style={styles.rowMeta}>
              {item.scope_type === "lab" ? "Lab 지식" : "Holdings 지식"} · 원문은 보존됨
            </Text>
            <Text style={styles.recordSuggestion}>
              AI 초안 제안 · {recordSuggestion(item.suggested_disposition, item.suggested_record_action)}
            </Text>
            <View style={styles.recordActions}>
              {needsSemantic ? (
                <Pressable
                  disabled={isBusy}
                  style={[styles.recordPrimary, isBusy && styles.disabled]}
                  onPress={() => void semanticReviewRecord(item)}
                >
                  <Text style={styles.recordPrimaryText}>AI로 정리 · 최대 $0.01</Text>
                </Pressable>
              ) : (
                <Pressable
                  disabled={isBusy}
                  style={[styles.recordPrimary, isBusy && styles.disabled]}
                  onPress={() => void resolveRecord(item, "adopt")}
                >
                  <Text style={styles.recordPrimaryText}>현재 지식으로 반영</Text>
                </Pressable>
              )}
              {!needsSemantic ? (
                <Pressable
                  disabled={isBusy}
                  style={[styles.recordButton, isBusy && styles.disabled]}
                  onPress={() => void resolveRecord(item, "archive", "experiment")}
                >
                  <Text style={styles.recordButtonText}>실험으로 기록</Text>
                </Pressable>
              ) : null}
              {!needsSemantic && canSupersede ? (
                <Pressable
                  disabled={isBusy}
                  style={[styles.recordButton, isBusy && styles.disabled]}
                  onPress={() => void resolveRecord(item, "supersede")}
                >
                  <Text style={styles.recordButtonText}>기존 방향 대체</Text>
                </Pressable>
              ) : null}
              <Pressable
                disabled={isBusy}
                style={[styles.recordButton, isBusy && styles.disabled]}
                onPress={() => void resolveRecord(item, "archive")}
              >
                <Text style={styles.recordButtonText}>보관</Text>
              </Pressable>
              <Pressable
                disabled={isBusy}
                style={[styles.recordButton, isBusy && styles.disabled]}
                onPress={() => void resolveRecord(item, "reject")}
              >
                <Text style={styles.recordButtonText}>반려</Text>
              </Pressable>
            </View>
          </View>
        );
      })}
      {recordError ? <Text style={styles.error}>{recordError}</Text> : null}

      <View style={styles.rule} />

      <View style={styles.sectionHead}>
        <Text style={styles.sectionTitle}>진행 중</Text>
        <Text style={styles.count}>{active.length}</Text>
      </View>
      {active.length === 0 ? (
        <Text style={styles.empty}>현재 진행 중인 업무가 없습니다.</Text>
      ) : active.map((item: any) => (
        <Pressable
          key={item.id}
          style={styles.row}
          onPress={() => void onOpenMission(item.lab_id, item.mission_id)}
        >
          <Text style={styles.rowTitle} numberOfLines={2}>{item.title}</Text>
          <Text style={styles.rowMeta}>
            {labById.get(item.lab_id)?.lab?.title ?? "Lab"} · {statusLabel(item.status)}
          </Text>
        </Pressable>
      ))}

      <View style={styles.rule} />

      <View style={styles.sectionHead}>
        <Text style={styles.sectionTitle}>최근 완료</Text>
        <Text style={styles.count}>{completed.length}</Text>
      </View>
      {completed.length === 0 ? (
        <Text style={styles.empty}>아직 완료 보고가 없습니다.</Text>
      ) : completed.map((item: any) => (
        <Pressable
          key={item.id}
          style={styles.row}
          onPress={() => void onOpenMission(item.lab_id, item.mission_id)}
        >
          <Text style={styles.rowTitle} numberOfLines={2}>{item.title}</Text>
          <Text style={styles.rowMeta}>
            {labById.get(item.lab_id)?.lab?.title ?? "Lab"} · 완료보고
          </Text>
        </Pressable>
      ))}

      <View style={styles.rule} />

      <View style={styles.sectionHead}>
        <Text style={styles.sectionTitle}>보류함</Text>
        <Text style={styles.count}>{deferred.length}</Text>
      </View>
      {deferred.length === 0 ? (
        <Text style={styles.empty}>보류한 서류가 없습니다.</Text>
      ) : deferred.slice(0, 4).map((item: any) => (
        <Pressable
          key={item.mission_id}
          style={styles.row}
          onPress={() => void onOpenMission(item.lab_id, item.mission_id)}
        >
          <Text style={styles.rowTitle} numberOfLines={2}>{item.objective}</Text>
          <Text style={styles.rowMeta}>
            {labById.get(item.lab_id)?.lab?.title ?? "Lab"} · 다시 검토
          </Text>
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  shell: { gap: 12 },
  header: { paddingTop: 6, paddingBottom: 6 },
  eyebrow: { fontSize: 9, letterSpacing: 1.7, fontWeight: "700", color: "#74746D" },
  title: { marginTop: 5, fontSize: 28, lineHeight: 34, fontWeight: "800", color: "#171714" },
  subtitle: { marginTop: 6, fontSize: 12, lineHeight: 18, color: "#686862", maxWidth: 560 },
  commandCard: { borderWidth: 1, borderColor: "#CFCFC7", backgroundColor: "#FAFAF7" },
  commandInput: {
    minHeight: 106,
    paddingHorizontal: 14,
    paddingVertical: 14,
    fontSize: 15,
    lineHeight: 22,
    color: "#171714",
    textAlignVertical: "top",
  },
  commandButton: {
    alignSelf: "flex-end",
    marginRight: 10,
    marginBottom: 10,
    backgroundColor: "#1D4D3A",
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  commandButtonText: { color: "#FFFFFF", fontSize: 12, fontWeight: "800" },
  disabled: { opacity: 0.4 },
  receipt: { borderLeftWidth: 3, borderLeftColor: "#1D4D3A", paddingLeft: 12, paddingVertical: 6 },
  receiptTitle: { fontSize: 12, fontWeight: "800", color: "#1D4D3A" },
  receiptBody: { marginTop: 3, fontSize: 11, color: "#44443F" },
  receiptLink: { marginTop: 4, fontSize: 10, fontWeight: "700", color: "#1D4D3A" },
  rule: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#D3D3CB", marginTop: 3 },
  sectionHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingTop: 4 },
  sectionTitle: { fontSize: 15, fontWeight: "800", color: "#242420" },
  count: { fontSize: 12, fontWeight: "700", color: "#6E6E67" },
  empty: { fontSize: 11, lineHeight: 17, color: "#7A7A73", paddingBottom: 3 },
  row: { paddingVertical: 9, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: "#E1E1DA" },
  rowTitle: { fontSize: 12, lineHeight: 18, fontWeight: "600", color: "#242420" },
  rowMeta: { marginTop: 3, fontSize: 9.5, lineHeight: 14, color: "#77776F" },
  recordCard: {
    paddingVertical: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "#E1E1DA",
    gap: 5,
  },
  recordKind: { fontSize: 9, fontWeight: "800", letterSpacing: 0.5, color: "#7A6334" },
  recordSuggestion: { fontSize: 9, lineHeight: 14, color: "#6D6D66" },
  recordActions: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 4 },
  recordPrimary: { backgroundColor: "#1D4D3A", paddingHorizontal: 9, paddingVertical: 7 },
  recordPrimaryText: { fontSize: 9, fontWeight: "700", color: "#FFFFFF" },
  recordButton: { borderWidth: 1, borderColor: "#B8B8B0", paddingHorizontal: 9, paddingVertical: 7 },
  recordButtonText: { fontSize: 9, fontWeight: "700", color: "#3F3F3A" },
  error: { fontSize: 11, lineHeight: 17, color: "#8B2E2E" },
});
