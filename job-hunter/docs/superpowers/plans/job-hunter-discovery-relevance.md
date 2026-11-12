# Working plan — Job Hunter discovery relevance

Tracking file for the brainstorming → spec → plan flow. Not the spec itself.

## Brainstorming checklist
- [x] 1. Explore project context
- [x] 2. Offer visual companion just-in-time (not needed — all text/decision questions so far)
- [x] 3. Ask clarifying questions (goal, audiences, noise categories, aggressiveness)
- [x] 4. Propose 2–3 approaches with trade-offs + recommendation (chose B)
- [x] 5. Present design in sections, approve after each (7 sections approved)
- [x] 6. Write design doc → docs/superpowers/specs/2026-11-12-job-hunter-discovery-relevance-design.md, commit
- [x] 7. Spec self-review (fixed wage-floor + description-threshold ambiguity, added phasing)
- [ ] 8. User reviews written spec
- [ ] 9. Invoke writing-plans

## Locked requirements (from Q&A)
- Goal: **cut noise / fix relevance** (not coverage, not automation).
- Audiences: **tech**, **entry/gig/online**, **visa-sponsorship/relocation** — cleanly separated.
- Noise to drop (all six): wrong-country "remote"; off-profile titles; wrong seniority + generic postings;
  scam/bait/poverty-wage; dead links + reposts + duplicates; unactionable/missing-metadata.
- Aggressiveness: **Broad (keep all passing)** — hard rules drop clear noise, ranking sorts the rest.
- Real profile: Patrick Hirwa, impatrickhi@gmail.com, Rwanda, remote preferred; roles PM / AI-Automation /
  SWE / Project Manager; skills from CV.

## Root cause already proven
- Dockerfile `COPY config.example.yaml config.yaml` → live container runs placeholder profile + all boards.
- No config mount in compose; no real config.yaml on the VPS.
- Live DB: 374 jobs, all `new`, 347 score 0; company empty on search boards; eligibility leaks wrong-country.
