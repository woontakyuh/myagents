---
description: Fast 1-minute initial paper screening for editorial decision
---

# Quick Screen — Fast Initial Paper Screening

Rapid 1-minute assessment of a manuscript for initial editorial screening.

## Usage
For editors who need to quickly decide: send for review or desk reject?

## Workflow

1. **Extract basics** from PDF in `papers/inbox/`:
   - Title, abstract, study type
   - Sample size, key outcomes
   - Reference count and recency

2. **Screen for**:
   - Within journal scope?
   - Minimum methodological threshold met?
   - Ethical approval mentioned?
   - Sample size reasonable for study type?
   - Any obvious red flags?

3. **Output** (directly in chat, no file):
   ```
   📋 QUICK SCREEN: {Title}
   ✅/❌ Scope: {yes/no + reason}
   ✅/❌ Methods: {basic assessment}
   ✅/❌ Ethics: {IRB mentioned?}
   ✅/❌ Sample: {adequate?}
   📊 Study type: {type} | LoE: {level}
   🔴 Red flags: {any immediate concerns}
   
   → Recommendation: Send for review / Desk reject / Need more info
   ```

## Notes
- This is for SPEED, not depth
- Do not run sub-agents — handle directly
- 30-60 seconds target time
