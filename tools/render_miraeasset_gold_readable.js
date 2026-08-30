const fs = require("fs");

const sourcePath = "evals/gold/miraeasset_actual_86.table.md";
const outputPath = "evals/gold/miraeasset_actual_86.readable.md";

const text = fs.readFileSync(sourcePath, "utf8");
const lines = text.split(/\r?\n/);

let headers = null;
const rows = [];

function splitRow(line) {
  let value = line.trim();
  if (value.startsWith("|")) value = value.slice(1);
  if (value.endsWith("|")) value = value.slice(0, -1);
  return value.split(/ \| /).map((cell) => cell.trim());
}

for (const line of lines) {
  if (line.startsWith("| ID | 질문 | 근거충분도 |")) {
    headers = splitRow(line);
  } else if (headers && /^\| MA-/.test(line)) {
    const cells = splitRow(line);
    const row = {};
    headers.forEach((header, index) => {
      row[header] = cells[index] || "";
    });
    rows.push(row);
  }
}

function clean(value) {
  return String(value || "")
    .replace(/<br><br>/g, "\n")
    .replace(/<br>/g, "\n")
    .replace(/&rarr;/g, "->")
    .replace(/&middot;/g, "·")
    .replace(/\u00a0/g, " ")
    .trim();
}

function supportGroup(id) {
  if (id.startsWith("MA-PP")) return "개인연금";
  if (id.startsWith("MA-RP")) return "퇴직연금";
  if (id.startsWith("MA-ISA")) return "ISA·연금";
  return "기타";
}

function claims(value) {
  const text = clean(value);
  if (!text || text === "직접 확정할 필수 주장 없음") {
    return ["- 직접 확정할 필수 주장 없음"];
  }
  return text
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => `- ${line}`);
}

function evidence(value) {
  const text = clean(value);
  if (!text || text === "직접 인용할 제공 문서 근거 없음") {
    return ["- 직접 인용할 제공 문서 근거 없음"];
  }
  return text
    .split(/\n\n+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const id = (part.match(/^\*\*([^*]+)\*\*/) || [null, "근거"])[1];
      const doc = (part.match(/— \[([^\]]+)\]/) || [null, ""])[1];
      const retrieval = (part.match(/retrieval `([^`]+)`/) || [null, ""])[1];
      const quote = (part.match(/인용: “([^”]+)”/) || [null, ""])[1];
      const page = (part.match(/page\/slide `([^`]+)`/) || [null, ""])[1];
      const noPage = part.includes("페이지 provenance 없음");

      let line = `- **${id}**`;
      if (doc) line += ` · ${doc}`;
      if (page) line += ` · page/slide ${page}`;
      if (noPage) line += " · 페이지 provenance 없음";
      if (retrieval) line += ` · retrieval \`${retrieval}\``;
      if (quote) line += `\n  - 인용: ${quote}`;
      return line;
    });
}

const byGroup = {
  "개인연금": rows.filter((row) => supportGroup(row.ID) === "개인연금"),
  "퇴직연금": rows.filter((row) => supportGroup(row.ID) === "퇴직연금"),
  "ISA·연금": rows.filter((row) => supportGroup(row.ID) === "ISA·연금"),
};

const supportCounts = rows.reduce((counts, row) => {
  counts[row["근거충분도"]] = (counts[row["근거충분도"]] || 0) + 1;
  return counts;
}, {});

const output = [];

output.push("# PR #130 미래에셋 실제 FAQ 86문항 Gold Answer 쉬운 검수본");
output.push("");
output.push(
  "원본 표가 너무 넓어 문항별 카드 형태로 다시 펼친 검수용 문서입니다. 정본은 `miraeasset_actual_86.table.md`입니다.",
);
output.push("");
output.push("## 빠른 요약");
output.push("");
output.push(`- 전체 문항: ${rows.length}개`);
output.push(`- 개인연금: ${byGroup["개인연금"].length}개`);
output.push(`- 퇴직연금: ${byGroup["퇴직연금"].length}개`);
output.push(`- ISA·연금: ${byGroup["ISA·연금"].length}개`);
output.push(
  `- 근거충분도: ${Object.entries(supportCounts)
    .map(([key, count]) => `${key} ${count}개`)
    .join(", ")}`,
);
output.push("");
output.push("## 검수 방법");
output.push("");
output.push("- 먼저 `근거충분도`와 `목표 답변`만 읽어 답변 방향이 맞는지 봅니다.");
output.push("- `필수 주장`은 Agent 답변에 반드시 들어가야 하는 핵심 채점 포인트입니다.");
output.push("- `부족 근거·금지 주장`은 환각이나 과잉 단정을 잡는 체크리스트입니다.");
output.push(
  "- `근거 요약`은 원본 근거 위치를 빠르게 훑기 위한 축약본입니다. 자세한 좌표는 원본 표를 보세요.",
);
output.push("");

for (const group of ["개인연금", "퇴직연금", "ISA·연금"]) {
  output.push(`## ${group} (${byGroup[group].length}개)`);
  output.push("");

  for (const row of byGroup[group]) {
    output.push(`### ${row.ID} · ${row["근거충분도"]}`);
    output.push("");
    output.push(`**질문**: ${clean(row["질문"])}`);
    output.push("");
    output.push("**목표 답변**");
    output.push("");
    for (const paragraph of clean(row["목표 답변"]).split(/\n+/).filter(Boolean)) {
      output.push(`> ${paragraph}`);
    }
    output.push("");
    output.push("**필수 주장**");
    output.push("");
    output.push(...claims(row["필수 주장"]));
    output.push("");
    output.push("**근거 요약**");
    output.push("");
    output.push(...evidence(row["문서 내 정확한 근거 위치"]));
    output.push("");
    output.push("**부족 근거·금지 주장**");
    output.push("");
    const limitations = clean(row["부족 근거·금지 주장"]);
    if (limitations) {
      for (const line of limitations.split(/\n+/).filter(Boolean)) {
        output.push(line.startsWith("**") || line.startsWith("•") ? line : `- ${line}`);
      }
    } else {
      output.push("- 없음");
    }
    output.push("");
    output.push("**검수 체크**");
    output.push("");
    output.push("- [ ] 목표 답변이 질문에 직접 답한다");
    output.push("- [ ] 필수 주장이 빠지지 않았다");
    output.push("- [ ] 금지 주장을 포함하지 않는다");
    output.push("- [ ] 근거충분도 판정이 납득된다");
    output.push("");
  }
}

fs.writeFileSync(outputPath, `${output.join("\n")}\n`, "utf8");
console.log(JSON.stringify({ rows: rows.length, output: outputPath }));
