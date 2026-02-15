---
description: Generate editor decision letter based on existing review(s)
---

# Editor Decision — Generate Decision Letter

Generate an editor decision letter based on existing review(s).

## Usage
Run after `/review-paper` has been completed, or provide review files directly.

## Workflow

1. **Find Reviews**: Look in `papers/reviews/` for the most recent review files for the paper.

2. **Generate Decision** (decision-drafter agent):
   - Synthesize all reviewer comments
   - Draft decision letter with editorial comments
   - Save to `papers/decisions/`

3. **Output**:
   - Display decision letter draft
   - Ask for decision type confirmation (Accept/Minor/Major/Reject)
   - Allow editing before finalization

## Notes
- If no review files exist, suggest running `/review-paper` first
- Decision letter is always a DRAFT requiring editor approval
