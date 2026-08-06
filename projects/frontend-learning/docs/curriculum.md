# 프론트엔드 학습 커리큘럼

최종 목표: SSOT Viewer(주문 프로세스 상태 머신 뷰어)와 비슷한, React Flow 기반 노드/엣지 다이어그램 뷰어를 직접 만들기.

각 단계 실습 코드는 프로젝트 루트의 동일 번호 폴더(예: `01-html-css-js/`)에 작성합니다.

---

## 1단계 — HTML/CSS/JS 기본기

**목표**: 마크업 구조, 박스 모델/flex/grid, JS의 map/filter/async를 다룰 수 있게 되기.

**핵심 개념**
- HTML: 시맨틱 태그, 폼
- CSS: flexbox, grid, box model
- JS: 배열 메서드(map/filter/reduce), 화살표 함수, async/await, fetch

**참고 문서**
- MDN Web Docs (HTML/CSS/JS)

**실습 과제**
- 정적 HTML/CSS로 "주문 상태 카드" 목업 UI 만들기 (상태별 색상 다르게)
- JS로 더미 주문 데이터 배열을 만들고 map/filter로 상태별 필터링해서 화면에 렌더링

---

## 2단계 — TypeScript 기초

**목표**: 타입을 읽고 쓸 수 있게 되기 (React 코드를 이해하는 데 필요한 수준).

**핵심 개념**
- 기본 타입, interface/type
- 함수 타입, 제네릭 기초
- union 타입 (상태값 표현에 자주 씀 — 예: `'pending' | 'shipped' | 'delivered'`)

**참고 문서**
- TypeScript 공식 Handbook

**실습 과제**
- 1단계의 주문 데이터를 TS로 옮기고, 주문 상태를 union 타입으로 정의
- 상태 전이가 가능한 조합만 허용하는 간단한 타입/함수 작성

---

## 3단계 — React (컴포넌트, props, state, 훅)

**목표**: 컴포넌트 단위로 UI를 쪼개고, useState/useEffect로 상태를 다룰 수 있게 되기.

**핵심 개념**
- 컴포넌트, props, JSX
- useState, useEffect
- 리스트 렌더링, 조건부 렌더링, 이벤트 핸들링

**참고 문서**
- React 공식 문서 (react.dev)

**실습 과제**
- 1~2단계 데이터를 React 컴포넌트로 재구성 (`OrderCard`, `OrderList` 컴포넌트 분리)
- 상태 필터 버튼 클릭 시 useState로 화면 갱신

---

## 4단계 — Tailwind CSS v4

**목표**: 유틸리티 클래스 조합 방식에 익숙해지기.

**핵심 개념**
- 유틸리티 우선 스타일링 방식
- v4 변경점 (설정 방식, CSS 기반 설정)
- 반응형/다크모드 클래스

**참고 문서**
- Tailwind CSS 공식 문서

**실습 과제**
- 3단계에서 만든 컴포넌트에 Tailwind로 스타일 입히기 (상태별 배지 색상 등)

---

## 5단계 — shadcn/ui

**목표**: 컴포넌트를 "복사해서 커스터마이징"하는 방식에 익숙해지기 (일반 npm 패키지와 다른 점 이해).

**핵심 개념**
- shadcn/ui의 설치 방식 (컴포넌트 소스를 프로젝트에 복사)
- Button, Card, Badge, Table 등 기본 컴포넌트 활용

**참고 문서**
- shadcn/ui 공식 문서

**실습 과제**
- 기존 주문 카드 UI를 shadcn/ui의 Card, Badge 컴포넌트로 교체

---

## 6단계 — @xyflow/react (React Flow)

**목표**: 노드/엣지 기반 다이어그램을 그릴 수 있게 되기 — SSOT Viewer의 핵심 기능.

**핵심 개념**
- 노드/엣지 데이터 구조 정의
- 커스텀 노드 컴포넌트
- 레이아웃, 줌/팬 인터랙션

**참고 문서**
- React Flow(@xyflow/react) 공식 문서

**실습 과제**
- 주문 상태(pending → shipped → delivered 등)를 노드로, 상태 전이를 엣지로 표현하는 상태 머신 다이어그램 만들기

---

## 7단계 — react-router-dom, Vite

**목표**: 여러 화면(라우트) 구성과 Vite 프로젝트 구조를 이해하기.

**핵심 개념**
- react-router-dom의 라우트 정의, 링크 이동
- Vite 프로젝트 구조, dev 서버, 빌드

**참고 문서**
- react-router 공식 문서, Vite 공식 문서

**실습 과제**
- 지금까지 만든 화면들을 여러 라우트(목록 페이지 / 다이어그램 페이지)로 분리

---

## 최종 통합

1~7단계 실습을 하나의 프로젝트로 합쳐 SSOT Viewer 스타일의 "주문 프로세스 상태 머신 뷰어" 미니 클론 완성.
