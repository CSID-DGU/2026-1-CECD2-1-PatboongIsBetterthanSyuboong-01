export interface ClinicVisitContext {
  patientId: number;
  visitNumber?: string;
  deptId: number;
  waitingId?: number;
  entryDate?: string;
  symptom?: string | null;
  memo?: string | null;
  historyId?: number | null;
}








