## src 폴더 가이드

이 문서는 `src` 폴더의 구조와 경로 별칭 사용법을 안내합니다.

### 폴더 구조

```text
app/
  (routes)/        라우팅 그룹 (유틸 페이지 등)
  (marketing)/     랜딩/마케팅 페이지 그룹
  (dashboard)/     대시보드 페이지 그룹
  (auth)/          인증 페이지 그룹 (sign-in/sign-up 등)
  (docs)/          문서/가이드 페이지 그룹
  api/             Route Handlers
assets/
  fonts/           웹폰트
  icons/           아이콘(svg 등)
  images/          이미지 리소스
components/
  common/          범용 컴포넌트
  layout/          레이아웃/헤더/푸터 등
  ui/              재사용 UI 단위 (Button, Input 등)
constants/         상수/환경설정 값
features/          도메인 단위 기능 묶음 (슬라이스 컴포넌트/로직)
hooks/             커스텀 훅
lib/               비즈니스 독립 라이브러리/유틸
mocks/             목 데이터/핸들러(msw 등)
services/          API 클라이언트/서버 통신 레이어
store/             전역 상태 (예: Zustand/Redux)
styles/            전역/테마 스타일
test/              테스트 유틸/케이스
types/             타입 선언(d.ts)/공용 타입
utils/             순수 유틸 함수
```

### 경로 별칭

`tsconfig.json`의 paths 설정으로 절대 경로 import를 지원합니다.

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@app/*": ["./src/app/*"],
      "@assets/*": ["./src/assets/*"],
      "@components/*": ["./src/components/*"],
      "@constants/*": ["./src/constants/*"],
      "@features/*": ["./src/features/*"],
      "@hooks/*": ["./src/hooks/*"],
      "@lib/*": ["./src/lib/*"],
      "@mocks/*": ["./src/mocks/*"],
      "@services/*": ["./src/services/*"],
      "@store/*": ["./src/store/*"],
      "@styles/*": ["./src/styles/*"],
      "@test/*": ["./src/test/*"],
      "@types/*": ["./src/types/*"],
      "@utils/*": ["./src/utils/*"]
    }
  }
}
```

예시

```ts
import Button from "@components/ui/Button";
import { fetcher } from "@services/http";
```


