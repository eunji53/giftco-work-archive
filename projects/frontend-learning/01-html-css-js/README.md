# 1단계 — HTML/CSS/JS 기본기

커리큘럼: [../docs/curriculum.md](../docs/curriculum.md#1단계--htmlcssjs-기본기)

목표: "주문 상태 카드" 목업 UI를 정적 HTML/CSS로 만들고, JS로 더미 주문 데이터를 map/filter로 필터링해서 렌더링하기.

실습 파일: 이 폴더의 `index.html`, `style.css`, `script.js`

---

## 기본 문법 요약

실습에서 쓰는 문법만 먼저 훑어봅니다. 모르는 게 나오면 언제든 이 표로 돌아와서 확인하세요.

### HTML

| 문법 | 의미 |
|---|---|
| `<태그 속성="값">내용</태그>` | HTML의 기본 구조. 여는 태그 + 내용 + 닫는 태그 |
| `<div>`, `<p>`, `<h1>~<h6>` | 박스(의미 없음), 문단, 제목 |
| `<button>`, `<span>`, `<a>`, `<ul>/<li>` | 버튼, 인라인 박스, 링크, 목록 |
| `class="이름"` | CSS/JS에서 이 요소를 찾을 때 쓰는 이름표. 여러 요소가 같은 class를 가질 수 있음 |
| `id="이름"` | class와 비슷하지만 한 페이지에 딱 하나만 있어야 함 |
| `data-*="값"` | 커스텀 데이터를 저장하는 속성 (예: `data-status="배송중"`). JS에서 `element.dataset.status`로 읽음 |
| `<!-- 내용 -->` | 주석. 화면에 안 보이고 코드에만 남는 메모 |

### CSS

| 문법 | 의미 |
|---|---|
| `선택자 { 속성: 값; }` | 기본 구조. "이 선택자에 해당하는 요소들에 이 스타일을 적용" |
| `태그이름 { ... }` | 태그 선택자 (예: `body { ... }` → 모든 body) |
| `.클래스이름 { ... }` | 클래스 선택자 (예: `.order-card { ... }` → class="order-card"인 요소들) |
| `#아이디 { ... }` | id 선택자 |
| **박스 모델** | 요소는 `content`(내용) → `padding`(안쪽 여백) → `border`(테두리) → `margin`(바깥 여백) 순으로 감싸짐 |
| `color`, `background-color` | 글자색, 배경색 |
| `font-size`, `font-weight` | 글자 크기, 굵기 |
| `display: flex` | 자식 요소들을 가로로 나란히 배치하는 컨테이너로 만듦 |
| `gap`, `flex-wrap` | flex 자식 사이 간격, 줄바꿈 여부 |
| `border-radius`, `box-shadow` | 모서리 둥글게, 그림자 |
| 단위 `px`, `%`, `rem` | px=고정 픽셀, %=부모 기준 비율, rem=기본 글자크기 기준 배수 |

### JavaScript

| 문법 | 의미 |
|---|---|
| `const 이름 = 값;` | 재할당 안 하는 변수 선언 (기본으로 이걸 씀) |
| `let 이름 = 값;` | 재할당이 필요할 때만 사용 |
| 데이터 타입 | 문자열 `'텍스트'`, 숫자 `123`, boolean `true/false`, 배열 `[1,2,3]`, 객체 `{key: value}` |
| `function 이름() { ... }` / `(인자) => { ... }` | 함수 선언 / 화살표 함수 (실습에서는 화살표 함수 위주로 사용) |
| `` `문자열 ${변수} 문자열` `` | 템플릿 리터럴. 백틱(`` ` ``)과 `${}`로 문자열에 변수 값을 끼워넣음 |
| `배열.map(item => ...)` | 배열의 각 요소를 변환해서 **새 배열**을 만듦 (원본은 안 바뀜) |
| `배열.filter(item => 조건)` | 조건을 만족하는 요소만 골라 **새 배열**을 만듦 |
| `배열.join('')` | 배열(주로 문자열 배열)을 하나의 문자열로 합침 |
| `document.querySelector('.클래스')` | HTML에서 해당 요소를 찾아옴 (DOM 조작의 시작점) |
| `요소.innerHTML = 문자열` | 그 요소 안의 내용을 문자열(HTML)로 통째로 교체 |
| `요소.addEventListener('click', 함수)` | 클릭 등 이벤트가 발생하면 함수 실행 |
| `event.target` | 이벤트가 실제로 발생한 요소 (이벤트 위임에서 사용) |

---

## Step 1 — HTML 뼈대 + 카드 1개

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>주문 상태 카드</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <h1>주문 목록</h1>
  <!-- 여기에 카드를 넣을 예정 -->
</body>
</html>
```

**개념 포인트**
- `<!DOCTYPE html>`: 이 문서가 HTML5라고 브라우저에 알려주는 선언
- `<head>`: 화면에 안 보이는 메타 정보(제목, CSS 연결 등)
- `<body>`: 실제 화면에 보이는 내용

이 상태로 브라우저에서 파일을 열어(더블클릭) "주문 목록"이 보이는지 확인.

## Step 2 — 카드 하나 만들기

`<body>` 안, 주석 자리에 카드 하나를 추가합니다.

```html
<div class="order-card">
  <p class="order-id">주문번호: A1001</p>
  <p class="order-status">배송중</p>
</div>
```

**개념 포인트**
- `<div>`는 의미 없는 박스 — 이후 CSS로 스타일 줄 대상
- `class="order-card"`는 이 요소를 CSS/JS에서 찾을 때 쓸 이름표

## Step 3 — CSS로 카드 꾸미기

`style.css`에 작성:

```css
body {
  font-family: sans-serif;
  background-color: #f5f5f5;
  padding: 20px;
}

.order-card {
  background-color: white;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 16px;
  max-width: 300px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.order-id {
  font-weight: bold;
  margin: 0 0 8px 0;
}

.order-status {
  display: inline-block;
  background-color: #fef3c7;
  color: #92400e;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 14px;
}
```

**개념 포인트**
- **박스 모델**: `padding`(테두리 안쪽 여백), `border`(테두리 선), `border-radius`(모서리 둥글게) — 카드처럼 보이게 만드는 핵심
- **클래스 선택자**: `.order-card`처럼 `.`으로 시작하면 `class="order-card"`인 요소를 선택
- `.order-status`에 배경색+패딩+radius를 준 건 "배지(badge)" 느낌을 내려는 것
- `box-shadow`: 은은한 그림자로 카드가 배경에서 떠 보이게 함

저장 후 새로고침(F5)하면 흰 배경 카드 안에 굵은 글씨 주문번호 + 노란 배지 형태의 "배송중"이 보임.

## Step 4 — 카드 여러 개 나열

`index.html`에서 카드를 감싸는 wrapper를 만들고, 카드를 2개 더 추가:

```html
<h1>주문 목록</h1>
<div class="order-list">
  <div class="order-card">
    <p class="order-id">주문번호: A1001</p>
    <p class="order-status">배송중</p>
  </div>
  <div class="order-card">
    <p class="order-id">주문번호: A1002</p>
    <p class="order-status">배송완료</p>
  </div>
  <div class="order-card">
    <p class="order-id">주문번호: A1003</p>
    <p class="order-status">주문접수</p>
  </div>
</div>
```

`style.css`에 추가:

```css
.order-list {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}
```

**개념 포인트**
- `display: flex`: 이 요소의 **자식들**을 가로로 나란히 배치하는 컨테이너로 만듦
- `flex-wrap: wrap`: 한 줄에 다 안 들어가면 다음 줄로 넘김
- `gap`: 자식 요소들 사이 간격 (margin 안 써도 됨)

저장 후 새로고침하면 카드 3개가 가로로 나란히 (화면이 좁으면 줄바꿈되며) 보임.

## Step 5 — JS로 데이터 만들고 자동 렌더링

`index.html`에서 `.order-list` 안의 카드 3개를 지우고 빈 컨테이너로 만든 뒤, `</body>` 위에 script 태그 추가:

```html
<h1>주문 목록</h1>
<div class="order-list"></div>

<script src="script.js"></script>
</body>
</html>
```

`script.js`에 작성:

```js
const orders = [
  { id: 'A1001', status: '배송중' },
  { id: 'A1002', status: '배송완료' },
  { id: 'A1003', status: '주문접수' },
];

const orderListEl = document.querySelector('.order-list');

const cardsHtml = orders.map(order => `
  <div class="order-card">
    <p class="order-id">주문번호: ${order.id}</p>
    <p class="order-status">${order.status}</p>
  </div>
`).join('');

orderListEl.innerHTML = cardsHtml;
```

**개념 포인트**
- `orders`: 객체 배열로 데이터를 표현 — 실무에서 API로 받아오는 데이터도 보통 이런 배열 형태
- `document.querySelector('.order-list')`: HTML에서 `class="order-list"`인 요소를 찾아옴
- `orders.map(...)`: 배열의 각 `order` 객체를 → HTML 문자열로 "변환"해서 새 배열을 만듦 (원본 `orders`는 안 바뀜)
- `` `...${order.id}...` ``: 템플릿 리터럴로 문자열 안에 변수 값을 끼워넣음
- `.join('')`: map이 만든 문자열 배열을 하나의 긴 문자열로 합침
- `orderListEl.innerHTML = ...`: 그 문자열을 실제 화면(DOM)에 집어넣음

저장 후 새로고침하면 Step 4와 동일한 화면(카드 3개)이 보임 — 이번엔 HTML이 아니라 JS 데이터로 만들어진 것.

## Step 6 — 상태별 필터 버튼

`index.html`에 필터 버튼 추가:

```html
<h1>주문 목록</h1>

<div class="filter-buttons">
  <button data-status="all">전체</button>
  <button data-status="배송중">배송중</button>
  <button data-status="배송완료">배송완료</button>
  <button data-status="주문접수">주문접수</button>
</div>

<div class="order-list"></div>

<script src="script.js"></script>
```

`style.css`에 버튼 스타일 추가:

```css
.filter-buttons {
  margin-bottom: 16px;
}

.filter-buttons button {
  padding: 6px 12px;
  margin-right: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: white;
  cursor: pointer;
}

.filter-buttons button:hover {
  background-color: #f0f0f0;
}
```

`script.js`를 렌더링 함수 + 클릭 이벤트로 리팩터링:

```js
const orders = [
  { id: 'A1001', status: '배송중' },
  { id: 'A1002', status: '배송완료' },
  { id: 'A1003', status: '주문접수' },
];

const orderListEl = document.querySelector('.order-list');
const filterButtonsEl = document.querySelector('.filter-buttons');

function renderOrders(list) {
  const cardsHtml = list.map(order => `
    <div class="order-card">
      <p class="order-id">주문번호: ${order.id}</p>
      <p class="order-status">${order.status}</p>
    </div>
  `).join('');
  orderListEl.innerHTML = cardsHtml;
}

filterButtonsEl.addEventListener('click', (event) => {
  const status = event.target.dataset.status;
  if (!status) return;

  if (status === 'all') {
    renderOrders(orders);
  } else {
    const filtered = orders.filter((order) => order.status === status);
    renderOrders(filtered);
  }
});

renderOrders(orders);
```

**개념 포인트**
- 렌더링 로직을 `renderOrders(list)` **함수**로 분리 — 아무 배열이나 넣으면 그걸로 다시 그려줌
- `data-status="배송중"` 같은 **data 속성**: HTML 요소에 커스텀 데이터를 심어두고, JS에서 `event.target.dataset.status`로 읽음
- **이벤트 위임**: 버튼 4개 각각에 리스너를 달지 않고, 부모 `.filter-buttons`에 리스너 하나만 달아 `event.target`으로 클릭된 버튼을 판별
- `orders.filter(...)`: `map`의 자매 메서드 — 조건을 만족하는 요소만 골라 새 배열을 만듦

저장 후 새로고침 → "배송중" 버튼 클릭 시 카드 1개만 남고, "전체" 클릭 시 3개 다시 표시되면 완료.

---

## 완료 체크리스트

- [x] Step 1 — HTML 뼈대
- [x] Step 2 — 카드 1개
- [x] Step 3 — CSS 스타일링
- [x] Step 4 — 카드 여러 개 나열 (flex)
- [x] Step 5 — JS 데이터로 자동 렌더링 (map)
- [x] Step 6 — 상태별 필터 버튼 (filter, 이벤트 위임)

다음: [2단계 — TypeScript 기초](../docs/curriculum.md#2단계--typescript-기초)
