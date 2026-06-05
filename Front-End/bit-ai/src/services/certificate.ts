import { get, post } from "./http/client";

export interface CertificateHistoryDTO {
  historyId: number;
  patientId: number;
  patientName: string;
  patientNumber: string;
  age: number;
  gender: string;
  department: string;
  doctor: string;
  issueDate: string;
  symptomDetail: string;
}

export interface PatientDTO {
  id: number;
  name: string;
  phoneNumber: string;
  identityNumber: string;
  birth: string;
  gender: string;
}

/** 전체 환자 목록 조회 */
export async function getAllPatients(): Promise<PatientDTO[]> {
  return get<PatientDTO[]>("/api/patients/get_all");
}

/** 환자 ID(DB id)로 환자 상세 정보 조회 */
export async function getPatientById(patientId: number): Promise<PatientDTO> {
  return post<PatientDTO, Record<string, never>>(
    `/api/patients/search_patient/${patientId}`,
    {}
  );
}

/** 진단서 발급 이력 검색 (히스토리 기반) */
export async function searchCertificates(params: {
  patientName?: string;
  patientNumber?: string;
  department?: string;
  doctorName?: string;
  startDate?: string;
  endDate?: string;
}): Promise<CertificateHistoryDTO[]> {
  return get<CertificateHistoryDTO[]>("/api/agent/document/search", { params });
}
