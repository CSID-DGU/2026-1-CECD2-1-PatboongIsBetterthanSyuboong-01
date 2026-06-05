"use client";

import { FormEvent, useMemo, useState } from "react";
import * as XLSX from "xlsx";
import {
  evaluateDocumentCertificate,
  generateDocumentCertificate,
  type DocumentGenerateResponse,
  type DocumentEvaluateResponse,
} from "@/services/agent";
import styles from "./page.module.css";

type ApiError = {
  error?: string;
  message?: string;
};

type BatchResult = {
  rowNumber: number;
  diseaseCode: string;
  prescriptionCode: string;
  prescriptionName: string;
  status: "success" | "error";
  medicalCertificate?: string;
  generateRawResponse?: unknown;
  evaluateRawResponse?: DocumentEvaluateResponse;
  error?: string;
};

type HealthCheckResult = {
  status: "success" | "error";
  checkedAt: string;
  request: {
    diseaseCode: string;
    prescriptionCode: string;
    prescriptionName: string;
  };
  medicalCertificate?: string;
  evaluate?: DocumentEvaluateResponse;
  error?: string;
};

const MAX_BATCH_ROWS = 5000;
const MAX_CONCURRENT_REQUESTS = 5;

function toPrettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function escapeCsvCell(value: unknown): string {
  const text = String(value ?? "");
  const escaped = text.replace(/"/g, '""');
  return `"${escaped}"`;
}

function columnLabelToIndex(label: string): number | null {
  const normalized = label.trim().toUpperCase();
  if (!/^[A-Z]+$/.test(normalized)) {
    return null;
  }

  let index = 0;
  for (let i = 0; i < normalized.length; i += 1) {
    index = index * 26 + (normalized.charCodeAt(i) - 64);
  }

  return index - 1;
}

function isRowEmpty(row: string[]): boolean {
  return row.every((cell) => cell.trim() === "");
}

async function parseWorksheetRows(file: File): Promise<string[][]> {
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: "array" });
  const firstSheetName = workbook.SheetNames[0];

  if (!firstSheetName) {
    throw new Error("XLSX 파일에 시트가 없습니다.");
  }

  const worksheet = workbook.Sheets[firstSheetName];
  const rawRows = XLSX.utils.sheet_to_json<(string | number | boolean | null)[]>(worksheet, {
    header: 1,
    raw: false,
    defval: "",
  });

  return rawRows.map((row) => row.map((cell) => String(cell ?? "")));
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function buildDummyGenerateResponse(
  diseaseCode: string,
  prescriptionCode: string,
  prescriptionName: string
): DocumentGenerateResponse {
  return {
    grantType: "Bearer",
    accessToken: "dummy-access-token",
    refreshToken: "dummy-refresh-token",
    medicalCertificate: [
      `상병코드: ${diseaseCode}`,
      `처방코드: ${prescriptionCode}`,
      `처방명: ${prescriptionName}`,
      "",
      "의사소견:",
      `${diseaseCode} 관련 증상에 대해 ${prescriptionName}(${prescriptionCode}) 처방을 바탕으로 경과 관찰 및 약물 치료가 필요합니다.`,
    ].join("\n"),
  };
}

function buildDummyEvaluateResponse(medicalCertificate: string): DocumentEvaluateResponse {
  const lines = medicalCertificate
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const totalPairs = 3;
  const entailmentCount = Math.min(2, Math.max(1, lines.length % 3 || 2));
  const score = Number((entailmentCount / totalPairs).toFixed(3));

  return {
    score,
    entailmentCount,
    totalPairs,
    premise: lines.slice(0, 3).join("\n"),
    details: [
      {
        index: 1,
        hypothesis: "상병코드와 처방 정보가 문서에 포함되어 있다.",
        judgment: "ENTAILMENT",
        reason: "더미 문서 본문에 상병코드, 처방코드, 처방명이 모두 포함되어 있습니다.",
      },
      {
        index: 2,
        hypothesis: "향후 치료 또는 경과 관찰 필요성이 언급되어 있다.",
        judgment: entailmentCount >= 2 ? "ENTAILMENT" : "NEUTRAL",
        reason:
          entailmentCount >= 2
            ? "의사소견에 경과 관찰 및 약물 치료 필요성이 명시되어 있습니다."
            : "치료 필요성 표현이 충분하지 않다고 가정한 더미 결과입니다.",
      },
      {
        index: 3,
        hypothesis: "입원 치료가 반드시 필요하다고 단정한다.",
        judgment: "NEUTRAL",
        reason: "더미 문서에는 입원 필요성에 대한 단정적 표현이 없습니다.",
      },
    ],
  };
}

function buildResultsCsv(results: BatchResult[]): string {
  const header = [
    "rowNumber",
    "diseaseCode",
    "prescriptionCode",
    "prescriptionName",
    "status",
    "medicalCertificate",
    "score",
    "entailmentCount",
    "totalPairs",
    "premise",
    "details",
    "error",
  ];

  const lines = results.map((item) => {
    const evaluation = item.evaluateRawResponse;
    return [
      item.rowNumber,
      item.diseaseCode,
      item.prescriptionCode,
      item.prescriptionName,
      item.status,
      item.medicalCertificate ?? "",
      evaluation?.score ?? "",
      evaluation?.entailmentCount ?? "",
      evaluation?.totalPairs ?? "",
      evaluation?.premise ?? "",
      evaluation ? JSON.stringify(evaluation.details) : "",
      item.error ?? "",
    ]
      .map(escapeCsvCell)
      .join(",");
  });

  return [header.map(escapeCsvCell).join(","), ...lines].join("\r\n");
}

export default function EvaluationPage() {
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [diseaseCodeColumn, setDiseaseCodeColumn] = useState("A");
  const [prescriptionCodeColumn, setPrescriptionCodeColumn] = useState("D");
  const [prescriptionNameColumn, setPrescriptionNameColumn] = useState("E");
  const [maxRowsInput, setMaxRowsInput] = useState("");
  const [skipHeaderRow, setSkipHeaderRow] = useState(true);
  const [useDummyResponses, setUseDummyResponses] = useState(false);
  const [latestMedicalCertificate, setLatestMedicalCertificate] = useState("");
  const [latestEvaluation, setLatestEvaluation] = useState<DocumentEvaluateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [batchResults, setBatchResults] = useState<BatchResult[]>([]);
  const [processedRows, setProcessedRows] = useState(0);
  const [totalRows, setTotalRows] = useState(0);
  const [healthChecking, setHealthChecking] = useState(false);
  const [healthCheckResult, setHealthCheckResult] = useState<HealthCheckResult | null>(null);

  const requestPreview = useMemo(() => {
    return {
      fileName: csvFile?.name ?? null,
      diseaseCodeColumn: diseaseCodeColumn.trim().toUpperCase(),
      prescriptionCodeColumn: prescriptionCodeColumn.trim().toUpperCase(),
      prescriptionNameColumn: prescriptionNameColumn.trim().toUpperCase(),
      maxRows: maxRowsInput.trim() ? Number(maxRowsInput) : null,
      skipHeaderRow,
      useDummyResponses,
    };
  }, [
    csvFile,
    diseaseCodeColumn,
    prescriptionCodeColumn,
    prescriptionNameColumn,
    maxRowsInput,
    skipHeaderRow,
    useDummyResponses,
  ]);

  const resultSummary = useMemo(() => {
    const successCount = batchResults.filter((item) => item.status === "success").length;
    const errorCount = batchResults.length - successCount;
    return {
      totalRows,
      processedRows,
      successCount,
      errorCount,
    };
  }, [batchResults, processedRows, totalRows]);
  const progressPercent = useMemo(() => {
    if (totalRows === 0) {
      return 0;
    }
    return Math.round((processedRows / totalRows) * 100);
  }, [processedRows, totalRows]);

  function handleDownloadResults() {
    if (batchResults.length === 0) {
      setError("다운로드할 결과가 없습니다. 먼저 CSV 요청을 실행해주세요.");
      return;
    }

    const csvContent = buildResultsCsv(batchResults);
    const blob = new Blob(["\uFEFF", csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const baseName = (csvFile?.name ?? "evaluation-results.xlsx").replace(/\.(csv|xlsx)$/i, "");

    link.href = url;
    link.download = `${baseName}-results.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  async function handleHealthCheck() {
    const request = {
      diseaseCode: "J06.9",
      prescriptionCode: "TEST-RX-001",
      prescriptionName: "헬스체크용 처방",
    };

    setHealthChecking(true);
    setHealthCheckResult(null);
    setError(null);

    try {
      const generated = await generateDocumentCertificate(request);
      const medicalCertificate = generated.medicalCertificate ?? generated.medical_certificate ?? "";

      if (!medicalCertificate.trim()) {
        throw new Error("generate-test 응답에 medicalCertificate가 없습니다.");
      }

      const evaluated = await evaluateDocumentCertificate({
        medicalCertificate,
        ...request,
      });

      setHealthCheckResult({
        status: "success",
        checkedAt: new Date().toISOString(),
        request,
        medicalCertificate,
        evaluate: evaluated,
      });
    } catch (err: unknown) {
      const maybeAxios = err as { response?: { data?: ApiError }; message?: string };
      const serverMessage =
        maybeAxios?.response?.data?.error ??
        maybeAxios?.response?.data?.message ??
        maybeAxios?.message ??
        "헬스체크 중 오류가 발생했습니다.";

      setHealthCheckResult({
        status: "error",
        checkedAt: new Date().toISOString(),
        request,
        error: serverMessage,
      });
    } finally {
      setHealthChecking(false);
    }
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();

    if (!csvFile) {
      setError("XLSX 파일을 먼저 업로드해주세요.");
      return;
    }

    const diseaseIndex = columnLabelToIndex(diseaseCodeColumn);
    const prescriptionCodeIndex = columnLabelToIndex(prescriptionCodeColumn);
    const prescriptionNameIndex = columnLabelToIndex(prescriptionNameColumn);
    const parsedMaxRows = Number(maxRowsInput);
    const maxRows =
      maxRowsInput.trim() === ""
        ? MAX_BATCH_ROWS
        : Number.isInteger(parsedMaxRows) && parsedMaxRows > 0
          ? parsedMaxRows
          : null;

    if (
      diseaseIndex == null ||
      prescriptionCodeIndex == null ||
      prescriptionNameIndex == null
    ) {
      setError("열 이름은 A, B, C 같은 형식으로 입력해주세요.");
      return;
    }

    if (maxRowsInput.trim() !== "" && maxRows == null) {
      setError("개수 제한은 1 이상의 정수로 입력해주세요.");
      return;
    }
    if (maxRows != null && maxRows > MAX_BATCH_ROWS) {
      setError(`처리 개수 제한은 최대 ${MAX_BATCH_ROWS}개까지 가능합니다.`);
      return;
    }

    setLoading(true);
    setError(null);
    setBatchResults([]);
    setLatestMedicalCertificate("");
    setLatestEvaluation(null);
    setProcessedRows(0);
    setTotalRows(0);

    try {
      const parsedRows = (await parseWorksheetRows(csvFile)).filter((row) => !isRowEmpty(row));
      const sourceRows = skipHeaderRow ? parsedRows.slice(1) : parsedRows;
      const dataRows = sourceRows.slice(0, Math.min(maxRows ?? MAX_BATCH_ROWS, MAX_BATCH_ROWS));

      if (dataRows.length === 0) {
        throw new Error("처리할 XLSX 데이터 행이 없습니다.");
      }

      setTotalRows(dataRows.length);
      const taskFactories = dataRows.map((row, i) => async (): Promise<BatchResult> => {
        const rowNumber = skipHeaderRow ? i + 2 : i + 1;
        const diseaseCode = row[diseaseIndex]?.trim() ?? "";
        const prescriptionCode = row[prescriptionCodeIndex]?.trim() ?? "";
        const prescriptionName = row[prescriptionNameIndex]?.trim() ?? "";

        if (!diseaseCode || !prescriptionCode || !prescriptionName) {
          return {
            rowNumber,
            diseaseCode,
            prescriptionCode,
            prescriptionName,
            status: "error",
            error: "지정한 열에서 필요한 값(상병코드, 처방코드, 처방명)을 모두 찾지 못했습니다.",
          };
        }

        try {
          const generated = useDummyResponses
            ? (await (async () => {
                await sleep(120);
                return buildDummyGenerateResponse(
                  diseaseCode,
                  prescriptionCode,
                  prescriptionName
                );
              })())
            : await generateDocumentCertificate({
                diseaseCode,
                prescriptionCode,
                prescriptionName,
              });
          const generatedCertificate =
            generated.medicalCertificate ?? generated.medical_certificate ?? "";

          if (!generatedCertificate.trim()) {
            throw new Error("생성 응답에 medicalCertificate가 없습니다.");
          }

          const evaluated = useDummyResponses
            ? (await (async () => {
                await sleep(80);
                return buildDummyEvaluateResponse(generatedCertificate);
              })())
            : await evaluateDocumentCertificate({
                medicalCertificate: generatedCertificate,
                diseaseCode,
                prescriptionCode,
                prescriptionName,
              });

          setLatestMedicalCertificate(generatedCertificate);
          setLatestEvaluation(evaluated);
          return {
            rowNumber,
            diseaseCode,
            prescriptionCode,
            prescriptionName,
            status: "success",
            medicalCertificate: generatedCertificate,
            generateRawResponse: generated,
            evaluateRawResponse: evaluated,
          };
        } catch (err: unknown) {
          const maybeAxios = err as { response?: { data?: ApiError }; message?: string };
          const serverMessage =
            maybeAxios?.response?.data?.error ??
            maybeAxios?.response?.data?.message ??
            maybeAxios?.message ??
            "생성 또는 평가 요청 중 오류가 발생했습니다.";
          return {
            rowNumber,
            diseaseCode,
            prescriptionCode,
            prescriptionName,
            status: "error",
            error: serverMessage,
          };
        } finally {
          setProcessedRows((prev) => prev + 1);
        }
      });
      const results: BatchResult[] = [];
      for (let i = 0; i < taskFactories.length; i += MAX_CONCURRENT_REQUESTS) {
        const chunk = taskFactories.slice(i, i + MAX_CONCURRENT_REQUESTS);
        const chunkResults = await Promise.all(chunk.map((task) => task()));
        results.push(...chunkResults);
      }
      const sorted = [...results].sort((a, b) => a.rowNumber - b.rowNumber);
      setBatchResults(sorted);
    } catch (err: unknown) {
      const fallback = "XLSX 처리 또는 생성 요청 중 오류가 발생했습니다.";
      const maybeAxios = err as { response?: { data?: ApiError }; message?: string };
      const serverMessage =
        maybeAxios?.response?.data?.error ??
        maybeAxios?.response?.data?.message ??
        maybeAxios?.message;
      setError(serverMessage || fallback);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.page}>
      <section className={styles.panel}>
        <h1 className={styles.title}>Document Evaluation</h1>
        <p className={styles.description}>
          XLSX 파일의 첫 번째 시트를 읽고 열 문자(`A`, `B`, `C`...)를 지정하면 각 행의
          데이터를 비동기로 처리해 `POST /api/agent/document/generate-test` 요청을 보내고,
          응답의 `medicalCertificate`로 바로 `POST /api/agent/document/evaluate`
          요청까지 이어서 보냅니다. 더미 응답 체크 시 실제 API 대신 로컬 더미 데이터를
          사용합니다.
        </p>

        <form className={styles.form} onSubmit={handleSubmit}>
          <label className={styles.label}>
            XLSX 파일
            <input
              className={styles.input}
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(e) => setCsvFile(e.target.files?.[0] ?? null)}
              required
            />
          </label>

          <label className={styles.label}>
            diseaseCode 열
            <input
              className={styles.input}
              type="text"
              value={diseaseCodeColumn}
              onChange={(e) => setDiseaseCodeColumn(e.target.value)}
              placeholder="예: A"
              required
            />
          </label>

          <label className={styles.label}>
            prescriptionCode 열
            <input
              className={styles.input}
              type="text"
              value={prescriptionCodeColumn}
              onChange={(e) => setPrescriptionCodeColumn(e.target.value)}
              placeholder="예: B"
              required
            />
          </label>

          <label className={styles.label}>
            prescriptionName 열
            <input
              className={styles.input}
              type="text"
              value={prescriptionNameColumn}
              onChange={(e) => setPrescriptionNameColumn(e.target.value)}
              placeholder="예: C"
              required
            />
          </label>

          <label className={styles.label}>
            처리 개수 제한
            <input
              className={styles.input}
              type="number"
              min={1}
              max={MAX_BATCH_ROWS}
              step={1}
              value={maxRowsInput}
              onChange={(e) => setMaxRowsInput(e.target.value)}
              placeholder={`비우면 최대 ${MAX_BATCH_ROWS}개 처리`}
            />
          </label>

          <label className={styles.checkboxLabel}>
            <input
              type="checkbox"
              checked={skipHeaderRow}
              onChange={(e) => setSkipHeaderRow(e.target.checked)}
            />
            첫 행은 헤더로 보고 건너뛰기
          </label>

          <label className={styles.checkboxLabel}>
            <input
              type="checkbox"
              checked={useDummyResponses}
              onChange={(e) => setUseDummyResponses(e.target.checked)}
            />
            더미 응답 사용 (체크 시 실제 API 호출 안 함)
          </label>

          <div className={styles.buttonRow}>
            <button className={styles.button} type="submit" disabled={loading}>
              {loading ? "비동기 처리 중..." : "XLSX 요청 시작"}
            </button>
            <button
              className={styles.secondaryButton}
              type="button"
              onClick={handleHealthCheck}
              disabled={loading || healthChecking}
            >
              {healthChecking ? "헬스체크 중..." : "API Healthy 체크"}
            </button>
            <button
              className={styles.secondaryButton}
              type="button"
              onClick={handleDownloadResults}
              disabled={loading || batchResults.length === 0}
            >
              결과 CSV 다운로드
            </button>
          </div>
        </form>

        <div className={styles.block}>
          <h2>Request Setup</h2>
          <pre>{toPrettyJson(requestPreview)}</pre>
        </div>

        <div className={styles.block}>
          <h2>Progress</h2>
          {totalRows > 0 && (
            <div className={styles.progressWrap}>
              <div className={styles.progressTrack}>
                <div className={styles.progressBar} style={{ width: `${progressPercent}%` }} />
              </div>
              <div className={styles.progressText}>
                {processedRows}/{totalRows} ({progressPercent}%)
              </div>
            </div>
          )}
          <pre>{toPrettyJson(resultSummary)}</pre>
        </div>

        <div className={styles.block}>
          <h2>Latest medicalCertificate</h2>
          <pre>{latestMedicalCertificate || "(아직 생성 전)"}</pre>
        </div>

        <div className={styles.block}>
          <h2>Latest evaluation</h2>
          <pre>{latestEvaluation ? toPrettyJson(latestEvaluation) : "(아직 평가 전)"}</pre>
        </div>

        <div className={styles.block}>
          <h2>API Health Check</h2>
          <pre>
            {healthCheckResult
              ? toPrettyJson(healthCheckResult)
              : "(아직 실행 전) 버튼을 눌러 generate-test + evaluate 호출 결과를 확인하세요."}
          </pre>
        </div>

        {error && (
          <div className={styles.errorBox} role="alert">
            <strong>Error</strong>
            <p>{error}</p>
          </div>
        )}

        {batchResults.length > 0 && (
          <div className={styles.block}>
            <h2>Batch Results</h2>
            <div className={styles.resultList}>
              {batchResults.map((item) => (
                <article
                  key={`${item.rowNumber}-${item.prescriptionCode}-${item.diseaseCode}`}
                  className={styles.resultCard}
                >
                  <div className={styles.resultHeader}>
                    <strong>Row {item.rowNumber}</strong>
                    <span
                      className={
                        item.status === "success" ? styles.successBadge : styles.errorBadge
                      }
                    >
                      {item.status === "success" ? "SUCCESS" : "ERROR"}
                    </span>
                  </div>
                  <pre>
                    {toPrettyJson({
                      diseaseCode: item.diseaseCode,
                      prescriptionCode: item.prescriptionCode,
                      prescriptionName: item.prescriptionName,
                    })}
                  </pre>
                  {item.status === "success" ? (
                    <>
                      <div className={styles.resultSectionTitle}>medicalCertificate</div>
                      <pre>{item.medicalCertificate || "(빈 응답)"}</pre>
                      <div className={styles.resultSectionTitle}>generateRawResponse</div>
                      <pre>{toPrettyJson(item.generateRawResponse)}</pre>
                      <div className={styles.resultSectionTitle}>evaluateRawResponse</div>
                      <pre>{toPrettyJson(item.evaluateRawResponse)}</pre>
                    </>
                  ) : (
                    <>
                      <div className={styles.resultSectionTitle}>error</div>
                      <pre>{item.error}</pre>
                    </>
                  )}
                </article>
              ))}
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
