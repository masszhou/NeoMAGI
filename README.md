# NeoMAGI

[中文](README_ch.md) | [Deutsch](README_de.md)

NeoMAGI is an open-source personal agent project.

The product idea is straightforward: build an agent that can carry memory over time, represent the user's information interests, and gradually move from hosted model APIs toward more local and user-controlled model stacks.

## Product Position

NeoMAGI is not trying to be a generic chatbot shell.

The intended direction is a long-term partner-style AI that:
- remembers useful context across time
- acts in service of the user rather than platform incentives
- can expand its capabilities in a controlled and auditable way
- keeps a practical migration path from commercial APIs to local models

## Principles

- Think deeply, implement simply.
- Prefer the smallest useful closed loop.
- Avoid unnecessary abstraction and dependency sprawl.
- Treat governance, rollback, and scope boundaries as product features, not only engineering details.

## Current Status

This repository is still in an early product-building stage.

The Phase 1 foundation has largely been built and archived as reference. Phase 2 planning is about reducing context burden, clarifying the next product chapter, and moving from base infrastructure toward a more explicit growth and capability-evolution model.

The README intentionally stays high level. It is meant as a project introduction, not a full implementation contract.

## Documentation

- Project design entry: `design_docs/index.md`
- Phase 1 archive: `design_docs/phase1/index.md`
- Runtime prompt model: `design_docs/system_prompt.md`
- Memory principles: `design_docs/memory_architecture_v2.md`
- Repo governance: `AGENTS.md`, `CLAUDE.md`, `AGENTTEAMS.md`

## Status Note

Expect active iteration.

Names, boundaries, and implementation details may continue to change as the product direction becomes sharper and more of the system is validated through real use.
