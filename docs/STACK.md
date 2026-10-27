# Stack and agent tooling decisions

**Application:** Next.js/React/TypeScript/Tailwind frontend; Python 3.12+/FastAPI/Pydantic/uv backend; OpenCV+NumPy (SciPy if needed) first; optional openly licensed learned segmentation only if benchmarked; Meta SAM 3.1 and Muse later; simple private temporary storage with no database until need is proven. Choose simple cloud deployment once platform constraints are tested.

**Codex skill stack:** Existing GStack and ECC (do not reinstall blindly); Context7 for version-appropriate library docs; GitHub repo/PR/Actions; GStack or Playwright browser QA where available. Skills present in ChatGPT are not automatically in Codex Cloud. Review untrusted MCP/skills for maintainer, permissions, license and install scripts; avoid overlapping 'mega-frameworks'. Missing optional skills **never blocks writing code**.

**Cloud:** Codex Cloud does code tasks and PRs, not necessarily the public app's runtime. Select hosted runtime for API and web only after checking storage/upload budgets, timeout constraints, sleep policies and secret handling.

**Implementation policy:** deterministic templates are enough for planning until LLM integration is worthwhile; all open-weight models require license verification and actual runtime evaluation. Provider-independent contracts ahead of provider brand decisions.
