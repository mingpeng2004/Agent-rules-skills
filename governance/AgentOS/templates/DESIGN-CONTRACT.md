# DESIGN.md - {{PRODUCT_OR_PROJECT}} design contract

Version: 0.1 (draft) | Contract domain: ui_and_interaction | Tokens: design-tokens.json

## 1. Design principles

- Primary goal:
- Density and rhythm:
- Contrast and emphasis:
- Motion policy:
- Target environment (screen size, input method, ambient light):

## 2. Information architecture

- Primary objects and their relationship:
- Critical user flows (3 or fewer):
- Navigation model:
- What is deliberately out of scope:

## 3. Interaction model

- Core actions per screen:
- Feedback and error presentation:
- Destructive and irreversible actions:
- Keyboard / touch / encoder behavior:
- Empty, loading and long-content states:

## 4. Component inventory

| Component | Purpose | Variants | States | Source |
|---|---|---|---|---|
|  |  |  | default / hover / active / disabled / focus / error |  |

Rule: a screen may only use components from this inventory. A new component is a
contract amendment.

## 5. Design tokens

Values live in design-tokens.json and are not restated here.

| Token group | Purpose | Notes |
|---|---|---|
| color | | |
| typography | | |
| spacing | | |
| radius | | |
| elevation | | |
| motion | | |

## 6. Accessibility

- Contrast targets:
- Focus order and visible focus:
- Labels and units:
- Touch or knob hit targets:

## 7. Embedded / device constraints

- Display: size, resolution, orientation
- Memory and frame budget:
- Input method:
- GUI framework and mapping notes:

## 8. Verification checklist

- [ ] No hard-coded colors, sizes or spacing outside tokens
- [ ] Every component has its defined states
- [ ] Text fits at the supported size; no silent truncation
- [ ] Layout stable across loading, empty, error and long content
- [ ] Same action behaves the same across screens
- [ ] Contrast, focus and labels meet section 6
- [ ] Terminology matches the product goal

## 9. Change path

- Token or spacing change inside this system: preference decision, 300-second
  delegated default, recorded.
- Component structure, interaction model or token scale change: contract amendment,
  explicit confirmation, contract version bump.
- External reference adopted: record source, license and what was internalized.

## Provenance

| Item | Source | License / note |
|---|---|---|