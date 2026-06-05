"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "./HistoryDiagnose.module.css";
import {
  getPatientHistories,
  getHistoryDiseases,
  getHistoryDiagnoses,
  type HistoryDiseaseResponse,
  type HistoryDiagnoseResponse,
} from "@/services/history";
import type { HistoryEntry } from "@/types/history";

type HistoryProps = {
  employeeId: number;
  patientId?: number | null;
  refreshKey?: number;
};

type HistoryRecord = {
  history: HistoryEntry;
  diseases: HistoryDiseaseResponse[];
  diagnoses: HistoryDiagnoseResponse[];
};

function formatDate(dateString: string | null | undefined) {
  if (!dateString) return "-";
  try {
    const date = new Date(dateString);
    return date
      .toLocaleDateString("ko-KR", {
        year: "2-digit",
        month: "2-digit",
        day: "2-digit",
      })
      .replace(/\./g, "-")
      .replace(/ /g, "")
      .slice(0, -1);
  } catch {
    return dateString;
  }
}

function formatDiagnoseMeta(diagnose: HistoryDiagnoseResponse) {
  const parts = [];
  parts.push(`${diagnose.dose}mg`);
  parts.push(`${diagnose.time}회`);
  parts.push(`${diagnose.days}일`);
  return parts.join(" · ");
}

function formatLocalDate(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export default function History({ employeeId, patientId, refreshKey }: HistoryProps) {
  const [startDate, setStartDate] = useState(() => {
    const date = new Date();
    date.setFullYear(date.getFullYear() - 1);
    return formatLocalDate(date);
  });
  const [endDate, setEndDate] = useState(() => formatLocalDate(new Date()));
  const [selectedPeriod, setSelectedPeriod] = useState("12개월");
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const periods = useMemo(() => ["1개월", "3개월", "6개월", "12개월"], []);

  useEffect(() => {
    if (!patientId) {
      setRecords([]);
      setError(null);
      return;
    }

    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const historyList = await getPatientHistories(employeeId, patientId, startDate, endDate);
        const histories = Array.isArray(historyList.histories) ? historyList.histories : [];
        const sorted = [...histories].sort((a, b) => {
          const dateA = new Date(a.entryDate ?? "").getTime();
          const dateB = new Date(b.entryDate ?? "").getTime();
          return dateB - dateA;
        });

        const detailed = await Promise.all(
          sorted.map(async (history) => {
            const [diseases, diagnoses] = await Promise.all([
              getHistoryDiseases(history.id, employeeId),
              getHistoryDiagnoses(history.id, employeeId),
            ]);
            return { history, diseases, diagnoses } satisfies HistoryRecord;
          })
        );

        setRecords(detailed);
      } catch (err) {
        console.error("히스토리 상세 조회 실패:", err);
        setError("과거 진료 기록을 불러오지 못했습니다.");
      } finally {
        setLoading(false);
      }
    };

    void fetchData();
  }, [employeeId, patientId, startDate, endDate, refreshKey]);

  const handlePeriodSelect = (period: string) => {
    setSelectedPeriod(period);
    const today = new Date();
    const nextStart = new Date(today);

    switch (period) {
      case "1개월":
        nextStart.setMonth(today.getMonth() - 1);
        break;
      case "3개월":
        nextStart.setMonth(today.getMonth() - 3);
        break;
      case "6개월":
        nextStart.setMonth(today.getMonth() - 6);
        break;
      case "12개월":
      default:
        nextStart.setFullYear(today.getFullYear() - 1);
        break;
    }

    setStartDate(formatLocalDate(nextStart));
    setEndDate(formatLocalDate(today));
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3>과거 진료 기록</h3>
      </div>
      <div className={styles.content}>
        <div className={styles.dateSection}>
          <div className={styles.dateInputs}>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className={styles.dateInput}
            />
            <span className={styles.dateSeparator}>-</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className={styles.dateInput}
            />
          </div>
          <div className={styles.periodButtons}>
            {periods.map((period) => (
              <button
                key={period}
                type="button"
                onClick={() => handlePeriodSelect(period)}
                className={`${styles.periodButton} ${selectedPeriod === period ? styles.active : ""}`}
              >
                {period}
              </button>
            ))}
            <button type="button" className={styles.searchButton} onClick={() => setSelectedPeriod("직접선택")}>
              조회
            </button>
          </div>
        </div>

        {!patientId ? (
          <div className={styles.emptyMessage}>환자를 선택하면 과거 진료 기록을 확인할 수 있습니다.</div>
        ) : loading ? (
          <div className={styles.emptyMessage}>불러오는 중...</div>
        ) : error ? (
          <div className={styles.emptyMessage}>{error}</div>
        ) : records.length === 0 ? (
          <div className={styles.emptyMessage}>해당 기간에 기록된 진료가 없습니다.</div>
        ) : (
          <div className={styles.historyList}>
            {records.map((record) => (
              <div key={record.history.id} className={styles.historyItem}>
                <div className={styles.historyHeader}>
                  <span className={styles.historyDate}>{formatDate(record.history.entryDate)}</span>
                  <span className={styles.historyHospital}>
                    {`진료과: ${record.history.deptId} · 담당의 ID: ${record.history.employeeId}`}
                  </span>
                </div>

                {record.history.symptomDetail && (
                  <div className={styles.symptom}>
                    증상 메모: <span>{record.history.symptomDetail}</span>
                  </div>
                )}

                <div className={styles.detailsList}>
                  {record.diseases.map((disease) => (
                    <div key={`disease-${disease.id}`} className={styles.detailItem}>
                      <div className={styles.detailCode}>{disease.code}</div>
                      <div className={styles.detailContent}>
                        <div className={styles.detailValue}>{disease.name}</div>
                        {disease.degree ? (
                          <div className={styles.detailDescription}>중증도: {disease.degree}</div>
                        ) : null}
                      </div>
                    </div>
                  ))}

                  {record.diagnoses.map((diagnose) => (
                    <div key={`diagnose-${diagnose.id}`} className={styles.detailItem}>
                      <div className={styles.detailCode}>{diagnose.code}</div>
                      <div className={styles.detailContent}>
                        <div className={styles.detailValue}>{diagnose.name}</div>
                        <div className={styles.detailDescription}>{formatDiagnoseMeta(diagnose)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}



