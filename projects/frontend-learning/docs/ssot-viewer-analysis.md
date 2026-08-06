# SSOT Viewer 분석 메모

학습 계기가 된 사이트: `ssot.neordinary.xyz/apps/order-process-shipping-fee`
(giftco 사내 SSOT Data Platform — 주문 프로세스 상태 머신 뷰어)

## 확인된 기술 스택 (F12 개발자도구 분석 기준)

- **빌드 도구**: Vite (dev 서버가 그대로 노출됨)
- **프레임워크**: React 19 + TypeScript
- **스타일링**: Tailwind CSS v4
- **UI 컴포넌트**: shadcn/ui
- **다이어그램**: @xyflow/react (React Flow) — 노드/엣지 기반 상태 머신 시각화
- **라우팅**: react-router-dom
- **패키지 매니저**: pnpm
- **관리 도구 추정**: `.claude/schema.json`이 노출된 것으로 보아 Claude Code로 관리되는 프로젝트로 추정

## 이 프로젝트와의 연결점

- 최종 목표는 이 스택 조합으로 비슷한 노드/엣지 상태 머신 뷰어를 직접 만들어보는 것.
- 특히 6단계(React Flow)가 이 사이트의 핵심 기능과 가장 밀접하게 연결됨.
