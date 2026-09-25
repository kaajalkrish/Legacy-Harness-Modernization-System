# Gaps and Assumptions Register

Total gaps: **16**  ·  critical: 0  ·  high: 0  ·  medium: 11  ·  low: 5

| Gap ID | Severity | Type | Description | Source |
|---|---|---|---|---|
| GAP-001 | MEDIUM | unresolved_reference | SQL_INCLUDE target 'DCLTRCAT' is not in the repository (referenced by COTRTUPC) — its definition is needed to complete the data model / call graph. | inventory |
| GAP-002 | MEDIUM | unresolved_reference | SQL_INCLUDE target 'DCLTRTYP' is not in the repository (referenced by COBTUPDT, COTRTLIC, COTRTUPC) — its definition is needed to complete the data model / call graph. | inventory |
| GAP-003 | MEDIUM | rule_sme_review | BR-004 “Delete a user only after the deletion is confirmed” — low confidence, requires SME confirmation. | rules |
| GAP-004 | MEDIUM | rule_sme_review | BR-005 “Default a zero cycle debit to 2525.00 in the account extract” — low confidence, requires SME confirmation. | rules |
| GAP-005 | MEDIUM | rule_sme_review | BR-019 “Reject a transaction dated after the account expiration date” — low confidence, requires SME confirmation. | rules |
| GAP-006 | MEDIUM | rule_sme_review | BR-022 “Add a transaction only when its key and data fields are valid” — low confidence, requires SME confirmation. | rules |
| GAP-007 | MEDIUM | rule_sme_review | BR-026 “Refuse a bill payment when there is nothing to pay” — low confidence, requires SME confirmation. | rules |
| GAP-008 | MEDIUM | rule_sme_review | BR-027 “Pay the full outstanding balance only after the user confirms” — low confidence, requires SME confirmation. | rules |
| GAP-009 | MEDIUM | rule_sme_review | BR-028 “Report only transactions processed within the requested date range” — low confidence, requires SME confirmation. | rules |
| GAP-010 | MEDIUM | rule_sme_review | BR-032 “Delete a pending-authorization detail that qualifies for deletion” — low confidence, requires SME confirmation. | rules |
| GAP-011 | MEDIUM | rule_sme_review | BR-033 “Delete an authorization summary with no approved authorizations left” — low confidence, requires SME confirmation. | rules |
| GAP-012 | LOW | ambiguous_logic | CBACT04C: 1 paragraph(s) flagged ambiguous during pseudocode extraction. | logic |
| GAP-013 | LOW | ambiguous_logic | CBIMPORT: 1 paragraph(s) flagged ambiguous during pseudocode extraction. | logic |
| GAP-014 | LOW | ambiguous_logic | CBSTM03A: 3 paragraph(s) flagged ambiguous during pseudocode extraction. | logic |
| GAP-015 | LOW | ambiguous_logic | COACCT01: 2 paragraph(s) flagged ambiguous during pseudocode extraction. | logic |
| GAP-016 | LOW | ambiguous_logic | CODATE01: 2 paragraph(s) flagged ambiguous during pseudocode extraction. | logic |

## External system dependencies (not gaps)

Platform components provided by the mainframe runtime; they are expected to be absent from the application repository.

| Component | Subsystem | Kind | Used by |
|---|---|---|---|
| DFHAID | CICS | CICS system copybook / interface | COACTUPC, COACTVWC, COADM01C, COBIL00C, COCRDLIC, COCRDSLC, COCRDUPC, COMEN01C (+13) |
| DFHBMSCA | CICS | CICS system copybook / interface | COACTUPC, COACTVWC, COADM01C, COBIL00C, COCRDLIC, COCRDSLC, COCRDUPC, COMEN01C (+13) |
| SQLCA | DB2 | DB2 interface | COTRTLIC |
| CMQGMOV | IBM MQ | MQ API copybook | COACCT01, CODATE01, COPAUA0C |
| CMQMDV | IBM MQ | MQ API copybook | COACCT01, CODATE01, COPAUA0C |
| CMQODV | IBM MQ | MQ API copybook | COACCT01, CODATE01, COPAUA0C |
| CMQPMOV | IBM MQ | MQ API copybook | COACCT01, CODATE01, COPAUA0C |
| CMQTML | IBM MQ | MQ API copybook | COACCT01, CODATE01, COPAUA0C |
| CMQV | IBM MQ | MQ API copybook | COACCT01, CODATE01, COPAUA0C |
| MQCLOSE | IBM MQ | MQ API call | COACCT01, CODATE01, COPAUA0C |
| MQGET | IBM MQ | MQ API call | COACCT01, CODATE01, COPAUA0C |
| MQOPEN | IBM MQ | MQ API call | COACCT01, CODATE01, COPAUA0C |
| MQPUT | IBM MQ | MQ API call | COACCT01, CODATE01 |
| MQPUT1 | IBM MQ | MQ API call | COPAUA0C |
| CBLTDLI | IMS | IMS DL/I interface | DBUNLDGS, PAUDBLOD, PAUDBUNL |
| CEE3ABD | Language Environment | LE runtime service | CBACT01C, CBACT02C, CBACT03C, CBACT04C, CBCUS01C, CBEXPORT, CBIMPORT, CBSTM03A (+3) |
| CEEDAYS | Language Environment | LE runtime service | CSUTLDTC |

