"use client";

import { useState, useRef } from "react";
import styles from "./AIReport.module.css";
import { PredictedDisease, uploadAndAnalyzeImage, XrayView } from "@/services/radiology";

const EXCLUDED_DISEASE_TAGS = new Set(["no_finding", "support_devices"]);
const MAX_VISIBLE_DISEASES = 3;

interface AIReportProps {
  patientId?: number;
  employeeId?: number;
  deptId?: number;
  entryDate?: string; // yyyy-MM-dd 형식
}

function getVisiblePredictedDiseases(diseases: PredictedDisease[] | undefined): PredictedDisease[] {
  return (diseases || [])
    .filter((item) => item.disease && !EXCLUDED_DISEASE_TAGS.has(item.disease.toLowerCase()))
    .sort((a, b) => b.score - a.score)
    .slice(0, MAX_VISIBLE_DISEASES);
}

export default function AIReport({
  patientId,
  employeeId,
  deptId,
  entryDate,
}: AIReportProps) {
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const [resultImage, setResultImage] = useState<string | null>(null);
  const [predictedDiseases, setPredictedDiseases] = useState<PredictedDisease[]>([]);
  const [warning, setWarning] = useState<string | null>(null);
  const [view, setView] = useState<XrayView>("PA");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const selectedFileRef = useRef<File | null>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // 이미지 파일인지 확인
      if (!file.type.startsWith("image/")) {
        alert("이미지 파일만 업로드 가능합니다.");
        return;
      }

      // 파일 객체 저장
      selectedFileRef.current = file;

      // FileReader를 사용하여 이미지 미리보기 생성
      const reader = new FileReader();
      reader.onloadend = () => {
        setUploadedImage(reader.result as string);
      };
      reader.readAsDataURL(file);
      
      // 에러 초기화
      setError(null);
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleRemoveImage = () => {
    setUploadedImage(null);
    setResultImage(null);
    setPredictedDiseases([]);
    setWarning(null);
    setError(null);
    selectedFileRef.current = null;
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleAnalyze = async () => {
    if (!uploadedImage || !selectedFileRef.current) {
      alert("이미지를 먼저 업로드해주세요.");
      return;
    }

    // 필수 파라미터 확인
    if (!patientId || !employeeId || !deptId || !entryDate) {
      alert("환자 정보가 없습니다. 진료실에서 환자를 선택해주세요.");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const file = selectedFileRef.current;
      const response = await uploadAndAnalyzeImage(
        file,
        patientId,
        employeeId,
        deptId,
        entryDate,
        view
      );

      setResultImage(response.heatmapUrl || uploadedImage);
      setPredictedDiseases(getVisiblePredictedDiseases(response.predictedDiseases));
      setWarning(response.warning || null);
    } catch (err: unknown) {
      console.error("AI 분석 오류:", err);
      const apiError = err as { response?: { data?: { error?: string } }; message?: string };
      const errorMessage =
        apiError.response?.data?.error ||
        apiError.message ||
        "AI 분석 중 오류가 발생했습니다.";
      setError(errorMessage);
      alert(`AI 분석 실패: ${errorMessage}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3>AI 리포트</h3>
      </div>
      <div className={styles.content}>
        {/* 업로드된 이미지 표시 영역 */}
        <div className={styles.imageSection}>
          {uploadedImage ? (
            <div className={styles.imageContainer}>
              <img 
                src={uploadedImage} 
                alt="업로드된 이미지" 
                className={styles.uploadedImage}
              />
              <button 
                className={styles.removeButton}
                onClick={handleRemoveImage}
                aria-label="이미지 제거"
              >
                ×
              </button>
            </div>
          ) : (
            <div className={styles.imagePlaceholder}>
              <p>이미지를 업로드하거나 선택하세요</p>
            </div>
          )}
        </div>
        
        <div className={styles.controlSection}>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept="image/*"
            style={{ display: "none" }}
          />
          <button 
            className={styles.uploadButton}
            onClick={handleUploadClick}
          >
            이미지 업로드
          </button>
          <select
            className={styles.viewSelect}
            value={view}
            onChange={(event) => setView(event.target.value as XrayView)}
            aria-label="X-ray 촬영 방향"
          >
            <option value="PA">PA</option>
            <option value="AP">AP</option>
          </select>
          <button 
            className={styles.analyzeButton}
            disabled={!uploadedImage || isLoading}
            onClick={handleAnalyze}
          >
            {isLoading ? "분석 중..." : "AI 분석"}
          </button>
        </div>

        {/* 결과 이미지 표시 영역 */}
        {resultImage && (
          <div className={styles.resultImageSection}>
            <div className={styles.imageContainer}>
              <img 
                src={resultImage} 
                alt="분석 결과 이미지" 
                className={styles.uploadedImage}
              />
            </div>
          </div>
        )}

        {/* 분석 결과 텍스트 영역 */}
        {(predictedDiseases.length > 0 || warning) && (
          <div className={styles.resultTextSection}>
            <div className={styles.resultContent}>
              <span className={styles.resultLabel}>추론된 상병:</span>
              {predictedDiseases.length > 0 ? (
                <ul className={styles.predictionList}>
                  {predictedDiseases.map((item, index) => (
                    <li key={`${item.disease}-${index}`} className={styles.predictionItem}>
                      <div className={styles.predictionHeader}>
                        <span className={styles.resultValue}>{item.disease}</span>
                        <span className={styles.score}>{item.score.toFixed(3)}</span>
                      </div>
                      <p className={styles.reason}>{item.reason}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <span className={styles.normal}>추론된 상병 없음</span>
              )}
              {warning && <p className={styles.warning}>{warning}</p>}
            </div>
          </div>
        )}

        {/* 에러 메시지 표시 */}
        {error && (
          <div className={styles.errorMessage}>
            <p>{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}

