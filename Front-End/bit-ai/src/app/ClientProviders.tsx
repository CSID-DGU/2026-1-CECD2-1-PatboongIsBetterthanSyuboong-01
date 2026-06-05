"use client";

import { useEffect } from "react";
import { setAuthTokenGetter } from "@/services";
import { getAccessToken } from "@/lib/auth/token";

export default function ClientProviders({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    setAuthTokenGetter(async () => getAccessToken());
  }, []);

  return children as React.ReactElement;
}


