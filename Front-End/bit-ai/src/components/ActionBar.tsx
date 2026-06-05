"use client";

import { useState } from "react";
import styles from "./ActionBar.module.css";
import SearchPatientModal from "./SearchPatientModal";
import { PatientInfo } from "./PatientInfoBar";

type ActionBarProps = {
  onPatientSelect: (patient: PatientInfo, visit?: unknown) => void;
  onRegisterClick?: () => void;
};

export default function ActionBar({ onPatientSelect, onRegisterClick }: ActionBarProps) {
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);

  const today = new Date().toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });

  const handleSearchClick = () => {
    setIsSearchModalOpen(true);
  };

  const closeSearchModal = () => {
    setIsSearchModalOpen(false);
  };

  return (
    <>
      <div className={styles.actionBar}>
        <div className={styles.leftSection}>
          <span className={styles.date}>{today}</span>
        </div>

        <div className={styles.rightSection}>
          <button
            className={`${styles.button} ${styles.registerButton}`}
            onClick={onRegisterClick}
          >
            환자 등록
          </button>
          <button
            className={`${styles.button} ${styles.searchButton}`}
            onClick={handleSearchClick}
          >
            환자 조회
          </button>
        </div>
      </div>

      <SearchPatientModal
        isOpen={isSearchModalOpen}
        onClose={closeSearchModal}
        title="환자 조회"
        onSelectPatient={(patient) => {
          onPatientSelect(patient);
        }}
      />
    </>
  );
}
