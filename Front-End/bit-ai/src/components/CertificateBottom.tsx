"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "./CertificateBottom.module.css";
import { getPatientHistories, getHistoryDiseases, type HistoryDiseaseResponse } from "@services/history";

const TABS = ["상병", "상용구", "과거처방", "사용자설정"] as const;
type Tab = typeof TABS[number];

interface HistoryVisitGroup {
  historyId: number;
  entryDate: string;
  diseases: HistoryDiseaseResponse[];
}

export interface CertificateDiseaseApplyPayload {
  diseaseCode: string;
  primaryDiseaseName: string;
  additionalDiseaseNames: string;
  historyId: number;
}

function buildDiseaseApplyPayload(
  diseases: HistoryDiseaseResponse[],
  historyId: number
): CertificateDiseaseApplyPayload {
  return {
    diseaseCode: diseases
      .map((d) => d.code.trim())
      .filter(Boolean)
      .join("\n"),
    primaryDiseaseName: diseases[0]?.name.trim() ?? "",
    additionalDiseaseNames: diseases
      .slice(1)
      .map((d) => d.name.trim())
      .filter(Boolean)
      .join("\n"),
    historyId,
  };
}

interface Props {
  patientId?: number;
  employeeId: number;
  onApplyDiagnosisToCertificate?: (payload: CertificateDiseaseApplyPayload) => void;
}

export default function CertificateBottom({
  patientId,
  employeeId,
  onApplyDiagnosisToCertificate,
}: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("상병");
  const [visitGroups, setVisitGroups] = useState<HistoryVisitGroup[]>([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!patientId) {
      setVisitGroups([]);
      setSelectedHistoryId(null);
      return;
    }

    let cancelled = false;

    const fetchDiseases = async () => {
      setLoading(true);
      setError(null);
      try {
        const { histories } = await getPatientHistories(employeeId, patientId);

        const results = await Promise.allSettled(
          histories.map((h) =>
            getHistoryDiseases(h.id, employeeId).then((list) => ({
              historyId: h.id,
              entryDate: h.entryDate,
              diseases: list,
            }))
          )
        );

        if (cancelled) return;

        const groups: HistoryVisitGroup[] = histories.map((h, i) => {
          const r = results[i];
          if (r.status === "fulfilled") return r.value;
          return { historyId: h.id, entryDate: h.entryDate, diseases: [] };
        });

        groups.sort((a, b) => b.entryDate.localeCompare(a.entryDate));

        setVisitGroups(groups);
        setSelectedHistoryId(groups[0]?.historyId ?? null);
      } catch {
        if (!cancelled) {
          setError("상병 내역을 불러오지 못했습니다.");
          setVisitGroups([]);
          setSelectedHistoryId(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchDiseases();
    return () => { cancelled = true; };
  }, [patientId, employeeId]);

  const selectedDiseases = useMemo(() => {
    if (selectedHistoryId == null) return [];
    const g = visitGroups.find((v) => v.historyId === selectedHistoryId);
    return g?.diseases ?? [];
  }, [visitGroups, selectedHistoryId]);

  return (
    <div className={styles.container}>
      <div className={styles.tabBar}>
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            className={`${styles.tab} ${activeTab === tab ? styles.activeTab : ""}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className={styles.body}>
        {activeTab === "상병" && (
          <>
            {loading && <p className={styles.placeholder}>조회 중…</p>}
            {!loading && error && <p className={styles.placeholder}>{error}</p>}
            {!loading && !error && !patientId && (
              <p className={styles.placeholder}>환자를 조회하면 진료별 상병이 표시됩니다.</p>
            )}
            {!loading && !error && patientId && visitGroups.length === 0 && (
              <p className={styles.placeholder}>진료 이력이 없습니다.</p>
            )}
            {!loading && !error && patientId && visitGroups.length > 0 && (
              <div className={styles.diseaseSplit}>
                <div className={styles.historyColumn}>
                  <div className={styles.columnTitle}>진료일 (이력)</div>
                  <ul className={styles.historyList} role="listbox" aria-label="진료 이력">
                    {visitGroups.map((g) => {
                      const selected = g.historyId === selectedHistoryId;
                      return (
                        <li key={g.historyId}>
                          <button
                            type="button"
                            role="option"
                            aria-selected={selected}
                            className={`${styles.historyRow} ${selected ? styles.historyRowSelected : ""}`}
                            onClick={() => setSelectedHistoryId(g.historyId)}
                          >
                            <span className={styles.historyDate}>{g.entryDate.slice(0, 10)}</span>
                            <span className={styles.historyMeta}>
                              상병 {g.diseases.length}건
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
                <div className={styles.diseaseColumn}>
                  <div className={styles.diseaseHeaderRow}>
                    <div className={styles.columnTitle}>해당 진료 상병</div>
                    <button
                      type="button"
                      className={styles.applyButton}
                      disabled={
                        selectedDiseases.length === 0 || !onApplyDiagnosisToCertificate
                      }
                      onClick={() => {
                        if (
                          selectedDiseases.length > 0 &&
                          selectedHistoryId != null &&
                          onApplyDiagnosisToCertificate
                        ) {
                          onApplyDiagnosisToCertificate(
                            buildDiseaseApplyPayload(selectedDiseases, selectedHistoryId)
                          );
                        }
                      }}
                    >
                      적용
                    </button>
                  </div>
                  {selectedDiseases.length === 0 ? (
                    <p className={styles.diseaseEmpty}>이 진료에 등록된 상병이 없습니다.</p>
                  ) : (
                    <div className={styles.diseaseTableWrap}>
                      <table className={styles.diseaseTable}>
                        <thead>
                          <tr>
                            <th>No.</th>
                            <th>상병코드</th>
                            <th>상병명</th>
                            <th>구분</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedDiseases.map((d, i) => (
                            <tr key={d.id}>
                              <td>{i + 1}</td>
                              <td>{d.code}</td>
                              <td>{d.name}</td>
                              <td>{d.degree ?? "-"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}
        {activeTab === "상용구" && (
          <p className={styles.placeholder}>상용구 내용을 여기에 추가하세요.</p>
        )}
        {activeTab === "과거처방" && (
          <p className={styles.placeholder}>과거처방 내용을 여기에 추가하세요.</p>
        )}
        {activeTab === "사용자설정" && (
          <p className={styles.placeholder}>사용자설정 내용을 여기에 추가하세요.</p>
        )}
      </div>
    </div>
  );
}
