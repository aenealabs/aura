# CKGE Platform End-User Guide

## 1. Submitting a Request (The "Single Prompt")

The CKGE operates by accepting a single, comprehensive natural language prompt. This prompt initiates the **System 2 AI** process, which breaks down the task into thousands of sub-steps.

### Best Practices for Prompting

* **Be Specific:** Clearly state the *intent* (WHY) and the *requirements* (WHAT).
  * *Good:* "Refactor the DataProcessor class to use SHA256 for checksum calculation and log the outcome."
  * *Bad:* "Make the data security better."
* **Include Constraints:** If you have known technical constraints (e.g., "Must use Java 21 Virtual Threads," or "Avoid adding new dependencies"), include them.
* **Focus on the Goal:** Describe the desired architectural or functional outcome, not the line-by-line code.

## 2. Interpreting the Handover Report

Once the autonomous process is complete (typically 4-12 hours in a real environment), the **Handover Report** is generated on the console. This report provides the final $100\%$ of the solution: the generated code and the remaining $20\%$ of human work.

### A. The Metrics Dashboard (For Manager/Audit Review)

This section provides immediate reassurance that the code is safe and cost-effective.

| Metric | Meaning | Actionable Insight |
| :--- | :--- | :--- |
| **Vulnerabilities Remediated** | The number of critical flaws the AI fixed *autonomously*. | A score > 0 confirms the AI is actively enforcing security policies. |
| **Engineering Hours Saved** | Time saved vs. a human coding the feature from scratch. | Used by management (Senior Manager, Engineering Ops) to track platform ROI. |
| **Cost Per Feature** | Total LLM/Compute expense for the request. | Use this to manage your **multi-million-dollar IT budgets**. |

### B. The Human Developer Handoff (The Critical 20%)

The system generates $80\%$ of the solution, but the final $20\%$ requires human ingenuity and review.

* **Review the Code:** The final, clean, and tested code is presented. Review it for complex business logic and final sign-off.
* **Focus on Gaps:** Pay closest attention to the **"Next Steps for Human Developer"** section. These tasks (e.g., performance testing, final security review of IAM policies) are high-value tasks the AI cannot yet fully automate.

---
