"use client";

import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { useMedicalSelection, type PrescriptionFeedbackItem } from "@store/medicalSelection";
import styles from "./Diagnosis.module.css";
import { ClinicVisitContext } from "@/types/clinic";
import {
  getValidationJob,
  recommendPrescriptions,
  savePrescriptionFeedback,
  setHistoryDiagnoses,
  type RecommendedPrescriptionItem,
  type ValidationJobResponse,
} from "@/services/history";
import { HttpError } from "@/services/http/types";

type DiagnosisProps = {
  clinicVisit: ClinicVisitContext | null;
  ensureHistory: () => Promise<number>;
  employeeId: number;
  onHistoryUpdated?: () => void;
};

function asText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function extractValidationReasons(job: ValidationJobResponse | null): string[] {
  const result = job?.result;
  if (!result) return [];

  const reasons: string[] = [];
  const overallReason = asText(result.reason);
  if (overallReason) reasons.push(overallReason);

  const checks = Array.isArray(result.checks) ? result.checks : [];
  checks.forEach((item) => {
    const message = asText(item.message);
    const action = asText(item.recommendedAction);
    if (message) reasons.push(message);
    if (action) reasons.push(`권고: ${action}`);
  });

  const suspectedIssues = Array.isArray(result.suspectedIssues) ? result.suspectedIssues : [];
  suspectedIssues.forEach((item) => {
    const description = asText(item.description);
    const reason = asText(item.reason);
    if (description) reasons.push(description);
    if (reason) reasons.push(`이유: ${reason}`);
  });

  const reasoningTrace = Array.isArray(result.reasoningTrace) ? result.reasoningTrace : [];
  reasoningTrace.slice(-3).forEach((step) => {
    const action = asText(step.action);
    const observation = step.observation;
    let observationText = "";
    if (typeof observation === "string") {
      observationText = observation;
    } else if (observation && typeof observation === "object") {
      const status = asText((observation as Record<string, unknown>).status);
      const evidence = (observation as Record<string, unknown>).evidence;
      const evidenceText = Array.isArray(evidence)
        ? evidence.map((item) => String(item)).join(", ")
        : "";
      observationText = [status, evidenceText].filter(Boolean).join(" - ");
    }
    if (action && observationText) {
      reasons.push(`${action}: ${observationText}`);
    }
  });

  return Array.from(new Set(reasons.filter(Boolean))).slice(0, 6);
}

function extractPubmedReferences(job: ValidationJobResponse | null): string[] {
  const validation = job?.result?.validation;
  const pubmedEvidence =
    validation && typeof validation === "object" && Array.isArray(validation.pubmedEvidence)
      ? validation.pubmedEvidence
      : [];
  const summary =
    validation && typeof validation === "object"
      ? asText(validation.pubmedEvidenceSummary)
      : "";

  const references = pubmedEvidence.slice(0, 3).flatMap((article) => {
    if (!article || typeof article !== "object") return [];
    const row = article as Record<string, unknown>;
    const title = asText(row.title);
    const pmid = asText(row.pmid);
    const source = asText(row.source);
    const pubdate = asText(row.pubdate);
    const abstractSnippet = asText(row.abstractSnippet);
    if (!title) return [];
    const meta = [source, pubdate, pmid ? `PMID ${pmid}` : ""].filter(Boolean).join(", ");
    return [`${title}${meta ? ` (${meta})` : ""}${abstractSnippet ? ` - 초록: ${abstractSnippet}` : ""}`];
  });
  return summary ? [`근거 요약: ${summary}`, ...references] : references;
}

export default function Diagnosis({ clinicVisit, ensureHistory, employeeId, onHistoryUpdated }: DiagnosisProps) {
  const { diseases, diagnoses, prescriptionFeedback, addDiagnosis, removeDiagnosis, clearDiagnoses, setPrescriptionFeedback, clearPrescriptionFeedback } = useMedicalSelection();
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [aiRecommendations, setAiRecommendations] = useState<RecommendedPrescriptionItem[]>([]);
  const [selectedRecommendationKeys, setSelectedRecommendationKeys] = useState<string[]>([]);
  const [validationModal, setValidationModal] = useState<ValidationJobResponse | null>(null);
  const [aiSessionHistoryId, setAiSessionHistoryId] = useState<number | null>(null);
  const [aiSessionHistoryDiagnoseId, setAiSessionHistoryDiagnoseId] = useState<number | null>(null);
  const prevPatientIdRef = useRef<number | null>(null);

  useEffect(() => {
    const currentPatientId = clinicVisit?.patientId ?? null;
    if (prevPatientIdRef.current !== currentPatientId) {
      prevPatientIdRef.current = currentPatientId;
      clearDiagnoses();
      clearPrescriptionFeedback();
      setAiRecommendations([]);
      setSelectedRecommendationKeys([]);
      setAiSessionHistoryId(null);
      setAiSessionHistoryDiagnoseId(null);
    }
  }, [clearDiagnoses, clearPrescriptionFeedback, clinicVisit?.patientId]);

  useEffect(() => {
    clearPrescriptionFeedback();
    setAiRecommendations([]);
    setSelectedRecommendationKeys([]);
    setAiSessionHistoryId(null);
    setAiSessionHistoryDiagnoseId(null);
  }, [clearPrescriptionFeedback, clinicVisit?.historyId]);

  const handleSave = useCallback(async () => {
    if (!clinicVisit) {
      alert("환자를 먼저 선택해주세요.");
      return;
    }

    if (diagnoses.length === 0) {
      return;
    }

    setSaving(true);
    try {
      const historyId = await ensureHistory();
      const persistableDiagnoses = diagnoses.filter((item) => item.id > 0);
      if (persistableDiagnoses.length === 0) {
        alert("현재 목록은 DB 미매칭 AI 추천만 있어 저장할 수 없습니다.");
        return;
      }
      await setHistoryDiagnoses(
        historyId,
        employeeId,
        persistableDiagnoses.map((item) => ({
          id: item.id,
        }))
      );
      onHistoryUpdated?.();

      // AI가 추천하지 않았지만 의사가 직접 추가·저장한 처방 → missed로 기록
      // AI를 아예 안 쓴 경우에도 모든 저장 처방이 missed로 분류됨
      const aiRecommendedIds = new Set(prescriptionFeedback.map((f) => f.id).filter((id) => id > 0));
      const missedItems = persistableDiagnoses.filter((d) => !aiRecommendedIds.has(d.id));
      if (missedItems.length > 0) {
        try {
          await savePrescriptionFeedback({
            historyId,
            historyDiagnoseId: aiSessionHistoryDiagnoseId ?? undefined,
            feedbackItems: missedItems.map((d) => ({
              rank: 0,
              prescriptionId: d.id,
              prescriptionCode: d.code,
              prescriptionName: d.name,
              status: "missed" as const,
            })),
          });
        } catch (error) {
          console.error("missed 처방 피드백 저장 실패:", error);
        }
      }

      if (persistableDiagnoses.length !== diagnoses.length) {
        alert(
          `처방 정보가 저장되었습니다. (DB 매칭 ${persistableDiagnoses.length}건 저장, ${
            diagnoses.length - persistableDiagnoses.length
          }건은 미매칭으로 제외)`
        );
      } else {
        alert("처방 정보가 저장되었습니다.");
      }
    } catch (error) {
      console.error("처방 정보 저장 실패:", error);
      alert("처방 정보를 저장하지 못했습니다. 잠시 후 다시 시도해주세요.");
    } finally {
      setSaving(false);
    }
  }, [aiSessionHistoryDiagnoseId, clinicVisit, diagnoses, employeeId, ensureHistory, prescriptionFeedback]);

  const handleGenerateByAI = useCallback(async () => {
    if (!clinicVisit) {
      alert("환자를 먼저 선택해주세요.");
      return;
    }

    setGenerating(true);
    try {
      const historyId = await ensureHistory();
      const response = await recommendPrescriptions({
        history_id: historyId,
        arango_patient_id: clinicVisit.visitNumber || undefined,
        // true 이면 GraphDB/langchain_graph_qa/patient_ctx.example.json 이 증상·top_rx 등을 덮어씀(데모 전용). 실제 Arango/MySQL 기반 추천은 false.
        use_example_context: false,
        disease_codes: diseases.map((d) => d.code),
      });
      const job = await pollValidationJob(response.jobId);
      if (job.status === "FAILED") {
        throw new Error(job.lastError || "검증 에이전트 작업이 실패했습니다.");
      }
      const result = job.result ?? {};
      const recommended =
        result.recommendedPrescriptions ??
        result.candidatePrescriptions ??
        [];

      if (recommended.length === 0) {
        alert(
          "AI 추천/검증 결과가 비어 있습니다. 검증 요약을 확인해주세요."
        );
        setValidationModal(job);
        return;
      }

      setAiRecommendations(recommended);
      setSelectedRecommendationKeys(recommended.map((item) => `${item.rank}:${item.prescription_code}:${item.prescription_name}`));
      setAiSessionHistoryId(historyId);
      setAiSessionHistoryDiagnoseId(null);
      clearPrescriptionFeedback();
      setValidationModal(job);
    } catch (error) {
      console.error("AI 처방 생성 실패:", error);
      const hint =
        error instanceof HttpError
          ? `\n\n[HTTP ${error.status}] ${error.message}` +
            (error.data && typeof error.data === "object"
              ? `\n${JSON.stringify(error.data).slice(0, 400)}`
              : "")
          : error instanceof Error
            ? `\n\n${error.message}`
            : "";
      alert(`AI 처방 생성에 실패했습니다.${hint}`);
    } finally {
      setGenerating(false);
    }
  }, [clearPrescriptionFeedback, clinicVisit, diseases, ensureHistory]);

  const pollValidationJob = async (jobId: string): Promise<ValidationJobResponse> => {
    const maxAttempts = 90;
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      const job = await getValidationJob(jobId);
      if (job.status === "DONE" || job.status === "FAILED") {
        return job;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
    }
    throw new Error("검증 에이전트 응답 대기 시간이 초과되었습니다.");
  };

  const toggleRecommendation = useCallback((key: string) => {
    setSelectedRecommendationKeys((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  }, []);

  const handleApplySelectedRecommendations = useCallback(async () => {
    if (aiRecommendations.length === 0) {
      alert("먼저 AI 추천을 생성해주세요.");
      return;
    }
    // selectedRecommendationKeys가 0이어도 전체 거부 피드백으로 저장

    const feedback: PrescriptionFeedbackItem[] = [];
    let mappedCount = 0;
    let unmappedCount = 0;

    for (const item of aiRecommendations) {
      const key = `${item.rank}:${item.prescription_code}:${item.prescription_name}`;
      const isAccepted = selectedRecommendationKeys.includes(key);

      feedback.push({
        rank: item.rank,
        id: item.id,
        prescription_code: item.prescription_code ?? "",
        prescription_name: item.prescription_name ?? "",
        confidence_score: item.confidence_score ?? 0,
        reason: item.reason ?? "",
        status: isAccepted ? "accepted" : "rejected",
      });

      if (!isAccepted) continue;

      const isMapped = Boolean(item.id && item.id > 0);
      const diagnosisId = isMapped ? item.id : -Math.max(1, item.rank ?? unmappedCount + 1);
      addDiagnosis({
        id: diagnosisId,
        code: item.prescription_code ?? "",
        name: item.prescription_name ?? "",
        dose: item.dose ?? 0,
        time: item.time ?? 0,
        days: item.days ?? 0,
        reason: isMapped
          ? item.reason ?? ""
          : `[DB 미매칭] ${item.reason ?? "현재 진료 DB에 동일 처방 코드/명이 없습니다."}`,
      });
      if (isMapped) mappedCount += 1;
      else unmappedCount += 1;
    }

    setPrescriptionFeedback(feedback);

    if (aiSessionHistoryId !== null) {
      try {
        await savePrescriptionFeedback({
          historyId: aiSessionHistoryId,
          historyDiagnoseId: aiSessionHistoryDiagnoseId ?? undefined,
          feedbackItems: feedback.map((f) => ({
            rank: f.rank,
            prescriptionId: f.id > 0 ? f.id : undefined,
            prescriptionCode: f.prescription_code,
            prescriptionName: f.prescription_name,
            confidenceScore: f.confidence_score,
            reason: f.reason,
            status: f.status,
          })),
        });
      } catch (error) {
        console.error("처방 피드백 저장 실패:", error);
      }
    }

    const acceptedCount = feedback.filter((f) => f.status === "accepted").length;
    if (acceptedCount === 0) {
      alert("추천 처방을 모두 거부하였습니다. 피드백이 기록되었습니다.");
    } else if (mappedCount === 0) {
      alert("선택한 추천은 화면 반영만 되었고, DB 저장 가능한 항목은 없습니다.");
    } else {
      alert(`선택 반영 완료: DB 매칭 ${mappedCount}건, DB 미매칭 ${unmappedCount}건`);
    }
  }, [addDiagnosis, aiRecommendations, aiSessionHistoryDiagnoseId, aiSessionHistoryId, selectedRecommendationKeys, setPrescriptionFeedback]);

  return (
    <div className={styles.container}>
      {validationModal && (
        <div className={styles.modalBackdrop} role="presentation">
          <div className={styles.modalPanel} role="dialog" aria-modal="true">
            <h3 className={styles.modalTitle}>검증 완료</h3>
            <div className={styles.modalCard}>
              <div className={styles.modalCardHead}>
                <span className={styles.modalRank}>
                  {validationModal.result?.overallStatus ?? validationModal.status}
                </span>
              </div>
              <p className={styles.modalReason}>
                {validationModal.result?.summary ?? validationModal.summary ?? "검증 결과를 확인했습니다."}
              </p>
              {extractValidationReasons(validationModal).length > 0 && (
                <div className={styles.modalReasons}>
                  <strong>검증 이유</strong>
                  <ul>
                    {extractValidationReasons(validationModal).map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                </div>
              )}
              {extractPubmedReferences(validationModal).length > 0 && (
                <div className={styles.modalReferences}>
                  <strong>PubMed 참고 근거</strong>
                  <ul>
                    {extractPubmedReferences(validationModal).map((reference) => (
                      <li key={reference}>{reference}</li>
                    ))}
                  </ul>
                </div>
              )}
              {(
                validationModal.result?.recommendedPrescriptions ??
                validationModal.result?.candidatePrescriptions ??
                []
              ).slice(0, 3).map((item) => (
                <div
                  key={`${item.rank}-${item.prescription_code}-${item.prescription_name}`}
                  className={styles.modalName}
                >
                  [{item.rank}] {item.prescription_name} ({item.prescription_code})
                </div>
              ))}
            </div>
            <button
              type="button"
              className={styles.modalCloseBtn}
              onClick={() => setValidationModal(null)}
            >
              확인
            </button>
          </div>
        </div>
      )}
      <div className={styles.header}>
        <h3>처방</h3>
        <div className={styles.controls}>
          <button
            type="button"
            className={styles.controlButtonAI}
            onClick={handleGenerateByAI}
            disabled={generating}
          >
            {generating ? "추천/검증 중..." : "AI 처방 추천"}
          </button>
          <button
            type="button"
            className={styles.controlButton}
            onClick={handleSave}
            disabled={diagnoses.length === 0 || saving}
          >
            {saving ? "저장 중..." : "저장"}
          </button>
          <button
            type="button"
            className={styles.controlButtonSecondary}
            onClick={clearDiagnoses}
            disabled={diagnoses.length === 0}
          >
            전체 삭제
          </button>
        </div>
      </div>
      <div className={styles.content}>
        {aiRecommendations.length > 0 ? (
          <div className={styles.aiPanel}>
            <div className={styles.aiPanelHeader}>
              <strong>AI 추천 처방</strong>
              <button type="button" className={styles.controlButtonAI} onClick={handleApplySelectedRecommendations}>
                선택 처방 반영
              </button>
            </div>
            <div className={styles.aiList}>
              {aiRecommendations.map((item) => {
                const key = `${item.rank}:${item.prescription_code}:${item.prescription_name}`;
                return (
                  <label key={key} className={styles.aiItem}>
                    <input
                      type="checkbox"
                      checked={selectedRecommendationKeys.includes(key)}
                      onChange={() => toggleRecommendation(key)}
                    />
                    <span>
                      [{item.rank}] {item.prescription_name} ({item.prescription_code})
                    </span>
                  </label>
                );
              })}
            </div>
          </div>
        ) : null}
        <div className={styles.tableContainer}>
          <table className={styles.diseaseTable}>
            <thead>
              <tr className={styles.tableHeader}>
                <th>No.</th>
                <th>ID</th>
                <th>코드</th>
                <th>처방명</th>
                {/* 
                <th>투여량</th>
                <th>횟수</th>
                <th>일수</th>
                */}
                <th>삭제</th>
              </tr>
            </thead>
            <tbody>
              {diagnoses.length === 0 ? (
                <tr className={styles.tableRow}>
                  <td colSpan={8} className={styles.emptyRow}>
                    선택된 처방이 없습니다. 오른쪽 데이터베이스에서 더블클릭하여 추가하세요.
                  </td>
                </tr>
              ) : (
                diagnoses.map((item, index) => (
                  <Fragment key={`${item.id}-${index}`}>
                    <tr className={styles.tableRow}>
                      <td className={styles.sequence}>{index + 1}</td>
                      <td className={styles.identifier}>{item.id > 0 ? item.id : "미매칭"}</td>
                      <td className={styles.code}>{item.code}</td>
                      <td className={styles.name}>{item.name}</td>
                      
                      {/*
                      <td className={styles.dose}>{item.dose}</td>
                      <td className={styles.time}>{item.time}</td>
                      <td className={styles.days}>{item.days}</td>
                      */  }
                      <td className={styles.actionCell}>
                        <button
                          type="button"
                          className={styles.removeButton}
                          onClick={() => removeDiagnosis(item.id)}
                        >
                          삭제
                        </button>
                      </td>
                    </tr>
                    <tr className={styles.reasonRow}>
                      <td colSpan={8} className={styles.reasonCell}>
                        <strong>AI 추천 사유</strong>
                        <p className={styles.reasonText}>{item.reason ?? "-"}</p>
                      </td>
                    </tr>
                  </Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}