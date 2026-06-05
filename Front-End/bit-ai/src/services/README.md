## API Wrapper 사용법 (axios 기반)

### 설치

Yarn 사용 시:

```bash
yarn add axios
```

### 환경 변수

`.env.local`에 기본 API URL을 설정할 수 있습니다.

```env
NEXT_PUBLIC_API_BASE_URL=https://api.example.com
```

### 초기화 (선택)

최초 1회 커스텀 옵션으로 인스턴스를 구성할 수 있습니다.

```ts
import { http } from "@services";

http({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL,
  timeoutMs: 15000,
});
```

### 토큰 주입기 설정 (선택)

요청 헤더에 `Authorization: Bearer <token>`을 자동으로 추가합니다.

```ts
import { setAuthTokenGetter } from "@services";

setAuthTokenGetter(async () => localStorage.getItem("token"));
```

### 요청 헬퍼 사용

간단한 CRUD 요청을 위한 헬퍼를 제공합니다.

```ts
import { get, post, put, del } from "@services";

type User = { id: string; name: string };

const me = await get<User>("/users/me");
const created = await post<User, Partial<User>>("/users", { name: "Alice" });
const updated = await put<User, Partial<User>>(`/users/${me.id}`, { name: "Bob" });
await del(`/users/${me.id}`);
```

### 에러 처리

모든 HTTP 에러는 `HttpError`로 throw 됩니다.

```ts
import { get, HttpError } from "@services";

try {
  await get("/users/unknown");
} catch (e) {
  if (e instanceof HttpError) {
    console.error(e.status, e.message, e.data);
  }
}
```

### 엔드포인트 모듈 예시

엔드포인트별 함수를 `src/services/api/*`에 분리해 관리하세요.

```ts
// src/services/api/user.ts
import { get, post } from "@services";

export const fetchMe = () => get<User>("/users/me");
export const createUser = (body: Partial<User>) => post<User, Partial<User>>("/users", body);
```


