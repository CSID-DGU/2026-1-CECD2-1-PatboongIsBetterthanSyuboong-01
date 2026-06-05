import { get } from "./http/client";
import type { PaginatedResponse } from "@/types/api";

export interface DiagnoseMasterItem {
  id: number;
  code: string;
  name: string;
  dose: number;
  time: number;
  days: number;
}

export async function fetchDiagnosesPage(
  page = 0,
  size = 1,
  params?: { code?: string }
): Promise<PaginatedResponse<DiagnoseMasterItem>> {
  return get<PaginatedResponse<DiagnoseMasterItem>>("/api/diagnoses", {
    params: { page, size, ...params },
  });
}

/** set_diagnoses 더미 요청용: DB에 존재하는 임의 처방 마스터 id */
export async function fetchFirstDiagnoseMasterId(): Promise<number | null> {
  const res = await fetchDiagnosesPage(0, 1);
  const first = res.items[0];
  return first?.id ?? null;
}

export async function fetchDiagnoseMasterByCode(
  code: string
): Promise<DiagnoseMasterItem | null> {
  const trimmed = code.trim();
  if (!trimmed) return null;
  const res = await fetchDiagnosesPage(0, 1, { code: trimmed });
  return res.items[0] ?? null;
}
