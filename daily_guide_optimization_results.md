# Daily Guide Optimization Results (Backup)

Generated on: 2026-04-21

### Results Comparison

| Metric | Old Architecture | New Architecture | Difference |
| :--- | :--- | :--- | :--- |
| **API Calls (Google Search)** | 5 | 2 | **-60% API cost** |
| **Total Cards Generated** | 61 | 78 | **+27% more events** |
| **Duplicate Checking** | None (Bleed across tiers) | Automatic | **7 duplicates removed** |
| **Zero-Cost Baseline?** | No | Yes (Staples Tier) | **Guaranteed events** |

### Breakdown by Tier

Here is the exact card count broken down by tier from the run we just did:

*   📍 **Staples (Baseline):** 8 cards (4 today, 4 tomorrow) — *$0.00 cost*
*   🆓 **Free:** 15 cards (7 today, 8 tomorrow)
*   💵 **Under $20:** 14 cards (7 today, 7 tomorrow)
*   🍸 **Under $50:** 14 cards (7 today, 7 tomorrow)
*   🌟 **Splurge:** 11 cards (8 today, 3 tomorrow)
*   🃏 **Wildcard:** 16 cards (8 today, 8 tomorrow)

### Why this is a huge improvement:
1.  **More Volume for Less Money:** We successfully pushed Gemini to generate **17 more unique cards** while cutting the Search Grounding API costs by 60%.
2.  **No More "Tier Bleed":** The script actively identified and removed **7 duplicate activities** (like a "Freedom Park walk" showing up in both Free and Under $20).
3.  **Resiliency:** The 8 "Staples" cards load instantly without touching the AI. If the API is ever rate-limited, users will still have something to see.
