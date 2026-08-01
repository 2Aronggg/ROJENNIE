#!/usr/bin/env node
/*
 * Audit a RAG JSONL corpus for common retrieval-quality problems.
 *
 * Default target:
 *   data/corpus/all.jsonl
 *
 * Usage:
 *   node server/scripts/audit_corpus.js
 *   node server/scripts/audit_corpus.js server/rag/chunks.jsonl
 *   node server/scripts/audit_corpus.js --out data/corpus/audit-report.json
 */

const fs = require("fs");
const path = require("path");

const DEFAULT_INPUT = "data/corpus/all.jsonl";
const DEFAULT_LONG_TEXT = 3000;
const DEFAULT_SHORT_TEXT = 30;

function parseArgs(argv) {
  const args = {
    input: DEFAULT_INPUT,
    out: null,
    longText: DEFAULT_LONG_TEXT,
    shortText: DEFAULT_SHORT_TEXT,
    maxExamples: 10,
  };

  const rest = [];
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--out") {
      args.out = argv[++index];
    } else if (arg === "--long-text") {
      args.longText = Number(argv[++index]);
    } else if (arg === "--short-text") {
      args.shortText = Number(argv[++index]);
    } else if (arg === "--max-examples") {
      args.maxExamples = Number(argv[++index]);
    } else {
      rest.push(arg);
    }
  }

  if (rest[0]) args.input = rest[0];
  return args;
}

function addExample(report, kind, value, limit) {
  if (!report.examples[kind]) report.examples[kind] = [];
  if (report.examples[kind].length < limit) report.examples[kind].push(value);
}

function countChars(value) {
  const text = String(value || "");
  let hangul = 0;
  let cjk = 0;
  let question = 0;
  let replacement = 0;
  for (const char of text) {
    const code = char.codePointAt(0);
    if (code >= 0xac00 && code <= 0xd7a3) hangul += 1;
    if (code >= 0x4e00 && code <= 0x9fff) cjk += 1;
    if (char === "?") question += 1;
    if (code === 0xfffd) replacement += 1;
  }
  return { hangul, cjk, question, replacement, length: text.length || 1 };
}

function likelyBrokenKorean(value) {
  const sample = String(value || "").slice(0, 1200);
  const counts = countChars(sample);
  return (
    counts.replacement > 0 ||
    (counts.question > 20 && counts.hangul < 60) ||
    (counts.cjk / counts.length > 0.08 && counts.hangul / counts.length < 0.22)
  );
}

function percentile(sortedNumbers, ratio) {
  if (!sortedNumbers.length) return 0;
  return sortedNumbers[Math.floor((sortedNumbers.length - 1) * ratio)];
}

function summarizeLengths(lengthsByType) {
  const result = {};
  for (const [docType, lengths] of Object.entries(lengthsByType)) {
    const sorted = [...lengths].sort((left, right) => left - right);
    result[docType] = {
      min: sorted[0] || 0,
      p50: percentile(sorted, 0.5),
      p90: percentile(sorted, 0.9),
      p99: percentile(sorted, 0.99),
      max: sorted[sorted.length - 1] || 0,
    };
  }
  return result;
}

function initTypeBucket(report, docType) {
  if (!report.by_doc_type[docType]) {
    report.by_doc_type[docType] = {
      count: 0,
      empty_text: 0,
      very_short_text: 0,
      too_long_text: 0,
      missing_product: 0,
      missing_effective_date: 0,
      embedding_null: 0,
      duplicate_text: 0,
      likely_broken_text: 0,
    };
  }
  return report.by_doc_type[docType];
}

function auditCorpus(inputPath, options) {
  const raw = fs.readFileSync(inputPath, "utf8");
  const lines = raw.split(/\r?\n/).filter((line) => line.trim());
  const seenChunkIds = new Map();
  const seenTexts = new Map();
  const lengthsByType = {};
  const report = {
    file: inputPath,
    generated_at: new Date().toISOString(),
    thresholds: {
      very_short_text_below: options.shortText,
      too_long_text_above: options.longText,
    },
    totals: {
      lines: lines.length,
      invalid_json: 0,
      empty_text: 0,
      very_short_text: 0,
      too_long_text: 0,
      duplicate_chunk_id: 0,
      duplicate_text: 0,
      missing_doc_id: 0,
      missing_chunk_id: 0,
      missing_path: 0,
      missing_doc_type: 0,
      missing_product: 0,
      missing_effective_date: 0,
      likely_broken_text: 0,
      embedding_null: 0,
    },
    by_doc_type: {},
    products: {},
    length_summary: {},
    examples: {
      invalid_json: [],
      empty_text: [],
      very_short_text: [],
      too_long_text: [],
      duplicate_chunk_id: [],
      duplicate_text: [],
      missing_doc_type: [],
      missing_product: [],
      missing_effective_date: [],
      likely_broken_text: [],
    },
  };

  for (let index = 0; index < lines.length; index += 1) {
    const lineNumber = index + 1;
    let row;
    try {
      row = JSON.parse(lines[index]);
    } catch (error) {
      report.totals.invalid_json += 1;
      addExample(report, "invalid_json", { line: lineNumber, error: error.message }, options.maxExamples);
      continue;
    }

    const docType = row.doc_type || "(missing)";
    const bucket = initTypeBucket(report, docType);
    bucket.count += 1;
    if (!lengthsByType[docType]) lengthsByType[docType] = [];

    const text = String(row.text || "");
    const normalizedText = text.replace(/\s+/g, " ").trim();
    const textLength = text.length;
    lengthsByType[docType].push(textLength);

    if (!row.doc_id) report.totals.missing_doc_id += 1;
    if (!row.chunk_id) {
      report.totals.missing_chunk_id += 1;
    } else if (seenChunkIds.has(row.chunk_id)) {
      report.totals.duplicate_chunk_id += 1;
      addExample(
        report,
        "duplicate_chunk_id",
        { chunk_id: row.chunk_id, first_line: seenChunkIds.get(row.chunk_id), line: lineNumber },
        options.maxExamples,
      );
    } else {
      seenChunkIds.set(row.chunk_id, lineNumber);
    }

    if (!row.path) report.totals.missing_path += 1;
    if (!row.doc_type) {
      report.totals.missing_doc_type += 1;
      addExample(report, "missing_doc_type", { line: lineNumber, chunk_id: row.chunk_id }, options.maxExamples);
    }

    if (!Array.isArray(row.product) || row.product.length === 0) {
      report.totals.missing_product += 1;
      bucket.missing_product += 1;
      addExample(report, "missing_product", { line: lineNumber, chunk_id: row.chunk_id, doc_type: row.doc_type }, options.maxExamples);
    } else {
      for (const product of row.product) {
        report.products[product] = (report.products[product] || 0) + 1;
      }
    }

    if (!row.effective_from && !row.effective_to) {
      report.totals.missing_effective_date += 1;
      bucket.missing_effective_date += 1;
      addExample(
        report,
        "missing_effective_date",
        { line: lineNumber, chunk_id: row.chunk_id, doc_type: row.doc_type, path: row.path },
        options.maxExamples,
      );
    }

    if (!normalizedText) {
      report.totals.empty_text += 1;
      bucket.empty_text += 1;
      addExample(report, "empty_text", { line: lineNumber, chunk_id: row.chunk_id }, options.maxExamples);
    } else if (textLength < options.shortText) {
      report.totals.very_short_text += 1;
      bucket.very_short_text += 1;
      addExample(
        report,
        "very_short_text",
        { line: lineNumber, chunk_id: row.chunk_id, doc_type: row.doc_type, length: textLength, text },
        options.maxExamples,
      );
    }

    if (textLength > options.longText) {
      report.totals.too_long_text += 1;
      bucket.too_long_text += 1;
      addExample(
        report,
        "too_long_text",
        { line: lineNumber, chunk_id: row.chunk_id, doc_type: row.doc_type, length: textLength, path: row.path },
        options.maxExamples,
      );
    }

    if (normalizedText) {
      if (seenTexts.has(normalizedText)) {
        report.totals.duplicate_text += 1;
        bucket.duplicate_text += 1;
        addExample(
          report,
          "duplicate_text",
          { line: lineNumber, chunk_id: row.chunk_id, first_chunk_id: seenTexts.get(normalizedText), doc_type: row.doc_type },
          options.maxExamples,
        );
      } else {
        seenTexts.set(normalizedText, row.chunk_id);
      }
    }

    if (likelyBrokenKorean(text) || likelyBrokenKorean(row.path)) {
      report.totals.likely_broken_text += 1;
      bucket.likely_broken_text += 1;
      addExample(
        report,
        "likely_broken_text",
        { line: lineNumber, chunk_id: row.chunk_id, doc_type: row.doc_type, path: row.path, preview: text.slice(0, 160) },
        options.maxExamples,
      );
    }

    if (row.embedding == null) {
      report.totals.embedding_null += 1;
      bucket.embedding_null += 1;
    }
  }

  report.length_summary = summarizeLengths(lengthsByType);
  return report;
}

function printSummary(report) {
  console.log(`Corpus audit: ${report.file}`);
  console.log(`- lines: ${report.totals.lines}`);
  console.log(`- invalid_json: ${report.totals.invalid_json}`);
  console.log(`- empty_text: ${report.totals.empty_text}`);
  console.log(`- very_short_text: ${report.totals.very_short_text}`);
  console.log(`- too_long_text: ${report.totals.too_long_text}`);
  console.log(`- duplicate_text: ${report.totals.duplicate_text}`);
  console.log(`- duplicate_chunk_id: ${report.totals.duplicate_chunk_id}`);
  console.log(`- missing_doc_type: ${report.totals.missing_doc_type}`);
  console.log(`- missing_product: ${report.totals.missing_product}`);
  console.log(`- missing_effective_date: ${report.totals.missing_effective_date}`);
  console.log(`- likely_broken_text: ${report.totals.likely_broken_text}`);
  console.log(`- embedding_null: ${report.totals.embedding_null}`);
  console.log("\nBy doc_type:");
  console.log(JSON.stringify(report.by_doc_type, null, 2));
  console.log("\nLength summary:");
  console.log(JSON.stringify(report.length_summary, null, 2));
  console.log("\nExamples:");
  console.log(JSON.stringify(report.examples, null, 2));
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!fs.existsSync(args.input)) {
    console.error(`Corpus file not found: ${args.input}`);
    process.exitCode = 1;
    return;
  }

  const report = auditCorpus(args.input, args);
  printSummary(report);

  if (args.out) {
    fs.mkdirSync(path.dirname(args.out), { recursive: true });
    fs.writeFileSync(args.out, `${JSON.stringify(report, null, 2)}\n`, "utf8");
    console.log(`\nWrote JSON report: ${args.out}`);
  }
}

main();
