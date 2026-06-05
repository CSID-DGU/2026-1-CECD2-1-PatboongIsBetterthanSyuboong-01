"use client";

import {
  useState,
  useRef,
  useCallback,
  useEffect,
  type Dispatch,
  type SetStateAction,
} from "react";
import Header from "@/components/Header";
import Sidebar from "@/components/Sidebar";
import ActionBar from "@/components/ActionBar";
import PatientInfoBar, { PatientInfo } from "@/components/PatientInfoBar";
import PatientForm, { PatientFormRef } from "@/components/PatientForm";
import WaitingStatus, { WaitingVisitContext } from "@/components/WaitingStatus";
import MedicalInfo, { MedicalInfoRef } from "@/components/MedicalInfo";
import SpecialNote from "@/components/SpecialNote";
import History from "@/components/History";
import Diagnosis from "@/components/Diagnosis";
import Disease from "@/components/Disease";
import ViewDataBase from "@/components/ViewDataBase";
import AIReport from "@/components/AIReport";
import Calender from "@/components/Calender";
import TimeLine from "@/components/TimeLine";
import { MedicalSelectionProvider, useMedicalSelection } from "@store/medicalSelection";
import { ClinicVisitContext } from "@/types/clinic";
import { Role } from "@/types/user";
import { getMe, getRole } from "@/services/auth";
import styles from "./page.module.css";
import {
  createHistory,
  getHistoryDiseases,
  getHistoryDiagnoses,
} from "@/services/history";
import type { HistoryEntry } from "@/types/history";
import MedicalCertificate from "@/components/MedicalCertificate";
import CertificatePatientSearch, { CertificatePatientInfo } from "@/components/CertificatePatientSearch";
import CertificateList, { CertificateItem } from "@/components/CertificateList";
import CertificateBottom, { type CertificateDiseaseApplyPayload } from "@/components/CertificateBottom";

function formatLocalDate(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/** 진료실 TimeLine은 Provider 안에서만 쓰임 — 내원 더블클릭 시 상병·처방 패널에 반영 */
function ClinicTimelineSection({
  employeeId,
  patientId,
  refreshKey,
  setClinicVisit,
  onPendingHistoryReset,
}: {
  employeeId: number;
  patientId?: number | null;
  refreshKey?: number;
  setClinicVisit: Dispatch<SetStateAction<ClinicVisitContext | null>>;
  onPendingHistoryReset: () => void;
}) {
  const { replaceDiseases, replaceDiagnoses } = useMedicalSelection();

  const handleHistoryDoubleClick = useCallback(
    async (entry: HistoryEntry) => {
      if (!patientId || entry.patientId !== patientId) {
        return;
      }
      try {
        onPendingHistoryReset();
        const [diseaseRows, diagnoseRows] = await Promise.all([
          getHistoryDiseases(entry.id, employeeId),
          getHistoryDiagnoses(entry.id, employeeId),
        ]);
        setClinicVisit((prev) => ({
          patientId: entry.patientId,
          deptId: entry.deptId,
          entryDate: entry.entryDate,
          symptom: entry.symptomDetail ?? "",
          historyId: entry.id,
          visitNumber: prev?.visitNumber,
          waitingId: prev?.waitingId,
        }));
        replaceDiseases(diseaseRows.map((d) => ({ id: d.id, code: d.code, name: d.name })));
        replaceDiagnoses(
          diagnoseRows.map((d) => ({
            id: d.id,
            code: d.code,
            name: d.name,
            dose: d.dose,
            time: d.time,
            days: d.days,
            reason: "",
          }))
        );
      } catch (err) {
        console.error("내원 상병·처방 조회 실패:", err);
        alert("해당 내원의 상병·처방 정보를 불러오지 못했습니다.");
      }
    },
    [
      employeeId,
      patientId,
      replaceDiseases,
      replaceDiagnoses,
      setClinicVisit,
      onPendingHistoryReset,
    ]
  );

  return (
    <TimeLine
      employeeId={employeeId}
      patientId={patientId}
      refreshKey={refreshKey}
      onHistoryEntryDoubleClick={handleHistoryDoubleClick}
    />
  );
}

export default function DashboardPage() {
  const [activeMenu, setActiveMenu] = useState("환자접수");
  const [selectedPatient, setSelectedPatient] = useState<PatientInfo | null>(null);
  const [clinicVisit, setClinicVisit] = useState<ClinicVisitContext | null>(null);
  const historyCreationRef = useRef<Promise<number> | null>(null);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const patientFormRef = useRef<PatientFormRef>(null);
  const medicalInfoRef = useRef<MedicalInfoRef>(null);
  const [userRole, setUserRole] = useState<Role | null>(null);
  const [selectedCertificate, setSelectedCertificate] = useState<CertificateItem | null>(null);
  const [certificatePatient, setCertificatePatient] = useState<CertificatePatientInfo | null>(null);
  const [certificateDiagnosisApply, setCertificateDiagnosisApply] = useState<{
    key: number;
    diseaseCode: string;
    primaryDiseaseName: string;
    additionalDiseaseNames: string;
    historyId: number;
  } | null>(null);

  const envEmployeeId = Number(process.env.NEXT_PUBLIC_EMPLOYEE_ID ?? "1") || 1;
  const [employeeId, setEmployeeId] = useState<number>(envEmployeeId);
  const defaultDeptId = Number(process.env.NEXT_PUBLIC_DEFAULT_DEPT_ID ?? "1") || 1;
  const selectedPatientId = (() => {
    if (!selectedPatient?.patientId) return undefined;
    const parsed = Number(selectedPatient.patientId);
    return Number.isNaN(parsed) ? undefined : parsed;
  })();
  const clinicPatientId = clinicVisit?.patientId ?? selectedPatientId;

  // 메뉴 접근 권한 체크 함수
  const canAccessMenu = useCallback((menuId: string): boolean => {
    if (!userRole) return false;

    if (userRole === Role.SUPER_USER || userRole === Role.DOCTOR) {
      return ["환자접수", "진료실", "진단서"].includes(menuId);
    }
    if (userRole === Role.NURSE || userRole === Role.RECEPTIONIST) {
      return menuId === "환자접수";
    }
    return false;
  }, [userRole]);

  // 사용자 역할 가져오기 및 초기 메뉴 설정
  useEffect(() => {
    const fetchRole = async () => {
      try {
        const [role, me] = await Promise.all([getRole(), getMe()]);
        setUserRole(role);
        if (me?.id && me.id > 0) {
          setEmployeeId(me.id);
        }
        
        const checkAccess = (menuId: string, roleValue: Role): boolean => {
          if (roleValue === Role.SUPER_USER || roleValue === Role.DOCTOR) {
            return ["환자접수", "진료실", "진단서"].includes(menuId);
          }
          if (roleValue === Role.NURSE || roleValue === Role.RECEPTIONIST) {
            return menuId === "환자접수";
          }
          return false;
        };

        if (!checkAccess(activeMenu, role)) {
          const accessibleMenus = ["환자접수", "진료실", "진단서"].filter(menu => checkAccess(menu, role));
          
          if (accessibleMenus.length > 0) {
            setActiveMenu(accessibleMenus[0]);
          }
        }
      } catch (error) {
        console.error("역할을 가져오는데 실패했습니다:", error);
      }
    };
    fetchRole();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ensureHistory = useCallback(async () => {
    if (!clinicVisit) {
      throw new Error("선택된 환자 정보가 없습니다.");
    }

    if (!employeeId || employeeId <= 0) {
      throw new Error("유효한 의료진 ID를 확인할 수 없습니다. 다시 로그인 후 시도해주세요.");
    }

    if (clinicVisit.historyId) {
      return clinicVisit.historyId;
    }

    if (historyCreationRef.current) {
      return historyCreationRef.current;
    }

    const entryDate = clinicVisit.entryDate
      ? clinicVisit.entryDate.slice(0, 10)
      : formatLocalDate(new Date());

    const payload = {
      employeeId,
      patientId: clinicVisit.patientId,
      deptId: clinicVisit.deptId || defaultDeptId,
      symptomDetail: clinicVisit.symptom ?? "",
      memo: clinicVisit.memo ?? "",
      entryDate,
    };

    console.log("히스토리 생성 요청", payload);

    const creationPromise = createHistory(payload)
      .then((history) => {
        console.log("히스토리 생성 성공", history);
        setClinicVisit((prev) => {
          if (!prev || prev.patientId !== history.patientId) {
            return prev;
          }
          return { ...prev, historyId: history.id };
        });
        setHistoryRefreshKey((prev) => prev + 1);
        historyCreationRef.current = null;
        return history.id;
      })
      .catch((error) => {
        console.error("히스토리 생성 실패", error);
        historyCreationRef.current = null;
        throw error;
      });

    historyCreationRef.current = creationPromise;
    return creationPromise;
  }, [clinicVisit, defaultDeptId, employeeId]);

  const resetPendingHistoryCreation = useCallback(() => {
    historyCreationRef.current = null;
  }, []);

  const handleMenuChange = (menuId: string) => {
    if (!canAccessMenu(menuId)) {
      alert("접근 권한이 없습니다.");
      return;
    }
    setActiveMenu(menuId);
  };

  const applyCertificateDiagnosis = useCallback(
    (payload: CertificateDiseaseApplyPayload) => {
      setCertificateDiagnosisApply((prev) => ({
        key: (prev?.key ?? 0) + 1,
        diseaseCode: payload.diseaseCode,
        primaryDiseaseName: payload.primaryDiseaseName,
        additionalDiseaseNames: payload.additionalDiseaseNames,
        historyId: payload.historyId,
      }));
    },
    []
  );

  useEffect(() => {
    setCertificateDiagnosisApply(null);
  }, [certificatePatient?.patientId]);

  const handlePatientSelection = useCallback(
    (patient: PatientInfo | null, visit?: WaitingVisitContext) => {
      setSelectedPatient(patient);

      if (!patient?.patientId) {
        setClinicVisit(null);
        historyCreationRef.current = null;
        return;
      }

      const patientIdNumber = Number(patient.patientId);
      if (Number.isNaN(patientIdNumber)) {
        setClinicVisit(null);
        historyCreationRef.current = null;
        return;
      }

      setClinicVisit({
        patientId: patientIdNumber,
        visitNumber: patient.visitNumber,
        deptId: visit?.deptId ?? defaultDeptId,
        waitingId: visit?.waitingId,
        entryDate: visit?.visitDate ?? visit?.entryDate,
        symptom: visit?.symptom ?? "",
        memo: visit?.memo ?? "",
        historyId: null,
      });
      historyCreationRef.current = null;
    },
    [defaultDeptId]
  );

  // 진료과 이름을 deptId로 변환하는 함수
  const getDeptIdFromDepartment = useCallback((department: string): number => {
    void department;
    return defaultDeptId;
  }, [defaultDeptId]);

  // 환자 등록 핸들러
  const handleRegisterPatient = useCallback(async () => {
    if (!patientFormRef.current || !medicalInfoRef.current) {
      alert("폼 데이터를 불러올 수 없습니다.");
      return;
    }

    const patientData = patientFormRef.current.getFormData();
    const medicalData = medicalInfoRef.current.getFormData();

    // 환자 정보 필수 필드 검증
    if (
      !patientData.name ||
      !patientData.birthDate ||
      !patientData.phone ||
      !patientData.identityNumber ||
      !patientData.visitNumber
    ) {
      alert("환자 정보의 필수 항목(환자명, 생년월일, 연락처, 주민등록번호, 내원번호)을 입력해주세요.");
      return;
    }

    // 진료 정보 필수 필드 검증
    if (
      !medicalData.department ||
      !medicalData.doctor ||
      !medicalData.visitDate ||
      !medicalData.visitTime
    ) {
      alert("진료 정보의 필수 항목(진료과목, 진료의사, 진료일, 접수시간)을 입력해주세요.");
      return;
    }

    try {
      // 1. 환자 등록
      const patientPayload = {
        name: patientData.name,
        phoneNumber: patientData.phone,
        identityNumber: patientData.identityNumber,
        visitNumber: patientData.visitNumber,
        birth: patientData.birthDate,
        gender: patientData.gender,
      };

      console.log("환자 등록 요청 시작:", patientPayload);

      const patientResponse = await fetch(
        "http://localhost:8080/api/patients/get_patient_id",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(patientPayload),
        }
      );

      if (!patientResponse.ok) {
        const errorText = await patientResponse.text();
        console.error("서버 오류 응답:", errorText);
        throw new Error(
          `HTTP error! status: ${patientResponse.status}, message: ${errorText}`
        );
      }

      const patientResult = await patientResponse.json();
      const patientId = patientResult.patientId;
      console.log("환자 등록 성공:", patientResult);

      // 2. 대기 목록 등록
      const deptId = getDeptIdFromDepartment(medicalData.department);
      const waitingData = {
        patientId: patientId,
        deptId: deptId,
        symptom: patientData.symptoms || medicalData.visitReason || "일반 진료",
        state: "waiting",
        department: medicalData.department, // 진료과목
        doctor: medicalData.doctor, // 진료의사
        entryDate: `${medicalData.visitDate} ${medicalData.visitTime}:00`,
        visitTime: medicalData.visitTime, // 접수시간
        visitType: medicalData.visitType, // 초/재진
        visitReason: medicalData.visitReason, // 내원사유
        visitRoute: medicalData.visitRoute, // 내원경로
        treatmentType: medicalData.treatmentType, // 진료유형
        memo: medicalData.memo, // 당일메모
      };

      console.log("대기 목록 등록 시작:", waitingData);

      const waitingResponse = await fetch(
        "http://localhost:8080/api/waiting/register",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(waitingData),
        }
      );

      if (!waitingResponse.ok) {
        const errorText = await waitingResponse.text();
        console.error("대기 등록 오류:", errorText);
        throw new Error(`대기 등록 실패: ${waitingResponse.status} - ${errorText}`);
      }

      const waitingResult = await waitingResponse.json();
      console.log("대기 등록 성공:", waitingResult);

      alert(
        `환자 정보와 진료 정보가 등록되고 대기 목록에 추가되었습니다! (환자 ID: ${patientId})`
      );

      // 폼 초기화
      patientFormRef.current.resetForm();
      medicalInfoRef.current.resetForm();
    } catch (error) {
      console.error("등록 실패:", error);
      alert("등록 중 오류가 발생했습니다. 다시 시도해주세요.");
    }
  }, [getDeptIdFromDepartment]);

  const renderContent = () => {
    if (activeMenu === "환자접수") {
      return (
        <div className={styles.contentGrid}>
          {/* Left Column - Special Notes & History */}
          <div className={styles.leftColumn}>
            <SpecialNote />
            <History
              employeeId={employeeId}
              patientId={selectedPatientId}
              refreshKey={historyRefreshKey}
            />
          </div>

          {/* Middle Column - Patient Form */}
          <div className={styles.middleColumn}>
            <PatientForm ref={patientFormRef} />
          </div>

          {/* Right Column - Waiting Status & Medical Info */}
          <div className={styles.rightColumn}>
            <WaitingStatus
              onPatientSelect={(patient, visit) => handlePatientSelection(patient, visit)}
            />
            <MedicalInfo ref={medicalInfoRef} />
          </div>
        </div>
      );
    } else if (activeMenu === "진료실") {
      return (
        <MedicalSelectionProvider>
          <div className={styles.contentGridClinic}>
            {/* Left Column - Calendar & History */}
            <div className={styles.leftColumn}>
              <Calender employeeId={employeeId} patientId={clinicPatientId} refreshKey={historyRefreshKey} />
              <ClinicTimelineSection
                employeeId={employeeId}
                patientId={clinicPatientId}
                refreshKey={historyRefreshKey}
                setClinicVisit={setClinicVisit}
                onPendingHistoryReset={resetPendingHistoryCreation}
              />
            </div>

            {/* Middle Column - Vertical Layout for Clinic Components */}
            <div className={styles.clinicMiddleColumn}>
              <WaitingStatus
                onPatientSelect={(patient, visit) => handlePatientSelection(patient, visit)}
              />
              <Disease
                clinicVisit={clinicVisit}
                ensureHistory={ensureHistory}
                employeeId={employeeId}
                onHistoryUpdated={() => setHistoryRefreshKey((prev) => prev + 1)}
              />
              <Diagnosis
                clinicVisit={clinicVisit}
                ensureHistory={ensureHistory}
                employeeId={employeeId}
                onHistoryUpdated={() => setHistoryRefreshKey((prev) => prev + 1)}
              />
            </div>

            {/* Right Column - ViewDataBase & AIReport */}
            <div className={styles.clinicRightColumn}>
              <ViewDataBase />
              <AIReport 
                patientId={clinicPatientId}
                employeeId={employeeId}
                deptId={clinicVisit?.deptId ?? defaultDeptId}
                entryDate={clinicVisit?.entryDate ? formatLocalDate(new Date(clinicVisit.entryDate)) : undefined}
              />
            </div>
          </div>
        </MedicalSelectionProvider>
      );
    } else if (activeMenu === "진단서") {
      return (
        <div className={styles.contentGridCertificate}>
          <div className={styles.leftColumn}>
            <CertificatePatientSearch onPatientFound={setCertificatePatient} />
          </div>
          <div className={styles.certificateCenterColumn}>
            <CertificateList
              selected={selectedCertificate}
              onSelect={setSelectedCertificate}
            />
            <CertificateBottom
              patientId={certificatePatient?.patientId}
              employeeId={employeeId}
              onApplyDiagnosisToCertificate={applyCertificateDiagnosis}
            />
          </div>
          <div className={styles.certificateRightColumn}>
            <MedicalCertificate
              selected={selectedCertificate}
              patientInfo={certificatePatient}
              employeeId={employeeId}
              diagnosisApply={certificateDiagnosisApply}
            />
          </div>
        </div>
      );
    }
  };

  return (
    <div className={styles.container}>
      <Header activeMenu={activeMenu} />

      <div className={styles.mainWrapper}>
        <Sidebar 
          activeMenu={activeMenu} 
          onMenuChange={handleMenuChange}
          userRole={userRole}
          canAccessMenu={canAccessMenu}
        />

        <main className={styles.mainContent}>
          <ActionBar 
            onPatientSelect={(patient) => handlePatientSelection(patient, undefined)}
            onRegisterClick={handleRegisterPatient}
          />
          <PatientInfoBar patient={selectedPatient ?? undefined} />

          <div className={styles.contentArea}>{renderContent()}</div>
        </main>
      </div>
    </div>
  );
}
