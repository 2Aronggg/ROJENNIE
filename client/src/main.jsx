import React, {useCallback, useEffect, useMemo, useReducer, useRef, useState} from "react";
import {createRoot} from "react-dom/client";
import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./style.css";

const API_BASE = import.meta.env.VITE_API_BASE || window.API_BASE || "http://localhost:8000";
const DEMO_ONLY = new URLSearchParams(window.location.search).get("demo") === "1";
const CONTROL_LABEL = {proceed: "진행 중", ask: "리포트 생성됨", amend: "보완 필요", hold: "검토 대기"};
const DECISION_LABEL = {proceed: "진행", ask: "추가 확인 필요", amend: "보완 필요", hold: "검토 대기"};
const NODE_LABEL = {user_answer: "사용자 진술", decision: "사용자 선택", derived: "계산 결과", evidence: "근거 자료"};

const DEMO_ANALYSIS = {
  case_id: "demo_case",
  issues: [
    {
      issue_id: "issue_1",
      product: "예금",
      issue_type: "예금 만기 이자 금액 불일치",
      focal: {type: "예금 거래내역"},
      target: {subject: "금융회사"},
      facts: [{field: "실제 지급 금액", value: 279180}, {field: "적용 금리", value: "연 3.3%"}],
      missing_facts: ["안내 금액"],
      evidence_refs: [{doc_id: "demo-deposit-terms", page: 8, section: "이자 계산 및 지급", score: .92, snippet: "약정 금리와 실제 지급 시 세금 공제를 반영하여 이자를 계산합니다."}],
      decision: {control: "ask", risk_flags: ["missing_facts"]},
      mock_data: {available: false, account: null},
      next_steps: ["예상하신 이자 금액은 얼마인가요?"],
    },
    {
      issue_id: "issue_2",
      product: "적금",
      issue_type: "적금 금리 변경 미안내",
      focal: {type: "금리 변경 안내문"},
      target: {subject: "금융회사"},
      facts: [{field: "기본금리", value: "3.5%"}, {field: "우대조건 상태", value: "미충족"}, {field: "금리 변경 이력", value: []}, {field: "안내 이력", value: []}],
      missing_facts: [],
      evidence_refs: [{doc_id: "demo-savings-terms", page: 3, section: "우대금리 조건", score: .88, snippet: "자동이체 조건 미충족 시 우대금리가 적용되지 않을 수 있습니다."}],
      decision: {control: "proceed", risk_flags: []},
      mock_data: {available: true, account: {base_rate: .035, preferential_rate: .005, applied_rate: .035, rate_change_history: [], notice_history: []}},
      next_steps: ["금리 변경 이력과 우대조건 적용 결과를 확인했습니다."],
    },
  ],
};

const EMPTY_ANALYSIS = {case_id: "new_case", issues: []};
const HISTORY_KEY = "kb-key-buddy-case-history";
const CASE_STATUS_LABEL = {proceed: "승인", ask: "확인중", amend: "보완 필요", hold: "검토 대기"};
const TERM_DICTIONARY = {
  우대금리: "기본금리에 특정 조건을 충족했을 때 추가로 적용되는 금리입니다.",
  분쟁조정: "금융회사와 소비자 사이의 다툼을 정식 기관 절차로 조정받는 과정입니다.",
  중도해지: "만기 전에 계약을 끝내는 절차입니다.",
  환매: "투자상품을 다시 현금화하기 위해 매도 또는 지급을 신청하는 절차입니다.",
  명의도용: "본인의 동의 없이 본인 명의가 사용된 상황입니다.",
};

function readCaseHistory() {
  try {
    const value = JSON.parse(window.localStorage.getItem(HISTORY_KEY) || "[]");
    return Array.isArray(value) ? value : [];
  } catch (_) {
    return [];
  }
}

function rememberCase(analysis, prompt = "") {
  const current = readCaseHistory();
  const previous = current.find(function(item) { return item.case_id === analysis.case_id; });
  const next = [{
    case_id: analysis.case_id,
    prompt: prompt || previous?.prompt || "",
    created_at: previous?.created_at || new Date().toISOString(),
    analysis,
  }, ...current.filter(function(item) { return item.case_id !== analysis.case_id; })].slice(0, 30);
  window.localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
  return next;
}

function caseStatus(analysis) {
  const controls = (analysis.issues || []).map(function(issue) { return issue.decision?.control || "ask"; });
  if (controls.includes("hold")) return "hold";
  if (controls.includes("ask")) return "ask";
  if (controls.includes("amend")) return "amend";
  return "proceed";
}

function completedIssues(history) {
  return history.flatMap(function(record) {
    return (record.analysis?.issues || [])
      .filter(function(issue) { return issue.decision?.control === "proceed"; })
      .map(function(issue) { return {...issue, case_id: record.case_id, created_at: record.created_at, prompt: record.prompt}; });
  });
}

function sourceLabel(ref) {
  const source = String(ref.path || ref.doc_id || "");
  if (ref.section) return ref.section;
  if (/판결|case|judgment/i.test(source)) return "관련 판례";
  if (/은행법|bank/i.test(source)) return "은행법";
  if (/약관|terms/i.test(source)) return "상품 약관";
  return ref.doc_id || "관련 근거";
}

function termsForIssue(issue) {
  const text = JSON.stringify(issue || {});
  const found = Object.keys(TERM_DICTIONARY).filter(function(term) { return text.includes(term); });
  return found.length ? found : ["우대금리", "분쟁조정"].filter(function(term) { return text.includes(term) || term === "우대금리"; });
}

function clone(value) {
  return typeof structuredClone === "function" ? structuredClone(value) : JSON.parse(JSON.stringify(value));
}

function won(value) {
  return typeof value === "number" && Number.isFinite(value) ? new Intl.NumberFormat("ko-KR").format(value) + "원" : String(value ?? "미확인");
}

function valueText(value) {
  if (Array.isArray(value)) return value.length ? value.map(valueText).join(", ") : "없음";
  if (value && typeof value === "object") return Object.entries(value).map(function(entry) { return entry[0] + ": " + valueText(entry[1]); }).join(", ");
  if (typeof value === "number") return Number.isInteger(value) ? won(value) : String(value);
  return String(value ?? "미확인");
}

function label(control) {
  return CONTROL_LABEL[control] || control || "미확인";
}

function decisionLabel(control) {
  return DECISION_LABEL[control] || control || "미확인";
}

function issueLetter(index) {
  return String.fromCharCode(65 + index);
}

function initialPhase(issue) {
  const missing = issue.missing_facts || [];
  if (missing.includes("안내 금액")) return "expected";
  if (missing.includes("실제 지급 금액")) return "actual";
  return "done";
}

function initialQuestion(issue) {
  if (issue.decision?.control === "ask" && issue.target?.is_unclear) return "처리할 금융회사는 어디인가요?";
  const missing = issue.missing_facts || [];
  if (missing.includes("안내 금액")) return "만기 때 받을 것으로 예상하신 이자 금액은 얼마인가요?";
  if (missing.includes("실제 지급 금액")) return "실제로 입금된 세후 이자는 얼마였나요?";
  return issue.next_steps?.[0] || "이 섹션의 확인이 완료되었습니다.";
}

function createState(issue) {
  return {
    nodes: [],
    messages: [{role: "assistant", text: initialQuestion(issue)}],
    phase: initialPhase(issue),
    decision: issue.decision?.control || "ask",
    expectedInterest: null,
    actualInterest: null,
    pendingAmount: null,
    pendingAmountNodeId: null,
    answerParentId: null,
    taxParentId: null,
    inputParentId: null,
    expectedNodeId: null,
    actualNodeId: null,
    calculationNodeId: null,
    principal: null,
    rate: null,
    days: null,
    taxBasis: null,
    mockAccount: issue.mock_data?.available ? issue.mock_data.account : null,
  };
}

function createSession(analysis) {
  const states = {};
  (analysis.issues || []).forEach(function(issue) { states[issue.issue_id] = createState(issue); });
  return {analysis, states, selectedIssueId: analysis.issues?.[0]?.issue_id || null, selectedNodeId: null, drawerNodeId: null, drawerIssueId: null};
}

function getIssue(session, issueId = session.selectedIssueId) {
  return (session.analysis.issues || []).find(function(issue) { return issue.issue_id === issueId; });
}

function addMessage(state, role, text) {
  state.messages.push({role, text});
}

function nextNodeId(session) {
  const count = Object.values(session.states).reduce(function(total, state) { return total + state.nodes.length; }, 0) + 1;
  return "node_" + String(count).padStart(3, "0");
}

function addNode(session, issue, data) {
  const state = session.states[issue.issue_id];
  const node = {
    node_id: nextNodeId(session),
    parent_id: Object.prototype.hasOwnProperty.call(data, "parent_id") ? data.parent_id : null,
    type: data.type,
    title: data.title,
    content: data.content || data.title,
    source: data.source || NODE_LABEL[data.type] || "시스템",
    raw: data.raw || "",
    details: data.details || {},
    evidence: data.evidence || [],
    conversation: data.conversation || [],
    created_at: new Date().toLocaleString("ko-KR", {hour12: false}),
  };
  state.nodes.push(node);
  session.selectedNodeId = node.node_id;
  return node;
}

function addUserFact(session, issue, data) {
  return addNode(session, issue, {
    type: "user_answer",
    title: data.title,
    content: data.content,
    raw: data.raw,
    source: "사용자 진술",
    parent_id: data.parent_id ?? null,
    details: data.details,
    conversation: data.conversation,
  });
}

function parseAmount(value) {
  const text = String(value).replace(/[，,\s]/g, "").replace(/원/g, "");
  if (!text || /모르|없/.test(text)) return null;
  if (/^\d+(?:\.\d+)?$/.test(text)) return Number(text);
  let total = 0;
  [["억", 100000000], ["천만", 10000000], ["백만", 1000000], ["만", 10000], ["천", 1000], ["백", 100]].forEach(function(pair) {
    const match = text.match(new RegExp("(\\d+(?:\\.\\d+)?)" + pair[0]));
    if (match) total += Number(match[1]) * pair[1];
  });
  return total > 0 ? total : null;
}

function parseRate(value) {
  const text = String(value).replace(/,/g, "");
  const match = text.match(/\d+(?:\.\d+)?/);
  if (!match) return null;
  const number = Number(match[0]);
  if (text.includes("%")) return number;
  return number < 1 ? number * 100 : number;
}

function parseDays(value) {
  const text = String(value);
  if (/네|일년|1년/.test(text)) return 365;
  const match = text.match(/\d+/);
  if (!match) return null;
  return Number(match[0]) * (text.includes("개월") ? 30 : 1);
}

function handleExpected(session, issue, state, raw) {
  const amount = parseAmount(raw);
  if (!amount) {
    addMessage(state, "assistant", "금액을 확인하지 못했습니다. ‘20만 원’처럼 입력해주세요.");
    return;
  }
  const conversation = [{role: "AI", text: "만기 때 받을 것으로 예상하신 이자 금액은 얼마인가요?"}, {role: "사용자", text: raw}];
  state.pendingAmount = amount;
  if (amount >= 1000000) {
    const pending = addNode(session, issue, {
      type: "decision",
      title: "금액 의미 확인 필요: " + won(amount),
      content: "입력한 금액이 가입 원금인지 예상 이자인지 확인이 필요합니다.",
      raw,
      source: "재확인 필요",
      details: {"입력 금액": won(amount), "확인 상태": "예상 이자로 확정하지 않음"},
      conversation,
    });
    state.pendingAmountNodeId = pending.node_id;
    state.phase = "expected_basis";
    addMessage(state, "assistant", won(amount) + "은 예금에 가입한 원금인가요, 만기 때 예상한 이자 금액인가요?");
    return;
  }
  const expected = addUserFact(session, issue, {
    title: "예상 이자: " + won(amount),
    content: "값: " + won(amount),
    raw,
    parent_id: state.inputParentId,
    details: {"값": won(amount), "신뢰 상태": "사용자 진술"},
    conversation,
  });
  state.expectedInterest = amount;
  state.expectedNodeId = expected.node_id;
  state.phase = "actual";
  addMessage(state, "assistant", "실제로 입금된 세후 이자는 얼마였나요?");
}

function chooseExpectedBasis(session, issue, state, choice) {
  const amount = state.pendingAmount;
  const branch = addNode(session, issue, {
    type: "decision",
    title: choice,
    content: choice + ": " + won(amount),
    source: "사용자 선택",
    parent_id: state.pendingAmountNodeId,
    details: {"선택 금액": won(amount), "분기": choice},
  });
  state.answerParentId = branch.node_id;
  addMessage(state, "user", choice);
  if (choice === "가입 원금으로 확인") {
    state.principal = amount;
    const principal = addUserFact(session, issue, {
      title: "가입 원금: " + won(amount),
      content: "값: " + won(amount),
      raw: String(amount),
      parent_id: branch.node_id,
      details: {"값": won(amount), "신뢰 상태": "사용자 답변 + 분기 확인"},
    });
    state.inputParentId = principal.node_id;
    state.phase = "expected";
    addMessage(state, "assistant", "가입 원금으로 확인했습니다. 만기 때 예상한 이자 금액은 얼마인가요?");
  } else {
    const expected = addUserFact(session, issue, {
      title: "예상 이자: " + won(amount),
      content: "값: " + won(amount),
      raw: String(amount),
      parent_id: branch.node_id,
      details: {"값": won(amount), "신뢰 상태": "사용자 진술 + 분기 확인"},
    });
    state.expectedInterest = amount;
    state.expectedNodeId = expected.node_id;
    state.phase = "actual";
    addMessage(state, "assistant", "예상 이자로 확인했습니다. 실제로 입금된 세후 이자는 얼마였나요?");
  }
}

function handleActual(session, issue, state, raw) {
  const amount = parseAmount(raw);
  if (!amount) {
    addMessage(state, "assistant", "실제 지급 금액을 다시 입력해주세요.");
    return;
  }
  const actual = addUserFact(session, issue, {
    title: "실제 지급 이자: " + won(amount),
    content: "값: " + won(amount),
    raw,
    parent_id: state.answerParentId,
    details: {"값": won(amount), "신뢰 상태": "사용자 진술"},
  });
  state.actualInterest = amount;
  state.actualNodeId = actual.node_id;
  if (state.expectedInterest != null) {
    const difference = state.expectedInterest - state.actualInterest;
    const derived = addNode(session, issue, {
      type: "derived",
      title: "차이 금액: " + won(Math.abs(difference)) + (difference >= 0 ? " 부족" : " 초과"),
      content: "사용자 예상 이자와 실제 지급 이자의 차이입니다.",
      source: "계산 결과",
      parent_id: actual.node_id,
      details: {"노드 유형": "Derived Fact", "산식": won(state.expectedInterest) + " - " + won(state.actualInterest), "결과": won(Math.abs(difference)) + (difference >= 0 ? " 부족" : " 초과")},
    });
    state.taxParentId = derived.node_id;
  } else {
    state.taxParentId = actual.node_id;
  }
  state.phase = "tax_basis";
  addMessage(state, "assistant", "예상하신 금액은 세전 금액인가요, 세후 금액인가요?");
}

function calculateContract(session, issue, state) {
  const gross = Math.round(state.principal * (state.rate / 100) * (state.days / 365));
  const tax = Math.round(gross * .154);
  const net = gross - tax;
  const calculation = addNode(session, issue, {
    type: "derived",
    title: "계약 예상액 " + won(net),
    content: "계약조건 기준 예상 이자",
    source: "계산 결과",
    parent_id: state.inputParentId,
    evidence: issue.evidence_refs || [],
    details: {"가입금액": won(state.principal), "약정금리": "연 " + state.rate + "%", "예치기간": state.days + "일", "세전이자": won(gross), "세금": won(tax), "세후이자": won(net), "산식": "원금 × 연 금리 × 예치기간 / 365", "데이터 출처": "가입금액·금리·기간: 사용자 답변 / 산식: 시스템 계산"},
  });
  state.calculationNodeId = calculation.node_id;
  const comparisonAmount = state.taxBasis === "세전 금액" ? gross : net;
  if (state.expectedInterest != null) {
    const gap = comparisonAmount - state.expectedInterest;
    const comparison = addNode(session, issue, {
      type: "derived",
      title: Math.abs(gap) <= 5000 ? "계약조건 계산액과 유사" : "계약조건 계산액과 차이",
      content: Math.abs(gap) <= 5000 ? "사용자 예상액과 계약조건 기준 계산액이 유사합니다." : "사용자 예상액과 계약조건 기준 계산액의 차이를 추가 확인합니다.",
      source: "비교 결과",
      parent_id: calculation.node_id,
      details: {"사용자 예상액": won(state.expectedInterest), "비교 계산액": won(comparisonAmount), "차이": won(Math.abs(gap)) + (gap >= 0 ? " 많음" : " 적음")},
    });
    if (state.actualInterest != null) {
      const actualGap = comparisonAmount - state.actualInterest;
      addNode(session, issue, {
        type: "derived",
        title: actualGap === 0 ? "계산액과 실제 지급액 일치" : "추가 차이 확인 필요",
        content: actualGap === 0 ? "계약조건 기준 계산액과 실제 지급액이 일치합니다." : "계약조건 기준 계산액과 실제 지급액 사이의 차이를 확인해야 합니다.",
        source: actualGap === 0 ? "계산 결과" : "추가 검증",
        parent_id: comparison.node_id,
        details: {"계약조건 계산액": won(comparisonAmount), "실제 지급 이자": won(state.actualInterest), "추가 차이": won(Math.abs(actualGap))},
      });
    }
  }
  state.phase = "done";
  addMessage(state, "system", "계약조건 계산과 RAG 근거 연결을 완료했습니다.");
}

function chooseTaxBasis(session, issue, state, choice) {
  state.taxBasis = choice;
  addMessage(state, "user", choice);
  const decision = addNode(session, issue, {type: "decision", title: "예상 금액 기준: " + choice, content: choice, source: "사용자 선택", parent_id: state.taxParentId, details: {"선택": choice}});
  if (choice === "잘 모르겠어요") {
    state.decision = "ask";
    state.phase = "done";
    addNode(session, issue, {type: "derived", title: "세전·세후 기준 미확인", content: "예상 금액의 세전·세후 기준을 확인할 수 없어 추가 판단이 필요합니다.", source: "판단 대기", parent_id: decision.node_id, details: {"결정": "ASK", "이유": "예상 금액 기준 미확인"}});
    addMessage(state, "assistant", "세전·세후 기준이 확인되지 않아 추가 확인이 필요한 상태로 남겨둘게요.");
    return;
  }
  const path = addNode(session, issue, {type: "derived", title: choice === "세전 금액" ? "세금 공제 검토 필요" : "금리·기간·우대조건 검증 필요", content: choice === "세전 금액" ? "세전 예상액과 실제 세후 지급액의 세금 공제 여부를 검토합니다." : "세금만으로 차이가 설명되지 않을 수 있어 계약조건을 검증합니다.", source: "검증 경로", parent_id: decision.node_id, details: {"예상 금액 기준": choice, "다음 단계": "계약조건 확인"}});
  state.inputParentId = path.node_id;
  if (state.mockAccount) {
    state.principal = state.mockAccount.principal;
    state.rate = state.mockAccount.applied_rate ? state.mockAccount.applied_rate * 100 : null;
    state.days = 365;
    calculateContract(session, issue, state);
  } else {
    state.phase = "principal";
    addMessage(state, "assistant", "예금 가입금액은 얼마인가요?");
  }
}

function handlePrincipal(session, issue, state, raw) {
  const amount = parseAmount(raw);
  if (!amount) { addMessage(state, "assistant", "가입금액을 다시 입력해주세요."); return; }
  const principal = addUserFact(session, issue, {title: "가입 원금: " + won(amount), content: "값: " + won(amount), raw, parent_id: state.inputParentId, details: {"값": won(amount), "신뢰 상태": "사용자 진술"}});
  state.principal = amount;
  state.inputParentId = principal.node_id;
  state.phase = "rate";
  addMessage(state, "assistant", "가입 당시 안내받은 연 금리는 얼마였나요?");
}

function handleRate(session, issue, state, raw) {
  const rate = parseRate(raw);
  if (rate == null) { addMessage(state, "assistant", "‘연 1.2%’처럼 금리를 입력해주세요."); return; }
  const rateNode = addUserFact(session, issue, {title: "약정 금리: 연 " + rate + "%", content: "값: 연 " + rate + "%", raw, parent_id: state.inputParentId, details: {"값": "연 " + rate + "%", "신뢰 상태": "사용자 진술"}});
  state.rate = rate;
  state.inputParentId = rateNode.node_id;
  state.phase = "period";
  addMessage(state, "assistant", "예치 기간은 1년이었나요?");
}

function handlePeriod(session, issue, state, raw) {
  const days = parseDays(raw);
  if (!days) { addMessage(state, "assistant", "‘1년’ 또는 ‘365일’처럼 입력해주세요."); return; }
  const period = addUserFact(session, issue, {title: "예치 기간: " + days + "일", content: "값: " + days + "일", raw, parent_id: state.inputParentId, details: {"값": days + "일", "신뢰 상태": "사용자 진술"}});
  state.days = days;
  state.inputParentId = period.node_id;
  calculateContract(session, issue, state);
}

function sessionReducer(session, action) {
  if (action.type === "RESET") return createSession(action.analysis);
  if (action.type === "SELECT_ISSUE") return {...session, selectedIssueId: action.issueId, selectedNodeId: null, drawerNodeId: null, drawerIssueId: null};
  if (action.type === "SELECT_NODE") return {...session, selectedIssueId: action.issueId, selectedNodeId: action.nodeId, drawerIssueId: null};
  if (action.type === "OPEN_DRAWER") return {...session, selectedIssueId: action.issueId, selectedNodeId: action.nodeId, drawerNodeId: action.nodeId, drawerIssueId: null};
  if (action.type === "OPEN_ISSUE_REPORT") return {...session, selectedIssueId: action.issueId, selectedNodeId: null, drawerNodeId: null, drawerIssueId: action.issueId};
  if (action.type === "CLOSE_DRAWER") return {...session, drawerNodeId: null, drawerIssueId: null};

  const next = clone(session);
  const issue = getIssue(next, action.issueId || next.selectedIssueId);
  if (!issue) return session;
  const state = next.states[issue.issue_id];
  if (action.type === "ANSWER") {
    const raw = String(action.value || "").trim();
    if (!raw) return session;
    addMessage(state, "user", raw);
    if (state.phase === "expected") handleExpected(next, issue, state, raw);
    else if (state.phase === "actual") handleActual(next, issue, state, raw);
    else if (state.phase === "principal") handlePrincipal(next, issue, state, raw);
    else if (state.phase === "rate") handleRate(next, issue, state, raw);
    else if (state.phase === "period") handlePeriod(next, issue, state, raw);
    else if (state.phase === "done" && state.decision === "ask") {
      const answer = addUserFact(next, issue, {title: "추가 확인 답변", content: raw, raw, details: {"출처": "사용자 진술"}});
      state.inputParentId = answer.node_id;
      addMessage(state, "assistant", "확인했어요. 답변을 확인 자료로 반영했습니다.");
    }
    else addMessage(state, "assistant", "현재 섹션의 확인이 완료되었습니다.");
    return next;
  }
  if (action.type === "EXPECTED_BASIS") {
    chooseExpectedBasis(next, issue, state, action.choice);
    return next;
  }
  if (action.type === "TAX_BASIS") {
    chooseTaxBasis(next, issue, state, action.choice);
    return next;
  }
  return session;
}

function selectedNodePath(nodes, selectedNodeId) {
  const path = new Set();
  let current = nodes.find(function(node) { return node.node_id === selectedNodeId; });
  while (current) {
    path.add(current.node_id);
    current = nodes.find(function(node) { return node.node_id === current.parent_id; });
  }
  return path;
}

function buildFlowGraph(session) {
  if (!(session.analysis.issues || []).length) return {nodes: [], edges: []};
  const graphNodes = [{id: "root", type: "flowNode", data: {kind: "root", title: "복합 금융 문의"}, position: {x: 0, y: 0}}];
  const graphEdges = [];
  const relations = [{id: "root", parent: null}];
  const allNodes = session.analysis.issues || [];

  allNodes.forEach(function(issue, index) {
    const issueId = "issue:" + issue.issue_id;
    const state = session.states[issue.issue_id];
    const control = state.decision || issue.decision?.control || "ask";
    graphNodes.push({id: issueId, type: "flowNode", data: {kind: "issue", issueId: issue.issue_id, letter: issueLetter(index), title: issue.issue_type, product: issue.product, focal: issue.focal?.type, control, controlLabel: label(control)}, position: {x: 0, y: 0}, selected: issue.issue_id === session.selectedIssueId && !session.selectedNodeId});
    relations.push({id: issueId, parent: "root"});
    (state.nodes || []).filter(function(domainNode) { return domainNode.type !== "evidence"; }).forEach(function(domainNode) {
      const id = "fact:" + domainNode.node_id;
      const parent = domainNode.parent_id ? "fact:" + domainNode.parent_id : issueId;
      const path = selectedNodePath(state.nodes, session.selectedNodeId);
      graphNodes.push({id, type: "flowNode", data: {kind: "fact", issueId: issue.issue_id, nodeId: domainNode.node_id, title: domainNode.title, source: NODE_LABEL[domainNode.type] || domainNode.source, createdAt: domainNode.created_at, summary: domainNode.content, nodeType: domainNode.type, path: path.has(domainNode.node_id)}, position: {x: 0, y: 0}, selected: domainNode.node_id === session.selectedNodeId});
      relations.push({id, parent});
    });
  });

  const children = new Map();
  relations.forEach(function(relation) {
    if (!children.has(relation.parent)) children.set(relation.parent, []);
    if (relation.parent !== null) children.get(relation.parent).push(relation.id);
  });
  const positions = {};
  let leaf = 0;
  function layout(id, depth) {
    const childIds = children.get(id) || [];
    if (!childIds.length) {
      positions[id] = {x: depth * 300, y: leaf * 145};
      leaf += 1;
      return positions[id].y;
    }
    const ys = childIds.map(function(childId) { return layout(childId, depth + 1); });
    positions[id] = {x: depth * 300, y: ys.reduce(function(total, value) { return total + value; }, 0) / ys.length};
    return positions[id].y;
  }
  layout("root", 0);
  relations.forEach(function(relation) {
    const position = positions[relation.id] || {x: 0, y: 0};
    const node = graphNodes.find(function(item) { return item.id === relation.id; });
    if (node) node.position = position;
    if (relation.parent) {
      graphEdges.push({id: "auto:" + relation.parent + ":" + relation.id, source: relation.parent, target: relation.id, type: "smoothstep", markerEnd: {type: MarkerType.ArrowClosed, color: "#c8b88f"}});
    }
  });
  return {nodes: graphNodes, edges: graphEdges};
}

function FlowNode({data, selected}) {
  if (data.kind === "root") {
    return <div className={"flow-node root-node" + (selected ? " selected" : "")}><Handle type="source" position={Position.Right} /><strong>{data.title}</strong><span>민원별 분석 트리</span></div>;
  }
  if (data.kind === "issue") {
    return <div className={("flow-node issue-node " + data.control + (selected ? " selected" : ""))}>
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />
      <div className="flow-issue-head"><b>{data.letter}</b><span className="flow-status">{data.controlLabel}</span></div>
      <strong>{data.title}</strong>
      <span>focal: {data.focal || "미확인"}</span>
      <span>product: {data.product}</span>
    </div>;
  }
  return <div className={("flow-node fact-node " + data.nodeType + (data.path ? " path" : "") + (selected ? " selected" : ""))} title={data.summary}>
    <Handle type="target" position={Position.Left} />
    <Handle type="source" position={Position.Right} />
    <div className="flow-fact-title"><i></i><strong>{data.title}</strong></div>
    <span>{data.source}</span>
    <small>{data.createdAt}</small>
  </div>;
}

const nodeTypes = {flowNode: FlowNode};

function StatusSummary({session}) {
  const counts = {proceed: 0, ask: 0, amend: 0, hold: 0};
  (session.analysis.issues || []).forEach(function(issue) { counts[session.states[issue.issue_id].decision || issue.decision?.control || "ask"] += 1; });
  return <div className="summary">{Object.keys(counts).map(function(control) { return <span key={control}><b>{counts[control]}</b> {label(control)}</span>; })}</div>;
}

function Intake({onAnalyze}) {
  const [prompt, setPrompt] = useState("");
  const [fileName, setFileName] = useState("선택된 파일 없음");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("문의 내용을 입력해 주세요.");
  const fileRef = useRef(null);
  async function submit(event) {
    event.preventDefault();
    setLoading(true);
    const result = await onAnalyze(prompt);
    setNotice(result.notice);
    setLoading(false);
  }
  return <section className="intake">
    <h1>복합 금융 문의</h1>
    <p>여러 금융 문제를 한 번에 입력하면 민원별로 나누어 분석합니다.</p>
    <form onSubmit={submit}>
      <textarea required value={prompt} onChange={function(event) { setPrompt(event.target.value); }} placeholder="예: 예금 만기 이자가 예상과 다르고, 적금 금리 변경 안내도 받지 못했습니다." />
      <div className="form-actions"><div><input ref={fileRef} type="file" hidden multiple onChange={function(event) { const files = Array.from(event.target.files || []); setFileName(files.length ? files.map(function(file) { return file.name; }).join(", ") : "선택된 파일 없음"); }} /><button className="file-button" type="button" onClick={function() { fileRef.current?.click(); }}>파일 첨부</button><span className="file-name">{fileName}</span></div><button className="submit-button" disabled={loading} type="submit">{loading ? "분석 중..." : "민원 분석"}</button></div>
    </form>
    <p className="notice">{notice}</p>
  </section>;
}

function ChatPanel({issue, state, index, draft, setDraft, dispatch, onAnalyze}) {
  useEffect(function() { setDraft(""); }, [issue?.issue_id, state?.phase, setDraft]);
  if (!issue || !state) return <aside className="panel chat-panel"><div className="chat-content"><div className="empty-chat"><strong>상담을 시작하세요</strong><span>아래 입력창에 금융 문의를 작성하면 민원별 트리가 생성됩니다.</span></div></div><Intake onAnalyze={onAnalyze} /></aside>;
  const choices = state.phase === "expected_basis" ? ["가입 원금으로 확인", "예상 이자로 확인"] : state.phase === "tax_basis" ? ["세전 금액", "세후 금액", "잘 모르겠어요"] : [];
  const inputEnabled = !["done", "expected_basis", "tax_basis"].includes(state.phase) || (state.phase === "done" && state.decision === "ask");
  function submit(event) {
    event.preventDefault();
    dispatch({type: "ANSWER", value: draft});
    setDraft("");
  }
  return <aside className="panel chat-panel">
    <div className="chat-content">
      <div className="chat-head"><div><span className="chat-label">현재 상담 · 섹션 {issueLetter(index)}</span><h2>{issue.issue_type}</h2><p>답변에 따라 왼쪽 트리에 사실·분기·계산 노드가 추가됩니다.</p></div><span className={"status " + state.decision}>{label(state.decision)}</span></div>
      <div className="chat-messages">{state.messages.map(function(message, index) { return <div className={"message " + message.role} key={index}>{message.text}</div>; })}</div>
      {choices.length > 0 && <div className="chat-options" aria-label="분기 선택">{choices.map(function(choice) { return <button className="chat-option" key={choice} type="button" onClick={function() { dispatch({type: state.phase === "expected_basis" ? "EXPECTED_BASIS" : "TAX_BASIS", choice}); }}>{choice}</button>; })}</div>}
      {inputEnabled ? <form className="chat-composer" onSubmit={submit}><input value={draft} onChange={function(event) { setDraft(event.target.value); }} autoComplete="off" placeholder="답변을 입력하세요" /><button className="chat-send" type="submit">전송</button></form> : <div className="chat-composer"><button className="chat-send" type="button" disabled>상담 기록 생성됨</button></div>}
    </div>
    <Intake onAnalyze={onAnalyze} />
  </aside>;
}

function DetailDrawer({node, onClose, onEdit}) {
  const evidenceRef = useRef(null);
  if (!node) return null;
  return <div className="drawer-backdrop" onClick={onClose}>
    <aside className="detail-drawer" role="dialog" aria-modal="true" aria-label="노드 상세" onClick={function(event) { event.stopPropagation(); }}>
      <div className="drawer-head"><div><span className="chat-label">{NODE_LABEL[node.type] || node.source}</span><h2>{node.title}</h2></div><button className="drawer-close" type="button" onClick={onClose}>닫기</button></div>
      <div className="drawer-section"><h3>노드 정보</h3>{Object.entries(node.details || {}).map(function(entry) { return <div className="drawer-row" key={entry[0]}><span>{entry[0]}</span><span>{valueText(entry[1])}</span></div>; })}<div className="drawer-row"><span>출처</span><span>{node.source}</span></div><div className="drawer-row"><span>확인 시각</span><span>{node.created_at}</span></div></div>
      <div className="drawer-section"><h3>내용</h3><p>{node.content}</p></div>
      {node.conversation?.length > 0 && <div className="drawer-section"><h3>관련 대화</h3>{node.conversation.map(function(item, index) { return <p key={index}><strong>{item.role}:</strong> {item.text}</p>; })}</div>}
      {node.evidence?.length > 0 && <div className="drawer-section" ref={evidenceRef}><h3>관련 근거</h3><ul>{node.evidence.map(function(ref) { return <li key={ref.doc_id}>{ref.doc_id} · p.{ref.page} · {ref.snippet}</li>; })}</ul></div>}
      <div className="drawer-actions">{node.type === "user_answer" && <button type="button" onClick={function() { onEdit(node); }}>답변 수정</button>}<button type="button" onClick={function() { evidenceRef.current?.scrollIntoView({behavior: "smooth"}); }}>관련 근거 보기</button><button type="button" onClick={onClose}>축소</button></div>
    </aside>
  </div>;
}

function IssueReportDrawer({issue, state, index, onClose}) {
  const [openCandidate, setOpenCandidate] = useState(null);
  useEffect(function() { setOpenCandidate(null); }, [issue?.issue_id]);
  if (!issue || !state) return null;
  const decision = state.decision || issue.decision?.control || "ask";
  const facts = (issue.facts || []).map(function(fact) {
    return {title: fact.field, value: valueText(fact.value), source: fact.source_ref ? "검증된 사실" : "분석 입력"};
  });
  const sessionFacts = (state.nodes || [])
    .filter(function(node) { return node.type !== "evidence"; })
    .map(function(node) { return {title: node.title, value: node.content, source: node.source}; });
  const candidates = issue.evidence_refs || [];
  const report = issue.report || {
    complaint_content: issue.text || issue.issue_type,
    issue: issue.issue_type,
    processing_result: "현재 확인된 사실과 검색 후보자료를 바탕으로 리포트를 생성했습니다.",
    consumer_cautions: issue.next_steps || [],
    used_evidence_chunk_ids: [],
    current_decision: decisionLabel(decision),
    reasoning: "현재 확인된 사실과 검색 후보자료를 바탕으로 리포트를 생성했습니다.",
    follow_up_actions: issue.next_steps || [],
    generated_by: "fallback",
  };
  return <div className="drawer-backdrop" onClick={onClose}>
    <aside className="detail-drawer report-drawer" role="dialog" aria-modal="true" aria-label="민원 판단 리포트" onClick={function(event) { event.stopPropagation(); }}>
      <div className="drawer-head">
        <div><span className="chat-label">섹션 {issueLetter(index)} · 판단 리포트</span><h2>{issue.issue_type}</h2><p className="report-type">민원 유형: {issue.product} · {report.issue || issue.issue_type}</p></div>
        <button className="drawer-close" type="button" onClick={onClose}>닫기</button>
      </div>
      <div className="report-decision"><span>현재 판단</span><strong className={decision}>{report.current_decision}</strong></div>
      <div className="drawer-section report-main">
        <h3>민원내용</h3>
        <p className="report-copy report-reasoning">{report.complaint_content || issue.text}</p>
        <h3>쟁점</h3>
        <p className="report-copy report-reasoning">{report.issue || issue.issue_type}</p>
        <h3>처리결과</h3>
        <p className="report-copy report-reasoning">{report.processing_result || report.reasoning}</p>
        <h3>소비자 유의사항</h3>
        {(report.consumer_cautions || report.follow_up_actions || []).map(function(caution, cautionIndex) { return <p className="report-bullet" key={cautionIndex}>• {caution}</p>; })}
        {(issue.decision?.risk_flags || []).length > 0 && <p className="report-risk">위험 신호: {issue.decision.risk_flags.join(", ")}</p>}
      </div>
      <div className="drawer-section">
        <h3>확인된 사실</h3>
        {facts.length === 0 && sessionFacts.length === 0 && <p className="report-empty">아직 확인된 사실이 없습니다.</p>}
        {[...facts, ...sessionFacts].map(function(fact, factIndex) { return <div className="report-fact" key={fact.title + factIndex}><div><strong>{fact.title}</strong><p>{fact.value}</p></div><span>{fact.source}</span></div>; })}
      </div>
      <div className="drawer-section">
        <div className="report-section-head"><h3>RAG 검색 후보자료</h3><span>{candidates.length}건</span></div>
        <p className="report-copy">검색 상위 자료이며, 모두 최종 판단 근거로 확정된 것은 아닙니다.</p>
        {candidates.length === 0 && <p className="report-empty">검색된 후보자료가 없습니다.</p>}
        <ol className="candidate-list">
          {candidates.map(function(ref, refIndex) {
            const candidateId = ref.chunk_id || ref.doc_id + refIndex;
            const expanded = openCandidate === candidateId;
            const usedForResult = (report.used_evidence_chunk_ids || []).includes(ref.chunk_id);
            return <li key={candidateId}>
              <button className="candidate-toggle" type="button" onClick={function() { setOpenCandidate(expanded ? null : candidateId); }} aria-expanded={expanded}>
                <span>
                  <span className="candidate-head"><strong>후보 {refIndex + 1}</strong><em>{usedForResult ? "판단 근거" : "검토 후보"}</em></span>
                  <strong>{ref.section || ref.doc_id}</strong>
                  <small>{ref.path || ref.doc_id} · p.{ref.page}</small>
                </span>
                <b>{expanded ? "−" : "+"}</b>
              </button>
              {expanded && <div className="candidate-detail">
                <div><span>문서</span><strong>{ref.path || ref.doc_id}</strong></div>
                <div><span>페이지</span><strong>p.{ref.page}</strong></div>
                {ref.section && <div><span>조항</span><strong>{ref.section}</strong></div>}
                <p>{ref.snippet}</p>
              </div>}
            </li>;
          })}
        </ol>
      </div>
      <div className="drawer-actions"><button type="button" onClick={onClose}>리포트 닫기</button></div>
    </aside>
  </div>;
}

function PageNav({page, onNavigate}) {
  return <nav className="page-nav" aria-label="주요 메뉴">
    <button className={page === "mypage" ? "active" : ""} type="button" onClick={function() { onNavigate("mypage"); }}>마이 페이지</button>
    <button className={page === "chat" ? "active" : ""} type="button" onClick={function() { onNavigate("chat"); }}>민원 상담</button>
    <button className={page === "reports" ? "active" : ""} type="button" onClick={function() { onNavigate("reports"); }}>생성된 민원</button>
  </nav>;
}

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "날짜 미확인" : date.toLocaleString("ko-KR", {dateStyle: "medium", timeStyle: "short"});
}

function MyPage({history, onNavigate}) {
  const [financial, setFinancial] = useState({deposits: [], savings: [], loans: [], loading: true});

  useEffect(function() {
    let alive = true;
    Promise.all([
      fetch(API_BASE + "/mock/customers/CUST-001/deposits").then(function(response) { return response.ok ? response.json() : []; }),
      fetch(API_BASE + "/mock/customers/CUST-001/savings").then(function(response) { return response.ok ? response.json() : []; }),
      fetch(API_BASE + "/mock/customers/CUST-001/loans").then(function(response) { return response.ok ? response.json() : []; }),
    ]).then(function(values) {
      if (alive) setFinancial({deposits: values[0], savings: values[1], loans: values[2], loading: false});
    }).catch(function() {
      if (alive) setFinancial({deposits: [], savings: [], loans: [], loading: false});
    });
    return function() { alive = false; };
  }, []);

  return <main className="page-shell my-page">
    <div className="page-title"><div><span className="eyebrow">MY FINANCE</span><h1>마이 페이지</h1><p>민원 진행 상황과 연결된 금융 정보를 한 곳에서 확인합니다.</p></div><button className="primary-action" type="button" onClick={function() { onNavigate("chat"); }}>새 민원 상담</button></div>
    <section className="profile-card panel"><div><span className="eyebrow">본인 정보</span><h2>김민지</h2><p>CUST-001 · 본인인증 완료 · 정보 제공 동의 완료</p></div><div className="profile-badge">안전하게 연결됨</div></section>
    <section className="my-grid">
      <div className="panel complaint-history"><div className="card-head"><div><h2>민원 목록</h2><p>최근 접수 순으로 확인합니다.</p></div><strong>{history.length}건</strong></div>
        {history.length === 0 ? <div className="empty-state">아직 접수한 민원이 없습니다.<button type="button" onClick={function() { onNavigate("chat"); }}>민원 작성하기</button></div> : <div className="history-list">{history.map(function(record) {
          const status = caseStatus(record.analysis);
          return <article className="history-item" key={record.case_id}><div className="history-item-head"><span>{formatDate(record.created_at)}</span><b className={status}>{CASE_STATUS_LABEL[status]}</b></div><strong>{record.prompt || "복합 금융 문의"}</strong><div className="history-issues">{(record.analysis?.issues || []).map(function(issue) { const issueStatus = issue.decision?.control || "ask"; return <span key={issue.issue_id}>{issue.product} · {issue.issue_type} <em className={issueStatus}>{CASE_STATUS_LABEL[issueStatus]}</em></span>; })}</div><small>{record.case_id}</small></article>;
        })}</div>}
      </div>
      <div className="panel finance-status"><div className="card-head"><div><h2>내 금융 상황</h2><p>가상 금융 데이터 연결 기준</p></div><span className="connected-dot">연결됨</span></div>{financial.loading ? <div className="empty-state compact">금융 정보를 불러오는 중입니다.</div> : <div className="finance-groups">
        <FinanceGroup title="예금" items={financial.deposits} renderItem={function(item) { return <><strong>{item.product_name}</strong><span>가입금액 {won(item.principal)}</span><span>적용금리 연 {Number(item.applied_rate || 0) * 100}% · {item.status === "matured" ? "만기" : "가입 중"}</span></>; }} />
        <FinanceGroup title="적금" items={financial.savings} renderItem={function(item) { return <><strong>{item.product_name}</strong><span>적용금리 연 {Number(item.applied_rate || 0) * 100}%</span><span>우대조건 {item.preferential_conditions?.[0]?.status === "failed" ? "미충족" : "확인 필요"}</span></>; }} />
        <FinanceGroup title="대출" items={financial.loans} renderItem={function(item) { return <><strong>{item.product_name}</strong><span>현재 잔액 {won(item.outstanding_balance)} · {item.repayment_method}</span><span>적용금리 연 {Number(item.applied_rate || 0) * 100}% · {item.delinquency_status || "상태 확인 필요"}</span></>; }} />
        <FinanceGroup title="투자" items={[]} renderItem={function() { return <><strong>연결된 투자 상품 없음</strong><span>투자 계좌를 연결하면 이곳에서 확인할 수 있습니다.</span></>; }} />
      </div>}</div>
    </section>
  </main>;
}

function FinanceGroup({title, items, renderItem}) {
  const rows = items.length ? items : [{}];
  return <section className="finance-group"><h3>{title}</h3>{rows.map(function(item, index) { return <div className="finance-item" key={item.account_id || title + index}>{renderItem(item)}</div>; })}</section>;
}

function ReportBlock({title, children}) {
  return <section className="report-block"><h2>{title}</h2><div>{children}</div></section>;
}

function GeneratedComplaintsPage({history, onNavigate}) {
  const reports = completedIssues(history);
  const [selectedId, setSelectedId] = useState(reports[0]?.issue_id || null);
  const [dictionaryTerms, setDictionaryTerms] = useState({});
  const selected = reports.find(function(issue) { return issue.issue_id === selectedId; }) || reports[0];
  useEffect(function() { if (!selected && reports[0]) setSelectedId(reports[0].issue_id); }, [reports, selected]);
  const terms = selected ? termsForIssue(selected) : [];
  useEffect(function() {
    if (!selected) return;
    Promise.all(terms.map(function(term) {
      return fetch(API_BASE + "/dictionary/search?q=" + encodeURIComponent(term) + "&limit=1")
        .then(function(response) { return response.ok ? response.json() : []; })
        .then(function(items) { return [term, items[0]?.definition || ""]; })
        .catch(function() { return [term, ""]; });
    })).then(function(entries) { setDictionaryTerms(Object.fromEntries(entries)); });
  }, [selected?.issue_id]);

  if (!selected) return <main className="page-shell generated-page"><div className="page-title"><div><span className="eyebrow">COMPLETED CASES</span><h1>생성된 민원</h1><p>처리가 완료된 민원 리포트만 표시합니다.</p></div></div><div className="panel empty-page"><strong>완료된 민원 리포트가 없습니다.</strong><span>민원 상담을 완료하면 이곳에 처리 결과가 저장됩니다.</span><button className="primary-action" type="button" onClick={function() { onNavigate("chat"); }}>민원 상담 시작</button></div></main>;

  const report = selected.report || {complaint_content: selected.text || selected.issue_type, processing_result: selected.next_steps?.join("\n") || "검색된 약관과 사실을 기준으로 처리 결과를 정리했습니다.", consumer_cautions: selected.next_steps || []};
  const candidates = selected.evidence_refs || [];
  return <main className="page-shell generated-page">
    <div className="page-title"><div><span className="eyebrow">COMPLETED CASES</span><h1>생성된 민원</h1><p>완료된 민원의 처리 결과와 판단 근거를 확인합니다.</p></div><span className="completed-count">완료 {reports.length}건</span></div>
    <div className="report-layout">
      <aside className="panel report-list"><div className="card-head"><h2>완료 목록</h2></div>{reports.map(function(issue) { return <button className={"report-list-item" + (issue.issue_id === selected.issue_id ? " active" : "")} type="button" key={issue.issue_id} onClick={function() { setSelectedId(issue.issue_id); }}><span>{issue.product}</span><strong>{issue.issue_type}</strong><small>{formatDate(issue.created_at)}</small></button>; })}</aside>
      <article className="panel generated-report"><div className="generated-report-head"><div><span className="eyebrow">민원 리포트 · {selected.product}</span><h2>{selected.issue_type}</h2><p>{formatDate(selected.created_at)} · {selected.case_id}</p></div><b className="complete-badge">처리 완료</b></div>
        <ReportBlock title="민원내용"><p>{report.complaint_content || selected.issue_type}</p></ReportBlock>
        <ReportBlock title="처리결과"><p className="report-result">{report.processing_result || report.reasoning || "검색된 근거자료를 바탕으로 처리 결과를 생성했습니다."}</p></ReportBlock>
        <ReportBlock title="소비자 유의사항">{(report.consumer_cautions || report.follow_up_actions || selected.next_steps || []).map(function(item, index) { return <p className="report-bullet" key={index}>• {item}</p>; })}</ReportBlock>
      </article>
      <aside className="panel report-insights"><section><div className="card-head"><div><h2>금융 용어</h2><p>사전에서 쉽게 풀어쓴 설명</p></div><span>{terms.length}개</span></div>{terms.map(function(term) { return <div className="term-card" key={term}><strong>{term}</strong><p>{dictionaryTerms[term] || TERM_DICTIONARY[term]}</p></div>; })}</section><section className="evidence-summary"><div className="card-head"><div><h2>근거 기반 결론</h2><p>RAG가 검색한 자료 기반</p></div><span>{candidates.length}건</span></div><p className="insight-conclusion">{report.processing_result || report.reasoning || "검색된 근거자료를 바탕으로 처리 결과를 생성했습니다."}</p>{candidates.length === 0 ? <p className="empty-copy">연결된 근거자료가 없습니다.</p> : candidates.map(function(ref, index) { return <article className="evidence-card" key={(ref.chunk_id || ref.doc_id || "ref") + index}><strong>[{sourceLabel(ref)}]</strong><p>{ref.snippet || "관련 조항의 적용 내용을 확인했습니다."}</p><small>{ref.page ? "p." + ref.page : "관련 문서"}</small></article>; })}</section></aside>
    </div>
  </main>;
}

function App() {
  const [session, dispatch] = useReducer(sessionReducer, EMPTY_ANALYSIS, createSession);
  const [draft, setDraft] = useState("");
  const [page, setPage] = useState(function() { return window.location.hash.slice(1) || "chat"; });
  const [history, setHistory] = useState(readCaseHistory);
  const [flowNodes, setFlowNodes] = useState([]);
  const [flowEdges, setFlowEdges] = useState([]);
  const positions = useRef({});
  const graph = useMemo(function() { return buildFlowGraph(session); }, [session]);
  const selectedIssue = getIssue(session);
  const selectedState = selectedIssue ? session.states[selectedIssue.issue_id] : null;
  const selectedIssueIndex = (session.analysis.issues || []).findIndex(function(issue) { return issue.issue_id === selectedIssue?.issue_id; });
  const selectedNode = selectedIssue && session.drawerNodeId ? selectedState.nodes.find(function(node) { return node.node_id === session.drawerNodeId; }) : null;
  const reportIssue = session.drawerIssueId ? getIssue(session, session.drawerIssueId) : null;
  const reportState = reportIssue ? session.states[reportIssue.issue_id] : null;

  useEffect(function() {
    const onHashChange = function() { setPage(window.location.hash.slice(1) || "chat"); };
    window.addEventListener("hashchange", onHashChange);
    return function() { window.removeEventListener("hashchange", onHashChange); };
  }, []);

  function navigate(nextPage) {
    window.location.hash = nextPage;
    setPage(nextPage);
  }

  useEffect(function() {
    setFlowNodes(function(current) {
      return graph.nodes.map(function(node) {
        const previous = current.find(function(item) { return item.id === node.id; });
        return {...node, position: positions.current[node.id] || previous?.position || node.position};
      });
    });
    setFlowEdges(function(current) {
      const nodeIds = new Set(graph.nodes.map(function(node) { return node.id; }));
      const automaticIds = new Set(graph.edges.map(function(edge) { return edge.id; }));
      const manual = current.filter(function(edge) { return !automaticIds.has(edge.id) && nodeIds.has(edge.source) && nodeIds.has(edge.target); });
      return [...graph.edges, ...manual];
    });
  }, [graph]);

  const onNodesChange = useCallback(function(changes) {
    changes.forEach(function(change) { if (change.type === "position" && change.position) positions.current[change.id] = change.position; });
    setFlowNodes(function(nodes) { return applyNodeChanges(changes, nodes); });
  }, []);
  const onEdgesChange = useCallback(function(changes) { setFlowEdges(function(edges) { return applyEdgeChanges(changes, edges); }); }, []);
  const onConnect = useCallback(function(params) { setFlowEdges(function(edges) { return addEdge({...params, type: "smoothstep", markerEnd: {type: MarkerType.ArrowClosed, color: "#c8b88f"}}, edges); }); }, []);
  const onNodeClick = useCallback(function(_, node) {
    if (node.data.kind === "issue") dispatch({type: "SELECT_ISSUE", issueId: node.data.issueId});
    if (node.data.kind === "fact") dispatch({type: "SELECT_NODE", issueId: node.data.issueId, nodeId: node.data.nodeId});
  }, []);
  const onNodeDoubleClick = useCallback(function(_, node) {
    if (node.data.kind === "issue") dispatch({type: "OPEN_ISSUE_REPORT", issueId: node.data.issueId});
    if (node.data.kind === "fact") dispatch({type: "OPEN_DRAWER", issueId: node.data.issueId, nodeId: node.data.nodeId});
  }, []);

  async function analyze(prompt) {
    if (DEMO_ONLY) {
      dispatch({type: "RESET", analysis: DEMO_ANALYSIS});
      setHistory(rememberCase(DEMO_ANALYSIS, prompt));
      return {notice: "서버 없이 실행 중인 데모 모드입니다."};
    }
    try {
      const response = await fetch(API_BASE + "/api/v1/cases/analyze", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({prompt, customer_id: "CUST-001"})});
      if (!response.ok) throw new Error("HTTP " + response.status);
      const analysis = await response.json();
      dispatch({type: "RESET", analysis});
      setHistory(rememberCase(analysis, prompt));
      return {notice: "분석 결과를 표시했습니다."};
    } catch (error) {
      return {notice: "서버에 연결할 수 없습니다. 데모 결과를 유지합니다."};
    }
  }

  function editAnswer(node) {
    setDraft(node.raw || "");
    dispatch({type: "CLOSE_DRAWER"});
  }

  return <div className="app">
    <header className="topbar"><div className="brand"><img src="/images.png" alt="KB" /><div><strong>KB Key Buddy</strong><span>금융 소비자 보호 에이전트</span></div></div><PageNav page={page} onNavigate={navigate} /><div className="case-id">{session.analysis.case_id !== "new_case" ? session.analysis.case_id : "내 금융"}</div></header>
    {page === "mypage" ? <MyPage history={history} onNavigate={navigate} /> : page === "reports" ? <GeneratedComplaintsPage history={history} onNavigate={navigate} /> : <>
      <main className="workspace">
        <section className="panel case-panel"><div className="section-head"><div><h2>민원 흐름 트리</h2><p>노드를 드래그하고, 화면을 이동하거나 확대·축소할 수 있습니다.</p></div><StatusSummary session={session} /></div><div className="flow-shell">{flowNodes.length === 0 && <div className="flow-empty"><strong>아직 분석된 민원이 없습니다.</strong><span>오른쪽 입력창에 문의를 작성해 주세요.</span></div>}<ReactFlow nodes={flowNodes} edges={flowEdges} nodeTypes={nodeTypes} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} onNodeClick={onNodeClick} onNodeDoubleClick={onNodeDoubleClick} fitView fitViewOptions={{padding: .18}} minZoom={.2} maxZoom={2} panOnDrag zoomOnScroll nodesConnectable selectionOnDrag><MiniMap pannable zoomable /><Controls /><Background gap={22} size={1} color="#eadfca" /></ReactFlow></div></section>
        <ChatPanel issue={selectedIssue} state={selectedState} index={selectedIssueIndex < 0 ? 0 : selectedIssueIndex} draft={draft} setDraft={setDraft} dispatch={dispatch} onAnalyze={analyze} />
      </main>
      <DetailDrawer node={selectedNode} onClose={function() { dispatch({type: "CLOSE_DRAWER"}); }} onEdit={editAnswer} />
      <IssueReportDrawer issue={reportIssue} state={reportState} index={reportIssue ? (session.analysis.issues || []).findIndex(function(issue) { return issue.issue_id === reportIssue.issue_id; }) : 0} onClose={function() { dispatch({type: "CLOSE_DRAWER"}); }} />
    </>}
  </div>;
}

createRoot(document.getElementById("root")).render(<App />);
