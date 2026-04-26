# Design System Strategy: The Digital Sommelier

## 1. Overview & Creative North Star
The North Star for this design system is **"The Digital Sommelier."** 

We are moving away from the frantic, high-velocity "feed" culture of modern news. Instead, we are designing a ritual—a curated, intentional experience that feels like stepping into a quiet, high-end espresso bar at 7:00 AM. 

This system rejects the "template" look. We achieve a bespoke editorial feel through **intentional asymmetry**, where content is allowed to breathe within expansive margins. We prioritize **Tonal Layering** over structural lines, creating a UI that feels like stacked sheets of heavy-stock vellum and frosted glass rather than a flat digital grid. It is sophisticated, authoritative, and deeply comforting.

---

## 2. Colors: The Brew Palette
Our palette is rooted in the organic transitions of roasted coffee and the warmth of morning light.

### Tonal Hierarchy
- **Primary (`#33210d`) & Primary Container (`#4b3621`):** These represent the "Brew." Use these for high-intent actions and deep-contrast elements.
- **Surface & Background (`#fbfbe2`):** The "Warm Cream" base. This is the canvas.
- **Tertiary (`#3c1d00`) & Accent (`#ff8c00`):** The "Morning Orange." Use sparingly for "New Story" indicators, active toggles, or critical alerts.

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders to define sections.
Boundaries must be created through background color shifts. For example, a dashboard section should use `surface-container-low` to distinguish itself from the `surface` background. If you feel the urge to draw a line, increase the padding and shift the background tone instead.

### Signature Textures & Glassmorphism
To create "visual soul," use semi-transparent surface colors with a `backdrop-filter: blur(20px)` for floating navigation or overlay cards. This allows the warmth of the background to bleed through, ensuring the UI feels integrated and organic. Use subtle gradients (transitioning from `primary` to `primary-container`) for main CTA buttons to provide a "roasted" depth that flat hex codes cannot achieve.

---

## 3. Typography: The Editorial Voice
We use typography to convey authority and calm.

- **Display & Headlines (`Plus Jakarta Sans`):** These are our "Broadsheet" headers. Use `display-lg` for daily digests to create a high-end editorial impact. 
- **Body (`Manrope`):** Optimized for long-form reading. We use `body-lg` (1rem) as the standard to ensure the news is digestible and reduces eye strain.
- **Technical Logs (`Space Grotesk` / `JetBrains Mono`):** For the "Automation" side of the product (logs, terminal windows), we switch to these monospaced families. This creates a functional contrast between the "Organic" news and the "Mechanical" AI assistant.

---

## 4. Elevation & Depth: Tonal Layering
In this system, elevation is not about "distance from the screen" but "density of the material."

- **The Layering Principle:** Depth is achieved by stacking `surface-container` tiers. Place a `surface-container-lowest` card on a `surface-container-low` section to create a soft, natural lift.
- **Ambient Shadows:** When a floating effect is required (e.g., a modal or a floating action button), use extra-diffused shadows. 
    - **Shadow Color:** Tinted with `primary` (Brew Coffee) at 4%–8% opacity. 
    - **Blur:** Minimum 24px. Never use pure black or grey for shadows; it kills the "Warm & Minimal" aesthetic.
- **The "Ghost Border" Fallback:** If a border is required for accessibility, use the `outline-variant` token at 15% opacity. It should be felt, not seen.

---

## 5. Components: The Brew Kit

### Dashboard Stats Cards
- **Style:** No borders. Use `surface-container-high` as the base.
- **Layout:** Large `headline-lg` numbers in `primary`. Pair with `label-md` in `on-surface-variant` for descriptors.
- **Interaction:** On hover, shift the background to `surface-container-highest` and apply a 4% ambient shadow.

### Terminal-Style Log Windows
- **Base:** `primary-container` (#4B3621) with a 0.8 opacity.
- **Typography:** `JetBrains Mono` or `Space Grotesk`. 
- **Detail:** Use `on-tertiary-fixed` (#FFB77D) for "Success" logs and `error` (#BA1A1A) for "Halt" states. No scrollbars; use a subtle fade-to-transparent at the top and bottom.

### Elegant Forms
- **Input Fields:** A single `outline-variant` line at the bottom (0.5px) rather than a box. On focus, the line transitions to `accent` (#FF8C00) and a small "Morning Orange" glow appears.
- **Labels:** Use `label-sm` in all-caps with 0.05em letter spacing to evoke a premium, architectural feel.

### Buttons
- **Primary:** `primary-container` background with `on-primary` text. `rounded-md` (0.75rem) corners.
- **Secondary:** Transparent background with a `Ghost Border`.
- **Tertiary:** Text-only with an underline that appears only on hover.

---

## 6. Do's and Don'ts

### Do
- **Use "White Space" as a Separator:** If two pieces of content feel cluttered, increase the margin rather than adding a line.
- **Embrace Asymmetry:** Let the "Daily Brew" headline sit slightly off-center to mimic a bespoke magazine layout.
- **Tint Everything:** Ensure every neutral color has a hint of the "Warm Cream" or "Coffee" base. Pure #FFFFFF and #000000 are forbidden.

### Don't
- **Don't use 100% Opaque Borders:** This destroys the "Soft Minimalism" goal.
- **Don't use Harsh Transitions:** Color shifts between containers should be subtle (e.g., `surface` to `surface-container-low`).
- **Don't Overuse the Accent:** The "Morning Orange" is like a garnish. If it covers more than 5% of the screen, it’s too much.
- **Don't use Standard Shadows:** Avoid the "floating box" look of 2014 Material Design. Use tonal shifts first, shadows last.