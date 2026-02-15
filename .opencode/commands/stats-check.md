---
description: Statistics-only focused review of a paper
---

# Stats Check — Statistics-Only Review

Focused review of statistical methods and results only.

## Usage
When you only need to verify the statistical analysis is appropriate.

## Workflow

1. **Extract Methods and Results** from PDF
2. **Run methods-reviewer** agent with stats-only focus:
   - What tests were used?
   - Are they appropriate for the data?
   - Sample size adequate?
   - Multiple comparison corrections?
   - Effect sizes reported?
   - Missing data handled?
3. **Output** directly in chat:
   - Table of each statistical test used, its appropriateness, and issues
   - Specific recommendations

## Notes
- Faster than full review
- Does not assess study design, literature, or writing quality
- Good for revised manuscripts where only stats were changed
