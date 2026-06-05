"use client";

import { useEffect, useState, forwardRef, useImperativeHandle } from "react";
import { getDoctors, type DoctorProfile } from "@/services/auth";
import styles from "./MedicalInfo.module.css";

export type MedicalInfoFormData = {
  department: string;
  doctor: string;
  visitDate: string;
  visitTime: string;
  visitType: string;
  visitReason: string;
  visitRoute: string;
  treatmentType: string;
  memo: string;
};

export interface MedicalInfoRef {
  getFormData: () => MedicalInfoFormData;
  resetForm: () => void;
}

const MedicalInfo = forwardRef<MedicalInfoRef>((props, ref) => {
  const getToday = () => new Date().toISOString().slice(0, 10);
  const getCurrentTime = () => {
    const now = new Date();
    return `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  };
  const [formData, setFormData] = useState<MedicalInfoFormData>({
    department: "검진",
    doctor: "",
    visitDate: getToday(),
    visitTime: getCurrentTime(),
    visitType: "재진",
    visitReason: "",
    visitRoute: "",
    treatmentType: "",
    memo: "",
  });
  const [doctors, setDoctors] = useState<DoctorProfile[]>([]);

  useEffect(() => {
    let ignore = false;
    async function loadDoctors() {
      try {
        const rows = await getDoctors();
        if (ignore) return;
        setDoctors(rows);
        setFormData((prev) => ({
          ...prev,
          doctor: prev.doctor || rows[0]?.name || "",
        }));
      } catch (error) {
        console.error("진료의사 목록 조회 실패", error);
      }
    }
    void loadDoctors();
    return () => {
      ignore = true;
    };
  }, []);

  const handleInputChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >
  ) => {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  const resetForm = () => {
    setFormData({
      department: "검진",
      doctor: doctors[0]?.name || "",
      visitDate: getToday(),
      visitTime: getCurrentTime(),
      visitType: "재진",
      visitReason: "",
      visitRoute: "",
      treatmentType: "",
      memo: "",
    });
  };

  useImperativeHandle(ref, () => ({
    getFormData: () => formData,
    resetForm,
  }));

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3>진료정보</h3>
      </div>
      <div className={styles.content}>
        <form className={styles.form}>
        <div className={styles.row}>
          <div className={styles.field}>
            <label className={styles.label}>
              <span className={styles.required}>*</span>진료과목
            </label>
            <select
              name="department"
              value={formData.department}
              onChange={handleInputChange}
              className={styles.select}
            >
              <option value="검진">검진</option>
              <option value="내과">내과</option>
              <option value="정형외과">정형외과</option>
            </select>
          </div>

          <div className={styles.field}>
            <label className={styles.label}>
              <span className={styles.required}>*</span>진료의사
            </label>
            <select
              name="doctor"
              value={formData.doctor}
              onChange={handleInputChange}
              className={styles.select}
            >
              {doctors.length === 0 ? (
                <option value="">등록된 의사 없음</option>
              ) : (
                doctors.map((doctor) => (
                  <option key={doctor.id} value={doctor.name}>
                    {doctor.name}
                  </option>
                ))
              )}
            </select>
          </div>
        </div>

        <div className={styles.row}>
          <div className={styles.field}>
            <label className={styles.label}>
              <span className={styles.required}>*</span>진료일
            </label>
            <input
              type="date"
              name="visitDate"
              value={formData.visitDate}
              onChange={handleInputChange}
              className={styles.input}
            />
          </div>

          <div className={styles.field}>
            <label className={styles.label}>
              <span className={styles.required}>*</span>접수시간
            </label>
            <input
              type="time"
              name="visitTime"
              value={formData.visitTime}
              onChange={handleInputChange}
              className={styles.input}
            />
          </div>
        </div>

        <div className={styles.row}>
          <div className={styles.field}>
            <label className={styles.label}>초/재진</label>
            <select
              name="visitType"
              value={formData.visitType}
              onChange={handleInputChange}
              className={styles.select}
            >
              <option value="재진">재진</option>
              <option value="초진">초진</option>
            </select>
          </div>

          <div className={styles.field}>
            <label className={styles.label}>내원사유</label>
            <input
              type="text"
              name="visitReason"
              value={formData.visitReason}
              onChange={handleInputChange}
              className={styles.input}
            />
          </div>
        </div>

        <div className={styles.row}>
          <div className={styles.field}>
            <label className={styles.label}>내원경로</label>
            <select
              name="visitRoute"
              value={formData.visitRoute}
              onChange={handleInputChange}
              className={styles.select}
            >
              <option value="">선택</option>
              <option value="직접내원">직접내원</option>
              <option value="타병원의뢰">타병원의뢰</option>
            </select>
          </div>

          <div className={styles.field}>
            <label className={styles.label}>진료유형</label>
            <select
              name="treatmentType"
              value={formData.treatmentType}
              onChange={handleInputChange}
              className={styles.select}
            >
              <option value="">선택</option>
              <option value="일반진료">일반진료</option>
              <option value="응급진료">응급진료</option>
            </select>
          </div>
        </div>

        <div className={styles.fullWidth}>
          <label className={styles.label}>당일메모</label>
          <textarea
            name="memo"
            value={formData.memo}
            onChange={handleInputChange}
            className={styles.textarea}
            rows={4}
          />
        </div>
      </form>
      </div>
    </div>
  );
});

MedicalInfo.displayName = "MedicalInfo";

export default MedicalInfo;
