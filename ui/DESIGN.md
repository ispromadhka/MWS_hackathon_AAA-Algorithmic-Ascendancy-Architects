# Design System Specification: The Cognitive Workspace

## 1. Overview & Creative North Star
**Creative North Star: "The Orchestrated Intelligence"**

This design system moves away from the "chat-bubble" cliché of AI interfaces, transitioning instead into a sophisticated, high-performance IDE environment. We are building a "Digital Atelier" for developers—a space that feels as precise as a Swiss watch and as expansive as a modern command center.

To break the "standard template" look, this system utilizes **Intentional Asymmetry**. We pair a dense, information-rich code environment with a spacious, editorial-style chat interface. By utilizing overlapping panels and varied surface elevations, we create a sense of architectural depth, ensuring the multi-agent nature of the platform feels like a cohesive team rather than a fragmented list of messages.

---

## 2. Colors & Surface Philosophy
The palette is rooted in `Deep Charcoal` and `Slate`, providing a low-strain environment for long coding sessions, punctuated by high-energy pulses of `Electric Violet` and `Cyber Blue`.

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders for sectioning or layout containment. 
*   **Alternative:** Define boundaries solely through background color shifts. For example, a `surface-container-low` panel sitting on a `background` base.
*   **Exception:** Active states or "Ghost Borders" (see Elevation & Depth).

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers—stacked sheets of obsidian and smoked glass.
*   **Base (`surface` / `#060e20`):** The canvas.
*   **Secondary Zones (`surface-container-low`):** Sidebars and inactive panels.
*   **Active Workspace (`surface-container-high`):** The primary editor or chat focus area.
*   **Glassmorphism & Texture:** Use `surface-variant` with a 60% opacity and `backdrop-filter: blur(12px)` for floating overlays (e.g., command palettes or hover-state details). This prevents the UI from feeling "flat" and adds a layer of sophisticated polish.

---

## 3. Typography
We utilize a dual-font strategy to balance human conversation with machine precision.

*   **Display & Headlines (`Manrope`):** Used for high-level UI landmarks. Its geometric but slightly rounded nature provides an "intelligent yet approachable" feel.
    *   *Scale Example:* `display-sm` (2.25rem) for empty state greetings.
*   **UI & Body (`Inter`):** Our workhorse. Used for all labels, chat text, and metadata.
    *   *Scale Example:* `body-md` (0.875rem) for the primary chat output.
*   **Code Blocks (Monospace):** Not defined in the JSON but required for the "Tech-Forward" persona. Use *JetBrains Mono* or *Geist Mono*. It must maintain a high contrast against `surface-container-lowest` for maximum legibility.

---

## 4. Elevation & Depth
Hierarchy is achieved through **Tonal Layering** and light physics, not structural lines.

*   **The Layering Principle:** To lift a card, do not add a shadow immediately. First, shift its background from `surface-container` to `surface-container-highest`.
*   **Ambient Shadows:** Floating elements (Modals, Popovers) use extra-diffused shadows: `box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4)`. The shadow color should never be pure black; it should be a deep tint of our `surface` color to maintain tonal harmony.
*   **The "Ghost Border":** For accessibility in high-density areas, use a "Ghost Border": `outline-variant` at 15% opacity. It should feel felt, not seen.
*   **Active Glows:** Active agents or focused code blocks should utilize a subtle outer glow using the `primary_dim` (`#8a4cfc`) at a 20% spread to simulate a "live" powered state.

---

## 5. Components

### The "Side-by-Side" Layout
The core of this system is the dual-pane Orchestrator. The Chat (Left) and the Code (Right) are separated not by a line, but by a subtle shift from `surface-container-low` to `surface-container-lowest`.

*   **Buttons:**
    *   *Primary:* `primary_container` background with `on_primary_container` text. Apply a subtle 2px roundedness (`md`) to maintain the "Sleek" aesthetic.
    *   *Tertiary (Ghost):* No background. Only text in `secondary`. On hover, shift the background to `surface-bright`.
*   **Input Fields:**
    *   The chat input should appear as a "floating" pill using the Glassmorphism rule. No border. Use `surface-container-highest` as the base.
*   **Agent Chips:**
    *   Use `tertiary_container` for active agents. They should look like small, glowing indicators of life within the machine.
*   **Cards:**
    *   **Prohibit Divider Lines.** Separate header and body of cards through vertical white space (use 24px/1.5rem padding) or a subtle shift from `surface-container-high` to `surface-container`.
*   **Code Blocks:**
    *   Background: `surface-container-lowest` (#000000).
    *   Syntax Highlighting: Use `secondary` (Cyber Blue) for functions and `tertiary` (Seafoam) for strings.

---

## 6. Do’s and Don’ts

### Do
*   **Do** use asymmetrical layouts where one column is significantly wider than the other to create visual interest.
*   **Do** use "Micro-interactions." When an AI agent is thinking, use a subtle pulse on the `surface-tint` rather than a generic loading spinner.
*   **Do** leverage the `primary_dim` color for "Active State" glows—it feels more sophisticated than a flat color fill.

### Don't
*   **Don't** use 100% white text. Use `on_surface` (#dee5ff) or `on_surface_variant` (#a3aac4) to reduce eye strain and maintain the "Deep Charcoal" mood.
*   **Don't** ever use a 1px solid border to separate the chat from the code. Use the tonal shift between `surface` tiers.
*   **Don't** use standard "Material Design" rounded corners (e.g., 12px or 16px). Stick to the precise, professional `md` (0.375rem) or `lg` (0.5rem) scale for a sharper, tech-forward edge.