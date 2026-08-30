const fs = require("fs");
const path = require("path");

const ROOT = process.cwd();
const INPUT = path.join(ROOT, "evals", "gold", "hantoo_selected_30.table.md");
const OUTPUT = path.join(ROOT, "evals", "gold", "hantoo_selected_30.readable.md");

function clean(value) {
  return String(value || "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/&rarr;/g, "->")
    .replace(/&middot;/g, "·")
    .replace(/&nbsp;/g, " ")
    .trim();
}

function splitRow(line) {
  const trimmed = line.trim();
  if (!trimmed.startsWith("|") || !trimmed.endsWith("|")) return [];
  return trimmed
    .slice(1, -1)
    .split("|")
    .map((cell) => clean(cell));
}

function bulletLines(value) {
  const lines = clean(value)
    .split(/\n+/)
    .map((line) => line.replace(/^[-*]\s*/, "").trim())
    .filter(Boolean);

  if (lines.length === 0) return ["- 없음"];
  return lines.map((line) => `- ${line}`);
}

function evidenceLines(value) {
  const text = clean(value);
  if (!text) return ["- 없음"];

  const labels = [
    ["ID", /ID:\s*([^\n]+)/i],
    ["문서", /문서:\s*([^\n]+)/i],
    ["검색 스니펫", /검색 스니펫:\s*([^\n]+)/i],
    ["원문 인용", /원문 인용:\s*([^\n]+)/i],
    ["페이지·슬라이드", /(page\/slide metadata:[^\n]+)/i],
    ["근거 위치", /(no page\/slide provenance[^\n]*)/i],
  ];

  const extracted = labels
    .map(([label, pattern]) => {
      const match = text.match(pattern);
      return match ? `- ${label}: ${match[1].trim()}` : null;
    })
    .filter(Boolean);

  return extracted.length > 0 ? extracted : bulletLines(text);
}

function sectionForId(id) {
  if (id.startsWith("PROD-")) return "상품·운용";
  if (id.startsWith("POLICY-")) return "업무·제도";
  return "기타";
}

function parseRows(markdown) {
  const rows = [];
  let headers = null;

  for (const line of markdown.split(/\r?\n/)) {
    if (line.startsWith("| ID |")) {
      headers = splitRow(line);
      continue;
    }

    if (!headers || !/^\| (PROD|POLICY)-/.test(line)) continue;

    const cells = splitRow(line);
    if (cells.length !== headers.length) {
      throw new Error(`Unexpected column count for row: ${line.slice(0, 120)}`);
    }

    rows.push(
      Object.fromEntries(headers.map((header, index) => [header, cells[index]])),
    );
  }

  return rows;
}

function renderRow(row) {
  const id = row.ID;
  const support = row["근거충분도"];
  const question = row["질문"];
  const answer = clean(row["목표 답변"]);
  const claims = bulletLines(row["필수 주장"]);
  const evidence = evidenceLines(row["문서 내 정확한 근거 위치"]);
  const gaps = bulletLines(row["부족 근거·금지 주장"]);

  return [
    `### ${id} · ${support}`,
    "",
    `**질문**`,
    "",
    `> ${question}`,
    "",
    `**목표 답변**`,
    "",
    answer
      .split(/\n+/)
      .map((line) => `> ${line}`)
      .join("\n"),
    "",
    `**필수 주장**`,
    "",
    ...claims,
    "",
    `**문서 근거 요약**`,
    "",
    ...evidence,
    "",
    `**부족 근거·금지 주장**`,
    "",
    ...gaps,
    "",
    `**검수 체크**`,
    "",
    "- [ ] 질문 의도와 목표 답변이 맞다",
    "- [ ] 필수 주장이 답변에 빠짐없이 들어간다",
    "- [ ] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다",
    "- [ ] 금지 주장을 답변하지 않는다",
    "",
  ].join("\n");
}

function render(rows) {
  const groups = new Map();
  for (const row of rows) {
    const section = sectionForId(row.ID);
    if (!groups.has(section)) groups.set(section, []);
    groups.get(section).push(row);
  }

  const supportCounts = rows.reduce((acc, row) => {
    acc[row["근거충분도"]] = (acc[row["근거충분도"]] || 0) + 1;
    return acc;
  }, {});

  const sectionOrder = ["상품·운용", "업무·제도", "기타"];
  const lines = [
    "# PR #128 한투 30문항 Gold Answer 쉬운 검수본",
    "",
    "원본 표가 너무 넓어 문항별 카드 형태로 다시 펼친 검수용 문서입니다. 정본은 `hantoo_selected_30.table.md`입니다.",
    "",
    "## 빠른 요약",
    "",
    `- 전체 문항: ${rows.length}개`,
    ...sectionOrder
      .filter((section) => groups.has(section))
      .map((section) => `- ${section}: ${groups.get(section).length}개`),
    `- 근거충분도: ${Object.entries(supportCounts)
      .map(([key, count]) => `${key} ${count}개`)
      .join(", ")}`,
    "",
    "## 검수 방법",
    "",
    "- 각 문항은 질문, 목표 답변, 필수 주장, 문서 근거, 부족 근거·금지 주장 순서로 펼쳤습니다.",
    "- `근거충분도`가 `미지원` 또는 `부분 지원`이면 답변 가능 범위와 금지 주장을 먼저 확인하세요.",
    "- 문서 근거가 `no page/slide provenance`로 표시된 문항은 원문 위치 추적이 약한 항목입니다.",
    "",
  ];

  for (const section of sectionOrder) {
    const sectionRows = groups.get(section);
    if (!sectionRows) continue;

    lines.push(`## ${section} (${sectionRows.length}개)`, "");
    for (const row of sectionRows) {
      lines.push(renderRow(row));
    }
  }

  return lines.join("\n").replace(/\n{3,}/g, "\n\n");
}

const markdown = fs.readFileSync(INPUT, "utf8");
const rows = parseRows(markdown);

if (rows.length !== 30) {
  throw new Error(`Expected 30 rows, found ${rows.length}`);
}

fs.writeFileSync(OUTPUT, render(rows), "utf8");
console.log(JSON.stringify({ rows: rows.length, output: path.relative(ROOT, OUTPUT) }));
