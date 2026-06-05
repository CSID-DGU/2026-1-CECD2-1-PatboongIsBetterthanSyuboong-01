import type { AxiosInstance, InternalAxiosRequestConfig, AxiosError } from "axios";
import type { TokenGetter } from "./types";
import { HttpError } from "./types";

export function attachInterceptors(instance: AxiosInstance, getToken?: TokenGetter): void {
  instance.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
    if (getToken) {
      const token = await getToken();
      if (token) {
        config.headers = {
          ...(config.headers ?? {}),
          Authorization: `Bearer ${token}`,
        } as typeof config.headers;
      }
    }
    return config;
  });

  instance.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
      const status = error.response?.status ?? 0;
      const data = error.response?.data as unknown;
      const body = typeof data === "object" && data !== null ? (data as Record<string, unknown>) : null;
      const detail = body?.detail;
      const detailStr =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((x) => (typeof x === "object" && x && "msg" in x ? String((x as { msg: unknown }).msg) : String(x))).join("; ")
            : "";
      const message =
        detailStr ||
        (body?.message != null ? String(body.message) : "") ||
        error.message ||
        "HTTP Error";

      if (status === 401 && typeof window !== "undefined") {
        window.location.href = "/login";
      }

      throw new HttpError(message, status, data);
    }
  );
}


