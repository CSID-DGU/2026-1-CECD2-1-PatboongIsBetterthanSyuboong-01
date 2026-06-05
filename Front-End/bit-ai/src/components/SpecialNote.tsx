"use client";

import styles from "./SpecialNote.module.css";

export default function SpecialNote() {
  const specialNotes = [
    "특이사항 없음."
  ];

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3>특이사항</h3>
      </div>
      <div className={styles.content}>
        <div className={styles.notesList}>
          {specialNotes.map((note, index) => (
            <div key={index} className={styles.noteItem}>
              {note}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}