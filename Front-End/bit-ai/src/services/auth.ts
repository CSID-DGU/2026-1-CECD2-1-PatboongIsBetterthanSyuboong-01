import { Role } from "@/types/user";
import { post, get } from "./http/client";
import { clearTokens, getRefreshToken, setAccessToken, setRefreshToken } from "@/lib/auth/token";

export interface LoginRequestBody {
  username: string;
  password: string;
}

export interface LoginResponseBody {
  grantType: string;
  accessToken: string;
  refreshToken: string;
}

export interface SignupRequestBody {
  name: string;
  deptId?: string;
  role: string;
  username: string;
  password: string;
}

export interface CurrentUserProfile {
  id: number;
  name: string;
  deptId: number;
  role: Role;
  username: string;
}

export interface DoctorProfile {
  id: number;
  name: string;
  deptId: number;
  username: string;
}

interface LogoutRequestBody {
  refreshToken: string;
}

export async function login(body: LoginRequestBody): Promise<LoginResponseBody> {
  const data = await post<LoginResponseBody, LoginRequestBody>("/api/user/login", body);
  setAccessToken(data.accessToken ?? null);
  setRefreshToken(data.refreshToken ?? null);
  return data;
}

export async function signup(body: SignupRequestBody): Promise<void> {
  await post<void, SignupRequestBody>("/api/user/register", body);
}

export async function logout(): Promise<void> {
  const refreshToken = getRefreshToken();

  try {
    if (refreshToken) {
      await post<void, LogoutRequestBody>("/api/user/logout", { refreshToken });
    }
  } finally {
    clearTokens();
  }
}

export async function getRole(): Promise<Role> {  
  const data = await get<Role>("/api/patients/get_role");
  return data;
}

export async function getMe(): Promise<CurrentUserProfile> {
  return get<CurrentUserProfile>("/api/patients/get_me");
}

export async function getDoctors(): Promise<DoctorProfile[]> {
  return get<DoctorProfile[]>("/api/patients/doctors");
}
