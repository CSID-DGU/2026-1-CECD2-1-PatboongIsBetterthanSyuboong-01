"use client";

import { useState, forwardRef, useImperativeHandle } from "react";
import styles from "./PatientForm.module.css";

interface PatientData {
  name: string;
  phoneNumber: string;
  identityNumber: string;
  visitNumber: string;
  birth: string;
  gender: string;
}

export type PatientFormData = {
  name: string;
  birthDate: string;
  phone: string;
  identityNumber: string;
  visitNumber: string;
  gender: string;
  address: string;
  symptoms: string;
  notes: string;
};

export interface PatientFormRef {
  getFormData: () => PatientFormData;
  submitPatientData: (customMessage?: string) => Promise<void>;
  resetForm: () => void;
}

const PatientForm = forwardRef<PatientFormRef>((props, ref) => {
  const [formData, setFormData] = useState<PatientFormData>({
    name: "",
    birthDate: "",
    phone: "",
    identityNumber: "",
    visitNumber: "",
    gender: "M",
    address: "",
    symptoms: "",
    notes: "",
  });

  const [isLoading, setIsLoading] = useState(false);

  useImperativeHandle(ref, () => ({
    getFormData: () => formData,
    submitPatientData,
    resetForm,
  }));

  const handleChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
    >
  ) => {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  const createPatient = async (
    patientData: PatientData
  ): Promise<number | null> => {
    try {
      console.log("환자 등록 요청 시작:", patientData);

      const response = await fetch(
        "http://localhost:8080/api/patients/get_patient_id",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(patientData),
        }
      );

      console.log("응답 상태:", response.status);

      if (!response.ok) {
        const errorText = await response.text();
        console.error("서버 오류 응답:", errorText);
        throw new Error(
          `HTTP error! status: ${response.status}, message: ${errorText}`
        );
      }

      const result = await response.json();
      console.log("환자 등록 성공:", result);
      return result.patientId;
    } catch (error) {
      console.error("환자 등록 실패:", error);
      throw error;
    }
  };

  // 폼 초기화 함수
  const resetForm = () => {
    setFormData({
      name: "",
      birthDate: "",
      phone: "",
      identityNumber: "",
      visitNumber: "",
      gender: "M",
      address: "",
      symptoms: "",
      notes: "",
    });
  };

  // 대기 목록 등록 함수
  const registerWaiting = async (patientId: number) => {
    try {
      console.log("대기 목록 등록 시작:", patientId);

      const waitingData = {
        patientId: patientId,
        deptId: 1, // 기본 진료과 ID
        symptom: formData.symptoms || "일반 진료",
        state: "waiting"
      };

      const response = await fetch("http://localhost:8080/api/waiting/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(waitingData),
      });

      console.log("대기 등록 응답 상태:", response.status);

      if (!response.ok) {
        const errorText = await response.text();
        console.error("대기 등록 오류:", errorText);
        console.error("요청 데이터:", waitingData);
        throw new Error(`대기 등록 실패: ${response.status} - ${errorText}`);
      }

      const result = await response.json();
      console.log("대기 등록 성공:", result);
      return result;
    } catch (error) {
      console.error("대기 등록 실패:", error);
      throw error;
    }
  };

  // 환자 등록 로직
  const submitPatientData = async (customMessage?: string) => {
    if (
      !formData.name ||
      !formData.birthDate ||
      !formData.phone ||
      !formData.identityNumber ||
      !formData.visitNumber
    ) {
      alert(
        "필수 정보(환자명, 생년월일, 연락처, 주민등록번호, 내원번호)를 입력해주세요."
      );
      return;
    }

    setIsLoading(true);

    try {
      const patientData: PatientData = {
        name: formData.name,
        phoneNumber: formData.phone,
        identityNumber: formData.identityNumber,
        visitNumber: formData.visitNumber,
        birth: formData.birthDate,
        gender: formData.gender,
      };

      // 환자 등록
      const patientId = await createPatient(patientData);

      if (patientId) {
        // 대기 목록 등록
        try {
          await registerWaiting(patientId);
          const message = customMessage || `환자 정보가 등록되고 대기 목록에 추가되었습니다! (환자 ID: ${patientId})`;
          alert(message);
        } catch {
          // 환자는 등록되었지만 대기 목록 등록 실패
          const message = `환자 정보는 등록되었습니다 (환자 ID: ${patientId})\n하지만 대기 목록 등록에 실패했습니다.`;
          alert(message);
        }
        resetForm();
      }
    } catch {
      alert("환자 등록 중 오류가 발생했습니다. 다시 시도해주세요.");
    } finally {
      setIsLoading(false);
    }
  };




  const fillSampleData = () => {
    setFormData({
      name: "김철수",
      birthDate: "1990-01-01",
      phone: "010-1234-5678",
      identityNumber: "900101-1234567",
      visitNumber: "530524502",
      gender: "M",
      address: "서울시 강남구 테헤란로 123",
      symptoms: "E11",
      notes: "테스트용 환자 데이터 (상병 E11)",
    });
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3>환자 정보 입력</h3>
        <button
          type="button"
          onClick={fillSampleData}
          className={styles.sampleButton}
        >
          샘플 데이터
        </button>
      </div>
      <div className={styles.content}>
        <form className={styles.form}>
        <div className={styles.row}>
          <label className={styles.field}>
            <span className={styles.label}>환자명 *</span>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              className={styles.input}
              required
            />
          </label>

          <label className={styles.field}>
            <span className={styles.label}>생년월일 *</span>
            <input
              type="date"
              name="birthDate"
              value={formData.birthDate}
              onChange={handleChange}
              className={styles.input}
              required
            />
          </label>
        </div>

        <div className={styles.row}>
          <label className={styles.field}>
            <span className={styles.label}>연락처 *</span>
            <input
              type="tel"
              name="phone"
              value={formData.phone}
              onChange={handleChange}
              placeholder="010-0000-0000"
              className={styles.input}
              required
            />
          </label>

          <label className={styles.field}>
            <span className={styles.label}>성별 *</span>
            <select
              name="gender"
              value={formData.gender}
              onChange={handleChange}
              className={styles.input}
              required
            >
              <option value="M">남성</option>
              <option value="F">여성</option>
            </select>
          </label>
        </div>

        <label className={styles.field}>
          <span className={styles.label}>주민등록번호 *</span>
          <input
            type="text"
            name="identityNumber"
            value={formData.identityNumber}
            onChange={handleChange}
            placeholder="000000-0000000"
            className={styles.input}
            required
          />
        </label>

        <label className={styles.field}>
          <span className={styles.label}>내원번호 *</span>
          <input
            type="text"
            name="visitNumber"
            value={formData.visitNumber}
            onChange={handleChange}
            placeholder="예: 530524502"
            className={styles.input}
            required
          />
        </label>

        <label className={styles.field}>
          <span className={styles.label}>주소</span>
          <input
            type="text"
            name="address"
            value={formData.address}
            onChange={handleChange}
            className={styles.input}
          />
        </label>

        <label className={styles.field}>
          <span className={styles.label}>증상</span>
          <textarea
            name="symptoms"
            value={formData.symptoms}
            onChange={handleChange}
            rows={3}
            className={styles.textarea}
          />
        </label>

      </form>
      </div>
    </div>
  );
});

PatientForm.displayName = "PatientForm";

export default PatientForm;