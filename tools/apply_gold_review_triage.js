const fs = require("fs");
const path = require("path");

const ROOT = process.cwd();
const CHECKLIST = path.join(ROOT, "evals", "gold", "gold_answer_human_review_checklist.md");
const URGENT = path.join(ROOT, "evals", "gold", "gold_answer_review_urgent_items.md");

const okItems = {
  "POLICY-005": [
    "현재 `미지원` 유지가 적절함.",
    "연금계좌 미사용 납입한도 이월 가능 여부를 직접 정한 근거가 없고, ISA 이월 규정을 연금계좌에 전용하지 않도록 잘 제한하고 있음.",
    "답변이 `이월 불가`를 단정하지 않아 문서 근거 범위를 지킴.",
  ],
  "PROD-003": [
    "현재 `부분 지원` 유지가 적절함.",
    "ETF 구조, 금리 상승 시 채권가격 하락, 장기채권의 금리 민감도는 근거로 뒷받침됨.",
    "보유 종목·매수시점 없이 정확한 하락 원인을 특정하지 않아 답변 한계도 적절함.",
  ],
  "PROD-014": [
    "현재 `부분 지원` 유지가 적절함.",
    "환율과 채권가격 요인이 함께 작용할 수 있다는 설명은 근거 범위에 맞고, 실제 확정손익은 계좌 정보가 필요하다고 제한하고 있음.",
  ],
  "POLICY-008": [
    "현재 `부분 지원` 유지가 적절함.",
    "제공 문서상 세액공제 대상은 연금저축·IRP 납입액이라는 점을 기준으로 일반 CMA 간 이체를 세액공제 납입으로 보지 않도록 잘 제한하고 있음.",
  ],
  "MA-PP-002": [
    "현재 `미지원` 유지가 적절함.",
    "보험 연금상품의 세제 구분과 수관 가능 여부를 문서 근거 없이 단정하지 않음.",
  ],
  "MA-PP-004": [
    "현재 `미지원` 유지가 적절함.",
    "연금저축계좌 미투자 예수금의 이용료 대상 여부와 적용 기준을 제공 문서로 확인할 수 없다고 제한하고 있음.",
  ],
  "MA-PP-005": [
    "현재 `미지원` 유지가 적절함.",
    "해외 체류 고객의 대체 인증수단을 문서 근거 없이 단정하지 않고 공식 상담 채널 확인으로 제한하고 있음.",
  ],
  "MA-PP-008": [
    "현재 `미지원` 유지가 적절함.",
    "`세금우대 약정정보가 없습니다` 메시지의 발생 조건과 해결 절차를 문서 근거 없이 추정하지 않음.",
  ],
  "MA-PP-009": [
    "현재 `미지원` 유지가 적절함.",
    "일반 주식계좌 보유 주식의 연금계좌 현물 이전 가능 여부를 문서 근거 없이 가능/불가로 단정하지 않음.",
  ],
  "MA-PP-012": [
    "현재 `미지원` 유지가 적절함.",
    "연금계좌 이전 후 추가 분배금·배당 처리 주체와 지급 계좌를 문서 근거 없이 단정하지 않음.",
  ],
};

const urgentItems = [
  ["한투", "PROD-010", "투자 포트폴리오·수익률 목표 문항이라 추천/자문처럼 들릴 위험이 큼. 위험자산 70% 한도는 말해도 되지만 특정 비중 제안은 피해야 함."],
  ["한투", "PROD-011", "안정 운용 상품 추천 문항. 예적금·RP·MMF 등 열거가 추천처럼 보이지 않게 `문서상 예시`와 `개인 상황 확인 필요`를 분명히 해야 함."],
  ["한투", "PROD-013", "해외 ETF 분배금·외국납부세액·과세이연이 섞인 세금 문항. 최신 세법/적용 시점 표현이 민감해서 사람 확인 필요."],
  ["한투", "POLICY-001", "초과납입 인출과 비과세 재원 구분 문항. `페널티 없음`처럼 단순화하면 위험해서 세액공제 반영 여부·과세재원 확인 표현을 봐야 함."],
  ["한투", "POLICY-009", "세액공제 미신청 납입금, 운용수익, 과세재원 확정 절차가 섞여 있음. 비과세 범위를 과도하게 넓히지 않는지 확인 필요."],
  ["한투", "POLICY-011", "2013년 3월 1일 전후 가입일·연금수령연차 특례 문항. 이전 시 가입일 승계 조건을 문서 없이 단정하지 않는지 확인 필요."],
  ["미래에셋", "MA-PP-014", "세액공제 미수령 해지 세금 문항. 소득·세액공제확인서 제출 필요성과 과세 재원 표현이 민감함."],
  ["미래에셋", "MA-PP-032", "연금개시·중도인출·해지 시 소득·세액공제확인서 제출 여부 문항. 필수/선택 조건을 단정하면 위험함."],
  ["미래에셋", "MA-RP-030", "IRP 연금수령 요건과 퇴직금 재원 예외 문항. 5년 요건·55세·연금수령한도 표현 확인 필요."],
  ["미래에셋", "MA-ISA-001", "ISA 만기자금 연금전환 60일, 별도 납입한도, 추가 세액공제 문항. 날짜와 한도 수치가 있어 사람 확인 우선."],
  ["미래에셋", "MA-PP-031", "연금저축보험 해약환급금이 적은 이유를 사업비·수수료·세금으로 단정하지 않는지 확인 필요."],
  ["미래에셋", "MA-RP-004", "거래제한 코드의 원인과 제한 업무 범위를 근거 없이 추정하지 않는지 확인 필요."],
  ["미래에셋", "MA-RP-012", "예금별 만기·금리 조회 가능 여부와 메뉴 경로를 근거 없이 안내하지 않는지 확인 필요."],
  ["미래에셋", "MA-RP-015", "ETF 예약주문 가능/불가능 여부와 주문 가능 시간대를 근거 없이 단정하지 않는지 확인 필요."],
];

function replaceReviewBlock(markdown, id, notes) {
  const blockPattern = new RegExp(`(### \\d+\\. .*? ${id} · [^\\n]+\\n[\\s\\S]*?\\*\\*사람 검수 결과\\*\\*\\n\\n)([\\s\\S]*?)(\\n### \\d+\\. |\\n## |$)`);
  const match = markdown.match(blockPattern);
  if (!match) throw new Error(`Could not find block for ${id}`);

  if (/\[x\]/.test(match[2])) return markdown;

  const replacement = [
    "- 판정: [x] OK  [ ] 수정 필요  [ ] 보류",
    "- 확인:",
    "  - [x] 질문 의도",
    "  - [x] 목표 답변",
    "  - [x] 필수 주장",
    "  - [x] 부족 근거·금지 주장",
    "- 수정 메모:",
    ...notes.map((note) => `  - ${note}`),
    "- 최종 반영 여부: [ ] 반영 완료  [x] 반영 불필요  [ ] 미반영",
    "",
  ].join("\n");

  return markdown.replace(blockPattern, `${match[1]}${replacement}${match[3]}`);
}

let markdown = fs.readFileSync(CHECKLIST, "utf8");
for (const [id, notes] of Object.entries(okItems)) {
  markdown = replaceReviewBlock(markdown, id, notes);
}
fs.writeFileSync(CHECKLIST, markdown, "utf8");

const urgentMarkdown = [
  "# Gold Answer 급한 사람 검수 항목",
  "",
  "내가 먼저 체크할 수 있는 저위험 항목은 체크리스트에 `OK`로 채웠고, 아래는 사람이 우선 확인하면 좋은 항목입니다.",
  "",
  "## 우선순위 높음",
  "",
  ...urgentItems.map(([source, id, reason]) => `- ${source} ${id}: ${reason}`),
  "",
  "## 이미 내가 OK 처리한 항목",
  "",
  ...Object.keys(okItems).map((id) => `- ${id}`),
  "",
].join("\n");

fs.writeFileSync(URGENT, urgentMarkdown, "utf8");
console.log(JSON.stringify({ ok: Object.keys(okItems).length, urgent: urgentItems.length }));
