# Design Consistency Protocol v1.3

Purpose: keep interface and interaction decisions consistent across a long project,
and keep them enforceable as files rather than as taste. This protocol covers the
ui_and_interaction domain of the contract and its ongoing amendments.

## 1. Method sources, not dependencies

External UI references are useful as a method catalogue. They are not runtime
dependencies and are not copied into the repository by default.

| Reference class | Use in this system | Boundary |
|---|---|---|
| Real product libraries (Mobbin, Refero, Page Flows style) | Study information architecture and user flow before building a screen | Do not paste screenshots or proprietary UI into deliverables |
| Inspiration galleries (Lapa Ninja, Land-book, Siteinspire style) | Open up direction when the visual language is undecided | Never copy a layout or brand identity |
| Design system references and DESIGN.md files (public open-source ones) | Extract token structure, component vocabulary and naming discipline | Respect license; record source and license for anything adopted |
| Pattern and checklist libraries (UI Patterns, checklist.design style) | Turn interaction rules into verifier checklist items | Adapt to project constraints; do not import wholesale |

Rules:

- Adoption is a governance increment: record what was internalized in the project's
  DESIGN.md, tokens or checklist, with the source, and register it as a decision.
- Do not add external sites, assets, fonts or icon packs to the product path without
  owner approval, license review and a recorded SHA256, consistent with the project's
  third-party tool rules.
- Network fetching of references is forbidden by default; use only owner-approved
  sources, and never let a reference download become an untracked build dependency.

## 2. Design contract artifacts

For projects with a user interface, the project owns:

- DESIGN.md - the human-readable design contract: design principles, information
  architecture, interaction model, component inventory, states, accessibility
  targets, embedded constraints, and the rules for changing the contract.
- design-tokens.json - the machine-readable tokens: color, typography, spacing,
  radius, elevation, motion, and component-level tokens. Code and tests read it;
  prose does not redefine values.

These two artifacts are referenced from the contract's ui_and_interaction domain and
carry their own version and change path. A design change is an amendment when it
changes tokens, component structure or interaction model; a pure copy tweak inside the
existing system is a preference decision.

The design system may be inspired by a public reference (for example a well-known
product's DESIGN.md structure) but must be rewritten for this project's context,
constraints and hardware. Do not paste a third-party design file verbatim as the
project contract without recording its license and adapting it.

## 3. Five-stage workflow with outputs

Use stages in order; each stage has an output that can be reviewed.

| Stage | Goal | Output |
|---|---|---|
| Direction | Set the visual and interaction tone | A short direction note: mood, density, contrast, motion policy, target environment |
| Product decomposition | Understand real flows | Screen inventory and user-flow map for the critical paths |
| Contract | Freeze the language | DESIGN.md plus design-tokens.json versioned and registered |
| Detail | Refine components and states | Component-level specs and states, checked against a pattern checklist |
| Landing | Implement in the real constraints | Implementation mapped to the actual framework and hardware |

Skipping the contract stage is the most common cause of interface drift: without
tokens and an inventory, each screen invents its own spacing and color.

## 4. Consistency checks (verifier checklist)

At each interface milestone, verify and record:

- Every screen uses tokens only; no hard-coded colors, sizes or spacing in views.
- Component inventory is complete: each component has defined default, hover, active,
  disabled, focus and error states as applicable.
- Text fits its container at the supported viewport or screen size; long values do not
  overlap or truncate silently.
- Layout is stable under loading, empty, error and long-content states; no layout
  shift from dynamic content.
- Interaction rules are consistent: the same gesture or action behaves the same way
  across screens; destructive actions are distinguishable and reversible where possible.
- Accessibility basics hold for the target: contrast, focus order, labels, and
  keyboard or touch reachability appropriate to the device.
- Terminology matches the product goal and other screens; no duplicated concepts.
- Icons come from one library with a single stroke and size convention.

## 5. Embedded GUI constraints

Embedded and companion UIs are constrained by the device, and the contract must
state these before design tokens are frozen:

- Screen size, resolution, pixel density and orientation.
- Available RAM and flash for the UI; frame budget and refresh rate.
- Input method: touch, rotary encoder, buttons, remote; focus and hit-target sizes.
- Framebuffer or display driver constraints, and whether the UI runs on the
  microcontroller, an RTOS task, a companion PC or a browser.

Method: plan the interface in a design tool or as a token-first specification, then map
it onto the actual widget or component framework (for example an embedded GUI library
or a desktop toolkit) within its real limits. A desktop or web design system may supply
the visual language, but the component layer must obey the embedded constraints. Keep
the token file as the single source so the mapping step is mechanical and reviewable.

## 6. Recording design decisions

- Record each design decision in the contract's ui_and_interaction domain, with source
  type (user, project SSOT, or derived), reference, rationale, impact and rollback.
- Record adopted external methods in knowledge or DEC notes with license information.
- Treat a change to tokens, component inventory or interaction model as a contract
  amendment; a wording or spacing tweak inside the tokens is a preference decision and
  follows the 300-second delegated default.

## 7. Boundaries

- This protocol cannot render, judge aesthetics automatically or verify pixel output.
  It requires human or screenshot review for visual claims, recorded as such.
- No claim of design-system conformance to an external brand is made without an
  explicit comparison artifact.
- Design quality is verified by reviewers and checklists, not by the presence of a
  tokens file alone.