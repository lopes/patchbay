## Description
<!-- Provide a brief, high-level summary of your changes. Explain WHY rather than WHAT. -->

## Related Issue / Context
<!-- Link to issue, reference, or ticket (e.g. Closes #12) -->

## Type of Change
- [ ] MCP Server Tools & Handlers (`src/`)
- [ ] Spotify Web API Client & PKCE Auth (`src/`)
- [ ] Offline Unit & Fixture Shape Tests (`tests/`)
- [ ] Agent Skills & Documentation (`.agents/`, `AGENTS.md`, `README.md`)
- [ ] CI/CD & Governance (`.github/`)

## Quality Checklist
- [ ] Offline test suite passes in <1s (`uv run python -m unittest discover tests -v`).
- [ ] Stdlib-first invariant preserved (no new runtime dependencies beyond `mcp`).
- [ ] Fixture scrubbing preserved (zero personal Spotify IDs, tokens, or private data in `tests/fixtures/`).
- [ ] Commit follows [Scoped Commits](https://scopedcommits.com/) convention (`<scope>: <description>`).
