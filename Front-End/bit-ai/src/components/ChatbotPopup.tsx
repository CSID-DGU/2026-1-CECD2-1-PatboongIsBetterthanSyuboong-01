"use client";

import { useState, useRef, useEffect } from "react";
import styles from "./ChatbotPopup.module.css";

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
}

interface ChatbotPopupProps {
  onClose: () => void;
}

export default function ChatbotPopup({ onClose }: ChatbotPopupProps) {
  const [messages, setMessages] = useState<Message[]>([
    { id: 0, role: "assistant", content: "안녕하세요! AI 챗봇입니다. 무엇을 도와드릴까요?" },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    const userMsg: Message = { id: Date.now(), role: "user", content: trimmed };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed }),
      });

      if (!response.ok) throw new Error("응답 오류");

      const data = await response.json();
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, role: "assistant", content: data.reply },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, role: "assistant", content: "죄송합니다. 오류가 발생했습니다." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.popup} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <span className={styles.headerTitle}>AI 챗봇</span>
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        <div className={styles.messages}>
          {messages.map((msg) => (
            <div key={msg.id} className={`${styles.message} ${styles[msg.role]}`}>
              <div className={styles.bubble}>{msg.content}</div>
            </div>
          ))}
          {isLoading && (
            <div className={`${styles.message} ${styles.assistant}`}>
              <div className={styles.bubble}>
                <span className={styles.typing}>···</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className={styles.inputArea}>
          <input
            className={styles.input}
            type="text"
            placeholder="메시지를 입력하세요..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
          />
          <button
            className={styles.sendBtn}
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
          >
            전송
          </button>
        </div>
      </div>
    </div>
  );
}