"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function AuthLinkSwap() {
  const pathname = usePathname();
  const isLogin = pathname?.startsWith("/login");
  const isSignup = pathname?.startsWith("/signup");

  if (isLogin) {
    return (
      <p style={{ marginTop: 12, fontSize: 14 }}>
        계정이 없으신가요? <Link href="/signup">회원가입</Link>
      </p>
    );
  }

  if (isSignup) {
    return (
      <p style={{ marginTop: 12, fontSize: 14 }}>
        이미 계정이 있으신가요? <Link href="/login">로그인</Link>
      </p>
    );
  }

  return null;
}


