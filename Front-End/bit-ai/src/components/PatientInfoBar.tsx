"use client";

import styles from "./PatientInfoBar.module.css";

export type PatientInfo = {
  patientId?: string;
  visitNumber?: string;
  name?: string;
  age?: string;
  gender?: string;
  doctor?: string;
  date?: string;
  time?: string;
  address?: string;
  phone?: string;
};

type PatientInfoBarProps = {
  patient?: PatientInfo | null;
};

const safeValue = (value?: string) => (value && value.trim() ? value : "-");

export default function PatientInfoBar({ patient }: PatientInfoBarProps) {
  if (!patient) {
    return null;
  }

  const info = patient;

  return (
    <section className={styles.container} aria-label="환자 기본 정보">
      <ul className={styles.infoList}>
        <li className={styles.infoItem}>
          <span className={styles.label}>환자번호</span>
          <span className={styles.value}>{safeValue(info.patientId)}</span>
        </li>
        <li className={styles.divider} aria-hidden="true">
          |
        </li>
        <li className={styles.infoItem}>
          <span className={styles.label}>내원번호</span>
          <span className={styles.value}>{safeValue(info.visitNumber)}</span>
        </li>
        <li className={styles.divider} aria-hidden="true">
          |
        </li>
        <li className={styles.infoItem}>
          <span className={styles.label}>이름</span>
          <span className={styles.value}>{safeValue(info.name)}</span>
        </li>
        <li className={styles.divider} aria-hidden="true">
          |
        </li>
        <li className={styles.infoItem}>
          <span className={styles.label}>나이</span>
          <span className={styles.value}>{safeValue(info.age)}</span>
        </li>
        <li className={styles.divider} aria-hidden="true">
          |
        </li>
        <li className={styles.infoItem}>
          <span className={styles.label}>성별</span>
          <span className={styles.value}>{safeValue(info.gender)}</span>
        </li>
        <li className={styles.divider} aria-hidden="true">
          |
        </li>
        <li className={styles.infoItem}>
          <span className={styles.label}>담당의</span>
          <span className={styles.value}>{safeValue(info.doctor)}</span>
        </li>
        <li className={styles.divider} aria-hidden="true">
          |
        </li>
        <li className={styles.infoItem}>
          <span className={styles.label}>방문일</span>
          <span className={styles.value}>
            {safeValue(info.date)} {safeValue(info.time)}
          </span>
        </li>
        <li className={styles.divider} aria-hidden="true">
          |
        </li>
        <li className={styles.infoItem}>
          <span className={styles.label}>주소</span>
          <span className={styles.value}>{safeValue(info.address)}</span>
        </li>
        <li className={styles.divider} aria-hidden="true">
          |
        </li>
        <li className={styles.infoItem}>
          <span className={styles.label}>연락처</span>
          <span className={styles.value}>{safeValue(info.phone)}</span>
        </li>
      </ul>
    </section>
  );
}


