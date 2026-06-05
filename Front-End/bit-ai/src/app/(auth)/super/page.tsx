"use client";

import { useState, useEffect } from "react";
import { createUser, getAllUsers, setRole } from "@/services/super";
import { User, Role } from "@/types/user";
import styles from "./page.module.css";

export default function SuperPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [updatingRoles, setUpdatingRoles] = useState<Set<number>>(new Set());
  const [newUser, setNewUser] = useState({
    name: "",
    username: "",
    password: "",
    deptId: "1",
    role: Role.DOCTOR,
  });

  useEffect(() => {
    loadUsers();
  }, []);

  async function loadUsers() {
    setLoading(true);
    setError(null);
    try {
      const data = await getAllUsers();
      // 응답이 배열인 경우와 객체인 경우 모두 처리
      const userList = Array.isArray(data) ? data : (data?.users ?? []);
      setUsers(userList);
    } catch (err) {
      const message = err instanceof Error ? err.message : "유저 목록을 불러오는데 실패했습니다";
      setError(message);
      setUsers([]); // 에러 발생 시 빈 배열로 초기화
    } finally {
      setLoading(false);
    }
  }

  async function handleRoleChange(userId: number, newRole: Role) {
    setUpdatingRoles((prev) => new Set(prev).add(userId));
    try {
      await setRole({ id: userId, role: newRole });
      // 성공 시 로컬 상태 업데이트
      setUsers((prevUsers) =>
        prevUsers.map((user) =>
          user.id === userId ? { ...user, role: newRole } : user
        )
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "역할 변경에 실패했습니다";
      setError(message);
    } finally {
      setUpdatingRoles((prev) => {
        const next = new Set(prev);
        next.delete(userId);
        return next;
      });
    }
  }

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    const deptId = Number(newUser.deptId);
    if (!newUser.name.trim() || !newUser.username.trim() || !newUser.password.trim()) {
      setError("이름, 사용자명, 비밀번호를 모두 입력해주세요.");
      return;
    }
    if (!Number.isFinite(deptId) || deptId <= 0) {
      setError("부서 ID는 1 이상의 숫자여야 합니다.");
      return;
    }

    try {
      await createUser({
        name: newUser.name.trim(),
        username: newUser.username.trim(),
        password: newUser.password,
        deptId,
        role: newUser.role,
      });
      setSuccessMessage("직원이 추가되었습니다.");
      setNewUser({
        name: "",
        username: "",
        password: "",
        deptId: "1",
        role: Role.DOCTOR,
      });
      await loadUsers();
    } catch (err) {
      const message = err instanceof Error ? err.message : "직원 추가에 실패했습니다";
      setError(message);
    }
  }

  function getRoleLabel(role: Role): string {
    const roleMap: Record<Role, string> = {
      [Role.DEFAULT]: "일반",
      [Role.SUPER_USER]: "관리자",
      [Role.DOCTOR]: "의사",
      [Role.NURSE]: "간호사",
      [Role.RECEPTIONIST]: "접수원",
    };
    return roleMap[role] || role;
  }

  return (
    <div className={styles.container}>
      <div className={styles.wrapper}>
        {/* 헤더 카드 */}
        <div className={styles.headerCard}>
          <div className={styles.headerContent}>
            <div>
              <h1 className={styles.headerTitle}>전체 유저 조회</h1>
              {!loading && users && users.length > 0 && (
                <p className={styles.headerSubtitle}>
                  총 <strong>{users.length}명</strong>의 유저가 등록되어 있습니다
                </p>
              )}
            </div>
            <button
              onClick={loadUsers}
              disabled={loading}
              className={styles.refreshButton}
            >
              {loading ? "로딩 중..." : "새로고침"}
            </button>
          </div>
        </div>

        {/* 에러 메시지 */}
        {error && (
          <div className={styles.errorMessage} role="alert">
            {error}
          </div>
        )}
        {successMessage && (
          <div className={styles.successMessage} role="status">
            {successMessage}
          </div>
        )}

        <div className={styles.formCard}>
          <h2 className={styles.sectionTitle}>직원 추가</h2>
          <form className={styles.createForm} onSubmit={handleCreateUser}>
            <label className={styles.formField}>
              <span>이름</span>
              <input
                value={newUser.name}
                onChange={(e) => setNewUser((prev) => ({ ...prev, name: e.target.value }))}
                placeholder="홍길동"
                className={styles.formInput}
                required
              />
            </label>
            <label className={styles.formField}>
              <span>사용자명</span>
              <input
                value={newUser.username}
                onChange={(e) => setNewUser((prev) => ({ ...prev, username: e.target.value }))}
                placeholder="doctor01"
                className={styles.formInput}
                required
              />
            </label>
            <label className={styles.formField}>
              <span>비밀번호</span>
              <input
                type="password"
                value={newUser.password}
                onChange={(e) => setNewUser((prev) => ({ ...prev, password: e.target.value }))}
                className={styles.formInput}
                required
              />
            </label>
            <label className={styles.formField}>
              <span>부서 ID</span>
              <input
                type="number"
                min={1}
                value={newUser.deptId}
                onChange={(e) => setNewUser((prev) => ({ ...prev, deptId: e.target.value }))}
                className={styles.formInput}
                required
              />
            </label>
            <label className={styles.formField}>
              <span>역할</span>
              <select
                value={newUser.role}
                onChange={(e) => setNewUser((prev) => ({ ...prev, role: e.target.value as Role }))}
                className={styles.formInput}
              >
                <option value={Role.DOCTOR}>{getRoleLabel(Role.DOCTOR)}</option>
                <option value={Role.NURSE}>{getRoleLabel(Role.NURSE)}</option>
                <option value={Role.RECEPTIONIST}>{getRoleLabel(Role.RECEPTIONIST)}</option>
                <option value={Role.SUPER_USER}>{getRoleLabel(Role.SUPER_USER)}</option>
              </select>
            </label>
            <button type="submit" className={styles.createButton}>
              직원 추가
            </button>
          </form>
        </div>

        {/* 컨텐츠 카드 */}
        <div className={styles.contentCard}>
          {loading ? (
            <div className={styles.loadingContainer}>
              <p className={styles.loadingText}>로딩 중...</p>
            </div>
          ) : !users || users.length === 0 ? (
            <div className={styles.emptyContainer}>
              <p className={styles.emptyTitle}>등록된 유저가 없습니다</p>
            </div>
          ) : (
            <div className={styles.tableWrapper}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th className={styles.tableHeader}>ID</th>
                    <th className={styles.tableHeader}>이름</th>
                    <th className={styles.tableHeader}>사용자명</th>
                    <th className={styles.tableHeader}>역할</th>
                    <th className={styles.tableHeader}>부서 ID</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user, index) => {
                    const rowClass =
                      index % 2 === 0 ? styles.tableRowEven : styles.tableRowOdd;
                    return (
                      <tr
                        key={user.id}
                        className={`${styles.tableRow} ${rowClass}`}
                      >
                        <td className={`${styles.tableCell} ${styles.tableCellId}`}>
                          #{user.id}
                        </td>
                        <td className={`${styles.tableCell} ${styles.tableCellName}`}>
                          {user.name}
                        </td>
                        <td className={`${styles.tableCell} ${styles.tableCellUsername}`}>
                          {user.username}
                        </td>
                        <td className={`${styles.tableCell} ${styles.tableCellRole}`}>
                          <select
                            value={user.role}
                            onChange={(e) => handleRoleChange(user.id, e.target.value as Role)}
                            disabled={updatingRoles.has(user.id)}
                            className={styles.roleSelect}
                          >
                            <option value={Role.DEFAULT}>{getRoleLabel(Role.DEFAULT)}</option>
                            <option value={Role.SUPER_USER}>{getRoleLabel(Role.SUPER_USER)}</option>
                            <option value={Role.DOCTOR}>{getRoleLabel(Role.DOCTOR)}</option>
                            <option value={Role.NURSE}>{getRoleLabel(Role.NURSE)}</option>
                            <option value={Role.RECEPTIONIST}>{getRoleLabel(Role.RECEPTIONIST)}</option>
                          </select>
                        </td>
                        <td className={styles.tableCell}>
                          {user.deptId ? (
                            <span className={styles.deptBadge}>{user.deptId}</span>
                          ) : (
                            <span className={styles.deptEmpty}>-</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


