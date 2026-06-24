# N-of-1 Agentic Care Architecture

```text
                    ┌─────────────────────────────────────┐
                    │          Care orchestrator          │
                    │     Triages & prioritizes           │
                    └─────────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          │                    │                    │
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│   Rx risk agent   │ │ Adherence agent   │ │ Misuse monitor    │ │  Cost navigator   │
│ Genotype dosing   │ │ Daily check-ins   │ │ Refill anomalies  │ │ Copay & PA gaps   │
└───────────────────┘ └───────────────────┘ └───────────────────┘ └───────────────────┘
          \                 |                  |                 /
           \________________|__________________|________________/
                            │
            ┌─────────────────────────────────────┐
            │      Human-in-the-loop gate         │
            │      Final clinical sign-off        │
            └─────────────────────────────────────┘
                            │
            ┌─────────────────────────────────────┐
            │          Care actions               │
            │  Prescribe · adjust · outreach      │
            └─────────────────────────────────────┘

Purple = oversight & control
Teal = specialist agents & actions
Outcomes feed back into the orchestrator continuously.
```