# Serif Biomedicines Design System

Two sources, in this order of authority.

1. The [Serif Brand Guide](https://brandpad.io/serif/) on Brandpad, by One Design Company, updated May 2026 (password protected).
   It sets the palette, the typefaces and how to use them, the logo colors, the "S" monogram, the molecular illustrations, and the brand voice.
   Marketing contact: Jacob Rubens, jrubens@flagshippioneering.com.
2. [serifbiomedicines.com](https://serifbiomedicines.com), extracted on 17 September 2026.
   Pages reviewed: home, Science, Team, Updates, a team profile, a press release, the 404 page, and the mobile navigation.
   Sources: the production stylesheet (Tailwind v4 with a custom `@theme`), the JavaScript modules, the rendered pages at 1440px and 390px, and computed styles.

Where the two disagree, the brand guide wins.
Colour, typography, logo, brand graphics and voice lead with the brand guide, and rules there are labelled **Brand guide** or **Site**.
Layout, shape, components and motion come from the site.

This document describes what Serif's design does and why, so that new work reads as Serif rather than as a generic biotech site.
Machine-readable values live in [`tokens.css`](tokens.css).
Screenshots of every state referenced below live in [`reference/`](reference/).

## The Idea Behind the Design

The company name is a typographic metaphor and the whole site is built on it.
A serif changes the shape of a letter without changing what the word means.
Serif's chemistry changes the form of DNA without changing the genetic message.
Every visual decision restates that one idea.

* Two typefaces, one voice.
  A sans (Denim) is the plain form and a serif (Eliza) is the modified form.
  They swap mid-sentence at the same size and line height, so the sentence reads as one voice in two forms.
* The letterform is the molecule.
  The hero is a giant sans "S" that morphs into molecular blobs on hover.
  Cropped hairline outlines of the same "S" at enormous scale decorate page heads and CTA cards, where they read as helix arcs.
  The ACGT background video sets nucleotide letters in grey sans and flips single letters into dark serif: "the code of life in different fonts".
* Form changes under attention.
  Hovering a card does not lift it or add a shadow.
  Its corners soften from `radius-sm` to `radius-lg`.
  Portraits zoom slowly, titles turn vivid, underlines draw in.
  The change is always a change of form, never of position or depth.
* Restraint with one hot signal.
  **Brand guide:** "Floods of Dark and Light Gray should dominate most layouts." Red is used "sparingly as a highlight or call to action color" and "shows our impact or modification."
  **Site:** the page is a Light Gray ground with warm stone mid-tones and Dark Gray ink.
  Red, named `vivid` in the stylesheet, marks the live thing: the cursor, the hovered title, the pressed button, the external-link dot, the text selection.

## Vibe in One Paragraph

Quiet, editorial, confident, and a little witty.
Headlines are set in regular weight with full stops, like sentences in a book, not shouted claims.
Nothing is uppercase, nothing is bold except sub-heads, and there is no icon set beyond an arrow, a dot, play, pause, and close.
Whitespace is generous and grows with the viewport.
Motion is slow where it is decorative (ink-in text, portrait zoom) and quick where it is functional (buttons, links, cards).
The feeling is a well-set science book that happens to move.

## Colour

### Palette

**Brand guide:** "Our restrained color palette is a critical element of our brand's visual language."
Five colors, and the logo adds White.
Use the hex values: the RGB values Brandpad prints for Dark Gray, Mid Gray and Warm Gray do not match their hex, and the hex matches the swatches.
See [`reference/brandpad-palette.png`](reference/brandpad-palette.png).

| Brand name | Token | Site name | Hex | PMS | Role |
| --- | --- | --- | --- | --- | --- |
| Dark Gray | `dark-gray` | `gray-9` | `#2e2d29` | Black 2C | Ink: primary text, inverse surface, logo |
| Mid Gray | `mid-gray` | none | `#525046` | 4230C | Secondary text, secondary surface |
| Warm Gray | `warm-gray` | `gray-5` | `#ada990` | 7535C | Ghost: rules, placeholders, inactive text |
| Light Gray | `light-gray` | `gray-1` | `#e5e5e5` | 427C | Page ground, inverse text |
| Red | `red` | `red-3` | `#ff3d00` | 2028C | The accent |
| White | `white` | `white` | `#ffffff` | | Stark: cards, media frames, logo on dark grounds |

**Site:** the site adds tints between the brand colors.
The grey ramp is warm: gray-4 and Warm Gray are stone and khaki, not neutral grey, and they match the warm backdrops of the studio portraits and the 3D renders.
The site does not use Mid Gray; its secondary text is gray-7.
Keep these tints to the jobs listed and use the brand colors for everything else.

| Token | Hex | Role |
| --- | --- | --- |
| `gray-2` (`hairline`) | `#d6d6d4` | Start colour of the ink-in text reveal; hairlines and hover fills on `stark`, where Light Gray (1.26:1) disappears |
| `gray-3` | `#c7c6bd` | Hairline decoration stroke |
| `gray-4` | `#bdbaa6` | Site stone secondary surface, hero S outline, diagram strokes; new work uses Warm Gray for surfaces |
| `gray-7` | `#706d60` | Site secondary text; new work uses Mid Gray |
| `red-4` (`red-text`) | `#c72e00` | Red darkened for text: 5.50:1 on white. Defined but unused on the site pages reviewed |
| `black` | `#121110` | Defined but unused; text is never pure black |

### Semantic Names

Use the site's own vocabulary rather than raw greys.

* Surfaces: `bg-primary` (Light Gray), `bg-secondary` (Warm Gray; the site uses gray-4), `bg-inverse` (Dark Gray), `bg-scrim` (Dark Gray at 90%), `stark` (white)
* Text: `fg-primary` (Dark Gray), `fg-secondary` (Mid Gray), `fg-inactive` (Warm Gray), `fg-inverse` (Light Gray)
* Accent: `vivid` (Red), `ghost` (Warm Gray), `neutral` (Light Gray)

### Rules of Use

* **Brand guide:** floods of Dark Gray and Light Gray dominate most layouts.
  Mid Gray and Warm Gray fill secondary panels and carry line work.
* **Brand guide:** Red is a highlight or a call to action, used sparingly.
  The guide's own samples use it for call-to-action pills, arrows, a monogram outline, and at most one panel in a set.
* **Accessibility:** Red is mid-luminance.
  White on `#ff3d00` is 2.82:1 and Dark Gray on it 3.86:1, so on screen Red carries no text below large size, and white text on Red fails even the large-text threshold.
  Where Red must be text, use `red-text` (`#c72e00`, 5.50:1 on white).
  Red as a mark clears the 3:1 non-text threshold on white (3.55:1) and on Dark Gray (3.89:1), but not on Light Gray (2.82:1).
* **Site:** text is `fg-primary` on `bg-primary` or `stark`, or `fg-inverse` on `bg-inverse`.
  There is no coloured text at rest.
* **Site:** `vivid` appears at rest only as tiny marks: the 5px dot separator, the external-source dot, the play icon inside a control button, the cursor.
* **Site:** `vivid` appears at scale only in a hover, focus, or selection state.
* `stark` is a surface, not a text colour, except on a `vivid` hover fill.
* Selection is inverted: `vivid` background with `fg-inverse` text.
  Inside a vivid area the selection flips to `fg-inverse` background with `fg-primary` text.
* Imagery keeps the palette.
  3D molecular renders are grey with Red DNA; diagrams are gray-4 hairlines with sans labels and white pill labels; portraits sit on warm stone.

## Logo

* **Brand guide:** the wordmark "Serif" is a blend of sans and serif.
  It is only ever Dark Gray or White.
  Never alter its color, and keep enough contrast with the background for legibility.
* **Brand guide:** the "Biomedicines" lockup is for places with little or no industry context, such as sponsorships or signage.
  Use it with discretion; the same color rules apply.
* See [`reference/brandpad-logo.png`](reference/brandpad-logo.png) and [`reference/brandpad-logo-biomedicines.png`](reference/brandpad-logo-biomedicines.png).

## Typography

### Typefaces

**Brand guide:** the name Serif comes from allography, the variant forms of letters created through small distinctions such as a serif.
The typographic system mixes a sans (Denim) and a serif (Eliza).
See [`reference/brandpad-typography.png`](reference/brandpad-typography.png) and [`reference/brandpad-type-usage.png`](reference/brandpad-type-usage.png).

* Denim, by [Displaay Type Foundry](https://displaay.net/typeface/denim).
  Regular and SemiBold with italics.
  **Brand guide:** "a well-balanced, workhorse typeface."
  Headlines are set in Denim Regular by default, and all smaller text, such as body copy, is Denim.
  **Site:** a humanist-technical sans with flattened overshoots, used for body, navigation, buttons, labels, and the plain half of headlines.
* Eliza, by [Camelot Typefaces](https://camelot-typefaces.com/eliza).
  Regular only.
  **Brand guide:** "a familiar, humanistic serif with modern, pixel-influenced geometry," used in Eliza Regular for the highlight inside a Denim headline.
  **Site:** also used for whole titles: article cards, Team section titles, square CTA titles, the footer email.
  The brand guide limits Eliza to headline highlights, so new work sets those titles in Denim with at most a serif highlight.
* Both fonts are licensed.
  Do not copy the `woff2` files from the site into other projects.
* **Brand guide:** when the brand typefaces are unavailable, use Helvetica or Arial for Denim and Georgia for Eliza.
  **Site:** the stylesheet ships size-adjusted fallbacks: Arial at 94% for Denim and Times New Roman at 111% for Eliza.
  The token stacks list the open substitutes first, then the brand's alternatives.

### Free Substitutes

Denim and Eliza cannot be redistributed, so [`fonts-open/`](fonts-open/) holds open-licensed stand-ins under the SIL Open Font License.
They were chosen by rendering 30 Google Fonts candidates against the real fonts and comparing set width, x-height, cap height, and letter construction.
See [`reference/font-candidates.png`](reference/font-candidates.png) for the full line-up and [`reference/font-substitutes.png`](reference/font-substitutes.png) for the chosen pair beside the originals.

* Denim becomes Figtree at `size-adjust: 96%`.
  Single-storey `g`, flagged `1`, straight-legged `R`, identical x-height and cap height, about 4% wider before adjustment.
  Variable weight, so 400 and 600 both work.
* Eliza becomes PT Serif at `size-adjust: 104%`.
  Same squared transitional construction, straight `R` and `K` legs, flat `y` terminal, moderate contrast, about 4% narrower before adjustment.
  Slightly heavier than Eliza at display size.
* Alternates if the primary pair is unavailable: Hanken Grotesk at 97% for Denim, Newsreader at 104% for Eliza.
* With the adjustments, headlines and card titles break on the same words as the live site.
  Include `fonts-open/fonts.css` before `tokens.css`; the token font stacks already list the substitutes after the licensed names, and Helvetica, Arial and Georgia after those.

Free trials of the real fonts exist for mock-ups but not for shipping.

* [Displaay trials](https://displaay.net/trials) send full-character-set files by email.
  The trial license allows internal sketching and client presentation on one machine, not public or commercial use.
* [Camelot trials](https://camelot-typefaces.com/trials) send files by email with a limited character set: A to Z, a to z, 0 to 9, and basic punctuation.
  Accented characters fall back to the base letter, and designs made with trials may not be shown publicly.
* Retail licenses start at 75 EUR per style at Displaay.
  Camelot offers 20% off a roman and italic pair and 50% off the cheaper product in a desktop plus web bundle.

### Scale

The scale is fluid and interpolates linearly from a 320px to a 1920px viewport.
Line heights are tight everywhere, including body copy, which gives the dense set feel.

| Step | Min | Max | Line height | Tracking | Where it is used |
| --- | --- | --- | --- | --- | --- |
| `text-8` | 41px | 107px | 0.96 | -0.02em sans, -0.03em serif | Page-head mixed headline (`mixed-headline--lg`) |
| `text-6` | 32px | 69px | 0.96 | -0.01em | Display sans: "Updates", profile names, press-release titles |
| `text-5` | 29px | 55px | 1.0 | -0.01em sans, -0.02em serif | Section mixed headlines, "The latest from Serif.", square CTA titles |
| `text-4` | 26px | 44px | 1.04 | -0.01em | Hero flanking phrases, Team section titles in serif |
| `text-3` | 23px | 35px | 1.04 | -0.01em | Hero mission statement, rich-text h2 |
| `text-2` | 20px | 28px | 1.04 | 0 | Article-card titles in serif, footer email |
| `text-1` | 18px | 22.5px | 1.15 body, 1.1 sub | 0 | Body paragraphs, animated statement label, semibold names |
| `text-0` | 16px | 18px | 1.15 | 0 | Nav links, buttons, dates, roles, captions, section labels |
| `text--1` | 14.2px | 14.4px | 1.15 | -0.005em | Small body |
| `text--2` | 12.5px | 12.5px | 1.15 | 0.01em | Footer fine print |

### Named Styles

Production uses these class names.
Reuse them verbatim.

* `text-display-6x-sans`, `text-title-5x-sans`, `text-title-5x-serif`, `text-title-4x-sans`, `text-title-4x-serif`, `text-title-3x-sans`
* `text-sub-2x-serif`, `text-sub-1x` (the only 600 weight in the system)
* `text-body-1x`, `text-body-0x`, `text-body--1x`, `text-body--2x`
* `mixed-headline` and `mixed-headline--lg`, with `<span class="font-serif">` around the modified phrase
* `rich-text` for CMS copy, `rich-text long-form` for press releases

### The Mixed Headline

This is the signature move and the thing most likely to be done wrong.

* **Brand guide:** headlines are Denim Regular with a highlight in Eliza Regular.
  The highlight showcases impact or what makes Serif unique, and runs about 1 to 3 words, never more than half the headline.
* **Site:** the serif span inherits the exact size and line height of the sans around it.
  Do not enlarge, italicise, colour, or embolden it.
* The serif marks the transformation or the payoff, not a random word.
  Site examples: "The code of life, now in *different fonts*.", "*DNA*, rewritten as medicine.", "Building the future of DNA medicines, *together*.",
  "Transforming DNA from *blueprint into therapeutic*.", "Jacob (Jake) Rubens, *PhD*", "*404*: Page not found".
* **Site:** one swap per headline, occasionally two in a long statement.
* **Site:** headlines are `text-wrap: balance`, regular weight, and end with a full stop.
  The brand guide's samples set some headlines without one ("Introducing nucleic acid allography").

### Typographic Finish

The site cares about typesetting at a level most sites skip.
Keep these when building new pages.

* Discretionary ligatures are on globally (`font-feature-settings: "dlig"`).
* `hanging-punctuation: first allow-end` so opening quotes hang in the margin.
* Soft hyphens are inserted server-side in every word longer than a few letters, so long words break cleanly in narrow measures.
* Acronyms are wrapped in `<span class="caps">` and figures in `<span class="numbers">`.
  No CSS is attached today, but the hooks exist for small caps and oldstyle figures.
* Opening quotes use `pull-double` and `push-double` spans so the quote mark hangs.
* Body uses `text-wrap: pretty`, headlines use `text-wrap: balance`.
* External links end in a typed `↗` glyph, never an icon.
* Dates are short and set in sans: `May 12 '26`.
  Full dates on press releases read `April 21, 2026 at 6:30AM EDT`.
* Nothing is uppercase.
  **Brand guide:** headlines and body copy are always in sentence case.
  **Site:** section labels are ordinary sentences at `text-body-0x` or `text-body-1x`, such as "How Modified DNA works" and "The shape of things to come."

## Layout

### Grid and Gutters

* 12-column CSS grid with `gap-sm-lg` (1rem to 2.25rem).
* Two page gutters.
  Full-bleed blocks such as media, card lists, and the footer use `px-sm-lg` (1rem to 2.25rem).
  Text-led page heads and text sections use `px-sm-3xl` (1rem to 6.75rem), which pushes copy inward on wide screens.
* Content is left-aligned to the gutter.
  There is no centred max-width container; wide screens get wider gutters instead.

### Recurring Page Head

Every inner page opens the same way.

* Cropped hairline "S" outline anchored top-left, `pointer-events: none`.
* Headline in `mixed-headline--lg` spanning columns 1 to 7.
* Intro paragraph in `rich-text text-body-1x` in columns 9 to 12, top-aligned to the headline, followed by one pill CTA after `mt-lg-xl`.
* Top padding `pt-4xl-5xl` (8rem to 11.25rem) so the head sits well below the fixed header.

### Recurring Section Patterns

* Sticky label left, content right.
  Team sections keep a serif title (`text-title-4x-serif`) sticky in columns 1 to 3 while a 3-up grid of people scrolls in columns 4 to 12.
  The Updates page keeps the title, filters, and press email sticky in the left half while cards scroll on the right.
* Sticky text, cross-fading media.
  On Science, each text block is sticky and full-height on the left while the matching image or video fades in on the right.
  The media stack lives in a 150vh-minimum container so the swap has room.
* Animated statement.
  A short sans label at `text-body-1x` in the left half and a large mixed-type paragraph in the right half that inks in on scroll, followed by a pill CTA.
* Square CTA pair.
  Two `aspect-square` links side by side at the end of Science, Team, and Updates.
  One is `bg-secondary`, one is `bg-inverse`.
  Each carries the S-outline decoration, a control-button arrow top-left, and a `text-title-5x-serif` title bottom-left.
* Split media.
  Home pairs a mixed headline and paragraph on the left with a rounded white media frame on the right, `md:grid-cols-2`.

### Home Hero

* On desktop the page is 200vh.
  "Shaping tomorrow's" in `text-title-4x-sans` and "genetic medicines." in `text-title-4x-serif` are sticky in the outer columns.
  The white "S" scrolls up between them, and the mission statement in `text-title-3x-sans` scrolls into the centre after it.
* The "S" is white with a 1px `gray-4` outline.
  On desktop it is six Lottie tiles in two columns that morph into molecular forms on hover.
  On mobile it is one self-animating Lottie.
  With reduced motion it is a static image.
* On mobile the two phrases are sticky bands at the top and bottom of the viewport with the "S" between them.

### Spacing Rhythm

* Vertical rhythm comes from fluid pairs, not fixed values.
  A pair like `lg-4xl` is 2rem on a phone and 9rem on a wide desktop.
* Blocks are separated by `mt-sm-lg` and carry their own internal padding, usually `pt-lg-4xl` or `pt-sm-4xl` above and `pb-lg-5xl` or `pb-lg-6xl` below.
* The footer sits after `pt-2xl-6xl` (4rem to 13.5rem) of space.
* Small gaps are `2xs` and `3xs`; list gaps are `sm`; card padding is `md-lg`.

### Breakpoints

| Name | Min width | Notes |
| --- | --- | --- |
| `MIN` | 320px | Fluid scales start here |
| `SM` / `NAV` | 640px | Two-up grids, desktop navigation |
| `MD` | 784px | Sticky media, 12-column layouts, 3-up people grid |
| `LG` | 1440px | Footer alignment |
| `MAX` | 1920px | Fluid scales stop here |

## Shape

* Radius is fluid and tied to the space scale.
  `radius-sm` is the resting card radius (about 16 to 18px).
  `radius-md` frames media and the mobile nav panel.
  `radius-lg` (32 to 54px) is the hovered card radius.
* Pills (`999px`) are for actions and labels only: buttons, filter chips, control buttons, diagram labels.
* No borders on cards.
  The only rules are the 1px `fg-inactive` left rule on a person card and the 1px outline on a knockout button.
* No shadows anywhere.
  Depth comes from surface colour only: `stark` on `bg-primary`, `bg-inverse` for emphasis.
* Media frames are `overflow: hidden` with `radius-md`, on a `ghost` or `bg-secondary` placeholder while loading.
* Portraits are 3:4, slideshow images 15:8, video 16:9.
* The brand guide publishes no radius or spacing values.
  Its samples use Light Gray, Dark Gray, Mid Gray and Warm Gray panels with corners close to `radius-sm`, which matches the site.

## Brand Graphics

* **Brand guide:** the "S" monogram is the primary brand graphic.
  It shifts between sans and serif to stand for adding small modifications to a molecule.
  An approved library of "S" graphics exists in many colorways; use the whole "S" or crop in to use it as background texture.
  See [`reference/brandpad-monogram.png`](reference/brandpad-monogram.png).
* **Brand guide:** molecular illustrations come in two styles.
  The dimensional style is primary; the flat style is for many molecules at once or for small sizes.
  See [`reference/brandpad-molecular-illustrations.png`](reference/brandpad-molecular-illustrations.png).
* **Brand guide:** sample applications (stationery, swag, office signage, business cards, presentation, social and Zoom templates) show the system in use.
  See [`reference/brandpad-applications.png`](reference/brandpad-applications.png).
  Asset downloads are linked from the guide.

## Components

### Header

* Fixed, full width, `px-sm-lg py-xs-sm`, items baseline-aligned.
* Wordmark "Serif" in Eliza at `h-md` (about 1.5rem) on the left.
* Nav links at `text-0`, gap `md`, right-aligned.
  Each link has a 5px dot in a 1em box before the label that fades in over 300ms on hover, focus, or current page.
  Careers is external and ends in `↗`.
* Transparent at the top of the page, `bg-primary` once scrolled.
* Hides on scroll down after 80px and reveals on scroll up, translating over 500ms with `cubic-bezier(.25,1,.5,1)`.
* Below 640px the nav collapses to a "Menu" button that also names the current section ("Menu ・Science").

### Mobile Navigation

* A floating panel inset `2xs` from the top and sides, `bg-primary`, `radius-md`, over a `bg-scrim` that fades in over 250ms.
* Small wordmark top-left, close button top-right, links right-aligned in a column with gap `md`.
* Body scroll is locked while open.
* Open and close are GSAP timelines that grow the panel from the closed header height.

### Pill Button (`cta-link`)

* `bg-inverse` fill, `fg-inverse` text, `text-0`, padding `2xs` by `sm`, gap `2xs`.
* Hover and focus fill `vivid` over 200ms; text stays `fg-inverse`.
* Active presses to `scale(0.97)`.
* Knockout variant: transparent with a 1px `fg-primary` outline; hover fills `stark`; the `active` class fills `bg-inverse` for the selected filter.
* External buttons append `↗` as text.

### Text Links

* `simple-link` draws a 0.09em underline in from the left over 200ms using a background gradient.
  Used in the footer, breadcrumbs, and the press email.
* Links inside `rich-text` use a three-segment gradient so the underline slides out and back in over 350ms.
* Breadcrumbs are a typed `←` followed by the parent page name.

### Control Button

* Round, default size `xl` (about 3rem), `neutral` fill with a `vivid` glyph.
* Hover and focus invert to `vivid` fill with `stark` glyph over 250ms.
* Large variant (`2xl-3xl`) with `fg-primary` glyph opens the video modal.
* Small variant (`lg`) is `bg-inverse` at rest and closes the modal.
* Glyphs are simple filled shapes: play triangle, two-bar pause, 12px X, arrow.
* Also used as a static decoration in the square CTA cards, where it inverts when the whole card is hovered.

### Article Card

* `stark` surface, padding `md-lg`, `radius-sm`, listed in a single column with gap `sm`.
* Title in `text-sub-2x-serif`, `fg-primary`.
* Meta row at `text-body-0x` after `mt-sm-md`: date, then for external items a 5px `vivid` dot and the source name with `↗`.
* Hover: radius grows to `radius-lg` and the title turns `vivid`, both over 300ms.
  Nothing moves or lifts.
* The whole card is clickable; the JS forwards a click anywhere on the card to the title link unless the user is selecting text.

### Person Card

* 1px `fg-inactive` left rule with `pl-sm-lg`.
* 3:4 portrait on a `ghost` placeholder, `radius-sm`.
* Name in `text-sub-1x` (semibold), role in `text-body-0x` beneath.
* Hover: portrait scales to 1.08 over 1s with `ease-out-quartic`; frame radius grows to `radius-lg` over 800ms.
* Board, advisors, and founders use the same card without a portrait: name, role, then affiliation lines after `mt-4`.

### Square CTA Card

* `aspect-square`, padding `sm-2xl`, `radius-sm`, content spread between top and bottom.
* Surfaces alternate `bg-secondary` with `fg-primary` and `bg-inverse` with `fg-inverse`.
* Decorated with the hairline S outline, which disappears on hover as the card fills `stark` and the corners round to `radius-lg` over 150ms.
* Title in `text-title-5x-serif`, balanced.
* Careers card rotates its arrow 45 degrees to point outward.

### Media

* Background video figures are white or stone frames with a small control button bottom-right that toggles play and pause.
  Video is lazy-loaded 300px before entering view and paused under reduced motion.
* The video modal is a native `<dialog>` with a `bg-inverse` backdrop, a Plyr player with white controls and `vivid` hover, and a close control top-right.
* The image slideshow has progress-bar pagination: 4px white bars that fill left to right with the autoplay progress, a 5 second interval, 1 second fade, and a pause toggle that turns `vivid` on hover.
* Diagrams are hairline `gray-4` strokes with sans labels and white pill labels, and interactive regions reveal an overlay image on hover.

### Footer

* Large wordmark at 188px wide, then fine print at `text--2x`: "A Flagship Pioneering company." and the copyright line.
* Right half holds the email in `text-sub-2x-serif`, a three-line address at `text-body-0x` with `leading-none`, and a column of `simple-link` items.
* Footer is on the page ground, not a separate band.

### Custom Cursor

* A `vivid` disc, 52px at full size, shown at one third scale at rest.
* Grows to full size over 300ms when over a link, button, input, or card.
* Uses `mix-blend-mode: multiply` over interactive elements so it tints whatever is beneath it.
* Follows the pointer through a 100ms GSAP tween with `power3.out`, so it trails slightly.
* Only enabled when `(hover: hover)` matches.

### Skip Link and Focus

* A skip-to-content link is the first element and becomes a pill on focus.
* `:focus-visible` outlines sit 0.35rem outside the element.
* Every hover state is mirrored for `focus-visible` and, on cards, `focus-within`.

## Motion

### Principles

* Form, not position.
  Hovers change radius, colour, scale, or underline.
  Nothing translates on hover and nothing casts a shadow.
* Two speeds.
  Functional feedback is 150 to 300ms with `ease-out`.
  Decorative motion is slow: 750ms image fade, 800ms to 1s portrait change, 3s ink-in.
* Ease-out everywhere.
  Nothing uses ease-in or bounce.
* Everything respects `prefers-reduced-motion`.
  Transitions collapse to 0.001ms, videos pause, the hero becomes a still image, and sticky media shows all frames.

### Reference Timings

| Interaction | Duration | Easing |
| --- | --- | --- |
| Square CTA fill and radius | 150ms | `ease-out` |
| Pill button colour, simple-link underline | 200ms | `ease-out` |
| Control button, site scrim | 250ms | `ease-out` |
| Article card radius and title colour, nav dot | 300ms | `ease-out` |
| Rich-text link underline | 350ms | `ease-out` |
| Header hide and reveal | 500ms | `cubic-bezier(.25,1,.5,1)` |
| Lazy image fade | 750ms | `ease-out` |
| Person card radius | 800ms | `ease-out` |
| Portrait zoom to 1.08 | 1s | `cubic-bezier(.165,.84,.44,1)` |
| Hero DNA overlay slide | 1s | `cubic-bezier(.16,1,.3,1)` |
| Ink-in statement | 3s | `ease-out` |
| Button press | instant | `scale(0.97)` |

### Scroll Choreography

* The ink-in statement splits text into characters and colours them from `gray-2` to `gray-9` with a 10ms stagger, scrubbed to scroll between the block's top at 65% of the viewport and its bottom at the centre.
  Words appear to be inked onto the page as you read down.
* Sticky media sections fade the active image in and the previous one out, keyed to whichever text block is most visible.
* The header hides after 80px of downward scroll and returns on any upward scroll.
* Lazy images fade from 0 to 1 as they load rather than popping in.

### Motion Libraries in Production

* GSAP with ScrollTrigger and SplitText for the cursor, header reveal, navigation timelines, sticky media, and the ink-in statement.
* Lottie for the hero "S" morph.
* Splide for slideshows, Plyr for video, body-scroll-lock for the nav and modal.

## Voice

**Brand guide:** the persona is the Inspired Inventor (50% Pathfinder, 40% Creator, 10% Ruler).
Its attributes come in pairs, such as "bold but not loud," "refined but not dull," "restrained but not pessimistic," and "we have plans, not dreams."
The voice has four qualities.

* Informed: language worthy of a large goal, not sound bites.
  For now, lean into opportunities rather than deliverables, and questions rather than declarative statements: "What if we could control the source code in every cell?"
* Optimistic: honest about the stakes and the challenges, never hyperbolic.
* Humble: modest language, no bragging, and credit to the work Serif builds on.
* Focused: grounded and personable, like a human wrote it, with the science made easy to understand.
  The focus is scientific opportunity now and patients and impact later.

**Site:**

* Headlines are short declarative sentences with a full stop.
  "DNA, rewritten as medicine." "The latest from Serif." "The shape of things to come."
* Sentence case throughout, including buttons: "Our science", "All updates", "Join our team".
* Wordplay on type and text is on-brand: "The code of life, now in different fonts.", "'Type' Casting".
* Body copy is plain and specific.
  Technical terms appear without softening, and DNA, RNA, and mRNA are used as-is.
* No exclamation marks and no marketing superlatives.
  The brand guide favors questions for now, so an opening question is on-brand even though the site uses none.

## Do and Do Not

Do:

* Set headlines in regular weight and end them with a full stop
* Use one sans-to-serif swap per headline on the payoff phrase
* Grow the radius on hover and change colour; leave position alone
* Let Dark Gray and Light Gray dominate the layout (brand guide)
* Keep Red for the live element, tiny marks, and the call to action
* Keep the Eliza highlight to about 1 to 3 words, and set everything smaller than a headline in Denim (brand guide)
* Set the logo in Dark Gray or White only (brand guide)
* Use fluid pairs for section spacing so desktop breathes and mobile stays tight
* Type arrows as glyphs (`↗`, `←`, `→`)
* Mirror every hover with focus-visible

Do not:

* Use shadows, card lifts, or borders on cards
* Use uppercase, letter-spaced eyebrows, or bold display type
* Set the serif span larger, coloured, or italic
* Flood a layout with Red or set text on it on screen
* Set whole titles or body copy in Eliza (brand guide)
* Recolor the logo (brand guide)
* Use pure black or pure white for text
* Add an icon library; the system has an arrow, a dot, play, pause, and close
* Use ease-in or bouncy springs anywhere
* Centre content in a max-width container; align left to the fluid gutter

## Technical Notes

* Stack: Craft CMS with SEOmatic, Tailwind v4, Vite, GSAP, Lottie, Splide, Plyr, lazysizes.
* JavaScript is organised as `data-module` attributes with lazily imported classes:
  `PrimaryNav`, `HeaderReveal`, `Cursor`, `Card`, `InView`, `AnimatedText`, `StickyMediaSection`, `BackgroundVideo`, `VideoModal`, `VideoPlayer`, `ImageSlideshow`, `HowItWorksSlideshow`, `HomepageHeroAnimation`.
* Images are served through an image CDN with `avif` and `webp`, focal-point cropping, and `lazyload` markup with a transparent SVG placeholder.
* View transitions are enabled with `@view-transition { navigation: auto }`.
* The favicon is the Eliza "S" in Dark Gray, switching to Light Gray `#e5e5e5` in dark mode; the site itself has no dark theme.
  The brand guide allows the logo only in Dark Gray or White, so new work uses White on dark grounds.

## Files

* [`tokens.css`](tokens.css): every custom property, type style, and component rule, ready to drop into a stylesheet.
* [`fonts-open/`](fonts-open/): open-licensed substitute fonts with `fonts.css` and OFL license texts.
* [`reference/`](reference/): screenshots of each site page and state, named by page, viewport, and state; the font comparison sheets; and the brand guide's sections as `brandpad-<topic>.png`.
