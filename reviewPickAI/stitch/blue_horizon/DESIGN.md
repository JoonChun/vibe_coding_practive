# Design System Specification: The Fluid Authority

## 1. Overview & Creative North Star
**Creative North Star: "The Digital Curator"**

This design system moves beyond the rigid, boxy constraints of traditional fintech interfaces. Inspired by the precision of Korean minimalism, it adopts the persona of a "Digital Curator"—an interface that doesn't just display data but orchestrates it with quiet authority. 

To break the "template" look, we utilize **Intentional Asymmetry** and **Tonal Depth**. By moving away from hard-lined containers and toward organic, layered surfaces, we create a sense of infinite space. The system balances the high-trust reliability of an institutional bank with the frictionless, "air-filled" aesthetic of a modern lifestyle brand.

---

## 2. Colors & Surface Philosophy

Our palette is anchored by the signature `primary-container` (#0051FF), but its power is derived from the expansive neutral space surrounding it.

### The "No-Line" Rule
**Traditional 1px borders are strictly prohibited for sectioning.** Boundaries must be defined through background color shifts. Use `surface-container-low` (#f2f4f6) for large section backgrounds and `surface-container-lowest` (#ffffff) for the interactive elements sitting atop them. This creates a "soft-edge" layout that feels modern and expansive.

### Surface Hierarchy & Nesting
Treat the UI as a physical stack of premium materials.
- **Level 0 (Base):** `surface` (#f8f9fb) – The infinite canvas.
- **Level 1 (Sections):** `surface-container-low` (#f2f4f6) – Large grouping areas.
- **Level 2 (Cards):** `surface-container-lowest` (#ffffff) – The primary focal point for data.
- **Level 3 (Floating):** `surface-bright` (#f8f9fb) with Glassmorphism – For temporary overlays or navigation.

### Signature Textures
Main CTAs and high-impact data points should utilize a **Subtle Linear Gradient**. Instead of a flat `#0051FF`, transition from `primary` (#003dc7) to `primary-container` (#0051ff) at a 135° angle. This adds a "lithographic" depth that feels premium and tactile.

---

## 3. Typography: Editorial Authority

We use a dual-font strategy to balance character with readability.

*   **Display & Headlines:** *Plus Jakarta Sans*. Bold, geometric, and spacious. Used to anchor the page and provide a strong visual hierarchy.
*   **Body & UI:** *Inter* (or *Pretendard* for localized CJK support). Optimized for high-density data and functional clarity.

| Level | Token | Font | Size | Weight | Intent |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Display** | `display-md` | Plus Jakarta | 2.75rem | 700 | Hero metrics, balance totals |
| **Headline** | `headline-sm` | Plus Jakarta | 1.5rem | 600 | Section headers |
| **Title** | `title-md` | Inter | 1.125rem | 600 | Card titles, modal headers |
| **Body** | `body-md` | Inter | 0.875rem | 400 | Primary reading text |
| **Label** | `label-md` | Inter | 0.75rem | 500 | Captions, small metadata |

---

## 4. Elevation & Depth

We convey importance through **Tonal Layering** rather than structural shadows.

*   **The Layering Principle:** To lift a card, do not reach for a shadow first. Place a `surface-container-lowest` card on a `surface-container-low` background. The subtle contrast difference creates a "natural lift."
*   **Ambient Shadows:** For floating elements (Modals/Popovers), use a "Whisper Shadow":
    *   `box-shadow: 0 12px 32px -4px rgba(25, 28, 30, 0.06);`
    *   The color is a tinted version of `on-surface`, ensuring it looks like light passing through glass rather than a grey smudge.
*   **The Ghost Border Fallback:** If a container sits on an identical color (e.g., White on White), use a 1px border with `outline-variant` at **15% opacity**. Never use a 100% opaque border.
*   **Glassmorphism:** For sidebars or top-navs, use `surface-container-lowest` at 80% opacity with a `backdrop-filter: blur(20px)`. This grounds the UI in a 3D space.

---

## 5. Components

### Buttons & Interaction
*   **Primary:** High-gloss gradient (`primary` to `primary-container`). 16px (`xl`) border radius. High-contrast white text.
*   **Secondary:** `surface-container-high` background with `on-surface` text. No border.
*   **Haptic Sizing:** Buttons must have a minimum height of 48px to ensure a premium, accessible touch target.

### Data Cards & Lists
*   **The Divider Ban:** Never use horizontal lines to separate list items. Use **Vertical Rhythm** (16px to 24px gaps) or subtle alternating background shades (`surface-container-low` vs `surface-container-lowest`).
*   **Mindmap Nodes:** Use `xl` (1.5rem) corner radius. Connectors should be `outline-variant` at 30% opacity with a 2px width—never harsh black lines.

### Input Fields
*   **Quiet State:** No background, only a "Ghost Border" at the bottom or a subtle `surface-container-highest` background fill.
*   **Active State:** The border transitions to `primary-container` (#0051FF) with a 2px thickness. 
*   **Error State:** Use `error` (#ba1a1a) for text and a `error-container` (#ffdad6) soft glow.

### Sidebar Filters
*   **Integrated Design:** The sidebar should not have a vertical divider. Use a `surface-container-low` background for the entire sidebar area to distinguish it from the `surface-container-lowest` main content.

---

## 6. Do's and Don'ts

### Do
*   **Do** use generous whitespace (32px+) between major sections to let the "Digital Curator" aesthetic breathe.
*   **Do** use `primary-container` for active states and critical CTAs only. Excessive blue dilutes the "Trust" factor.
*   **Do** use Lucide-inspired icons with a "Regular" (2px) stroke weight for a refined, technical look.

### Don't
*   **Don't** use 1px #EEEEEE dividers. They clutter the UI and feel "dated fintech."
*   **Don't** use sharp corners. Every element, from small tooltips to large hero cards, must use at least an `md` (0.75rem) or `lg` (1rem) radius.
*   **Don't** use pure black (#000000). Always use `on-surface` (#191c1e) for typography to maintain visual softness.