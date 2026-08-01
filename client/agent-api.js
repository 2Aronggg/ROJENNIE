(function () {
  const STORE_KEY = "kb_agent_demo_case";
  const DEFAULT_API_BASE = "http://127.0.0.1:8000";

  const demoPayload = {
    case_id: "case_agent_demo_001",
    session_id: "session_agent_demo",
    prompt:
      "정기예금 만기 이자가 가입 때 안내받은 금리와 다르고, 적금 우대금리도 예상보다 낮게 적용된 것 같습니다.",
    as_of: "2026-07-31",
    issues: [
      {
        issue_id: "issue_001",
        product: "정기예금",
        issue_type: "예금 만기 이자",
        text: "가입 시 안내받은 만기 이자와 실제 지급 이자가 달라 추가 확인이 필요합니다.",
        focal: {
          primary_object: "정기예금 계약",
          event_date: "2025-03-10",
          remedy: "안내 이율과 실제 지급 이자의 차이 확인",
        },
        target: {
          institution: "KB국민은행",
          route: "금융회사 민원창구",
        },
        facts: [
          { key: "contract_date", value: "2025-03-10", source: "user_input" },
          { key: "actual_interest", value: "실제 지급 이자 확인", source: "user_input" },
        ],
        required_facts: ["가입 당시 안내받은 예상 이자", "이자 계산 내역서"],
      },
      {
        issue_id: "issue_002",
        product: "적금",
        issue_type: "적금 우대금리",
        text: "우대조건을 충족했다고 생각했지만 만기 시 기본금리만 적용된 것으로 보입니다.",
        focal: {
          primary_object: "적금 우대조건",
          event_date: "2025-03-10",
          remedy: "우대조건 충족 여부 및 적용 금리 확인",
        },
        target: {
          institution: "KB국민은행",
          route: "금융회사 민원창구",
        },
        facts: [
          { key: "base_rate", value: "기본금리 적용", source: "user_input" },
          { key: "preferred_rate_claim", value: "우대조건 충족 주장", source: "user_input" },
        ],
        required_facts: [],
      },
    ],
  };

  const fallbackAnalysis = {
    case_id: demoPayload.case_id,
    session_id: demoPayload.session_id,
    prompt: demoPayload.prompt,
    issues: [
      {
        issue_id: "issue_001",
        product: "정기예금",
        issue_type: "예금 만기 이자",
        focal: demoPayload.issues[0].focal,
        target: demoPayload.issues[0].target,
        facts: demoPayload.issues[0].facts,
        missing_facts: ["가입 당시 안내받은 예상 이자", "이자 계산 내역서"],
        evidence_refs: [
          {
            doc_id: "prod_deposit_terms_001",
            page: 4,
            section: "만기 이자 계산",
            score: 0.87,
            snippet: "만기 이자는 약정 이율과 실제 예치 기간을 기준으로 계산합니다.",
          },
          {
            doc_id: "notice_interest_2025",
            page: 1,
            section: "금리 안내",
            score: 0.78,
            snippet: "가입 시점 안내 자료와 만기 계산서의 금리 항목을 대조합니다.",
          },
        ],
        decision: { control: "ask", risk_flags: ["missing_facts"] },
        next_steps: ["가입 당시 안내받은 예상 이자와 만기 이자 계산 내역서를 추가로 확인합니다."],
      },
      {
        issue_id: "issue_002",
        product: "적금",
        issue_type: "적금 우대금리",
        focal: demoPayload.issues[1].focal,
        target: demoPayload.issues[1].target,
        facts: demoPayload.issues[1].facts,
        missing_facts: [],
        evidence_refs: [
          {
            doc_id: "prod_saving_terms_002",
            page: 6,
            section: "우대금리 조건",
            score: 0.91,
            snippet: "우대금리는 급여이체, 자동이체 등 조건 충족 여부에 따라 적용됩니다.",
          },
          {
            doc_id: "case_saving_rate_2024_15",
            page: 2,
            section: "유사 민원",
            score: 0.74,
            snippet: "조건 충족 증빙이 없으면 기본금리 적용 결론으로 안내한 사례입니다.",
          },
        ],
        decision: { control: "proceed", risk_flags: [] },
        next_steps: ["우대조건 충족 증빙과 은행 계산 내역을 함께 첨부해 리포트를 생성합니다."],
      },
    ],
  };

  function apiBase() {
    const params = new URLSearchParams(window.location.search);
    return params.get("api") || window.localStorage.getItem("kb_api_base") || DEFAULT_API_BASE;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function statusLabel(control) {
    return {
      proceed: "PROCEED",
      amend: "AMEND",
      ask: "ASK",
      hold: "HOLD",
    }[control] || "ASK";
  }

  function controlNote(control) {
    return {
      proceed: "진행 가능",
      amend: "정리 필요",
      ask: "추가 확인 필요",
      hold: "전문가 검토",
    }[control] || "추가 확인 필요";
  }

  function issueTitle(issue) {
    return issue.issue_type || issue.focal?.primary_object || issue.product || issue.issue_id;
  }

  function evidenceFor(issue) {
    return Array.isArray(issue.evidence_refs) && issue.evidence_refs.length ? issue.evidence_refs : [];
  }

  function normalize(analysis, source, elapsedMs) {
    const mergedIssues = (analysis.issues || []).map((issue, index) => {
      const fallback = fallbackAnalysis.issues[index] || fallbackAnalysis.issues[0];
      return {
        ...fallback,
        ...issue,
        focal: { ...fallback.focal, ...(issue.focal || {}) },
        target: { ...fallback.target, ...(issue.target || {}) },
        evidence_refs: evidenceFor(issue).length ? issue.evidence_refs : fallback.evidence_refs,
        decision: { ...fallback.decision, ...(issue.decision || {}) },
        next_steps: issue.next_steps?.length ? issue.next_steps : fallback.next_steps,
      };
    });

    return {
      source,
      elapsedMs,
      generatedAt: new Date().toISOString(),
      request: demoPayload,
      analysis: {
        ...fallbackAnalysis,
        ...analysis,
        issues: mergedIssues.length ? mergedIssues : fallbackAnalysis.issues,
      },
    };
  }

  async function fetchAnalysis() {
    const started = performance.now();
    const response = await fetch(`${apiBase()}/api/v1/cases/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(demoPayload),
    });
    if (!response.ok) throw new Error(`API ${response.status}`);
    const analysis = await response.json();
    return normalize(analysis, "api", Math.round(performance.now() - started));
  }

  async function loadOrAnalyze(options = {}) {
    if (!options.force) {
      try {
        const cached = JSON.parse(window.localStorage.getItem(STORE_KEY) || "null");
        if (cached?.analysis?.issues?.length) return cached;
      } catch (_error) {
        window.localStorage.removeItem(STORE_KEY);
      }
    }

    try {
      const state = await fetchAnalysis();
      window.localStorage.setItem(STORE_KEY, JSON.stringify(state));
      return state;
    } catch (_error) {
      const state = normalize(fallbackAnalysis, "fallback", 0);
      window.localStorage.setItem(STORE_KEY, JSON.stringify(state));
      return state;
    }
  }

  function setText(root, selector, value) {
    const node = root.querySelector(selector);
    if (node) node.textContent = value;
  }

  function updateTrace(root, state) {
    const status = state.source === "api" ? "200 OK" : "OFFLINE FALLBACK";
    setText(root, ".trace-id", `trace_id: ${state.analysis.case_id}`);
    setText(root, ".trace-status", status);
    setText(root, ".trace-elapsed", state.elapsedMs ? `elapsed ${state.elapsedMs}ms` : "local fixture");
    root.querySelectorAll(".meta-trace").forEach((node) => {
      node.textContent = `${state.analysis.case_id} · ${status} · ${state.elapsedMs || "fixture"}ms`;
    });
  }

  function renderTrackHeader(track, issue, index) {
    setText(track, ".problem-number", String(index + 1));
    setText(track, ".issue-id", issue.issue_id);
    setText(track, ".product-badge", issue.product || "금융상품");
    setText(track, ".track-title", issueTitle(issue));
  }

  function renderEvidenceCards(track, issue) {
    const cards = track.querySelector(".evidence-cards");
    if (!cards) return;
    cards.innerHTML = evidenceFor(issue)
      .slice(0, 2)
      .map((ev) => {
        const meta = [ev.page ? `${ev.page}페이지` : null, ev.section || ev.path || "근거 문서"]
          .filter(Boolean)
          .join(" · ");
        return `
          <div class="evidence-card api-card">
            <span class="ev-doc-id">${escapeHtml(ev.doc_id || ev.chunk_id || "evidence")}</span>
            <p class="ev-title">${escapeHtml(ev.section || ev.path || ev.doc_id || "근거 후보")}</p>
            <div class="ev-meta"><span>${escapeHtml(meta)}</span><span class="ev-date-check">score ${Math.round((ev.score || 0.72) * 100)}%</span></div>
          </div>
        `;
      })
      .join("");
  }

  function renderAgent1(root = document) {
    return loadOrAnalyze().then((state) => {
      const issues = state.analysis.issues;
      updateTrace(root, state);
      setText(root, ".statement p", state.analysis.prompt);
      issues.slice(0, 2).forEach((issue, index) => {
        const card = root.querySelector(index === 0 ? ".problem-card.one" : ".problem-card.two");
        const focal = root.querySelector(index === 0 ? ".focal-card.one" : ".focal-card.two");
        if (card) {
          setText(card, ".problem-num", String(index + 1));
          card.querySelectorAll(".field").forEach((field, fieldIndex) => {
            const value = field.querySelector("span");
            if (!value) return;
            value.textContent =
              fieldIndex === 0
                ? issue.focal?.remedy || issue.text
                : `${issue.focal?.event_date || "사건일 미상"} · ${issue.product || "금융상품"}`;
          });
        }
        if (focal) {
          setText(focal, ".focal-title", `민원 ${index + 1} · ${issueTitle(issue)}`);
          setText(focal, ".mini-id", issue.issue_id);
          setText(focal, ".target-line:nth-of-type(1) span", issue.target?.institution || "확인 대상 기관");
          setText(focal, ".target-line:nth-of-type(2) span", issue.target?.route || "금융회사 민원창구");
          setText(
            focal,
            ".missing-item",
            issue.missing_facts?.length ? `누락 정보: ${issue.missing_facts.join(", ")}` : "누락 정보: 없음"
          );
        }
      });
    });
  }

  function renderAgent2(root = document) {
    return loadOrAnalyze().then((state) => {
      updateTrace(root, state);
      state.analysis.issues.slice(0, 2).forEach((issue, index) => {
        const track = root.querySelector(index === 0 ? ".track-1" : ".track-2");
        if (!track) return;
        renderTrackHeader(track, issue, index);
        const chips = track.querySelectorAll(".query-line .qp");
        const queryTerms = [issue.product, issue.issue_type, issue.focal?.primary_object, issue.focal?.event_date].filter(Boolean);
        chips.forEach((chip, chipIndex) => {
          if (queryTerms[chipIndex]) chip.textContent = queryTerms[chipIndex];
        });
        track.querySelectorAll(".filter-chip").forEach((chip, chipIndex) => {
          const values = [`상품: ${issue.product}`, `쟁점: ${issue.issue_type}`, `기준일: ${issue.focal?.event_date || "미상"}`];
          chip.textContent = values[chipIndex] || chip.textContent;
        });
        renderEvidenceCards(track, issue);
      });
    });
  }

  function renderAgent3(root = document) {
    return loadOrAnalyze().then((state) => {
      updateTrace(root, state);
      state.analysis.issues.slice(0, 2).forEach((issue, index) => {
        const track = root.querySelector(index === 0 ? ".track-1" : ".track-2");
        if (!track) return;
        renderTrackHeader(track, issue, index);
        const missing = issue.missing_facts || [];
        const evidence = evidenceFor(issue);
        const rows = track.querySelectorAll(".condition-row");
        if (rows[0]) {
          setText(rows[0], ".cond-name", "관련 약관·근거 문서 연결");
          setText(rows[0], ".cond-refs", evidence[0]?.doc_id ? `근거 ${evidence[0].doc_id}` : "근거 후보 없음");
          setText(rows[0], ".cond-status", evidence.length ? "MET" : "MISSING");
        }
        if (rows[1]) {
          setText(rows[1], ".cond-name", "핵심 사실 충족 여부");
          setText(rows[1], ".cond-refs", missing.length ? `미확인: ${missing.join(", ")}` : "필수 사실 확인됨");
          setText(rows[1], ".cond-status", missing.length ? "MISSING" : "MET");
        }
        if (rows[2]) {
          setText(rows[2], ".cond-name", "보수적 판단 게이트");
          setText(rows[2], ".cond-refs", `decision.control = ${issue.decision?.control || "ask"}`);
          setText(rows[2], ".cond-status", statusLabel(issue.decision?.control));
        }
        setText(
          track,
          ".finding-desc",
          missing.length ? `핵심 정보 ${missing.length}건 미확인 · 자동 결론 보류` : "근거와 사실이 연결되어 다음 단계 진행 가능"
        );
        setText(track, ".finding-label", missing.length ? "ASK" : "PROCEED");
      });
    });
  }

  function renderAgent4(root = document) {
    return loadOrAnalyze().then((state) => {
      updateTrace(root, state);
      state.analysis.issues.slice(0, 2).forEach((issue, index) => {
        const track = root.querySelector(index === 0 ? ".track-1" : ".track-2");
        if (!track) return;
        renderTrackHeader(track, issue, index);
        const control = issue.decision?.control || "ask";
        const badge = track.querySelector(".control-badge");
        if (badge) {
          badge.className = `control-badge control-${control}`;
          const spans = badge.querySelectorAll("span");
          if (spans[1]) spans[1].textContent = statusLabel(control);
          if (spans[2]) spans[2].textContent = controlNote(control);
        }
        const answerItems = track.querySelectorAll(".answer-item .ai-text");
        if (answerItems[0]) answerItems[0].textContent = issue.facts?.length ? issue.facts.map((fact) => `${fact.key}: ${fact.value}`).join(" · ") : "확인된 사실 없음";
        if (answerItems[1]) answerItems[1].textContent = evidenceFor(issue).map((ev) => ev.doc_id || ev.section).slice(0, 2).join(" · ") || "근거 후보 없음";
        if (answerItems[2]) answerItems[2].textContent = control === "proceed" ? "근거와 사실이 연결되어 민원 리포트를 생성할 수 있습니다." : "필수 정보가 남아 있어 추가 답변을 받은 뒤 결론을 확정합니다.";
        if (answerItems[3]) answerItems[3].textContent = issue.missing_facts?.length ? issue.missing_facts.join(", ") : "없음";
        if (answerItems[4]) answerItems[4].textContent = issue.next_steps?.[0] || "금융회사 민원창구에 근거 자료와 함께 접수합니다.";
        if (answerItems[5]) answerItems[5].textContent = issue.missing_facts?.length ? issue.missing_facts.join(", ") : "계약서 사본, 계산 내역, 안내 자료";
        setText(track, ".closing-card.do .cc-text", control === "proceed" ? "리포트 생성" : "추가 답변 요청");
        setText(track, ".closing-card.prep .cc-text", evidenceFor(issue)[0]?.doc_id || "근거 자료");
        setText(track, ".closing-card.unclear .cc-text", issue.missing_facts?.length ? `${issue.missing_facts.length}건` : "없음");
      });
    });
  }

  const style = document.createElement("style");
  style.textContent = `
    .api-card, .answer-item, .condition-row, .problem-card, .focal-card {
      overflow-wrap: anywhere;
    }
    .evidence-cards, .answer-sections, .conditions-list {
      min-height: 0;
    }
    .evidence-card .ev-title,
    .ai-text,
    .cond-name,
    .cond-refs,
    .case-summary,
    .field span,
    .missing-item {
      overflow-wrap: anywhere;
      word-break: keep-all;
    }
    .track,
    .panel {
      min-width: 0;
    }
    .track.panel,
    .splitter.panel,
    .builder.panel {
      overflow: auto;
      scrollbar-width: thin;
    }
    .answer-sections,
    .conditions-list,
    .evidence-cards,
    .split-results,
    .builder-grid {
      align-content: start;
      min-height: 0;
    }
  `;
  document.head.appendChild(style);

  window.KBAgentDemo = {
    loadOrAnalyze,
    renderAgent1,
    renderAgent2,
    renderAgent3,
    renderAgent4,
    refresh: () => loadOrAnalyze({ force: true }),
  };
})();
