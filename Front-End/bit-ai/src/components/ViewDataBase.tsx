"use client";

import { useCallback, useEffect, useMemo, useState, type KeyboardEvent, type UIEvent } from "react";
import { useMedicalSelection } from "@store/medicalSelection";
import { get } from "@/services";
import type { PaginatedResponse } from "@/types/api";
import styles from "./ViewDataBase.module.css";

type ActiveTab = "disease" | "diagnose";

interface DiseaseItem {
  id: number;
  code: string;
  name: string;
}

interface DiagnoseItem extends DiseaseItem {
  dose: number;
  time: number;
  days: number;
}

type ResultItem = DiseaseItem | DiagnoseItem;

const PAGE_SIZE = 50;

export default function ViewDataBase() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("disease");
  const [diseases, setDiseases] = useState<DiseaseItem[]>([]);
  const [diagnoses, setDiagnoses] = useState<DiagnoseItem[]>([]);
  const [diseaseLoading, setDiseaseLoading] = useState(false);
  const [diagnoseLoading, setDiagnoseLoading] = useState(false);
  const [diseaseAppending, setDiseaseAppending] = useState(false);
  const [diagnoseAppending, setDiagnoseAppending] = useState(false);
  const [diseasePage, setDiseasePage] = useState(-1);
  const [diagnosePage, setDiagnosePage] = useState(-1);
  const [diseaseHasMore, setDiseaseHasMore] = useState(true);
  const [diagnoseHasMore, setDiagnoseHasMore] = useState(true);
  const [errors, setErrors] = useState<Record<ActiveTab, string | null>>({
    disease: null,
    diagnose: null,
  });
  /** 검색 입력창 값 */
  const [searchDraft, setSearchDraft] = useState("");
  /** API에 전달 중인 검색어(검색 버튼·Enter 시 반영) */
  const [appliedSearch, setAppliedSearch] = useState("");
  const { addDisease, addDiagnosis } = useMedicalSelection();

  const fetchDiseases = useCallback(async (pageToLoad = 0) => {
    const isInitialLoad = pageToLoad === 0;
    if (isInitialLoad) {
      setDiseaseLoading(true);
    } else {
      setDiseaseAppending(true);
    }
    setErrors((prev) => ({ ...prev, disease: null }));
    try {
      const q = appliedSearch.trim();
      const response = await get<PaginatedResponse<DiseaseItem>>("/api/diseases", {
        params: {
          page: pageToLoad,
          size: PAGE_SIZE,
          ...(q ? { query: q } : {}),
        },
      });
      setDiseases((prev) => (isInitialLoad ? response.items : [...prev, ...response.items]));
      setDiseasePage(response.page);
      const totalLoaded = response.page * response.pageSize + response.items.length;
      setDiseaseHasMore(totalLoaded < response.total);
    } catch (err) {
      console.error("Failed to load diseases", err);
      setErrors((prev) => ({ ...prev, disease: "상병 정보를 불러오지 못했습니다." }));
    } finally {
      if (isInitialLoad) {
        setDiseaseLoading(false);
      } else {
        setDiseaseAppending(false);
      }
    }
  }, [appliedSearch]);

  const fetchDiagnoses = useCallback(async (pageToLoad = 0) => {
    const isInitialLoad = pageToLoad === 0;
    if (isInitialLoad) {
      setDiagnoseLoading(true);
    } else {
      setDiagnoseAppending(true);
    }
    setErrors((prev) => ({ ...prev, diagnose: null }));
    try {
      const q = appliedSearch.trim();
      const response = await get<PaginatedResponse<DiagnoseItem>>("/api/diagnoses", {
        params: {
          page: pageToLoad,
          size: PAGE_SIZE,
          ...(q ? { query: q } : {}),
        },
      });
      setDiagnoses((prev) => (isInitialLoad ? response.items : [...prev, ...response.items]));
      setDiagnosePage(response.page);
      const totalLoaded = response.page * response.pageSize + response.items.length;
      setDiagnoseHasMore(totalLoaded < response.total);
    } catch (err) {
      console.error("Failed to load diagnoses", err);
      setErrors((prev) => ({ ...prev, diagnose: "진단 정보를 불러오지 못했습니다." }));
    } finally {
      if (isInitialLoad) {
        setDiagnoseLoading(false);
      } else {
        setDiagnoseAppending(false);
      }
    }
  }, [appliedSearch]);

  /** 탭 또는 검색어가 바뀌면 현재 탭 목록을 처음부터 다시 조회 */
  useEffect(() => {
    if (activeTab === "disease") {
      void fetchDiseases(0);
    } else {
      void fetchDiagnoses(0);
    }
  }, [activeTab, appliedSearch, fetchDiseases, fetchDiagnoses]);

  const submitSearch = useCallback(() => {
    setAppliedSearch(searchDraft.trim());
  }, [searchDraft]);

  const handleSearchKeyDown = useCallback(
    (event: KeyboardEvent<HTMLInputElement>) => {
      if (event.key === "Enter") {
        event.preventDefault();
        submitSearch();
      }
    },
    [submitSearch]
  );

  const itemsToRender = useMemo<ResultItem[]>(() => {
    if (activeTab === "disease") {
      return diseases;
    }
    return diagnoses;
  }, [activeTab, diseases, diagnoses]);

  const isInitialLoading = activeTab === "disease" ? diseaseLoading : diagnoseLoading;
  const isAppendLoading = activeTab === "disease" ? diseaseAppending : diagnoseAppending;
  const activeHasMore = activeTab === "disease" ? diseaseHasMore : diagnoseHasMore;
  const activeError = errors[activeTab];

  const handleTabChange = (tab: ActiveTab) => {
    if (tab !== activeTab) {
      setActiveTab(tab);
    }
  };

  const handleItemDoubleClick = useCallback(
    (item: ResultItem) => {
      if (activeTab === "disease") {
        addDisease(item as DiseaseItem);
      } else {
        const diagnoseItem = item as DiagnoseItem;
        addDiagnosis({
          ...diagnoseItem,
          dose: diagnoseItem.dose ?? 0,
          time: diagnoseItem.time ?? 0,
          days: diagnoseItem.days ?? 0,
        });
      }
    },
    [activeTab, addDisease, addDiagnosis]
  );

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>, item: ResultItem) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        handleItemDoubleClick(item);
      }
    },
    [handleItemDoubleClick]
  );

  const handleScroll = useCallback(
    (event: UIEvent<HTMLDivElement>) => {
      const { scrollTop, clientHeight, scrollHeight } = event.currentTarget;
      if (scrollHeight - (scrollTop + clientHeight) > 40) {
        return;
      }

      if (activeTab === "disease") {
        if (!diseaseHasMore || diseaseLoading || diseaseAppending) {
          return;
        }
        void fetchDiseases(diseasePage + 1);
      } else {
        if (!diagnoseHasMore || diagnoseLoading || diagnoseAppending) {
          return;
        }
        void fetchDiagnoses(diagnosePage + 1);
      }
    },
    [
      activeTab,
      diseaseHasMore,
      diagnoseHasMore,
      diseaseLoading,
      diagnoseLoading,
      diseaseAppending,
      diagnoseAppending,
      diseasePage,
      diagnosePage,
      fetchDiseases,
      fetchDiagnoses,
    ]
  );

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3>데이터베이스 조회</h3>
      </div>
      <div className={styles.content}>
        <div className={styles.searchSection}>
          <input
            type="text"
            placeholder="코드·상병명·처방명 검색 후 Enter 또는 검색"
            className={styles.searchInput}
            disabled={isInitialLoading}
            value={searchDraft}
            onChange={(e) => setSearchDraft(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            aria-label="데이터베이스 검색어"
          />
          <button
            type="button"
            className={styles.searchButton}
            disabled={isInitialLoading}
            onClick={submitSearch}
          >
            검색
          </button>
        </div>

        <div className={styles.tabSection}>
          <button
            className={`${styles.tab} ${activeTab === "disease" ? styles.active : ""}`}
            onClick={() => handleTabChange("disease")}
            type="button"
            disabled={isInitialLoading && activeTab !== "disease"}
          >
            상병
          </button>
          <button
            className={`${styles.tab} ${activeTab === "diagnose" ? styles.active : ""}`}
            onClick={() => handleTabChange("diagnose")}
            type="button"
            disabled={isInitialLoading && activeTab !== "diagnose"}
          >
            진단
          </button>
        </div>

        <div className={styles.resultSection}>
          {activeError && itemsToRender.length === 0 ? (
            <div className={styles.errorMessage}>{activeError}</div>
          ) : isInitialLoading && itemsToRender.length === 0 ? (
            <div className={styles.loadingMessage}>불러오는 중...</div>
          ) : itemsToRender.length === 0 ? (
            <div className={styles.emptyMessage}>표시할 데이터가 없습니다.</div>
          ) : (
            <div className={styles.resultList} onScroll={handleScroll}>
              {itemsToRender.map((item) => (
                <div
                  key={item.id}
                  className={styles.resultItem}
                  onDoubleClick={() => handleItemDoubleClick(item)}
                  title="더블클릭하거나 Enter 키로 선택 영역에 추가"
                  role="button"
                  tabIndex={0}
                  onKeyDown={(event) => handleKeyDown(event, item)}
                >
                  <div className={styles.resultCode}>{item.code}</div>
                  <div className={styles.resultName}>{item.name}</div>
                </div>
              ))}
              {isAppendLoading ? (
                <div className={styles.appendLoader}>추가 불러오는 중...</div>
              ) : !activeHasMore ? (
                <div className={styles.appendLoader}>마지막 페이지입니다.</div>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

