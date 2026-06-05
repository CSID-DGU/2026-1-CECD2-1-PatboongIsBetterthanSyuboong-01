"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useMedicalSelection } from "@store/medicalSelection";
import styles from "./Disease.module.css";
import { ClinicVisitContext } from "@/types/clinic";
import { setHistoryDiseases } from "@/services/history";
import { HttpError } from "@/services/http/types";

type DiseaseProps = {
  clinicVisit: ClinicVisitContext | null;
  ensureHistory: () => Promise<number>;
  employeeId: number;
  onHistoryUpdated?: () => void;
};

const DUMMY_DISEASES = [
  { id: 900001, code: "E11", name: "당뇨" },
  { id: 900002, code: "E16.2", name: "저혈당" },
  { id: 900003, code: "E03.9", name: "갑상선 저하증" },
] as const;

export default function Disease({ clinicVisit, ensureHistory, employeeId, onHistoryUpdated }: DiseaseProps) {
  const { diseases, addDisease, removeDisease, clearDiseases } = useMedicalSelection();
  const [saving, setSaving] = useState(false);
  const prevPatientIdRef = useRef<number | null>(null);

  useEffect(() => {
    const currentPatientId = clinicVisit?.patientId ?? null;
    if (prevPatientIdRef.current !== currentPatientId) {
      prevPatientIdRef.current = currentPatientId;
      clearDiseases();
    }
  }, [clinicVisit?.patientId, clearDiseases]);

  const handleSave = useCallback(async () => {
    if (!clinicVisit) {
      alert("환자를 먼저 선택해주세요.");
      return;
    }

    if (diseases.length === 0) {
      return;
    }

    setSaving(true);
    try {
      const historyId = await ensureHistory();
      await setHistoryDiseases(historyId, employeeId, diseases);
      onHistoryUpdated?.();
      alert("상병 정보가 저장되었습니다.");
    } catch (error) {
      console.error("상병 정보 저장 실패:", error);
      if (error instanceof HttpError) {
        alert(`상병 정보를 저장하지 못했습니다. [${error.status}] ${error.message}`);
      } else {
        alert("상병 정보를 저장하지 못했습니다. 잠시 후 다시 시도해주세요.");
      }
    } finally {
      setSaving(false);
    }
  }, [clinicVisit, diseases, employeeId, ensureHistory]);

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3>상병</h3>
        <div className={styles.controls}>
          <button
            type="button"
            className={styles.controlButton}
            onClick={handleSave}
            disabled={diseases.length === 0 || saving}
          >
            {saving ? "저장 중..." : "저장"}
          </button>
          <button
            type="button"
            className={styles.controlButtonSecondary}
            onClick={clearDiseases}
            disabled={diseases.length === 0}
          >
            전체 삭제
          </button>
        </div>
      </div>
      <div className={styles.content}>
        <div className={styles.quickSelect}>
          <span className={styles.quickSelectLabel}>테스트 상병 빠른 선택</span>
          <div className={styles.quickSelectButtons}>
            {DUMMY_DISEASES.map((disease) => (
              <button
                key={disease.id}
                type="button"
                className={styles.quickSelectButton}
                onClick={() => addDisease({ ...disease })}
              >
                {disease.name}
              </button>
            ))}
          </div>
        </div>
        <div className={styles.tableContainer}>
          <table className={styles.diseaseTable}>
            <thead>
              <tr className={styles.tableHeader}>
                <th>No.</th>
                <th>ID</th>
                <th>상병코드</th>
                <th>상병명칭</th>
                <th>삭제</th>
              </tr>
            </thead>
            <tbody>
              {diseases.length === 0 ? (
                <tr className={styles.tableRow}>
                  <td colSpan={5} className={styles.emptyRow}>
                    선택된 상병이 없습니다. 오른쪽 데이터베이스에서 더블클릭하여 추가하세요.
                  </td>
                </tr>
              ) : (
                diseases.map((item, index) => (
                  <tr key={item.id} className={styles.tableRow}>
                    <td className={styles.sequence}>{index + 1}</td>
                    <td className={styles.identifier}>{item.id}</td>
                    <td className={styles.code}>{item.code}</td>
                    <td className={styles.name}>{item.name}</td>
                    <td className={styles.actionCell}>
                      <button
                        type="button"
                        className={styles.removeButton}
                        onClick={() => removeDisease(item.id)}
                      >
                        삭제
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}