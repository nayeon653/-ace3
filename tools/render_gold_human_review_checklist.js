const fs = require("fs");
const path = require("path");

const ROOT = process.cwd();
const OUTPUT = path.join(ROOT, "evals", "gold", "gold_answer_human_review_checklist.md");

const SOURCES = [
  {
    label: "한투",
    table: path.join(ROOT, "evals", "gold", "hantoo_selected_30.table.md"),
    readable: "hantoo_selected_30.readable.md",
    idPattern: /^(PROD|POLICY)-/,
    sectionForId(id) {
      if (id.startsWith("PROD-")) return "상품·운용";
      if (id.startsWith("POLICY-")) return "업무·제도";
      return "기타";
    },
  },
  {
    label: "미래에셋",
    table: path.join(ROOT, "evals", "gold", "miraeasset_actual_86.table.md"),
    readable: "miraeasset_actual_86.readable.md",
    idPattern: /^MA-/,
    sectionForId(id) {
      if (id.startsWith("MA-PP-")) return "개인연금";
      if (id.startsWith("MA-RP-")) return "퇴직연금";
      if (id.startsWith("MA-ISA-")) return "ISA·연금";
      return "기타";
    },
  },
];

function clean(value) {
  return String(value || "")
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/&rarr;/g, "->")
    .replace(/&middot;/g, "·")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function cleanBlock(value) {
  return String(value || "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/&rarr;/g, "->")
    .replace(/&middot;/g, "·")
    .replace(/&nbsp;/g, " ")
    .trim();
}

function bulletLines(value) {
  const lines = cleanBlock(value)
    .split(/\n+/)
    .map((line) => line.replace(/^[-*]\s*/, "").trim())
    .filter(Boolean);

  if (lines.length === 0) return ["- 없음"];
  return lines.map((line) => `- ${line}`);
}

function quoteBlock(value) {
  const lines = cleanBlock(value).split(/\n+/).filter(Boolean);
  if (lines.length === 0) return ["> 없음"];
  return lines.map((line) => `> ${line}`);
}

function splitRow(line) {
  const trimmed = line.trim();
  if (!trimmed.startsWith("|") || !trimmed.endsWith("|")) return [];
  return trimmed
    .slice(1, -1)
    .split("|")
    .map((cell) => clean(cell));
}

function parseRows(source) {
  const markdown = fs.readFileSync(source.table, "utf8");
  const rows = [];
  let headers = null;

  for (const line of markdown.split(/\r?\n/)) {
    if (line.startsWith("| ID |")) {
      headers = splitRow(line);
      continue;
    }

    if (!headers) continue;

    const cells = splitRow(line);
    if (cells.length !== headers.length) continue;
    const row = Object.fromEntries(headers.map((header, index) => [header, cells[index]]));
    if (!source.idPattern.test(row.ID || "")) continue;

    rows.push({
      source: source.label,
      readable: source.readable,
      section: source.sectionForId(row.ID),
      id: row.ID,
      support: row["근거충분도"],
      question: row["질문"],
      answer: row["목표 답변"],
      claims: row["필수 주장"],
      evidence: row["문서 내 정확한 근거 위치"],
      gaps: row["부족 근거·금지 주장"],
    });
  }

  return rows;
}

function directSamples(rows, perSection = 3) {
  const samples = [];
  const groups = new Map();

  for (const row of rows.filter((item) => item.support === "직접 지원")) {
    const key = `${row.source} / ${row.section}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }

  for (const groupRows of groups.values()) {
    samples.push(...groupRows.slice(0, perSection));
  }

  return samples;
}

function renderTask(row, index) {
  return [
    `### ${index}. ${row.source} ${row.id} · ${row.support}`,
    "",
    `- 섹션: ${row.section}`,
    `- 원본 검수본: \`${row.readable}\`에서 \`${row.id}\` 검색`,
    `- 질문: ${row.question}`,
    "",
    "**목표 답변**",
    "",
    ...quoteBlock(row.answer),
    "",
    "**필수 주장**",
    "",
    ...bulletLines(row.claims),
    "",
    "**문서 근거·주의점**",
    "",
    ...bulletLines(row.evidence),
    "",
    "**부족 근거·금지 주장**",
    "",
    ...bulletLines(row.gaps),
    "",
    "**사람 검수 결과**",
    "",
    "- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류",
    "- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장",
    "- 수정 메모:",
    "- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영",
    "",
  ].join("\n");
}

function section(title, rows, startIndex) {
  const lines = [`## ${title} (${rows.length}개)`, ""];
  rows.forEach((row, offset) => lines.push(renderTask(row, startIndex + offset)));
  return lines;
}

const allRows = SOURCES.flatMap(parseRows);
const hantooRows = allRows.filter((row) => row.source === "한투");
const miraeRows = allRows.filter((row) => row.source === "미래에셋");

const buckets = [
  {
    title: "1차: 한투 미지원 6개 + 최신성 공백 1개",
    rows: hantooRows.filter((row) => row.support === "미지원" || row.support === "최신성 공백"),
  },
  {
    title: "2차: 한투 부분 지원 14개",
    rows: hantooRows.filter((row) => row.support === "부분 지원"),
  },
  {
    title: "3차: 미래에셋 미지원 21개",
    rows: miraeRows.filter((row) => row.support === "미지원"),
  },
  {
    title: "4차: 미래에셋 부분 지원 36개",
    rows: miraeRows.filter((row) => row.support === "부분 지원"),
  },
  {
    title: "5차: 직접 지원 샘플 확인",
    rows: directSamples(allRows, 3),
  },
];

let taskIndex = 1;
const lines = [
  "# Gold Answer 사람 검수 체크리스트",
  "",
  "한투와 미래에셋 Gold Answer를 사람이 검수하기 위한 작업지입니다.",
  "원본 표 대신 readable 검수본에서 해당 ID를 검색한 뒤, 아래 체크박스에 판정과 메모를 남기면 됩니다.",
  "",
  "## 진행 규칙",
  "",
  "- 아래 순서대로 검수합니다.",
  "- `미지원`, `부분 지원`, `최신성 공백` 문항을 먼저 보고, `직접 지원`은 샘플만 확인합니다.",
  "- 판정은 `OK`, `수정 필요`, `보류` 중 하나만 체크합니다.",
  "- 수정이 필요하면 `수정 메모`에 바꿔야 할 문구나 근거 문제를 짧게 적습니다.",
  "",
  "## 전체 요약",
  "",
  ...buckets.map((bucket) => `- ${bucket.title}: ${bucket.rows.length}개`),
  `- 총 검수 항목: ${buckets.reduce((sum, bucket) => sum + bucket.rows.length, 0)}개`,
  "",
];

for (const bucket of buckets) {
  lines.push(...section(bucket.title, bucket.rows, taskIndex));
  taskIndex += bucket.rows.length;
}

fs.writeFileSync(OUTPUT, lines.join("\n").replace(/\n{3,}/g, "\n\n"), "utf8");
console.log(
  JSON.stringify({
    output: path.relative(ROOT, OUTPUT),
    buckets: Object.fromEntries(buckets.map((bucket) => [bucket.title, bucket.rows.length])),
    total: taskIndex - 1,
  }),
);
