# 2단계 — TypeScript 기초

커리큘럼: [../docs/curriculum.md](../docs/curriculum.md#2단계--typescript-기초)

목표: 1단계 주문 데이터를 TS로 옮기고 상태값을 union 타입으로 정의, 상태 전이가 가능한 조합만 허용하는 타입/함수 작성하기.

실습 파일: 이 폴더의 `orders.ts`

---

## Step 1 — 환경 준비

```bash
cd 02-typescript
npm init -y
npm install -D typescript
```

**개념 포인트**
- `npm init -y`: 이 폴더를 npm 프로젝트로 만듦 (`package.json` 생성)
- `npm install -D typescript`: TypeScript 컴파일러를 이 폴더 안에 설치 (devDependency) — 이걸로 타입 에러를 실행 없이 미리 잡아낼 수 있음
- `node_modules/`는 프로젝트 `.gitignore`에 이미 등록돼 있어서 git에는 안 올라감

## Step 2 — 주문 데이터를 타입으로 표현하기

```ts
type OrderStatus = '배송중' | '배송완료' | '주문접수';

interface Order {
  id: string;
  status: OrderStatus;
}

const orders: Order[] = [
  { id: 'A1001', status: '배송중' },
  { id: 'A1002', status: '배송완료' },
  { id: 'A1003', status: '주문접수' },
];
```

**개념 포인트**
- `type OrderStatus = 'A' | 'B' | 'C'`: **union 타입** — 이 변수는 저 셋 중 하나의 값만 가질 수 있음. JS에서는 그냥 문자열이라 아무 값이나 넣을 수 있었지만, 이제는 오타나 잘못된 상태값을 코드 작성 중에 바로 잡아줌
- `interface Order { id: string; status: OrderStatus; }`: **객체의 모양(shape)**을 정의. "Order 타입은 반드시 id(문자열)와 status(OrderStatus) 필드를 가져야 한다"는 규칙
- `const orders: Order[]`: `orders`는 "Order 타입 객체들의 배열"이라고 타입을 명시

**타입 체크 방법**: `02-typescript` 폴더 안에서

```bash
npx tsc --noEmit orders.ts
```

에러 없이 조용히 끝나면 정상.

---

## 다음에 이어서 할 것

- Step 3: 일부러 잘못된 status 값을 넣어서 타입 에러가 나는 걸 직접 확인해보기
- Step 4: 상태 전이(예: 주문접수 → 배송중 → 배송완료)가 허용된 조합일 때만 통과시키는 함수 작성

## 진행 체크리스트

- [x] Step 1 — 환경 준비 (npm init, typescript 설치)
- [x] Step 2 — union 타입 + interface로 주문 데이터 타이핑
- [ ] Step 3 — 타입 에러 직접 확인해보기
- [ ] Step 4 — 상태 전이 제한 함수
