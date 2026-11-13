---
name: HP 437B Automation — local operator
description: The implemented local operator interface in the existing report style.
colors:
  paper: "#fff"
  ink: "#18242b"
  muted: "#4c6270"
  rule: "#cbd6dc"
  soft: "#f2f6f8"
  blue: "#135c91"
  blue-hover: "#0c426a"
  blue-soft: "#e9f2fa"
  green: "#246244"
  red: "#9d3030"
  red-soft: "#fff0ee"
  amber: "#76530b"
  amber-soft: "#fff5db"
  field-border: "#8d9fa9"
  selection: "#cce3f5"
typography:
  headline:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "32px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.025em"
  title:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "21px"
    fontWeight: 650
    lineHeight: 1.25
  body:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.5
  action:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.5
  supporting:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
  metadata:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  control: "8px"
  notice: "12px"
  progress: "3px"
spacing:
  space-4: "4px"
  space-8: "8px"
  space-10: "10px"
  space-12: "12px"
  space-14: "14px"
  space-16: "16px"
  space-18: "18px"
  space-20: "20px"
  space-24: "24px"
  space-26: "26px"
  space-28: "28px"
  space-32: "32px"
  space-40: "40px"
  space-48: "48px"
components:
  button-primary:
    backgroundColor: "{colors.blue}"
    textColor: "{colors.paper}"
    typography: "{typography.action}"
    rounded: "{rounded.control}"
    padding: "10px 16px"
  button-primary-hover:
    backgroundColor: "{colors.blue-hover}"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.blue}"
    typography: "{typography.action}"
    rounded: "{rounded.control}"
    padding: "10px 16px"
  button-secondary-hover:
    backgroundColor: "{colors.blue-soft}"
  button-danger:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.red}"
    rounded: "{rounded.control}"
    padding: "10px 16px"
  button-disabled:
    backgroundColor: "{colors.soft}"
    textColor: "{colors.muted}"
  button-text:
    textColor: "{colors.blue}"
    padding: "2px 0"
  field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "10px 12px"
  workflow-current:
    backgroundColor: "{colors.blue-soft}"
    padding: "15px 10px"
  boundary:
    backgroundColor: "{colors.soft}"
    rounded: "{rounded.notice}"
    padding: "16px 18px"
  notice-error:
    backgroundColor: "{colors.red-soft}"
    textColor: "{colors.red}"
    rounded: "{rounded.notice}"
    padding: "14px 18px"
---
# Design System: HP 437B Automation — local operator

## Overview

**Creative North Star: "The existing report style"**

The local operator surface inherits the owner-confirmed report style: white surfaces, dark ink, restrained blue actions, system typography, and clear rules. This document records the implemented browser surface; the report templates retain their own styles.

The interface uses spacing and dividers to separate setup, workflow progress, cancellation, and reports. Text labels accompany state colors, and operational status remains distinct from acceptance results.

**Key Characteristics:**
- White surfaces and ruled sections.
- Blue actions with explicit labels.
- Visible workflow states and cancellation boundaries.
- A stacked workspace on small screens.

## Colors

### Primary

Blue identifies actions, links, the active workflow, progress, focus, and the simulation label. Its darker hover and pale active-row companions support those states.

### Neutral

Paper, ink, muted text, soft backgrounds, and rules form the interface's base. Fields use the stronger field-border stroke. Selection uses a pale blue highlight.

### State colors

Green marks the finished phase. Red marks errors, failed workflow rows, and cancellation actions. Amber marks connection notices and pending cancellation.

**The State Text Rule.** Preserve the text labels accompanying state colors; phase completion is separate from an acceptance decision.

## Typography

All text uses the system font stack recorded above. The headline is the page title; title is the section heading; body and label support setup fields. Action, supporting, and metadata roles serve buttons, descriptions, status, workflow IDs, and the footer. Headings use a compact hierarchy rather than a separate display face.

The masthead project name uses a slightly larger body size (17px, weight 650). Run headlines use an intermediate title (20px, weight 600), and recent-run headings use 18px. Progress, workflow IDs, and table values use tabular numerals. Introductory copy is limited to 70ch; run and boundary descriptions use 65ch.

## Layout

Header and main content share a centered maximum width (1264px), with desktop horizontal gutters (40px). The workspace pairs a constrained setup column (280–380px) with a flexible progress column, separated by a gap (48px) and a ruled setup edge. Main top padding is 28px. The spacing tokens capture the recurring component and section rhythm.

At 820px and below, the workspace stacks with a 32px gap, 24px side gutters, and a horizontal setup divider. The page headline reduces to 28px. At 430px and below, masthead labels stack, workflow status moves below the workflow name, and report actions become full-width stacked links. Recent runs retain a horizontally scrollable table. Long descriptions and profile issues wrap within their containers.

## Elevation & Depth

There are no box shadows, gradients, overlays, or animated transitions in this surface. White and soft backgrounds, thin rules, and tinted state regions provide separation. Keyboard focus is a solid blue outline (3px) with a 4px offset, not a depth effect.

## Shapes

Controls have gently rounded corners using the control radius. Cancellation and notice regions use the larger notice radius. The thin progress track uses the progress radius. One-pixel strokes distinguish fields, buttons, workflow rows, and table rows; the workflow rail itself is flat and ruled.

## Components

### Buttons

Primary actions use filled blue; secondary actions use white with a blue outline; cancellation uses the secondary shape with a red label and border. All have a minimum height (44px), action typography, and the padding recorded in the frontmatter. Hover darkens the primary fill, tints secondary fill blue, and tints cancellation fill red. Disabled buttons use muted text, soft fill, a rule-colored border, and a not-allowed cursor. The underlined text button imports profiles; it has no filled container.

### Inputs / Fields

Text fields and selects share the field token, a stronger one-pixel border, and a minimum height (46px). Labels remain visible above them; supporting hints sit below. Placeholders use muted text at full opacity. Text carets and checkbox accents use blue. Disabled fields use soft fill and muted text. The global visible-focus outline applies to interactive elements. Errors appear in a separate focused alert; the build does not add a per-field error border.

### Workflow progress

A thin native progress element, numeric completion count, and ruled workflow rows convey progress. Rows pair workflow IDs with names, optional native result summaries, and explicit status text. The active row is pale blue; failed execution rows are pale red. Finished phase text is green, while acceptance remains in the run description and reports.

### Cancellation boundary

A soft inset region explains the cleanup boundary and contains the cancellation button. Pending cancellation changes the region to amber, names the active test and following boundary when available, changes the button label to Cancellation requested, and disables repeat requests. Reporting disables cancellation. The request does not immediately claim the suite has stopped.

### Notices and reports

Connection notices use amber; request errors use a red alert that receives focus. Dynamic run summaries use polite atomic announcements. Report actions are hidden until their respective artifacts are ready. The PDF link uses primary styling and opens a new tab; the package link uses secondary styling. Recent-run rows distinguish report errors, run errors, cancellation, stopped runs, and completion. Profile-loading issues use native disclosure behavior.

**The Available Action Rule.** Keep controls disabled or hidden according to their actual availability: setup is locked during an active suite, Start requires a selection, and reports appear only when ready.

## Do's and Don'ts

### Do:

- **Do** retain visible labels, state text, and completion counts alongside color.
- **Do** preserve visible keyboard focus and readable disabled states.
- **Do** wrap long descriptive text and allow the recent-runs table to scroll horizontally.
- **Do** distinguish a cancellation request from completed cancellation, and report errors from run outcomes.

### Don't:

- **Don't** infer an acceptance decision from the green Finished state.
- **Don't** hide the current workflow cleanup boundary when cancellation is requested.
- **Don't** apply this browser token sheet to report templates without checking their existing styles.
