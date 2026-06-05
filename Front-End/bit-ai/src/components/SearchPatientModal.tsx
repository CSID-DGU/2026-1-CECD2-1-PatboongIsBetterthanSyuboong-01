"use client";

import { ReactNode, useState, useEffect } from "react";
import styles from "./SearchPatientModal.module.css";
import { PatientInfo } from "./PatientInfoBar";

interface Patient {
  id: number;
  name: string;
  phoneNumber: string;
  identityNumber: string;
  visitNumber?: string;
  birth: string;
  gender: string;
}

interface SearchPatientModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  onSelectPatient: (patient: PatientInfo) => void;
  children?: ReactNode;
}

type SearchOption = "전체" | "환자명" | "전화번호" | "생년월일" | "주민등록번호" | "환자번호";

export default function SearchPatientModal({ isOpen, onClose, title, onSelectPatient, children }: SearchPatientModalProps) {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [filteredPatients, setFilteredPatients] = useState<Patient[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchOption, setSearchOption] = useState<SearchOption>("전체");
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchAllPatients();
      setSearchQuery(""); // 모달이 열릴 때 검색어 초기화
      setSearchOption("전체"); // 검색 옵션 초기화
    }
  }, [isOpen]);

  useEffect(() => {
    // 검색어가 변경될 때마다 필터링
    if (searchQuery.trim() === "") {
      setFilteredPatients(patients);
    } else {
      const query = searchQuery.toLowerCase().trim();
      const filtered = patients.filter((patient) => {
        // 선택된 옵션에 따라 검색
        switch (searchOption) {
          case "환자명":
            return patient.name.toLowerCase().includes(query);
          
          case "전화번호":
            const phoneNumber = patient.phoneNumber.replace(/-/g, "");
            return phoneNumber.includes(query.replace(/-/g, ""));
          
          case "생년월일":
            const birthDate = formatDate(patient.birth).toLowerCase();
            return birthDate.includes(query);
          
          case "주민등록번호":
            return patient.identityNumber.toLowerCase().includes(query);
          
          case "환자번호":
            return patient.id.toString().includes(query);
          
          case "전체":
          default:
            // 전체 검색: 모든 필드에서 검색
            if (patient.name.toLowerCase().includes(query)) return true;
            const phone = patient.phoneNumber.replace(/-/g, "");
            if (phone.includes(query.replace(/-/g, ""))) return true;
            const birth = formatDate(patient.birth).toLowerCase();
            if (birth.includes(query)) return true;
            if (patient.identityNumber.toLowerCase().includes(query)) return true;
            if (patient.id.toString().includes(query)) return true;
            return false;
        }
      });
      setFilteredPatients(filtered);
    }
  }, [searchQuery, searchOption, patients]);

  const fetchAllPatients = async () => {
    try {
      setIsLoading(true);
      const response = await fetch("http://localhost:8080/api/patients/get_all");
      
      if (!response.ok) {
        throw new Error(`환자 목록 조회 실패: ${response.status}`);
      }

      const data: Patient[] = await response.json();
      setPatients(data);
      setFilteredPatients(data); // 초기에는 모든 환자 표시
    } catch (error) {
      console.error("환자 목록 조회 실패:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString("ko-KR", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).replace(/\./g, '-').replace(/ /g, '').slice(0, -1);
    } catch {
      return dateString;
    }
  };

  // 드롭다운 외부 클릭 시 닫기
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (isDropdownOpen) {
        const target = event.target as HTMLElement;
        if (!target.closest(`.${styles.dropdownContainer}`)) {
          setIsDropdownOpen(false);
        }
      }
    };

    if (isDropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => {
        document.removeEventListener("mousedown", handleClickOutside);
      };
    }
  }, [isDropdownOpen]);

  const calculateAgeWithMonths = (birthString: string) => {
    if (!birthString) return "-";
    const birth = new Date(birthString);
    if (Number.isNaN(birth.getTime())) return "-";

    const today = new Date();
    let years = today.getFullYear() - birth.getFullYear();
    let months = today.getMonth() - birth.getMonth();

    if (today.getDate() < birth.getDate()) {
      months -= 1;
    }

    if (months < 0) {
      years -= 1;
      months += 12;
    }

    const ageText = `${years}세`;
    return months > 0 ? `${ageText} ${months}개월` : ageText;
  };

  const handlePatientSelect = (patient: Patient) => {
    const selectedPatient: PatientInfo = {
      patientId: patient.id?.toString(),
      visitNumber: patient.visitNumber,
      name: patient.name,
      age: calculateAgeWithMonths(patient.birth),
      gender: patient.gender,
      doctor: "-",
      date: "-",
      time: "-",
      address: "-",
      phone: patient.phoneNumber,
    };

    onSelectPatient(selectedPatient);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h3 className={styles.title}>{title}</h3>
          <button className={styles.closeButton} onClick={onClose}>
            ×
          </button>
        </div>
        <div className={styles.content}>
          {/* 검색 입력 필드 */}
          <div className={styles.searchSection}>
            <div className={styles.dropdownContainer}>
              <button
                className={styles.dropdownButton}
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              >
                {searchOption}
                <span className={styles.dropdownArrow}>▼</span>
              </button>
              {isDropdownOpen && (
                <div className={styles.dropdownMenu}>
                  {(["전체", "환자명", "전화번호", "생년월일", "주민등록번호", "환자번호"] as SearchOption[]).map((option) => (
                    <button
                      key={option}
                      className={`${styles.dropdownItem} ${searchOption === option ? styles.dropdownItemActive : ""}`}
                      onClick={() => {
                        setSearchOption(option);
                        setIsDropdownOpen(false);
                      }}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <input
              type="text"
              className={styles.searchInput}
              placeholder={searchOption === "전체" 
                ? "검색어를 입력하세요" 
                : `${searchOption}으로 검색`}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button
                className={styles.clearButton}
                onClick={() => setSearchQuery("")}
              >
                ✕
              </button>
            )}
          </div>

          {isLoading ? (
            <div className={styles.loadingMessage}>환자 목록을 불러오는 중...</div>
          ) : (
            <>
              {searchQuery && (
                <div className={styles.searchResultInfo}>
                  검색 결과: {filteredPatients.length}명
                </div>
              )}
              <div className={styles.tableContainer}>
                <table className={styles.patientTable}>
                  <thead>
                    <tr className={styles.tableHeader}>
                      <th>최근내원일</th>
                      <th>환자명</th>
                      <th>성별</th>
                      <th>생년월일</th>
                      <th>전화번호</th>
                      <th>진료과</th>
                      <th>담당의사</th>
                      <th>환자 번호</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPatients.length === 0 ? (
                      <tr>
                        <td colSpan={8} className={styles.emptyMessage}>
                          {searchQuery ? "검색 결과가 없습니다." : "등록된 환자가 없습니다."}
                        </td>
                      </tr>
                    ) : (
                      filteredPatients.map((patient) => (
                        <tr
                          key={patient.id}
                          className={styles.tableRow}
                          onClick={() => handlePatientSelect(patient)}
                        >
                          <td className={styles.entryTime}>-</td> {/* 최근내원일 */}
                          <td className={styles.patientName}>{patient.name}</td>
                          <td className={styles.gender}>
                            {patient.gender === 'M' ? '남' : patient.gender === 'F' ? '여' : '-'}
                          </td>
                          <td className={styles.birthDate}>{formatDate(patient.birth)}</td>
                          <td className={styles.phoneNumber}>{patient.phoneNumber}</td>
                          <td className={styles.department}>-</td>
                          <td className={styles.docter}>-</td>
                          <td className={styles.patientNumber}>{patient.id}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {children}
        </div>
      </div>
    </div>
  );
}

