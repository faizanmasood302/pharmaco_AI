# Metabolic Conversion Standards
**Reference:** CPIC / PharmGKB Unified Standards.

## 1. Baseline Conversion Metrics
The system defines the "Standard Therapeutic Window" based on the following pharmacokinetic baselines:

*   **Standard Conversion:** 5% – 15% of parent drug converted to active metabolite.
*   **Optimal State:** Steady-state plasma concentration within therapeutic range (e.g., 10-80 ng/mL for morphine).

## 2. Phenotype Deviations
*   **Accelerated (UM):** Predicted conversion >50% higher than baseline. Pulse visualization triggers at `speed: 1.3`.
*   **Reduced (IM):** Predicted conversion 20-40% below baseline.
*   **Blocked (PM):** Minimal to zero conversion detectable (<2%). 

## 3. Visual Representation Logic
*   **Green:** Normal enzymatic flux.
*   **Yellow/Orange:** Metabolic bottleneck or slight escalation.
*   **Red (Pulsing):** High-velocity toxic conversion or critical blockade.
