# YT Algo Dating App

## Documentation

All project decisions and documentation live in `docs/` using the ADR (Architecture Decision Record) format.

### ADR Naming Convention

Files are numbered sequentially with a descriptive slug:

```
docs/NNN-short-descriptive-name.md
```

Examples:
- `docs/001-validation-strategy-fingerprint-landing-page.md`
- `docs/002-tech-stack-selection.md`

### ADR Template

Every ADR must include:

- **Title** as `# ADR-NNN: Title`
- **Date** — when the decision was made
- **Status** — `Proposed`, `Accepted`, `Superseded`, or `Deprecated`
- **Decision** — one-paragraph summary of what was decided
- **Context** — why this decision was needed
- **Consequences** — what follows from this decision

Additional sections (How It Works, Success Criteria, etc.) are encouraged when they add clarity.

### When to Create an ADR

When the user asks for something to be documented, or when a significant decision is made about:
- Product strategy or direction
- Technical architecture or stack choices
- Data handling or privacy approaches
- Growth or go-to-market decisions
- Scope changes or pivots

Always check the current highest ADR number in `docs/` before creating a new one to maintain sequential numbering.
