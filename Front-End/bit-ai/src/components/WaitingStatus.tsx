"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import styles from "./WaitingStatus.module.css";
import { getAccessToken } from "@/lib/auth/token";
import { PatientInfo } from "./PatientInfoBar";

interface WaitingPatient {
  id: number;
  patientId: number;
  deptId: number;
  symptom: string;
  entryDate: string;
  state: string;
  patientName?: string;
  department?: string; // 진료과목
  doctor?: string; // 진료의사
  visitTime?: string; // 접수시간
  visitType?: string; // 초/재진
  visitReason?: string; // 내원사유
  visitRoute?: string; // 내원경로
  treatmentType?: string; // 진료유형
  memo?: string; // 당일메모
}

interface PatientDetail {
  id: number;
  name: string;
  phoneNumber: string;
  identityNumber: string;
  visitNumber?: string;
  birth: string;
  gender: string;
}

export interface WaitingVisitContext {
  waitingId: number;
  patientId: number;
  deptId: number;
  entryDate: string;
  visitDate?: string;
  symptom: string;
  memo?: string;
}

interface WaitingStatusProps {
  onPatientSelect?: (patient: PatientInfo, visit?: WaitingVisitContext) => void;
}

export default function WaitingStatus({ onPatientSelect }: WaitingStatusProps = {}) {
  const [selectedStatus, setSelectedStatus] = useState("waiting");
  const [waitingList, setWaitingList] = useState<WaitingPatient[]>([]);
  const [patientInfoMap, setPatientInfoMap] = useState<Map<number, PatientDetail>>(new Map());
  const [isLoading, setIsLoading] = useState(false);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; waitingId: number } | null>(null);
  const contextMenuRef = useRef<HTMLDivElement>(null);

  // 환자 정보 가져오기
  const fetchPatientInfos = useCallback(async (waitingData: WaitingPatient[]) => {
    const patientIds = [...new Set(waitingData.map(w => w.patientId))];
    const patientMap = new Map<number, PatientDetail>();

    for (const patientId of patientIds) {
      try {
        const response = await fetch(`http://localhost:8080/api/patients/search_patient/${patientId}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          }
        });
        
        if (response.ok) {
          const patientInfo: PatientDetail = await response.json();
          patientMap.set(patientId, patientInfo);
        }
      } catch (error) {
        console.error(`환자 정보 조회 실패 (ID: ${patientId}):`, error);
      }
    }

    setPatientInfoMap(patientMap);
  }, []);

  // 대기 목록 가져오기
  const fetchWaitingList = useCallback(async () => {
    try {
      setIsLoading(true);
      console.log("대기 목록 조회 시작");

      const response = await fetch("http://localhost:8080/api/waiting/get_list");
      
      if (!response.ok) {
        throw new Error(`대기 목록 조회 실패: ${response.status}`);
      }

      const data: WaitingPatient[] = await response.json();
      console.log("대기 목록 조회 성공:", data);
      
      setWaitingList(data);
      
      // 환자 정보도 함께 가져오기
      await fetchPatientInfos(data);
      
    } catch (error) {
      console.error("대기 목록 조회 실패:", error);
    } finally {
      setIsLoading(false);
    }
  }, [fetchPatientInfos]);

  // 컴포넌트 마운트 시 데이터 로드
  useEffect(() => {
    fetchWaitingList();
  }, [fetchWaitingList]);

  // 상태별 환자 수 계산
  const getStatusCounts = () => {
    const counts = {
      waiting: waitingList.filter(p => p.state === "waiting").length,
      hold: waitingList.filter(p => p.state === "hold").length,
      completed: waitingList.filter(p => p.state === "completed").length,
    };
    return counts;
  };

  const statusCounts = getStatusCounts();
  
  const statusData = [
    { status: "진료 대기", count: statusCounts.waiting, type: "waiting", filterStatus: "waiting" },
    { status: "진료 보류", count: statusCounts.hold, type: "hold", filterStatus: "hold" },
    { status: "진료 완료", count: statusCounts.completed, type: "completed", filterStatus: "completed" },
  ];

  const handleStatusClick = (filterStatus: string) => {
    setSelectedStatus(filterStatus);
  };

  // 선택된 상태에 따른 환자 필터링
  const filteredPatients = waitingList.filter(
    (patient) => patient.state === selectedStatus
  );

  // 시간 포맷팅 함수
  const formatTime = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleTimeString("ko-KR", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      });
    } catch {
      return "시간 미상";
    }
  };

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date
        .toLocaleDateString("ko-KR", {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
        })
        .replace(/\./g, "-")
        .replace(/ /g, "")
        .slice(0, -1);
    } catch {
      return "-";
    }
  };

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

  const handlePatientDoubleClick = (waitingPatient: WaitingPatient) => {
    if (!onPatientSelect) return;

    const patientInfo = patientInfoMap.get(waitingPatient.patientId);

    const selectedPatient: PatientInfo = {
      patientId: waitingPatient.patientId.toString(),
      visitNumber: patientInfo?.visitNumber,
      name: patientInfo?.name ?? waitingPatient.patientName,
      age: patientInfo?.birth ? calculateAgeWithMonths(patientInfo.birth) : "-",
      gender: patientInfo?.gender,
      doctor: waitingPatient.doctor || "-",
      date: formatDate(waitingPatient.entryDate),
      time: waitingPatient.visitTime || formatTime(waitingPatient.entryDate),
      address: "-",
      phone: patientInfo?.phoneNumber,
    };

    const visitContext: WaitingVisitContext = {
      waitingId: waitingPatient.id,
      patientId: waitingPatient.patientId,
      deptId: waitingPatient.deptId,
      entryDate: waitingPatient.entryDate,
      visitDate: formatDate(waitingPatient.entryDate),
      symptom: waitingPatient.symptom ?? "",
      memo: waitingPatient.memo ?? "",
    };

    onPatientSelect(selectedPatient, visitContext);
  };

  // 생년월일 포맷팅 함수
  const formatBirthDate = (birthString: string) => {
    try {
      const date = new Date(birthString);
      return date.toLocaleDateString("ko-KR", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).replace(/\./g, '-').replace(/ /g, '').slice(0, -1);
    } catch {
      return "-";
    }
  };


  // 상태별 제목
  const getSectionTitle = () => {
    switch (selectedStatus) {
      case "waiting": return "대기 환자";
      case "hold": return "보류 환자";
      case "completed": return "완료 환자";
      default: return "환자 목록";
    }
  };

  // 컨텍스트 메뉴 열기
  const handleContextMenu = (e: React.MouseEvent, waitingId: number) => {
    e.preventDefault();
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      waitingId,
    });
  };

  // 컨텍스트 메뉴 닫기
  const closeContextMenu = () => {
    setContextMenu(null);
  };

  // 컨텍스트 메뉴 외부 클릭 시 닫기
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (contextMenuRef.current && !contextMenuRef.current.contains(event.target as Node)) {
        closeContextMenu();
      }
    };

    if (contextMenu) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => {
        document.removeEventListener("mousedown", handleClickOutside);
      };
    }
  }, [contextMenu]);

  // 상태 변경 함수
  const updatePatientStatus = async (waitingId: number, newState: "hold" | "completed") => {
    try {
      let apiUrl = "";
      if (newState === "completed") {
        apiUrl = `http://localhost:8080/api/waiting/entry/${waitingId}/complete`;
      } else if (newState === "hold") {
        apiUrl = `http://localhost:8080/api/waiting/entry/${waitingId}/hold`;
      }

      const token = getAccessToken();
      const headers: HeadersInit = {
        "Content-Type": "application/json",
      };

      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const response = await fetch(apiUrl, {
        method: "PUT",
        headers,
      });

      if (!response.ok) {
        throw new Error(`상태 변경 실패: ${response.status}`);
      }

      closeContextMenu();
      // 목록 새로고침
      await fetchWaitingList();
    } catch (error) {
      console.error("상태 변경 실패:", error);
      alert("상태 변경에 실패했습니다.");
    }
  };

  const deleteWaitingEntry = async (waitingId: number) => {
    try {
      const token = getAccessToken();
      const headers: HeadersInit = {
        "Content-Type": "application/json",
      };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const response = await fetch(`http://localhost:8080/api/waiting/entry/${waitingId}`, {
        method: "DELETE",
        headers,
      });

      if (!response.ok) {
        throw new Error(`내원 정보 삭제 실패: ${response.status}`);
      }

      await fetchWaitingList();
    } catch (error) {
      console.error("내원 정보 삭제 실패:", error);
      alert("내원 정보 삭제에 실패했습니다.");
    }
  };

  const handleQuickAction = async (
    waitingId: number,
    currentState: string,
    nextState: "hold" | "completed"
  ) => {
    if (currentState === "completed") {
      alert("이미 진료 완료된 환자입니다.");
      return;
    }
    await updatePatientStatus(waitingId, nextState);
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3>진료 현황</h3>
        <button 
          onClick={fetchWaitingList}
          className={styles.refreshButton}
          disabled={isLoading}
        >
          {isLoading ? "새로고침 중..." : "새로고침"}
        </button>
      </div>
      <div className={styles.content}>
      {/* 상태 요약 */}
      <div className={styles.statusGrid}>
        {statusData.map((item) => (
          <button
            key={item.status}
            onClick={() => handleStatusClick(item.filterStatus)}
            className={`${styles.statusButton} ${styles[item.type]} ${
              selectedStatus === item.filterStatus ? styles.active : ""
            }`}
          >
            <div className={`${styles.statusCount} ${styles[item.type]}`}>
              {item.count}
            </div>
            <div className={styles.statusLabel}>{item.status}</div>
          </button>
        ))}
      </div>

      {/* 환자 목록 테이블 */}
      <div>
        <h4 className={styles.sectionTitle}>
          {getSectionTitle()} ({filteredPatients.length}명)
        </h4>

        {isLoading ? (
          <div className={styles.loadingMessage}>데이터를 불러오는 중...</div>
        ) : (
          <div className={styles.tableContainer}>
            <table className={styles.patientTable}>
              <thead>
                <tr className={styles.tableHeader}>
                  <th>환자 번호</th>
                  <th>접수시간</th>
                  <th>환자명</th>
                  <th>성별</th>
                  <th>생년월일</th>
                  <th>진료과목</th>
                  <th>진료의사</th>
                  <th>처리</th>
                </tr>
              </thead>
              <tbody>
                {filteredPatients.map((patient) => {
                  const patientInfo = patientInfoMap.get(patient.patientId);
                  return (
                    <tr
                      key={patient.id}
                      className={styles.tableRow}
                      onDoubleClick={() => handlePatientDoubleClick(patient)}
                    >
                      <td className={styles.patientNumber}>{patient.patientId}</td>
                      <td className={styles.entryTime}>
                        {patient.visitTime || formatTime(patient.entryDate)}
                      </td>
                      <td 
                        className={styles.patientName}
                        onContextMenu={(e) => handleContextMenu(e, patient.id)}
                        style={{ cursor: "context-menu" }}
                      >
                        {patientInfo?.name || `환자 ${patient.patientId}`}
                      </td>
                      <td className={styles.gender}>
                        {patientInfo?.gender === 'M' ? '남' : patientInfo?.gender === 'F' ? '여' : '-'}
                      </td>
                      <td className={styles.birthDate}>
                        {patientInfo?.birth ? formatBirthDate(patientInfo.birth) : '-'}
                      </td>
                      <td className={styles.department}>
                        {patient.department || '-'}
                      </td>
                      <td className={styles.doctor}>
                        {patient.doctor || '-'}
                      </td>
                      <td className={styles.actionCell}>
                        <div className={styles.actionButtons}>
                          <button
                            type="button"
                            className={styles.holdButton}
                            disabled={patient.state === "completed"}
                            onClick={(e) => {
                              e.stopPropagation();
                              void handleQuickAction(patient.id, patient.state, "hold");
                            }}
                          >
                            보류
                          </button>
                          <button
                            type="button"
                            className={styles.completeButton}
                            disabled={patient.state === "completed"}
                            onClick={(e) => {
                              e.stopPropagation();
                              void handleQuickAction(patient.id, patient.state, "completed");
                            }}
                          >
                            완료
                          </button>
                          <button
                            type="button"
                            className={styles.deleteButton}
                            onClick={(e) => {
                              e.stopPropagation();
                              const ok = window.confirm("이 내원 정보를 삭제하시겠습니까?");
                              if (!ok) return;
                              void deleteWaitingEntry(patient.id);
                            }}
                          >
                            삭제
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {!isLoading && filteredPatients.length === 0 && (
          <div className={styles.emptyMessage}>
            {getSectionTitle()}가 없습니다.
          </div>
        )}
      </div>

      {/* 컨텍스트 메뉴 */}
      {contextMenu && (
        <div
          ref={contextMenuRef}
          className={styles.contextMenu}
          style={{
            position: "fixed",
            left: `${contextMenu.x}px`,
            top: `${contextMenu.y}px`,
            zIndex: 1000,
          }}
        >
          <button
            className={styles.contextMenuItem}
            onClick={() => updatePatientStatus(contextMenu.waitingId, "hold")}
          >
            진료 보류 변경
          </button>
          <button
            className={styles.contextMenuItem}
            onClick={() => updatePatientStatus(contextMenu.waitingId, "completed")}
          >
            진료 완료 변경
          </button>
        </div>
      )}
      </div>
    </div>
  );
}