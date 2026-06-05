"use client";

import { useEffect, useState } from "react";
import styles from "./Calender.module.css";
import { getPatientHistories } from "@/services/history";
import type { HistoryEntry } from "@/types/history";

type CalenderProps = {
  employeeId: number;
  patientId?: number | null;
  refreshKey?: number;
};

function formatLocalDate(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function toDateKey(value: string | Date | null | undefined) {
  if (!value) return null;
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return formatLocalDate(date);
}

export default function Calender({ employeeId, patientId, refreshKey }: CalenderProps) {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [historyDateSet, setHistoryDateSet] = useState<Set<string>>(() => new Set());

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  // 이전 달로 이동
  const goToPreviousMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1));
  };

  // 다음 달로 이동
  const goToNextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1));
  };

  // 오늘로 이동
  const goToToday = () => {
    const today = new Date();
    setCurrentDate(today);
    setSelectedDate(today);
  };

  // 날짜 선택
  const handleDateClick = (date: Date) => {
    setSelectedDate(date);
  };

  // 달력 그리드 생성
  const getCalendarDays = () => {
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startDate = new Date(firstDay);
    startDate.setDate(startDate.getDate() - firstDay.getDay()); // 주의 시작일로 조정

    const days: Date[] = [];
    const current = new Date(startDate);

    // 6주 * 7일 = 42일
    for (let i = 0; i < 42; i++) {
      days.push(new Date(current));
      current.setDate(current.getDate() + 1);
    }

    return days;
  };

  const calendarDays = getCalendarDays();
  const today = new Date();
  const isToday = (date: Date) => {
    return (
      date.getDate() === today.getDate() &&
      date.getMonth() === today.getMonth() &&
      date.getFullYear() === today.getFullYear()
    );
  };

  const isSelected = (date: Date) => {
    if (!selectedDate) return false;
    return (
      date.getDate() === selectedDate.getDate() &&
      date.getMonth() === selectedDate.getMonth() &&
      date.getFullYear() === selectedDate.getFullYear()
    );
  };

  const isCurrentMonth = (date: Date) => {
    return date.getMonth() === month;
  };

  const getDayOfWeek = (dayIndex: number) => {
    const days = ["일", "월", "화", "수", "목", "금", "토"];
    return days[dayIndex];
  };

  const formatMonthYear = () => `${year}년 ${month + 1}월`;

  useEffect(() => {
    if (!patientId) {
      setHistoryDateSet(new Set());
      setSelectedDate(null);
      return;
    }

    const endDate = new Date();
    const startDate = new Date(endDate);
    startDate.setFullYear(startDate.getFullYear() - 5);

    const startDateStr = formatLocalDate(startDate);
    const endDateStr = formatLocalDate(endDate);

    getPatientHistories(employeeId, patientId, startDateStr, endDateStr)
      .then((res) => {
        const histories = Array.isArray(res.histories) ? res.histories : [];
        const nextSet = new Set<string>();
        histories.forEach((history: HistoryEntry) => {
          const key = toDateKey(history.entryDate);
          if (key) {
            nextSet.add(key);
          }
        });
        setHistoryDateSet(nextSet);
      })
      .catch((error) => {
        console.error("캘린더 히스토리 조회 실패:", error);
        setHistoryDateSet(new Set());
      });
  }, [employeeId, patientId, refreshKey]);

  useEffect(() => {
    if (!patientId || historyDateSet.size === 0) {
      return;
    }
    const latest = [...historyDateSet]
      .map((key) => new Date(key))
      .filter((date) => !Number.isNaN(date.getTime()))
      .sort((a, b) => b.getTime() - a.getTime())[0];

    if (latest) {
      setSelectedDate(latest);
      setCurrentDate(new Date(latest.getFullYear(), latest.getMonth(), 1));
    }
  }, [historyDateSet, patientId]);

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <button className={styles.navButton} onClick={goToPreviousMonth}>
          ←
        </button>
        <div className={styles.monthYear}>{formatMonthYear()}</div>
        <div className={styles.headerRight}>
          <button className={styles.todayButton} onClick={goToToday}>
            오늘
          </button>
          <button className={styles.navButton} onClick={goToNextMonth}>
            →
          </button>
        </div>
      </div>

      <div className={styles.weekdays}>
        {[0, 1, 2, 3, 4, 5, 6].map((dayIndex) => (
          <div
            key={dayIndex}
            className={`${styles.weekday} ${
              dayIndex === 0
                ? styles.sunday
                : dayIndex === 6
                ? styles.saturday
                : ""
            }`}
          >
            {getDayOfWeek(dayIndex)}
          </div>
        ))}
      </div>

      <div className={styles.daysGrid}>
        {calendarDays.map((date, index) => {
          const dayOfWeek = date.getDay();
          const dateKey = toDateKey(date);
          const hasHistory = dateKey ? historyDateSet.has(dateKey) : false;
          const isCurrent = isCurrentMonth(date);
          const isTodayDate = isToday(date);
          const isSelectedDate = isSelected(date);

          return (
            <button
              key={index}
              className={`${styles.day} ${
                !isCurrent ? styles.otherMonth : ""
              } ${dayOfWeek === 0 ? styles.sunday : ""} ${
                dayOfWeek === 6 ? styles.saturday : ""
              } ${isTodayDate ? styles.today : ""} ${
                isSelectedDate ? styles.selected : ""
              } ${
                hasHistory ? styles.hasHistory : ""
              }`}
              onClick={() => handleDateClick(date)}
            >
              {date.getDate().toString().padStart(2, "0")}
            </button>
          );
        })}
      </div>
    </div>
  );
}

