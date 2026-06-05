"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export interface DiseaseSelection {
  id: number;
  code: string;
  name: string;
}

export interface DiagnosisSelection {
  id: number;
  code: string;
  name: string;
  dose: number;
  time: number;
  days: number;
  reason?: string;
}

/** Active Learning용: AI 추천 처방에 대한 의사의 수용/거부 피드백 */
export interface PrescriptionFeedbackItem {
  rank: number;
  id: number;
  prescription_code: string;
  prescription_name: string;
  confidence_score: number;
  reason: string;
  /** 체크박스 선택 = accepted, 미선택 = rejected */
  status: "accepted" | "rejected";
}

interface MedicalSelectionContextValue {
  diseases: DiseaseSelection[];
  diagnoses: DiagnosisSelection[];
  /** 현재 AI 추천 세션의 accepted/rejected 피드백 (그래프 생성 시 인자로 전달) */
  prescriptionFeedback: PrescriptionFeedbackItem[];
  addDisease: (item: DiseaseSelection) => void;
  addDiagnosis: (item: DiagnosisSelection) => void;
  removeDisease: (id: number) => void;
  removeDiagnosis: (id: number) => void;
  clearDiseases: () => void;
  clearDiagnoses: () => void;
  /** 타임라인 등에서 특정 내원의 저장된 상병·처방을 통째로 불러올 때 사용 */
  replaceDiseases: (items: DiseaseSelection[]) => void;
  replaceDiagnoses: (items: DiagnosisSelection[]) => void;
  /** '선택 처방 반영' 클릭 시 accepted/rejected 피드백을 저장 */
  setPrescriptionFeedback: (items: PrescriptionFeedbackItem[]) => void;
  clearPrescriptionFeedback: () => void;
}

const MedicalSelectionContext = createContext<MedicalSelectionContextValue | null>(null);

export function MedicalSelectionProvider({ children }: { children: ReactNode }) {
  const [diseases, setDiseases] = useState<DiseaseSelection[]>([]);
  const [diagnoses, setDiagnoses] = useState<DiagnosisSelection[]>([]);
  const [prescriptionFeedback, setPrescriptionFeedbackState] = useState<PrescriptionFeedbackItem[]>([]);

  const addDisease = useCallback((item: DiseaseSelection) => {
    setDiseases((prev) => {
      const index = prev.findIndex((d) => d.id === item.id);
      if (index >= 0) {
        const next = [...prev];
        next[index] = item;
        return next;
      }
      return [...prev, item];
    });
  }, []);

  const addDiagnosis = useCallback((item: DiagnosisSelection) => {
    setDiagnoses((prev) => {
      const index = prev.findIndex((d) => d.id === item.id);
      if (index >= 0) {
        const next = [...prev];
        next[index] = item;
        return next;
      }
      return [...prev, item];
    });
  }, []);

  const removeDisease = useCallback((id: number) => {
    setDiseases((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const removeDiagnosis = useCallback((id: number) => {
    setDiagnoses((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const clearDiseases = useCallback(() => {
    setDiseases([]);
  }, []);

  const clearDiagnoses = useCallback(() => {
    setDiagnoses([]);
  }, []);

  const replaceDiseases = useCallback((items: DiseaseSelection[]) => {
    setDiseases(items);
  }, []);

  const replaceDiagnoses = useCallback((items: DiagnosisSelection[]) => {
    setDiagnoses(items);
  }, []);

  const setPrescriptionFeedback = useCallback((items: PrescriptionFeedbackItem[]) => {
    setPrescriptionFeedbackState(items);
  }, []);

  const clearPrescriptionFeedback = useCallback(() => {
    setPrescriptionFeedbackState([]);
  }, []);

  const value = useMemo<MedicalSelectionContextValue>(
    () => ({
      diseases,
      diagnoses,
      prescriptionFeedback,
      addDisease,
      addDiagnosis,
      removeDisease,
      removeDiagnosis,
      clearDiseases,
      clearDiagnoses,
      replaceDiseases,
      replaceDiagnoses,
      setPrescriptionFeedback,
      clearPrescriptionFeedback,
    }),
    [
      diseases,
      diagnoses,
      prescriptionFeedback,
      addDisease,
      addDiagnosis,
      removeDisease,
      removeDiagnosis,
      clearDiseases,
      clearDiagnoses,
      replaceDiseases,
      replaceDiagnoses,
      setPrescriptionFeedback,
      clearPrescriptionFeedback,
    ]
  );

  return <MedicalSelectionContext.Provider value={value}>{children}</MedicalSelectionContext.Provider>;
}

export function useMedicalSelection() {
  const ctx = useContext(MedicalSelectionContext);
  if (!ctx) {
    throw new Error("useMedicalSelection must be used within a MedicalSelectionProvider");
  }
  return ctx;
}


