# Chunking branch ledger (prototype, reviewed 2026-11-09)
Final review: With fixes (0 Critical, 2 Important, 6 Minor).
Final: fixed cell repair firing on genuine trailing commas/leading-zero codes — test_cell_repair_fires_only_on_the_extraction_artifact RED→GREEN; regroup gated on the raw "\n," artifact
Final: Ruling: residual table mangling (33.7% of table chunks, measured) is a documented extraction ceiling, not fixed — cell-level repair cannot reconstruct detached decimals or comma-cells confidently; prose text holds the printed numbers and quotes verify there — cost if wrong: retrieval recall on the worst tables until a layout-aware extractor lands
Final: minor (deferred): stale corpus module docstring still describes tab-joined table rows
Final: minor (deferred): chunk_eval divides by zero on an empty gold file and KeyErrors on a row without item_id
Final: minor (deferred): a row with empty label renders ": " prefix
Final: minor (deferred): a single row wider than the chunk size stays one oversized chunk (dense embedder truncates its tail)
Final: minor (deferred): pages below the text threshold drop their tables (pre-existing gate)
Final: minor (deferred): the --lr training flag rode on this branch (harmless drive-by, already on main)
