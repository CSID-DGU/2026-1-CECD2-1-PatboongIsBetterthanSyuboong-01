"use client";

import Link from "next/link";
import styles from "./Header.module.css";

interface HeaderProps {
  activeMenu?: string;
}

export default function Header({ activeMenu }: HeaderProps) {
  void activeMenu;

  return (
    <header className={styles.header}>
      <div className={styles.leftSection}>
        <h1 className={styles.title}>슈붕보다팥붕</h1>
      </div>

      <div className={styles.rightSection}>
        <span className={styles.username}>김동국</span>
        <Link href="/login" className={styles.button}>
          로그아웃
        </Link>
      </div>
    </header>
  );
}