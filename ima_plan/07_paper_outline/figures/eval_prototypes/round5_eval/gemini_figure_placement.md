## Consolidation Recommendations

**Question 6 (Figs 4, 5, 6):** **Absolutely consolidate.** You have 0.6 pages of text (~180 words) and three 7.0" × 2.2" double-column figures. Unconsolidated, they require 6.6 vertical inches, which will push subsequent floats multiple pages away. 
*Recommendation:* Combine them into a single `figure*` with three vertically stacked panels (a, b, c). Even better, strip the redundant X-axes (the 27 workloads) from the top two panels to compress the total height from 6.6" to ~4.5". 

**Question 3 (Figs 10a, 10b):** **Option C (One `figure` with two stacked images).** 
*Rationale:* Using `figure*` (Option B) steals a precious top-of-page slot from your critical double-column figures (like Fig 8 or 11). Two separate `figure` environments (Option A) risk being separated by page breaks. Stacked in a single column (3.5" × 5.0"), they perfectly fill exactly half a column, balancing the text without fighting the double-column float queue.

## Per-Figure Recommendations

| ID | Anchor Paragraph | Environment | Float Specifier | Rationale |
|---|---|---|---|---|
| **4, 5, 6** | ¶5.1.1 (Coverage) | `figure*` | `[!t]` | Combined 3-panel figure. Anchoring at the very start of §5.1 ensures it grabs the first available top-of-page slot (likely the page where §5 begins, or exactly the page after). |
| **7** | ¶5.2.1 (L1 Miss) | `figure*` | `[!t]` | Anchor at ¶5.2.1. LaTeX will process it into the double-column queue immediately after the 4/5/6 block. No need to restructure the text; just cite (a) in ¶5.2.1 and (b) in ¶5.2.2. |
| **8** | ¶5.3.1 (Intro/GMEAN) | `figure*` | `[!t]` | The most critical figure. Anchoring at the very first sentence of §5.3 guarantees it enters the float queue before any §5.4 figures, ensuring it lands on the same or next page. |
| **9** | ¶5.4.1 (Ablation) | `figure` | `[!b]` | Single-column. Using `[!b]` keeps it out of the way of the heavy top-page double-column floats and anchors it neatly at the bottom of the column where §5.4 starts. |
| **10a/b** | ¶5.4.2 (Throttle) | `figure` | `[!t]` | Combined stacked single-column. `[!t]` places it at the top of a single column, which pairs well visually opposite to Fig 9 at the bottom of a column. |
| **11** | ¶5.4.3 (Distance) | `figure*` | `[!t]` | Last double-column figure. Will naturally flow to the final page of the evaluation section. |
| **Tab 4** | ¶5.5.1 (HW Cost) | `table` | `[h]` or `[!b]` | Small inline table. `[h]` is preferred if it's tiny; otherwise `[!b]` to keep the reading flow of the final paragraphs uninterrupted. |

## Page Distribution Strategy

Assuming §5 Evaluation spans exactly 3 pages (e.g., Pages 9, 10, 11):

*   **Page 9 (Start of §5):**
    *   **Top:** Consolidated Fig 4+5+6 (`figure*`, ~4.5" tall).
    *   **Text:** §5.1, §5.2, and the start of §5.3.
    *   *Note:* If §5 starts mid-page on Page 8, Fig 4+5+6 might land on Page 8 top, pulling everything forward.
*   **Page 10 (The Core Analysis):**
    *   **Top:** Fig 7 (Mechanism, 2.2" tall) AND Fig 8 (Speedup vs SOTA, 2.5" tall) stacked together. LaTeX can easily fit two `figure*` environments at the top of one page if their combined height is < 5 inches.
    *   **Text:** Bulk of §5.3 (Speedup analysis) and start of §5.4.
    *   **Bottom/Inline:** Fig 9 (Ablation, single-col) at the bottom left or right column.
*   **Page 11 (Sensitivity & Conclusion):**
    *   **Top:** Fig 11 (Sensitivity, `figure*`, 2.5" tall).
    *   **Top Single-Col:** Consolidated Fig 10a+b (Throttle, `figure`, taking top of one column below Fig 11).
    *   **Text:** Remainder of §5.4, §5.5, and Table 4.

**Overflow Risk Warning:** 
Placing Fig 7 and Fig 8 on the same page (Page 10) is your layout linchpin. If their combined height plus captions exceeds ~5.5 inches, LaTeX will push Fig 8 to Page 11, separating it from §5.3 text. Ensure the bounding boxes for Figs 7 and 8 are tightly cropped.