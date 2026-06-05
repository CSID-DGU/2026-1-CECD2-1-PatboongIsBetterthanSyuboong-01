"use client";

import { useEffect, useRef, useState } from "react";
import { PDFDocument } from "pdf-lib";
import html2canvas from "html2canvas";
import {
  generateDocumentCertificateByHistory,
  HttpError,
  saveDocumentCertificate,
} from "@/services";
import { setAccessToken, setRefreshToken } from "@/lib/auth/token";
import styles from "./MedicalCertificate.module.css";
import { CertificateItem, CertificateType } from "./CertificateList";
import type { CertificatePatientInfo } from "./CertificatePatientSearch";

type FieldValues = Record<string, string>;

type TemplateControlType = "input" | "textarea" | "checkbox" | "select";

interface TemplateControl {
  id: string;
  type: TemplateControlType;
  top: string;
  left: string;
  width: string;
  height: string;
  rows?: number;
}

/** AI 미리보기 모달에서 수락·거절 후 저장 시 APPROVE/REJECT/MODIFY 판단에 사용 */
type AiModalResolution =
  | { accepted: true; proposedText: string }
  | { accepted: false; proposedText: string };

interface TokenEnvelope {
  accessToken?: string;
  refreshToken?: string;
}

const PDF_MIN_FONT_SIZE_PX = 6;
const PDF_MAX_FONT_SIZE_PX = 12;

function parsePixelValue(value: string | null | undefined, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function fitTextToBox(element: HTMLElement, maxFontSize: number) {
  const minFontSize = PDF_MIN_FONT_SIZE_PX;
  let fontSize = Math.min(maxFontSize, PDF_MAX_FONT_SIZE_PX);
  element.style.fontSize = `${fontSize}px`;
  element.style.lineHeight = "1.18";

  while (
    fontSize > minFontSize &&
    (element.scrollHeight > element.clientHeight || element.scrollWidth > element.clientWidth)
  ) {
    fontSize -= 0.5;
    element.style.fontSize = `${fontSize}px`;
  }
}

function getPrintableFieldText(
  element: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
): string {
  if (element.tagName === "SELECT") {
    const select = element as HTMLSelectElement;
    return select.selectedOptions[0]?.textContent?.trim() ?? select.value;
  }
  return element.value;
}

function replaceFieldWithPrintableText(
  clonedDoc: Document,
  element: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
) {
  if (element.tagName === "INPUT" && (element as HTMLInputElement).type === "checkbox") {
    element.style.boxShadow = "none";
    element.style.outline = "none";
    return;
  }

  const text = getPrintableFieldText(element);
  const computed = clonedDoc.defaultView?.getComputedStyle(element);
  const printable = clonedDoc.createElement("div");

  printable.className = element.className;
  printable.textContent = text;
  printable.style.cssText = element.getAttribute("style") ?? "";
  printable.style.position = computed?.position ?? "absolute";
  printable.style.zIndex = computed?.zIndex ?? "10";
  printable.style.boxSizing = "border-box";
  printable.style.padding = computed?.padding ?? "2px 4px";
  printable.style.border = "none";
  printable.style.background = "transparent";
  printable.style.color = computed?.color ?? "#111827";
  printable.style.fontFamily = computed?.fontFamily ?? '"Malgun Gothic", Arial, sans-serif';
  printable.style.whiteSpace = "pre-wrap";
  printable.style.wordBreak = "break-word";
  printable.style.overflow = "hidden";
  printable.style.display = "block";

  element.replaceWith(printable);
  const maxFontSize = parsePixelValue(computed?.fontSize, PDF_MAX_FONT_SIZE_PX);
  fitTextToBox(printable, maxFontSize);
}

function prepareCertificateCloneForPdf(clonedDoc: Document, clonedRoot: HTMLElement) {
  clonedRoot
    .querySelectorAll<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>("input, textarea, select")
    .forEach((element) => replaceFieldWithPrintableText(clonedDoc, element));
}

const PURPOSE_OPTIONS = [
  "사내 제출용",
  "학교 제출용",
  "군대/병무용",
  "보험사 제출용",
  "법적 증빙용",
];

const TEMPLATE_IMAGES: Record<CertificateType, string> = {
  general: "/certificates/general.png",
  military: "/certificates/military.png",
};

const STAMP_IMAGE = "/certificates/logo-removebg-preview.png";

const TEMPLATE_CONTROLS: Record<CertificateType, TemplateControl[]> = {
  general: [
    { id: "patientId", type: "input", top: "9.7%", left: "23.8%", width: "11.4%", height: "3.2%" },
    { id: "patientName", type: "input", top: "16.4%", left: "23.6%", width: "27.8%", height: "4.1%" },
    { id: "idNumber", type: "input", top: "16.4%", left: "64.8%", width: "25.1%", height: "4.1%" },
    { id: "diagnosis", type: "input", top: "28.1%", left: "26.0%", width: "43.0%", height: "3.8%" },
    { id: "diagnosisExtra", type: "textarea", top: "36.0%", left: "26.0%", width: "43.0%", height: "7.4%", rows: 3 },
    { id: "diseaseCode", type: "textarea", top: "27.8%", left: "73.2%", width: "16.7%", height: "17.2%", rows: 5 },
    { id: "clinicalEstimate", type: "checkbox", top: "38.7%", left: "12.0%", width: "1.8%", height: "1.8%" },
    { id: "finalDiagnosis", type: "checkbox", top: "41.1%", left: "12.0%", width: "1.8%", height: "1.8%" },
    { id: "diagnosisDate", type: "input", top: "46.1%", left: "64.6%", width: "22.6%", height: "3.4%" },
    { id: "opinion", type: "textarea", top: "51.2%", left: "23.5%", width: "66.3%", height: "14.9%", rows: 6 },
    { id: "purpose", type: "select", top: "70.1%", left: "23.5%", width: "66.3%", height: "3.4%" },
  ],
  military: [
    { id: "patientName", type: "input", top: "15.7%", left: "21.1%", width: "27.0%", height: "4.6%" },
    { id: "idNumber", type: "input", top: "15.7%", left: "49.0%", width: "24.0%", height: "4.6%" },
    { id: "diagnosis", type: "input", top: "30.9%", left: "21.0%", width: "33.0%", height: "2.5%" },
    { id: "clinicalEstimate", type: "checkbox", top: "31.5%", left: "39.0%", width: "1.4%", height: "1.4%" },
    { id: "finalDiagnosis", type: "checkbox", top: "31.5%", left: "47.5%", width: "1.4%", height: "1.4%" },
    { id: "diseaseCode", type: "input", top: "30.9%", left: "72.0%", width: "17.4%", height: "2.5%" },
    { id: "diagnosisDate", type: "input", top: "34.1%", left: "34.0%", width: "18.0%", height: "2.4%" },
    { id: "diagnosisExtra", type: "textarea", top: "40.1%", left: "21.0%", width: "68.8%", height: "4.6%", rows: 2 },
    { id: "opinion", type: "textarea", top: "45.0%", left: "21.0%", width: "68.8%", height: "10.1%", rows: 4 },
  ],
};

const STAMP_POSITIONS: Record<CertificateType, Array<{ top: string; left: string; width: string }>> = {
  general: [
    { top: "8.0%", left: "78.8%", width: "7.8%" },
    { top: "85.2%", left: "73.5%", width: "8.2%" },
  ],
  military: [
    { top: "20.8%", left: "87.7%", width: "4.2%" },
    { top: "78.5%", left: "58.0%", width: "8.5%" },
  ],
};

/** 로컬 기준 `YYYY년 MM월 DD일` (진단일·발급일 등) */
function formatKoreanDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}년 ${m}월 ${d}일`;
}

/** 환자 정보에서 필드 ID로 자동 채울 수 있는 매핑 */
const PATIENT_FIELD_MAP: Partial<Record<string, keyof CertificatePatientInfo>> = {
  patientName:  "patientName",
  patientId:    "patientNumber",
  idNumber:     "identityNumber",
};

export interface CertificateDiagnosisApply {
  key: number;
  diseaseCode: string;
  primaryDiseaseName: string;
  additionalDiseaseNames: string;
  historyId: number;
}

interface MedicalCertificateProps {
  selected: CertificateItem | null;
  patientInfo: CertificatePatientInfo | null;
  employeeId: number;
  /** 상병 패널에서 보낸 적용 요청; `key`가 바뀔 때마다 상병 코드와 상병명 필드에 반영 */
  diagnosisApply?: CertificateDiagnosisApply | null;
}

export default function MedicalCertificate({
  selected,
  patientInfo,
  diagnosisApply = null,
}: MedicalCertificateProps) {
  const [fieldValues, setFieldValues] = useState<Record<CertificateType, FieldValues>>({
    general: {},
    military: {},
  });
  const [saving, setSaving] = useState(false);
  const [aiGenerating, setAiGenerating] = useState(false);
  const [noticeModal, setNoticeModal] = useState<string | null>(null);
  const [aiPreviewModal, setAiPreviewModal] = useState<{ text: string } | null>(null);
  const [resolvedAiRound, setResolvedAiRound] = useState<AiModalResolution | null>(null);
  const certificatePageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setAiPreviewModal(null);
    setResolvedAiRound(null);
  }, [patientInfo?.patientId, selected?.id, diagnosisApply?.historyId]);

  // 진단서 종류 선택 시 진단일·발급일을 오늘(로컬) 날짜로 채움
  useEffect(() => {
    if (!selected) return;
    const today = formatKoreanDate(new Date());
    setFieldValues((prev) => ({
      ...prev,
      [selected.type]: {
        ...prev[selected.type],
        diagnosisDate: prev[selected.type].diagnosisDate ?? today,
        issueDate: prev[selected.type].issueDate ?? today,
      },
    }));
  }, [selected]);

  // 환자 정보가 들어오면 PDF가 로드된 타입의 필드를 자동으로 채움
  useEffect(() => {
    if (!patientInfo || !selected) return;

    const autoFilled: FieldValues = {};
    Object.entries(PATIENT_FIELD_MAP).forEach(([id, patientKey]) => {
      if (patientKey) {
        const value = patientInfo[patientKey];
        if (value) autoFilled[id] = String(value);
      }
    });

    if (Object.keys(autoFilled).length === 0) return;

    setFieldValues((prev) => ({
      ...prev,
      [selected.type]: { ...prev[selected.type], ...autoFilled },
    }));
  }, [patientInfo, selected]);

  useEffect(() => {
    if (!diagnosisApply || !selected) return;
    setFieldValues((prev) => ({
      ...prev,
      [selected.type]: {
        ...prev[selected.type],
        diseaseCode: diagnosisApply.diseaseCode,
        diagnosis: diagnosisApply.primaryDiseaseName,
        diagnosisExtra: diagnosisApply.additionalDiseaseNames,
      },
    }));
  }, [diagnosisApply, selected]);

  const handleChange = (type: CertificateType, fieldId: string, value: string) => {
    setFieldValues((prev) => ({
      ...prev,
      [type]: { ...prev[type], [fieldId]: value },
    }));
  };

  const handleCheckboxChange = (type: CertificateType, fieldId: string, checked: boolean) => {
    setFieldValues((prev) => {
      const next = { ...prev[type], [fieldId]: checked ? "true" : "" };
      if (checked && fieldId === "clinicalEstimate") {
        next.finalDiagnosis = "";
      }
      if (checked && fieldId === "finalDiagnosis") {
        next.clinicalEstimate = "";
      }
      return { ...prev, [type]: next };
    });
  };

  const getDiagnosisKind = (type: CertificateType): string => {
    const values = fieldValues[type];
    if (values.finalDiagnosis === "true") return "최종 진단";
    if (values.clinicalEstimate === "true") return "임상적 추정";
    return "미선택";
  };

  const createCertificatePdfBlob = async (): Promise<Blob> => {
    if (!certificatePageRef.current) {
      throw new Error("진단서 화면을 찾을 수 없습니다.");
    }
    const canvas = await html2canvas(certificatePageRef.current, {
      backgroundColor: "#ffffff",
      scale: 2,
      useCORS: true,
      onclone: (clonedDoc, cloned) => {
        prepareCertificateCloneForPdf(clonedDoc, cloned);
      },
    });
    const pngDataUrl = canvas.toDataURL("image/png");
    const pngBytes = await fetch(pngDataUrl).then((r) => r.arrayBuffer());
    const pdfDoc = await PDFDocument.create();
    const page = pdfDoc.addPage([595.28, 841.89]);
    const pngImage = await pdfDoc.embedPng(pngBytes);
    const { width, height } = page.getSize();
    page.drawImage(pngImage, { x: 0, y: 0, width, height });
    const savedBytes = await pdfDoc.save();
    return new Blob([savedBytes.buffer as ArrayBuffer], {
      type: "application/pdf",
    });
  };

  const getCertificateFilename = (): string => {
    if (!selected) return "진단서.pdf";
    const patientName = fieldValues[selected.type].patientName || "진단서";
    return `${selected.label}_${patientName}.pdf`;
  };

  const getFeedbackType = (): "APPROVE" | "MODIFY" | "REJECT" | "NONE" => {
    if (!selected || !resolvedAiRound) return "NONE";
    if (!resolvedAiRound.accepted) return "REJECT";
    const currentOpinion = (fieldValues[selected.type].opinion ?? "").trim();
    return currentOpinion === resolvedAiRound.proposedText.trim() ? "APPROVE" : "MODIFY";
  };

  const applySaveResponseTokens = (payload: unknown) => {
    if (!payload || typeof payload !== "object") return;
    const envelope = payload as TokenEnvelope;
    if (envelope.accessToken) setAccessToken(envelope.accessToken);
    if (envelope.refreshToken) setRefreshToken(envelope.refreshToken);
  };

  const handleAiGenerate = async () => {
    if (!selected) return;
    const historyId = diagnosisApply?.historyId;
    if (historyId == null) {
      setNoticeModal("진단서에 상병을 먼저 적용해 주세요.");
      return;
    }
    setAiGenerating(true);
    try {
      const res = await generateDocumentCertificateByHistory({
        historyId,
        certificateType: selected.type === "military" ? "MILITARY" : "GENERAL",
        diagnosisKind: getDiagnosisKind(selected.type),
        purpose: selected.type === "general" ? fieldValues[selected.type].purpose ?? "" : "",
      });
      const text = res.medicalCertificate ?? res.medical_certificate ?? "";
      setResolvedAiRound(null);
      setAiPreviewModal({ text });
    } catch (error: unknown) {
      console.error("AI 문서 생성 실패", error);
      if (error instanceof HttpError) {
        setNoticeModal(
          `AI 생성에 실패했습니다. [${error.status}] ${error.message}`
        );
      } else {
        setNoticeModal("AI 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.");
      }
    } finally {
      setAiGenerating(false);
    }
  };

  const handleDownload = async () => {
    if (!selected || !certificatePageRef.current) return;
    if (aiPreviewModal != null) {
      setNoticeModal("AI 생성 내용에 먼저 수락 또는 거절을 선택해 주세요.");
      return;
    }
    setSaving(true);
    try {
      const blob = await createCertificatePdfBlob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = getCertificateFilename();
      link.click();
      URL.revokeObjectURL(url);
      setNoticeModal("PDF 다운로드가 완료되었습니다.");
    } catch (error: unknown) {
      console.error("진단서 PDF 생성 실패", error);
      setNoticeModal("PDF 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveToDatabase = async () => {
    if (!selected) return;
    const historyId = diagnosisApply?.historyId;
    if (historyId == null) {
      setNoticeModal("진단서에 상병을 먼저 적용해 주세요.");
      return;
    }
    if (aiPreviewModal != null) {
      setNoticeModal("AI 생성 내용에 먼저 수락 또는 거절을 선택해 주세요.");
      return;
    }
    setSaving(true);
    try {
      const blob = await createCertificatePdfBlob();
      const formData = new FormData();
      const savedOpinion = fieldValues[selected.type].opinion ?? "";
      formData.append("historyId", String(historyId));
      formData.append("pdfFile", blob, getCertificateFilename());
      formData.append("agentUsed", String(resolvedAiRound != null));
      formData.append(
        "originalMedicalCertificate",
        resolvedAiRound?.proposedText ?? ""
      );
      formData.append("savedMedicalCertificate", savedOpinion);
      formData.append("feedbackType", getFeedbackType());
      const response = await saveDocumentCertificate(formData);
      applySaveResponseTokens(response);
      setNoticeModal("진단서 내용이 DB에 저장되었습니다.");
    } catch (error: unknown) {
      console.error("진단서 저장 실패", error);
      if (error instanceof HttpError) {
        setNoticeModal(`진단서 저장에 실패했습니다. [${error.status}] ${error.message}`);
      } else {
        setNoticeModal("진단서 저장에 실패했습니다. 잠시 후 다시 시도해 주세요.");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleAiPreviewAccept = () => {
    if (!selected || !aiPreviewModal) return;
    const proposedText = aiPreviewModal.text;
    setFieldValues((prev) => ({
      ...prev,
      [selected.type]: { ...prev[selected.type], opinion: proposedText },
    }));
    setResolvedAiRound({ accepted: true, proposedText });
    setAiPreviewModal(null);
  };

  const handleAiPreviewReject = () => {
    if (!aiPreviewModal) return;
    setResolvedAiRound({ accepted: false, proposedText: aiPreviewModal.text });
    setAiPreviewModal(null);
  };

  const renderTemplateControl = (control: TemplateControl) => {
    if (!selected) return null;
    const type = selected.type;
    const commonStyle = {
      top: control.top,
      left: control.left,
      width: control.width,
      height: control.height,
    };

    if (control.type === "checkbox") {
      return (
        <input
          key={control.id}
          type="checkbox"
          className={styles.templateCheckbox}
          style={commonStyle}
          checked={fieldValues[type][control.id] === "true"}
          onChange={(e) => handleCheckboxChange(type, control.id, e.target.checked)}
          aria-label={control.id}
        />
      );
    }

    if (control.type === "select") {
      return (
        <select
          key={control.id}
          className={styles.templateSelect}
          style={commonStyle}
          value={fieldValues[type][control.id] ?? ""}
          onChange={(e) => handleChange(type, control.id, e.target.value)}
          aria-label="용도"
        >
          <option value="">용도 선택</option>
          {PURPOSE_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      );
    }

    if (control.type === "textarea") {
      return (
        <textarea
          key={control.id}
          className={styles.templateTextarea}
          style={commonStyle}
          rows={control.rows ?? 3}
          value={fieldValues[type][control.id] ?? ""}
          onChange={(e) => handleChange(type, control.id, e.target.value)}
          aria-label={control.id}
        />
      );
    }

    return (
      <input
        key={control.id}
        type="text"
        className={styles.templateInput}
        style={commonStyle}
        value={fieldValues[type][control.id] ?? ""}
        onChange={(e) => handleChange(type, control.id, e.target.value)}
        aria-label={control.id}
      />
    );
  };

  return (
    <div className={styles.container}>
      {aiPreviewModal != null && selected && (
        <div
          className={styles.modalBackdrop}
          style={{ zIndex: 1001 }}
          role="presentation"
        >
          <div
            className={`${styles.modal} ${styles.modalWide}`}
            role="dialog"
            aria-modal="true"
            aria-labelledby="ai-preview-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="ai-preview-title" className={styles.modalHeading}>
              생성된 의사 소견을 진단서에 넣겠습니까?
            </h3>
            <textarea
              className={styles.aiPreviewTextarea}
              readOnly
              value={aiPreviewModal.text}
              rows={12}
              aria-label="AI 생성 소견 미리보기"
            />
            <div className={styles.modalActions}>
              <button
                type="button"
                className={styles.modalReject}
                onClick={handleAiPreviewReject}
              >
                거절
              </button>
              <button
                type="button"
                className={styles.modalAccept}
                onClick={handleAiPreviewAccept}
              >
                수락
              </button>
            </div>
          </div>
        </div>
      )}
      {noticeModal != null && (
        <div
          className={styles.modalBackdrop}
          role="presentation"
          onClick={() => setNoticeModal(null)}
        >
          <div
            className={styles.modal}
            role="dialog"
            aria-modal="true"
            aria-labelledby="cert-notice-title"
            onClick={(e) => e.stopPropagation()}
          >
            <p id="cert-notice-title" className={styles.modalMessage}>
              {noticeModal}
            </p>
            <button
              type="button"
              className={styles.modalConfirm}
              onClick={() => setNoticeModal(null)}
            >
              확인
            </button>
          </div>
        </div>
      )}
      <div className={styles.header}>
        <h2 className={styles.title}>
          {selected ? selected.label : "진단서"}
        </h2>
        <div className={styles.headerActions}>
          <button
            type="button"
            className={styles.aiButton}
            onClick={handleAiGenerate}
            disabled={
              !selected || saving || aiGenerating || aiPreviewModal != null
            }
          >
            {aiGenerating ? "생성 중…" : "AI 생성"}
          </button>
          <button
            type="button"
            className={styles.saveButton}
            onClick={handleDownload}
            disabled={
              !selected ||
              saving ||
              aiGenerating ||
              aiPreviewModal != null
            }
          >
            {saving ? "PDF 생성 중…" : "PDF 다운로드"}
          </button>
          <button
            type="button"
            className={styles.saveButton}
            onClick={handleSaveToDatabase}
            disabled={
              !selected ||
              saving ||
              aiGenerating ||
              aiPreviewModal != null
            }
          >
            {saving ? "저장 중…" : "저장"}
          </button>
        </div>
      </div>
      <div className={styles.body}>
        {selected ? (
          <div className={styles.certificatePage} ref={certificatePageRef}>
            <img
              src={TEMPLATE_IMAGES[selected.type]}
              alt={selected.label}
              className={styles.templateImage}
              draggable={false}
            />
            <div className={styles.templateOverlay}>
              {TEMPLATE_CONTROLS[selected.type].map(renderTemplateControl)}
              {STAMP_POSITIONS[selected.type].map((stamp, index) => (
                <img
                  key={`${selected.type}-stamp-${index}`}
                  src={STAMP_IMAGE}
                  alt=""
                  className={styles.stampImage}
                  style={stamp}
                  draggable={false}
                />
              ))}
            </div>
          </div>
        ) : (
          <p className={styles.placeholder}>목록에서 진단서를 선택하세요.</p>
        )}
      </div>
    </div>
  );
}
