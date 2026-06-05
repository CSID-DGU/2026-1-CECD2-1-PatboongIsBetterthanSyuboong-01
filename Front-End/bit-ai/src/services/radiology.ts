export interface RadiologyReportRequest {
  radiologyRequestId: number;
  patientId: number;
  employeeId: number;
  deptId: number;
  symptomDetail?: string | null;
  memo?: string | null;
  entryDate: string; // yyyy-MM-dd 형식
  detailImageAddress: string;
  view?: XrayView;
}

export type XrayView = "AP" | "PA";

export interface RadiologyReportResponse {
  heatmapUrl: string | null;
  predictedDiseases: PredictedDisease[];
  warning: string | null;
}

export interface PredictedDisease {
  disease: string;
  score: number;
  reason: string;
}

/**
 * 이미지 파일과 메타데이터를 함께 전송하여 AI 분석을 수행합니다.
 * @param file 이미지 파일
 * @param patientId 환자 ID
 * @param employeeId 근무자 ID
 * @param deptId 부서 ID
 * @param entryDate 등록일자 (yyyy-MM-dd)
 * @param symptomDetail 증상 상세 (선택)
 * @param memo 메모 (선택)
 * @returns AI 분석 결과
 */
export async function uploadAndAnalyzeImage(
  file: File,
  patientId: number,
  employeeId: number,
  deptId: number,
  entryDate: string,
  view: XrayView = "PA",
  symptomDetail?: string | null,
  memo?: string | null
): Promise<RadiologyReportResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("patientId", String(patientId));
  formData.append("employeeId", String(employeeId));
  formData.append("deptId", String(deptId));
  formData.append("entryDate", entryDate);
  formData.append("view", view);
  if (symptomDetail) {
    formData.append("symptomDetail", symptomDetail);
  }
  if (memo) {
    formData.append("memo", memo);
  }

  // multipart/form-data 요청을 위해 axios를 직접 사용
  const { http } = await import("./http/client");
  const instance = http();
  const response = await instance.post<RadiologyReportResponse>(
    "/api/radiology/upload-and-analyze",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );

  return response.data;
}

