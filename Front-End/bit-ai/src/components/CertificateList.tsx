"use client";

import styles from "./CertificateList.module.css";

export type CertificateType = "general" | "military";

export interface CertificateItem {
  id: number;
  type: CertificateType;
  label: string;
  pdfPath: string;
  patientNumber: string;
  patientName: string;
  age: number;
  department: string;
  doctor: string;
  issueDate: string;
}

interface CertificateListProps {
  selected: CertificateItem | null;
  onSelect: (item: CertificateItem) => void;
}

// TODO: API 연동 시 환자별 진단서 목록으로 교체
const MOCK_CERTIFICATES: CertificateItem[] = [
  {
    id: 1,
    type: "general",
    label: "일반 진단서",
    pdfPath: "/certificates/general.pdf",
    patientNumber: "-",
    patientName: "-",
    age: 0,
    department: "-",
    doctor: "-",
    issueDate: "-",
  },
  {
    id: 2,
    type: "military",
    label: "병무용 진단서",
    pdfPath: "/certificates/military.pdf",
    patientNumber: "-",
    patientName: "-",
    age: 0,
    department: "-",
    doctor: "-",
    issueDate: "-",
  },
];

export default function CertificateList({ selected, onSelect }: CertificateListProps) {
  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3 className={styles.title}>진단서 목록</h3>
        <span className={styles.count}>{MOCK_CERTIFICATES.length}건</span>
      </div>

      <div className={styles.body}>
        <div className={styles.listContainer}>
          {MOCK_CERTIFICATES.map((item) => (
            <div
              key={item.id}
              className={`${styles.listItem} ${selected?.id === item.id ? styles.selectedItem : ""}`}
              onClick={() => onSelect(item)}
            >
              <span className={styles.itemLabel}>{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
