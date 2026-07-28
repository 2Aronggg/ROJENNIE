from __future__ import annotations

from server.schemas import CaseAnalysis, LogicEdge, LogicGraph, LogicNode


VISIBLE_FACT_FIELDS = {
    "amount",
    "date_or_duration",
    "institution",
    "product_name",
    "rate",
    "requested_action",
}


def build_logic_graph(case: CaseAnalysis) -> LogicGraph:
    nodes = [
        LogicNode(
            node_id=f"case:{case.case_id}",
            node_type="case",
            label=case.case_id,
        )
    ]
    edges: list[LogicEdge] = []

    for issue in case.issues:
        issue_id = f"issue:{issue.issue_id}"
        condition_id = f"condition:{issue.issue_id}"
        decision_id = f"decision:{issue.issue_id}"
        answer_id = f"answer:{issue.issue_id}"
        nodes.extend(
            [
                LogicNode(
                    node_id=issue_id,
                    node_type="issue",
                    label=issue.issue_type,
                    attributes={"product": issue.product},
                ),
                LogicNode(
                    node_id=condition_id,
                    node_type="condition",
                    label=issue.issue_type,
                    attributes={"missing_facts": issue.missing_facts},
                ),
                LogicNode(
                    node_id=decision_id,
                    node_type="decision",
                    label=issue.decision.control,
                    attributes={"risk_flags": issue.decision.risk_flags},
                ),
                LogicNode(
                    node_id=answer_id,
                    node_type="answer",
                    label="next_steps",
                    attributes={"next_steps": issue.next_steps},
                ),
            ]
        )
        edges.extend(
            [
                LogicEdge(source=f"case:{case.case_id}", target=issue_id, relation="contains"),
                LogicEdge(source=issue_id, target=condition_id, relation="tests"),
                LogicEdge(source=condition_id, target=decision_id, relation="leads_to"),
                LogicEdge(source=decision_id, target=answer_id, relation="produces"),
            ]
        )

        if issue.focal:
            focal_id = f"focal:{issue.issue_id}"
            nodes.append(
                LogicNode(
                    node_id=focal_id,
                    node_type="focal",
                    label=str(issue.focal.get("type", "focal")),
                    attributes={"keys": sorted(issue.focal)},
                )
            )
            edges.append(LogicEdge(source=issue_id, target=focal_id, relation="focuses_on"))

        if issue.target:
            target_id = f"target:{issue.issue_id}"
            nodes.append(
                LogicNode(
                    node_id=target_id,
                    node_type="target",
                    label="action_target",
                    attributes={"keys": sorted(issue.target)},
                )
            )
            edges.append(LogicEdge(source=issue_id, target=target_id, relation="targets"))

        for index, fact in enumerate(issue.facts):
            fact_id = f"fact:{issue.issue_id}:{index}"
            value = fact.value if fact.field in VISIBLE_FACT_FIELDS else "[redacted]"
            nodes.append(
                LogicNode(
                    node_id=fact_id,
                    node_type="fact",
                    label=fact.field,
                    attributes={
                        "value": value,
                        "event_date": fact.event_date,
                        "recorded_date": fact.recorded_date,
                        "confidence": fact.confidence,
                    },
                )
            )
            edges.append(LogicEdge(source=issue_id, target=fact_id, relation="has_fact"))

        for evidence in issue.evidence_refs:
            evidence_id = f"evidence:{evidence.chunk_id}"
            nodes.append(
                LogicNode(
                    node_id=evidence_id,
                    node_type="evidence",
                    label=evidence.chunk_id,
                    attributes={
                        "doc_id": evidence.doc_id,
                        "page": evidence.page,
                        "section": evidence.section,
                        "effective_from": evidence.effective_from,
                        "match_type": evidence.match_type,
                    },
                )
            )
            edges.append(LogicEdge(source=condition_id, target=evidence_id, relation="supported_by"))

    return LogicGraph(nodes=nodes, edges=edges)