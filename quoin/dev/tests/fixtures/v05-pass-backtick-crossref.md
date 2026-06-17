This document refers to a sibling plan's task as `T-05` — that ID has no local
definition, but because it is wrapped in inline-code backticks it is exempt from
V-05 (IVG-78). The exemption is content-blind: `T-99` is also exempt even though
it is not defined anywhere. This pins the "any ID inside backticks is exempt"
behavior (see the plan's decision on content-blind exemption).

Local task list:

- T-01: The only locally-defined task

See T-01 for the implementation. Cross-artifact references use the backtick form:
`T-05` lives in the parent plan; `D-03` lives in the architecture doc.
