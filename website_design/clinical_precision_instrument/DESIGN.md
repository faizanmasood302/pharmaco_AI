---
name: Clinical Precision Instrument
colors:
  surface: '#ecfdf8'
  surface-dim: '#cdded9'
  surface-bright: '#ecfdf8'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#e6f7f2'
  surface-container: '#e0f2ed'
  surface-container-high: '#dbece7'
  surface-container-highest: '#d5e6e1'
  on-surface: '#0f1e1c'
  on-surface-variant: '#3e4946'
  inverse-surface: '#243330'
  inverse-on-surface: '#e3f4f0'
  outline: '#6e7976'
  outline-variant: '#bdc9c5'
  surface-tint: '#006b5e'
  primary: '#006156'
  on-primary: '#ffffff'
  primary-container: '#0e7c6e'
  on-primary-container: '#befff1'
  inverse-primary: '#7bd7c6'
  secondary: '#006b59'
  on-secondary: '#ffffff'
  secondary-container: '#7cf8d9'
  on-secondary-container: '#00725e'
  tertiary: '#923b01'
  on-tertiary: '#ffffff'
  tertiary-container: '#b2521b'
  on-tertiary-container: '#ffefe8'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#98f3e2'
  primary-fixed-dim: '#7bd7c6'
  on-primary-fixed: '#00201b'
  on-primary-fixed-variant: '#005047'
  secondary-fixed: '#7cf8d9'
  secondary-fixed-dim: '#5edbbe'
  on-secondary-fixed: '#002019'
  on-secondary-fixed-variant: '#005142'
  tertiary-fixed: '#ffdbcc'
  tertiary-fixed-dim: '#ffb693'
  on-tertiary-fixed: '#351000'
  on-tertiary-fixed-variant: '#7a3000'
  background: '#ecfdf8'
  on-background: '#0f1e1c'
  surface-variant: '#d5e6e1'
typography:
  display-lg:
    fontFamily: DM Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: DM Sans
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  headline-md:
    fontFamily: DM Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-md:
    fontFamily: DM Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-serif:
    fontFamily: Source Serif 4
    fontSize: 17px
    fontWeight: '400'
    lineHeight: 26px
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  label-sm:
    fontFamily: DM Sans
    fontSize: 12px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.04em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 40px
  container-max: 1440px
---

## Brand & Style
The design system is engineered for high-stakes clinical decision support, emphasizing clarity, stability, and surgical precision. It targets healthcare professionals—pharmacists, geneticists, and physicians—who require a calm, "trusted instrument" interface that reduces cognitive load during complex data analysis.

The aesthetic follows a **Modern / Corporate** healthcare approach with subtle **Glassmorphism** influences for depth. It avoids the cold, sterile feel of traditional medical software by utilizing a warm base palette, while maintaining rigor through strict alignment and refined typography. Every element is designed to feel intentional and reliable, evoking an emotional response of professional confidence and focused calm.

## Colors
The palette is rooted in "Medical Teals" to establish an immediate association with healthcare and hygiene. 

- **Primary & Secondary:** Used for branding, primary actions, and navigational wayfinding.
- **Warm White Base:** The background uses a slightly warm white to reduce screen glare and eye strain during long clinical shifts.
- **Functional Accents:** Warm Coral and Muted Red are reserved strictly for warnings and high-risk pharmacogenomic alerts. Use these sparingly to ensure "alert fatigue" is minimized.
- **Depth:** Soft teal shadows and borders create a layered hierarchy without relying on heavy blacks or greys.

## Typography
This design system employs a tri-font strategy to compartmentalize information types:
1.  **DM Sans (UI):** Used for the structural interface, buttons, and navigation. Its geometric clarity ensures high legibility.
2.  **Source Serif 4 (Clinical):** Used exclusively for long-form clinical notes, patient histories, and recommendations. The serif structure aids horizontal eye tracking during deep reading.
3.  **JetBrains Mono (Data):** Reserved for genetic sequences, phenotypic values, and AI logs. The fixed-width nature allows for easy comparison of character strings and numeric values.

## Layout & Spacing
The layout follows a **Fixed Grid** model on desktop to maintain a "dashboard-instrument" feel where elements remain in predictable locations. 

- **Grid:** 12-column system with 24px gutters.
- **Consistency:** All spacing is derived from a 4px base unit. 
- **Sidebars:** Use a fixed-width left navigation (240px) to house patient search and global controls.
- **Reflow:** On mobile devices, the 12-column grid collapses to a single-column vertical stack with 16px side margins. Data-heavy tables should implement horizontal scrolling rather than column dropping to preserve clinical integrity.

## Elevation & Depth
Depth is communicated through **Tonal Layers** and **Ambient Shadows**. 

- **Surface 0 (Page):** #FAFAF8 (Warm White).
- **Surface 1 (Cards):** #FFFFFF. These elements use a 1px border (#D1E3E0) and a soft teal-tinted shadow (Hex: #0E7C6E at 8% opacity, 12px blur, 4px Y-offset).
- **Interactive Depth:** On hover, cards should slightly increase their shadow spread to indicate interactivity.
- **Modals:** Use a heavy backdrop blur (12px) behind the modal to focus the clinician’s attention entirely on the critical task at hand.

## Shapes
The shape language is **Soft** but disciplined. 

- **Standard Elements:** Buttons, input fields, and cards utilize a 0.25rem (4px) radius. This provides a modern feel without appearing "playful" or unprofessional.
- **Pills:** Phenotype badges use a fully rounded (pill-shaped) radius to distinguish them from interactive buttons.
- **Data Containers:** Tables and logs maintain sharp 0px inner corners for a technical, precise look.

## Components
- **Pill Badges:** Used for phenotypes. 
    - *Ultra-Rapid:* Secondary Teal fill with white text.
    - *Normal:* Highlight Tint fill with Primary Teal text.
    - *Poor:* Muted Red fill with white text.
- **AI Pipeline Stepper:** A vertical or horizontal progression indicator using Primary Teal dots for completed steps, Active Teal for current, and 1px borders for upcoming steps.
- **Document Panels:** Use Source Serif 4 for content. Backgrounds should be the Highlight Tint (#E4F7F4) to separate the "Report" area from the "Interface" area.
- **Patient Cards:** Must include a high-contrast severity badge in the top-right corner using the Critical or Accent color tokens.
- **Input Fields:** 1px #D1E3E0 border, shifting to Active Teal on focus. Use JetBrains Mono for inputs containing clinical measurements.
- **Buttons:** 
    - *Primary:* Active Teal (#17A98E) background, white text.
    - *Secondary:* Ghost style with Primary Teal border and text.