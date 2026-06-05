import { get, post, put } from "./http/client";
import { Role, User } from "@/types/user";

interface SetRoleRequestBody {
    id: number;
    role: Role;
}

interface GetAllUsersResponseBody {
    totalUserCount: number;
    users: User[];
}

export async function setRole(body: SetRoleRequestBody): Promise<void> {
    const { id, role } = body;
    await put<void, { role: Role }>(`/api/super/set_role/${id}`, { role });
}

export interface CreateUserRequestBody {
    name: string;
    deptId: number;
    role: Role;
    username: string;
    password: string;
}

export async function createUser(body: CreateUserRequestBody): Promise<void> {
    await post<void, CreateUserRequestBody>("/api/super/create_user", body);
}

export async function getAllUsers(): Promise<GetAllUsersResponseBody | User[]> {
    const data = await get<GetAllUsersResponseBody | User[]>("/api/super/get_all_users");
    return data;
}
