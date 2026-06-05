"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login } from "@/services/auth";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login({ username, password });
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "로그인에 실패했습니다");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 360, margin: "64px auto", padding: 24 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 16 }}>
        로그인
      </h1>
      <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12 }}>
        <label style={{ display: "grid", gap: 6 }}>
          <span>사용자 ID</span>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="employee01"
            required
            style={{
              padding: "8px 12px",
              border: "1px solid #ddd",
              borderRadius: 8,
            }}
          />
        </label>
        <label style={{ display: "grid", gap: 6 }}>
          <span>비밀번호</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
            style={{
              padding: "8px 12px",
              border: "1px solid #ddd",
              borderRadius: 8,
            }}
          />
        </label>

        {error && (
          <div style={{ color: "#c00", fontSize: 14 }} role="alert">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          style={{
            padding: "10px 14px",
            borderRadius: 8,
            background: "#111",
            color: "#fff",
            border: 0,
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "로그인 중..." : "로그인"}
        </button>
      </form>

      <p style={{ marginTop: 12, fontSize: 14 }}>
        계정이 없으신가요? <Link href="/signup">회원가입</Link>
      </p>
    </div>
  );
}
