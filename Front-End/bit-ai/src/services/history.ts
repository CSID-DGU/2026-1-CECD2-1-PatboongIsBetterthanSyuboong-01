import { get, post, put } from "./http/client";
import type { HistoryEntry } from "@/types/history";

export interface HistoryPayload {
  employeeId: number;
  patientId: number;
  deptId: number;
  symptomDetail?: string | null;
  memo?: string | null;
  entryDate: string;
}

export interface HistoryResponse extends HistoryPayload {
  id: number;
}

export interface HistoryDiseasePayload {
  id?: number;
  historyId?: number;
  code: string;
  name: string;
  degree?: string | null;
}

export interface HistoryDiseaseResponse {
  id: number;
  historyId: number;
  code: string;
  name: string;
  degree: string | null;
}

export interface HistoryDiagnosePayload {
  id: number;
}

export interface HistoryDiagnoseResponse {
  id: number;
  historyId: number;
  code: string;
  name: string;
  dose: number;
  time: number;
  days: number;
}

export interface PrescriptionRecommendRequestPayload {
  history_id?: number;
  history_diagnose_id?: number;
  arango_patient_id?: string;
  use_example_context?: boolean;
  /** 상병 코드(E11 등). 생략 시 백엔드가 현재 진료 저장 상병으로 채움 */
  disease_codes?: string[];
}

export interface RecommendedPrescriptionItem {
  id: number;
  rank: number;
  prescription_code: string;
  prescription_name: string;
  reason: string;
  confidence_score: number;
  dose: number;
  time: number;
  days: number;
}

export interface PrescriptionRecommendResponse {
  history_diagnose_id?: number;
  recommended_prescriptions: RecommendedPrescriptionItem[];
}

export type ValidationJobStatus = "PENDING" | "RUNNING" | "DONE" | "FAILED";

export interface ValidationJobStartResponse {
  jobId: string;
  historyId: number;
  status: ValidationJobStatus;
}

export interface ValidationJobResponse {
  jobId: string;
  historyId: number;
  status: ValidationJobStatus;
  summary?: string | null;
  result?: {
    overallStatus?: string;
    summary?: string;
    reason?: string;
    recommendedPrescriptions?: RecommendedPrescriptionItem[];
    candidatePrescriptions?: RecommendedPrescriptionItem[];
    checks?: Array<Record<string, unknown>>;
    suspectedIssues?: Array<Record<string, unknown>>;
    reasoningTrace?: Array<Record<string, unknown>>;
    validation?: Record<string, unknown>;
    [key: string]: unknown;
  } | null;
  lastError?: string | null;
}

export interface HistoryListResponse {
  patientId: number;
  histories: HistoryEntry[];
}

export async function createHistory(payload: HistoryPayload): Promise<HistoryResponse> {
  return post<HistoryResponse, HistoryPayload>("/api/histories/write_history", payload);
}

export async function getPatientHistories(
  employeeId: number,
  patientId: number,
  startDate?: string,
  endDate?: string
): Promise<HistoryListResponse> {
  const params: Record<string, string> = {
    patientId: String(patientId),
  };
  if (startDate) params.startDate = startDate;
  if (endDate) params.endDate = endDate;
  return get<HistoryListResponse>(`/api/histories/search_history/${employeeId}`, { params });
}

export async function setHistoryDiseases(
  historyId: number,
  employeeId: number,
  diseases: HistoryDiseasePayload[]
): Promise<HistoryDiseaseResponse[]> {
  return put<HistoryDiseaseResponse[], HistoryDiseasePayload[]>(
    `/api/histories/${historyId}/set_diseases`,
    diseases,
    {
      params: { employeeId },
    }
  );
}

export async function setHistoryDiagnoses(
  historyId: number,
  employeeId: number,
  diagnoses: HistoryDiagnosePayload[]
): Promise<HistoryDiagnoseResponse[]> {
  return put<HistoryDiagnoseResponse[], HistoryDiagnosePayload[]>(
    `/api/histories/${historyId}/set_diagnoses`,
    diagnoses,
    {
      params: { employeeId },
    }
  );
}

export async function getHistoryDiseases(
  historyId: number,
  employeeId: number
): Promise<HistoryDiseaseResponse[]> {
  return get<HistoryDiseaseResponse[]>(`/api/histories/${historyId}/get_diseases`, {
    params: { employeeId },
  });
}

export async function getHistoryDiagnoses(
  historyId: number,
  employeeId: number
): Promise<HistoryDiagnoseResponse[]> {
  return get<HistoryDiagnoseResponse[]>(`/api/histories/${historyId}/get_diagnoses`, {
    params: { employeeId },
  });
}

/** Spring → Python prescription_api → Gemini 등 연쇄 호출용 (기본 axios 15초 초과 방지) */
const PRESCRIPTION_RECOMMEND_TIMEOUT_MS = 180_000;

export async function recommendPrescriptions(
  payload: PrescriptionRecommendRequestPayload
): Promise<ValidationJobStartResponse> {
  return post<ValidationJobStartResponse, PrescriptionRecommendRequestPayload>(
    "/api/agent/prescription/recommend",
    payload,
    { timeout: PRESCRIPTION_RECOMMEND_TIMEOUT_MS }
  );
}

export async function getValidationJob(jobId: string): Promise<ValidationJobResponse> {
  return get<ValidationJobResponse>(`/api/validation-jobs/${jobId}`);
}

export interface PrescriptionFeedbackItemPayload {
  rank: number;
  prescriptionId?: number;
  prescriptionCode: string;
  prescriptionName: string;
  confidenceScore?: number;
  reason?: string;
  /** accepted: 체크 선택, rejected: 체크 미선택, missed: AI 미추천이지만 의사가 직접 추가·저장 */
  status: "accepted" | "rejected" | "missed";
}

export interface SavePrescriptionFeedbackPayload {
  historyId: number;
  historyDiagnoseId?: number;
  feedbackItems: PrescriptionFeedbackItemPayload[];
}

export async function savePrescriptionFeedback(payload: SavePrescriptionFeedbackPayload): Promise<void> {
  return post<void, SavePrescriptionFeedbackPayload>("/api/agent/prescription/feedback", payload);
}

