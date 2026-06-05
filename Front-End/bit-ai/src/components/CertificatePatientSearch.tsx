"use client";

import { useState } from "react";
import styles from "./CertificatePatientSearch.module.css";
import { getAllPatients, getPatientById } from "@services/certificate";
import { get } from "@/services/http/client";
import type { PatientDTO } from "@services/certificate";

export interface CertificatePatientInfo {
  patientId: number;
  patientNumber: string;
  patientName: string;
  identityNumber: string;
  birth: string;
  gender: string;
}

interface Props {
  onPatientFound: (patient: CertificatePatientInfo) => void;
}

interface WaitingPatient {
  id: number;
  patientId: number;
  deptId: number;
  symptom?: string | null;
  entryDate: string;
  state: string;
  patientName?: string;
  department?: string;
  doctor?: string;
}

interface CompletedVisitPatient extends CertificatePatientInfo {
  waitingId: number;
  entryDate: string;
  symptom?: string | null;
}

export default function CertificatePatientSearch({ onPatientFound }: Props) {
  const [patientNumber, setPatientNumber] = useState("");
  const [loading, setLoading] = useState(false);
  const [completedLoading, setCompletedLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [found, setFound] = useState<CertificatePatientInfo | null>(null);
  const [completedPatients, setCompletedPatients] = useState<CompletedVisitPatient[]>([]);

  const toCertificatePatientInfo = (detail: PatientDTO): CertificatePatientInfo => ({
    patientId: detail.id,
    patientNumber: String(detail.id),
    patientName: detail.name,
    identityNumber: detail.identityNumber ?? "",
    birth: detail.birth ?? "",
    gender: detail.gender ?? "",
  });

  const handleSearch = async () => {
    const trimmed = patientNumber.trim();
    if (!trimmed) return;

    setLoading(true);
    setError(null);
    setFound(null);

    try {
      // 1. 전체 환자 목록에서 입력값과 일치하는 환자 찾기
      //    - 숫자면 patient.id 와 비교, 아니면 identityNumber 와 비교
      const allPatients = await getAllPatients();
      const isNumeric = /^\d+$/.test(trimmed);
      let matched: PatientDTO | undefined;

      if (isNumeric) {
        matched = allPatients.find((p) => String(p.id) === trimmed);
      } else {
        matched = allPatients.find((p) => p.identityNumber === trimmed);
      }

      if (!matched) {
        setError("해당 환자번호로 조회된 환자가 없습니다.");
        return;
      }

      // 2. 상세 조회로 최신 정보 확인 (실패하면 get_all 결과 그대로 사용)
      let detail: PatientDTO = matched;
      try {
        detail = await getPatientById(matched.id);
      } catch {
        // get_all 결과 그대로 사용
      }

      const info = toCertificatePatientInfo(detail);

      setFound(info);
      onPatientFound(info);
    } catch {
      setError("조회 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleSearch();
  };

  const handleLoadCompletedPatients = async () => {
    setCompletedLoading(true);
    setError(null);
    try {
      const waitingList = await get<WaitingPatient[]>("/api/waiting/get_list");
      const completed = waitingList
        .filter((item) => item.state === "completed")
        .sort((a, b) => new Date(b.entryDate).getTime() - new Date(a.entryDate).getTime())
        .slice(0, 20);

      const rows: CompletedVisitPatient[] = [];
      for (const visit of completed) {
        try {
          const detail = await getPatientById(visit.patientId);
          rows.push({
            ...toCertificatePatientInfo(detail),
            waitingId: visit.id,
            entryDate: visit.entryDate,
            symptom: visit.symptom,
          });
        } catch {
          rows.push({
            patientId: visit.patientId,
            patientNumber: String(visit.patientId),
            patientName: visit.patientName ?? `환자 ${visit.patientId}`,
            identityNumber: "",
            birth: "",
            gender: "",
            waitingId: visit.id,
            entryDate: visit.entryDate,
            symptom: visit.symptom,
          });
        }
      }

      setCompletedPatients(rows);
      if (rows.length === 0) {
        setError("진료 완료 상태의 환자가 없습니다.");
      }
    } catch {
      setError("진료 완료 환자 목록을 불러오지 못했습니다.");
    } finally {
      setCompletedLoading(false);
    }
  };

  const handleSelectCompletedPatient = (patient: CompletedVisitPatient) => {
    const info: CertificatePatientInfo = {
      patientId: patient.patientId,
      patientNumber: patient.patientNumber,
      patientName: patient.patientName,
      identityNumber: patient.identityNumber,
      birth: patient.birth,
      gender: patient.gender,
    };
    setFound(info);
    setPatientNumber(info.patientNumber);
    onPatientFound(info);
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3 className={styles.title}>환자 조회</h3>
      </div>

      <div className={styles.body}>
        <div className={styles.field}>
          <label className={styles.label}>환자번호</label>
          <input
            type="text"
            className={styles.input}
            value={patientNumber}
            onChange={(e) => setPatientNumber(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="환자번호 입력"
          />
        </div>

        <button
          type="button"
          className={styles.searchButton}
          onClick={handleSearch}
          disabled={loading || !patientNumber.trim()}
        >
          {loading ? "조회 중…" : "조회"}
        </button>

        <button
          type="button"
          className={styles.secondaryButton}
          onClick={handleLoadCompletedPatients}
          disabled={completedLoading}
        >
          {completedLoading ? "완료 환자 조회 중…" : "진료 완료 환자 조회"}
        </button>

        {error && <p className={styles.error}>{error}</p>}

        {completedPatients.length > 0 && (
          <div className={styles.completedList}>
            <p className={styles.resultTitle}>진료 완료 환자</p>
            {completedPatients.map((patient) => (
              <button
                key={`${patient.waitingId}-${patient.patientId}`}
                type="button"
                className={styles.completedItem}
                onClick={() => handleSelectCompletedPatient(patient)}
              >
                <span>
                  {patient.patientName} ({patient.patientNumber})
                </span>
                <small>{patient.entryDate.slice(0, 16).replace("T", " ")}</small>
              </button>
            ))}
          </div>
        )}

        {found && (
          <div className={styles.result}>
            <p className={styles.resultTitle}>조회 결과</p>
            <div className={styles.resultRow}>
              <span className={styles.resultLabel}>환자번호</span>
              <span className={styles.resultValue}>{found.patientNumber}</span>
            </div>
            <div className={styles.resultRow}>
              <span className={styles.resultLabel}>성명</span>
              <span className={styles.resultValue}>{found.patientName}</span>
            </div>
            {found.identityNumber && (
              <div className={styles.resultRow}>
                <span className={styles.resultLabel}>주민번호</span>
                <span className={styles.resultValue}>{found.identityNumber}</span>
              </div>
            )}
            {found.birth && (
              <div className={styles.resultRow}>
                <span className={styles.resultLabel}>생년월일</span>
                <span className={styles.resultValue}>{found.birth}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
