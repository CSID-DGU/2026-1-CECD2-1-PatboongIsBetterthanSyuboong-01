"use client";

import { Role } from "@/types/user";
import styles from "./Sidebar.module.css";

interface SidebarProps {
  activeMenu: string;
  onMenuChange: (menuId: string) => void;
  userRole: Role | null;
  canAccessMenu: (menuId: string) => boolean;
}

export default function Sidebar({ activeMenu, onMenuChange, userRole, canAccessMenu }: SidebarProps) {
  const menuItems = [
    { id: "환자접수", label: "환자 접수", shortLabel: "접수"},
    { id: "진료실", label: "진료실", shortLabel: "진료"},
    { id: "진단서", label: "진단서", shortLabel: "진단서"},
  ];

  return (
    <aside className={styles.sidebar}>
      <nav>
        {menuItems.map((item) => {
          const hasAccess = canAccessMenu(item.id);
          return (
            <button
              key={item.id}
              onClick={() => onMenuChange(item.id)}
              disabled={!hasAccess}
              className={`${styles.menuItem} ${activeMenu === item.id ? styles.active : ""} ${!hasAccess ? styles.disabled : ""}`}
              title={hasAccess ? item.label : "접근 권한이 없습니다"}
            >
              <span className={styles.fullLabel}>{item.label}</span>
              <span className={styles.shortLabel}>{item.shortLabel}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}