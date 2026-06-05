import type { InternalAxiosRequestConfig } from "axios";
import { http, post } from "./http/client";
import { fetchDiagnosesPage } from "./diagnoses";

export interface DocumentGenerateRequest {
  diseaseCode: string;
  prescriptionCode: string;
  prescriptionName: string;
  certificateType?: "GENERAL" | "MILITARY";
  diagnosisKind?: string;
  purpose?: string;
}

export interface DocumentGenerateByHistoryRequest {
  historyId: number;
  certificateType?: "GENERAL" | "MILITARY";
  diagnosisKind?: string;
  purpose?: string;
}

export interface DocumentEvaluateRequest {
  medicalCertificate: string;
  diseaseCode: string;
  prescriptionCode: string;
  prescriptionName: string;
}

export interface DocumentEvaluateDetail {
  index: number;
  hypothesis: string;
  judgment: string;
  reason: string;
}

export interface DocumentEvaluateResponse {
  score: number;
  entailmentCount: number;
  totalPairs: number;
  premise: string;
  details: DocumentEvaluateDetail[];
}

export interface DocumentGenerateResponse {
  grantType: string;
  accessToken: string;
  refreshToken: string;
  /** 백엔드(JSON) camelCase */
  medicalCertificate: string;
  /** 스네이크 케이스 응답 호환 */
  medical_certificate?: string;
}

const DOCUMENT_API_TIMEOUT_MS = 90000;

export async function generateDocumentCertificate(
  body: DocumentGenerateRequest
): Promise<DocumentGenerateResponse> {
  return post<DocumentGenerateResponse, DocumentGenerateRequest>(
    "/api/agent/document/generate-test",
    body,
    { timeout: DOCUMENT_API_TIMEOUT_MS }
  );
}

export async function generateDocumentCertificateByHistory(
  body: DocumentGenerateByHistoryRequest
): Promise<DocumentGenerateResponse> {
  return post<DocumentGenerateResponse, DocumentGenerateByHistoryRequest>(
    "/api/agent/document/generate",
    body,
    { timeout: DOCUMENT_API_TIMEOUT_MS }
  );
}

export async function evaluateDocumentCertificate(
  body: DocumentEvaluateRequest
): Promise<DocumentEvaluateResponse> {
  return post<DocumentEvaluateResponse, DocumentEvaluateRequest>(
    "/api/agent/document/evaluate",
    body,
    { timeout: DOCUMENT_API_TIMEOUT_MS }
  );
}

export type DocumentFeedbackType = "APPROVE" | "MODIFY" | "REJECT" | "NONE";

/** multipart/form-data — 필드명은 백엔드 스펙과 동일하게 유지 */
export async function saveDocumentCertificate(formData: FormData): Promise<unknown> {
  const res = await http().post<unknown>(
    "/api/agent/document/save",
    formData,
    {
      // axios 기본 Content-Type: application/json 이 FormData를 깨뜨림 → boundary 없이 JSON 직렬화됨
      transformRequest: [
        (data, rawHeaders) => {
          if (data instanceof FormData) {
            const headers = rawHeaders as InternalAxiosRequestConfig["headers"];
            if (headers && typeof headers.delete === "function") {
              headers.delete("Content-Type");
            } else if (headers && typeof headers === "object") {
              delete (headers as Record<string, unknown>)["Content-Type"];
            }
          }
          return data;
        },
      ],
    }
  );
  return res.data;
}

/** POST /api/agent/prescription/recommend 요청(JSON 스네이크 케이스) */
export interface PrescriptionRecommendRequestBody {
  history_diagnose_id: number;
}

export interface RecommendedPrescriptionItem {
  rank: number;
  prescription_code: string;
  prescription_name: string;
  reason: string;
  confidence_score: number;
}

/** 백엔드 직렬화(camelCase / snake_case) 모두 허용. 인증은 로그인·JWT와 동일 */
export type PrescriptionRecommendResponse = {
  history_diagnose_id?: number;
  patient_id?: number;
  /** 오타 대비 */
  history_dignose_id?: number;
  recommended_prescriptions?: RecommendedPrescriptionItem[];
  recommendedPrescriptions?: RecommendedPrescriptionItem[];
};

/**
 * 백엔드 추천 API 미구현 시 UI 검증용 — 실제 응답을 받은 뒤 추천 목록만 더미로 교체.
 * DB에 diagnose 가 있으면 상위 3건 코드를 써서 「적용」 시 마스터 조회가 되도록 함.
 */
async function buildLocalDummyRecommendedPrescriptions(): Promise<RecommendedPrescriptionItem[]> {
  try {
    const page = await fetchDiagnosesPage(0, 3);
    const rows = page.items.slice(0, 3);
    if (rows.length > 0) {
      return rows.map((d, i) => ({
        rank: i + 1,
        prescription_code: d.code,
        prescription_name: d.name,
        reason: "로컬 더미 추천 (백엔드 /api/agent/prescription/recommend 미연동)",
        confidence_score: Math.max(0.55, 0.92 - i * 0.08),
      }));
    }
  } catch {
    // ignore — 아래 고정 더미로 폴백
  }

  return [
    {
      rank: 1,
      prescription_code: "DUMMY-A",
      prescription_name: "더미 처방 A",
      reason: "DB 처방 마스터 없음 — 코드가 DB와 맞지 않으면 적용 시 조회 실패",
      confidence_score: 0.88,
    },
    {
      rank: 2,
      prescription_code: "DUMMY-B",
      prescription_name: "더미 처방 B",
      reason: "로컬 더미 (백엔드 미연동)",
      confidence_score: 0.72,
    },
    {
      rank: 3,
      prescription_code: "DUMMY-C",
      prescription_name: "더미 처방 C",
      reason: "로컬 더미 (백엔드 미연동)",
      confidence_score: 0.61,
    },
  ];
}

/** 백엔드 snake_case / camelCase 모두 허용. 유효 항목이 없으면 null */
function extractRemoteRecommendations(
  remote: PrescriptionRecommendResponse
): RecommendedPrescriptionItem[] | null {
  const raw = remote.recommended_prescriptions ?? remote.recommendedPrescriptions;
  if (!Array.isArray(raw) || raw.length === 0) return null;

  const out: RecommendedPrescriptionItem[] = [];
  for (const row of raw) {
    if (!row || typeof row !== "object") continue;
    const r = row as unknown as Record<string, unknown>;
    const rank = typeof r.rank === "number" ? r.rank : Number(r.rank);
    const code =
      (typeof r.prescription_code === "string" && r.prescription_code) ||
      (typeof r.prescriptionCode === "string" && r.prescriptionCode) ||
      "";
    const name =
      (typeof r.prescription_name === "string" && r.prescription_name) ||
      (typeof r.prescriptionName === "string" && r.prescriptionName) ||
      "";
    const reason = typeof r.reason === "string" ? r.reason : "";
    const scoreRaw = r.confidence_score ?? r.confidenceScore;
    const confidence_score = typeof scoreRaw === "number" ? scoreRaw : Number(scoreRaw);
    if (!Number.isFinite(rank) || !code) continue;
    out.push({
      rank,
      prescription_code: code,
      prescription_name: name,
      reason,
      confidence_score: Number.isFinite(confidence_score) ? confidence_score : 0,
    });
  }
  return out.length > 0 ? out : null;
}

export async function recommendPrescription(
  body: PrescriptionRecommendRequestBody
): Promise<PrescriptionRecommendResponse> {
  let remote: PrescriptionRecommendResponse = {};
  let apiSucceeded = false;
  try {
    remote = await post<PrescriptionRecommendResponse, PrescriptionRecommendRequestBody>(
      "/api/agent/prescription/recommend",
      body
    );
    apiSucceeded = true;
  } catch {
    // 네트워크/404/스펙 불일치 등 — 더미 추천만 사용
  }

  const fromApi = apiSucceeded ? extractRemoteRecommendations(remote) : null;
  const list =
    fromApi != null && fromApi.length > 0
      ? fromApi
      : await buildLocalDummyRecommendedPrescriptions();

  return {
    ...remote,
    history_diagnose_id: body.history_diagnose_id,
    recommended_prescriptions: list,
    recommendedPrescriptions: undefined,
  };
}
