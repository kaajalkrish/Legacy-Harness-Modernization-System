# Gaps and Assumptions Register

Total gaps: **26**  ·  critical: 0  ·  high: 3  ·  medium: 13  ·  low: 10

| Gap ID | Severity | Type | Description | Source |
|---|---|---|---|---|
| GAP-001 | HIGH | circular_copy | Circular COPY chain detected: CKPRST COPY CKPRST which COPYs CKPRST | inventory |
| GAP-002 | HIGH | empty_source | POSUPDT.cbl is empty — no program logic. | logic |
| GAP-003 | HIGH | truncated_source | CURSMGR.cbl truncated — fetch/close paragraphs missing though INQHIST depends on them. | logic |
| GAP-004 | MEDIUM | unresolved_reference | CALL target 'DELAY' not found in file registry — may be external or in load library | inventory |
| GAP-005 | MEDIUM | unresolved_reference | CICS_LINK target 'DB2ONLN' not found in file registry | inventory |
| GAP-006 | MEDIUM | unresolved_reference | CICS_LINK target 'DB2RECV' not found in file registry | inventory |
| GAP-007 | MEDIUM | unresolved_reference | CICS_LINK target 'ERRHNDL' not found in file registry | inventory |
| GAP-008 | MEDIUM | unresolved_reference | CICS_LINK target 'SECMGR' not found in file registry | inventory |
| GAP-009 | MEDIUM | unresolved_reference | CICS_LINK target 'SECMGR' not found in file registry | inventory |
| GAP-010 | MEDIUM | unresolved_reference | CICS_LINK target 'SECMGR' not found in file registry | inventory |
| GAP-011 | MEDIUM | unresolved_reference | SQL INCLUDE target 'SQLPOS' not found in file registry | inventory |
| GAP-012 | MEDIUM | skeletons | BCHCTL00, CKPRST, TSTVAL00, UTLVAL00 are skeletons — dispatch logic present but low-level sub-paragraphs / operation bodies unimplemented. | logic |
| GAP-013 | MEDIUM | rule_sme_review | BR-030 “Validate End Of Session (88 session Terminated)” — low confidence, requires SME confirmation. | rules |
| GAP-014 | MEDIUM | rule_sme_review | BR-032 “Validate End Of Tests” — low confidence, requires SME confirmation. | rules |
| GAP-015 | MEDIUM | rule_sme_review | BR-034 “Validate End Of Val” — low confidence, requires SME confirmation. | rules |
| GAP-016 | MEDIUM | rule_sme_review | BR-069 “Validate Position Found (88 position Exists)” — low confidence, requires SME confirmation. | rules |
| GAP-017 | LOW | complete_run | All 21 sample programs explained (no key, in-session). | logic |
| GAP-018 | LOW | notable_findings | INQONLN validates security AFTER dispatching the function; PORTADD/PORTREAD/PORTUPDT terminate-without-stopping on open failure; PORTUPDT/PORTMSTR EVALUATEs lack WHEN OTHER; INQHIST DB2 retry is unbounded recursion. | logic |
| GAP-019 | LOW | ambiguous_logic | INQHIST: 1 paragraph(s) flagged ambiguous during pseudocode extraction. | logic |
| GAP-020 | LOW | ambiguous_logic | PORTMSTR: 2 paragraph(s) flagged ambiguous during pseudocode extraction. | logic |
| GAP-021 | LOW | ambiguous_logic | BCHCTL00: 4 paragraph(s) flagged ambiguous during pseudocode extraction. | logic |
| GAP-022 | LOW | ambiguous_logic | CKPRST: 4 paragraph(s) flagged ambiguous during pseudocode extraction. | logic |
| GAP-023 | LOW | ambiguous_logic | DB2STAT: 1 paragraph(s) flagged ambiguous during pseudocode extraction. | logic |
| GAP-024 | LOW | ambiguous_logic | CURSMGR: 2 paragraph(s) flagged ambiguous during pseudocode extraction. | logic |
| GAP-025 | LOW | ambiguous_logic | TSTVAL00: 2 paragraph(s) flagged ambiguous during pseudocode extraction. | logic |
| GAP-026 | LOW | ambiguous_logic | UTLVAL00: 4 paragraph(s) flagged ambiguous during pseudocode extraction. | logic |
