# admin/theme.py
"""
The one shared design system for every admin/staff-facing page — the
onboarding wizard (admin/onboarding.py), the platform-admin tenant list/edit
pages (admin/onboarding.py, Section 12.1 follow-up), and the hospital-staff
bookings portal (portal.py, Section 12.7). Originally lived inline in
admin/onboarding.py as `_STYLE`; pulled out here once a second module
(portal.py) needed the exact same look rather than a re-implementation that
would inevitably drift from it.

Design reference (current, replacing the earlier sage/clay/Fraunces pass):
14 reference mockups (design-reference/ — "DAAP CareConnect") — deep forest
green + off-white/cream, clean single-family sans-serif (no serif anywhere),
rounded white cards on a warm off-white page background, green checklist
checkmarks, a numbered vertical step-rail, dark-green primary buttons,
soft-tan secondary accents. This pass is CSS-token-only: every existing
selector any page's <script> block queries (ids, or classes like
.rail-step/.dot/.step-panel/.tier-card/.dept-card/.doctor-card/.doctor-*/
.day-toggle/etc.) is unchanged — only the :root custom properties and a
handful of which-variable-a-rule-uses swaps (noted inline below) changed.

Font substitution note: the reference's headings use a clean geometric sans
that isn't precisely identifiable from static mockups alone; substituted
Inter (already loaded, already this file's body font) at heavier weights for
headings instead of guessing an unverified Google Fonts name — visually close
to the reference and zero extra risk. Revisit if the exact family matters.
"""

_FONT_LINKS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
"""

STYLE = _FONT_LINKS + """
<style>
  :root {
    --paper: #F7F7F5; --card: #FFFFFF; --ink: #182620; --ink-muted: #667066; --ink-faint: #97998F;
    --sage-deep: #1B4D3E; --sage-line: #E3E6DF; --clay: #9C7A3D; --clay-tint: #F1E9D4;
    --success: #1E9E5A; --success-tint: #E4F6EC; --error: #D14343; --error-tint: #FBEAEA;
    --radius: 12px;
    --font-display: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    --font-body: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--paper); color: var(--ink);
    font-family: var(--font-body); font-size: 15px; line-height: 1.6;
  }

  .shell { max-width: 980px; margin: 0 auto; padding: 48px 24px 80px; display: grid; grid-template-columns: 260px 1fr; gap: 40px; align-items: start; }
  .shell.no-rail { grid-template-columns: 1fr; max-width: 760px; }
  .brand { grid-column: 1 / -1; display: flex; align-items: baseline; gap: 10px; margin-bottom: 8px; }
  .brand-mark {
    width: 28px; height: 28px; border-radius: 8px; background: var(--sage-deep);
    display: flex; align-items: center; justify-content: center; color: #fff;
    font-family: var(--font-display); font-weight: 700; font-size: 15px; flex-shrink: 0;
  }
  .brand-name { font-family: var(--font-display); font-weight: 700; font-size: 17px; color: var(--sage-deep); }
  .brand-sub { color: var(--ink-faint); font-size: 13px; }
  .brand-row { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
  .brand-nav { display: flex; gap: 18px; font-size: 13px; }
  .brand-nav a { color: var(--ink-muted); font-weight: 500; text-decoration: none; border-bottom: 1px solid transparent; }
  .brand-nav a:hover { color: var(--sage-deep); border-bottom-color: var(--sage-deep); }

  /* Intake checklist rail -- mirrors the reference's numbered step-rail
     (active = solid dark green, done = solid mint/success green, upcoming =
     light gray outline), Reference: Step 1 mockup's right-hand rail. */
  .rail {
    background: var(--card); border: 1px solid var(--sage-line); border-radius: 14px;
    padding: 24px 20px; align-self: start; position: sticky; top: 40px;
  }
  .rail h1 {
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-faint);
    margin: 0 0 18px; font-weight: 600; font-family: var(--font-body);
  }
  .rail-step {
    display: flex; gap: 12px; padding-bottom: 22px; position: relative; align-items: flex-start; cursor: default;
  }
  .rail-step:last-child { padding-bottom: 0; }
  .rail-step::before {
    content: ''; position: absolute; left: 11px; top: 26px; bottom: 0; width: 1px; background: var(--sage-line);
  }
  .rail-step:last-child::before { display: none; }
  .rail-step .dot {
    width: 23px; height: 23px; border-radius: 50%; border: 1.5px solid var(--sage-line); background: var(--paper);
    flex-shrink: 0; display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700; color: var(--ink-faint); z-index: 1;
  }
  .rail-step span:last-child { font-size: 13.5px; color: var(--ink-faint); padding-top: 2px; }
  .rail-step.done .dot { background: var(--success); border-color: var(--success); color: #fff; }
  .rail-step.active .dot { background: var(--sage-deep); border-color: var(--sage-deep); color: #fff; }
  .rail-step.active span:last-child { color: var(--ink); font-weight: 600; }
  .rail-step.done span:last-child { color: var(--ink-muted); }
  .rail-step.clickable { cursor: pointer; }

  /* Main panel */
  .main {
    background: var(--card); border: 1px solid var(--sage-line); border-radius: 14px; padding: 40px 44px;
  }
  .step-panel { display: none; }
  .step-panel.active { display: block; }
  .eyebrow { font-size: 12px; color: var(--clay); font-weight: 700; letter-spacing: 0.03em; margin: 0 0 6px; }
  .step-panel h2, .main h2 {
    font-family: var(--font-display); font-weight: 700; font-size: 26px; margin: 0 0 10px; color: var(--ink);
  }
  .step-desc { color: var(--ink-muted); margin: 0 0 28px; max-width: 46ch; }

  .guide-box {
    background: var(--paper); border: 1px solid var(--sage-line); border-radius: var(--radius);
    padding: 18px 20px; margin-bottom: 18px; display: flex; gap: 14px; align-items: flex-start;
  }
  .guide-num { font-family: var(--font-display); color: var(--sage-deep); font-size: 20px; font-weight: 700; flex-shrink: 0; width: 24px; }
  .guide-text { flex: 1; }
  .guide-text p { margin: 0 0 8px; font-size: 14px; }
  .guide-text p:last-child { margin-bottom: 0; }
  .guide-text ol { margin: 0 0 10px; padding-left: 20px; font-size: 14px; }
  .guide-text ol li { margin-bottom: 6px; }
  .guide-text ol li:last-child { margin-bottom: 0; }
  .guide-text ol + .ext-link, .guide-text ol + p { margin-top: 4px; }
  .guide-box a, .ext-link {
    display: inline-flex; align-items: center; gap: 6px;
    color: var(--sage-deep); font-weight: 600; font-size: 13.5px; text-decoration: none;
    border-bottom: 1px solid var(--sage-deep); padding-bottom: 1px;
  }

  label {
    display: block; font-size: 13px; font-weight: 500; color: var(--ink); margin: 18px 0 6px;
  }
  /* Deliberately no label:first-of-type margin-collapse rule here (the design
     reference has one) -- with .field-row splitting fields into per-field
     wrapper divs, :first-of-type matches the first label in EVERY such div,
     not just the first label in a whole panel, which would zero out spacing
     on every second-column field. Uniform label spacing throughout instead. */
  input[type=text], input[type=password], input[type=number], input[type=time], textarea {
    width: 100%; font-family: var(--font-body); font-size: 14px; padding: 10px 12px;
    border: 1px solid var(--sage-line); border-radius: 8px; background: var(--paper); color: var(--ink);
  }
  input:focus, textarea:focus { outline: none; border-color: var(--sage-deep); box-shadow: 0 0 0 3px var(--success-tint); }
  .hint, .field-hint { font-size: 12.5px; color: var(--ink-faint); margin: 4px 0 0; }
  .checkbox-row { display: flex; align-items: center; gap: 8px; margin-top: 18px; font-weight: 500; font-size: 14px; color: var(--ink); }
  .checkbox-row input { width: auto; }

  .nav-buttons { display: flex; justify-content: space-between; margin-top: 32px; padding-top: 24px; border-top: 1px solid var(--sage-line); }
  button {
    font-family: var(--font-body); font-weight: 600; font-size: 14px; padding: 11px 22px;
    border-radius: 8px; cursor: pointer; border: none; background: var(--sage-deep); color: #fff;
  }
  button.secondary, button.back-btn, a.btn-secondary {
    background: transparent; color: var(--ink-muted); border: 1px solid var(--sage-line);
  }
  a.btn-secondary { display: inline-block; text-decoration: none; font-weight: 600; font-size: 14px; padding: 11px 22px; border-radius: 8px; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  button.small { padding: 8px 14px; font-size: 13px; }
  .add-doctor {
    background: none; border: 1.5px dashed var(--sage-line); color: var(--sage-deep);
    font-weight: 600; font-size: 13.5px; padding: 10px; width: 100%; border-radius: var(--radius); cursor: pointer;
  }

  .error-banner {
    background: var(--error-tint); border: 1px solid #F0B8B8; color: var(--error);
    border-radius: var(--radius); padding: 16px 20px; margin-bottom: 24px;
  }
  .error-banner ul { margin: 8px 0 0; padding-left: 20px; }
  .warning-banner {
    background: var(--clay-tint); border: 1px solid #DFC792; color: #6B4F17;
    border-radius: var(--radius); padding: 16px 20px; margin-top: 16px; font-size: 14px;
  }

  /* Reference: Step 0 (setup-tier cards) / Step 4 (feature-toggle cards) */
  .tier-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 8px; }
  .tier-card { border: 1.5px solid var(--sage-line); border-radius: var(--radius); padding: 16px; cursor: pointer; background: var(--card); }
  .tier-card.selected { border-color: var(--sage-deep); background: var(--success-tint); }
  .tier-card h3 { font-family: var(--font-body); font-weight: 700; font-size: 13.5px; margin: 0 0 4px; color: var(--ink); }
  .tier-card p { font-size: 12.5px; color: var(--ink-muted); margin: 0; }
  .tier-card .tier-consequence { margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--sage-line); font-style: italic; color: var(--ink-faint); }
  .tier-badge {
    display: inline-block; font-size: 10.5px; font-weight: 700; color: var(--clay); background: var(--clay-tint);
    padding: 2px 8px; border-radius: 100px; margin-bottom: 6px;
  }
  .tier2-fields, .tier3-note { display: none; margin-top: 20px; }
  .tier3-note {
    background: var(--clay-tint); border: 1px solid var(--sage-line); border-radius: var(--radius);
    padding: 14px 18px; font-size: 13px; color: var(--ink-muted);
  }

  .dept-card { border: 1px solid var(--sage-line); border-radius: var(--radius); padding: 18px 20px; margin-top: 18px; background: var(--card); }
  .dept-card-header { display: flex; align-items: center; gap: 12px; }
  .dept-card-header input { flex: 1; margin-top: 0; font-weight: 600; }
  .doctor-card { border: 1px solid var(--sage-line); border-radius: var(--radius); padding: 16px 18px; margin-top: 14px; background: var(--paper); }
  .doctor-card-header { display: flex; justify-content: space-between; align-items: center; }
  .doctor-card-header strong {
    font-size: 12.5px; color: var(--ink-muted); font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
  }
  .field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; }
  .days-row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 6px; }
  /* Reference: Doctor Schedule mockup's "Working days" pill row -- selected
     day = solid dark green pill, unselected = white/outline pill. */
  .day-toggle {
    border: 1px solid var(--sage-line); border-radius: 100px; padding: 6px 14px; font-size: 12.5px;
    cursor: pointer; background: var(--card); user-select: none; color: var(--ink-muted); font-weight: 600;
  }
  .day-toggle.on { background: var(--sage-deep); border-color: var(--sage-deep); color: #fff; }
  .remove-link { background: none; border: none; color: var(--clay); font-size: 12.5px; font-weight: 700; padding: 2px 4px; cursor: pointer; }

  .shift-row { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
  .shift-row:first-child { margin-top: 6px; }
  .shift-row input[type=time] { width: auto; flex: 1; }
  .shift-sep { font-size: 13px; color: var(--ink-faint); flex-shrink: 0; }
  .add-shift-btn { margin-top: 10px; width: auto; padding: 8px 14px; }

  .review-block { margin-top: 16px; }
  .review-section {
    background: var(--paper); border: 1px solid var(--sage-line); border-radius: var(--radius);
    padding: 16px 20px; margin-top: 12px;
  }
  .review-section:first-child { margin-top: 0; }
  .review-section-header { display: flex; justify-content: space-between; align-items: center; }
  .review-section-header h4 {
    margin: 0; font-family: var(--font-body); font-size: 12px; font-weight: 700; color: var(--ink-muted);
    text-transform: uppercase; letter-spacing: 0.04em;
  }
  .edit-link { color: var(--clay); font-size: 12.5px; font-weight: 700; text-decoration: none; cursor: pointer; }
  .review-section dl { margin: 10px 0 0; }
  .review-section dt {
    font-weight: 700; font-size: 12px; color: var(--ink-faint); text-transform: uppercase;
    letter-spacing: 0.04em; margin-top: 10px;
  }
  .review-section dt:first-child { margin-top: 0; }
  .review-section dd { margin: 3px 0 0; font-size: 14px; }
  .go-live-note { font-size: 13.5px; color: var(--ink-muted); margin-top: 16px; }

  .ok-page { max-width: 640px; margin: 0 auto; padding: 48px 24px 80px; }
  .ok-page .brand { margin-bottom: 32px; }
  .ok-page h1 { font-family: var(--font-display); font-weight: 700; color: var(--ink); }
  .ok-page h3 {
    font-family: var(--font-body); font-size: 12px; font-weight: 700; color: var(--ink-faint);
    text-transform: uppercase; letter-spacing: 0.04em; margin-top: 28px;
  }
  .ok-page ul { padding-left: 20px; }
  .ok-page a { color: var(--sage-deep); font-weight: 600; }
  /* Reference: Step 3 (Verify business & billing) checklist rows -- light
     off-white row, bold label + muted subtext, green circular checkmark. */
  .ok-box { background: var(--success-tint); border: 1px solid var(--success); border-radius: var(--radius); padding: 20px; }

  /* --- Added for /admin/tenants, /admin/edit-tenant, and portal.py (Section
     12.1 follow-up / Section 12.7) -- card-based list rows, status pills,
     stat tiles, and a login card, all built on the same tokens above rather
     than one-off colors, so a new page never looks bolted-on. */
  .page-header { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }
  .page-header h2 { margin: 0; }
  .card-list { display: flex; flex-direction: column; gap: 10px; }
  .list-row {
    display: flex; align-items: center; justify-content: space-between; gap: 16px;
    background: var(--paper); border: 1px solid var(--sage-line); border-radius: var(--radius); padding: 14px 18px;
  }
  .list-row-main { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
  .list-row-title { font-weight: 700; font-size: 14.5px; color: var(--ink); }
  .list-row-sub { font-size: 12.5px; color: var(--ink-faint); font-family: 'SF Mono', Consolas, monospace; }
  .list-row-meta { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
  .empty-note { color: var(--ink-faint); font-size: 14px; padding: 24px 0; text-align: center; }

  /* Reference: dashboard's "Confirmed" pill / stat-delta badges. */
  .pill {
    display: inline-block; font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 100px;
    text-transform: uppercase; letter-spacing: 0.03em;
  }
  .pill-active, .pill-booked { background: var(--success-tint); color: var(--success); }
  .pill-inactive, .pill-cancelled { background: var(--error-tint); color: var(--error); }
  .pill-rescheduled { background: var(--clay-tint); color: var(--clay); }

  /* Reference: Hospital Admin Dashboard's stat-card row (Today's
     Appointments / Confirmed / New Patients / No Shows). */
  .stat-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 28px; }
  .stat-tile {
    background: var(--paper); border: 1px solid var(--sage-line); border-radius: var(--radius); padding: 16px 18px;
  }
  .stat-tile .stat-value { font-family: var(--font-display); font-weight: 700; font-size: 26px; color: var(--ink); }
  .stat-tile .stat-label { font-size: 12px; color: var(--ink-faint); text-transform: uppercase; letter-spacing: 0.03em; margin-top: 2px; }

  /* Section 12.8: the staff dashboard's own sidebar layout -- scoped to
     /portal/dashboard only (every other portal.py page keeps .shell.no-rail's
     single-column layout with the horizontal .brand-nav strip; rebuilding
     every existing page around a permanent sidebar was out of scope here).
     Reference: Hospital Admin Dashboard mockup's left rail + stat-card grid
     + two-chart row + tables layout. */
  .dashboard-shell { max-width: 1180px; margin: 0 auto; padding: 32px 24px 80px; display: grid; grid-template-columns: 230px 1fr; gap: 28px; align-items: start; }
  .dashboard-sidebar {
    background: var(--card); border: 1px solid var(--sage-line); border-radius: 14px;
    padding: 22px 16px; align-self: start; position: sticky; top: 32px; display: flex; flex-direction: column; gap: 4px;
  }
  .dashboard-sidebar .brand { padding: 0 8px 18px; margin-bottom: 4px; border-bottom: 1px solid var(--sage-line); }
  .dashboard-sidebar a {
    display: block; padding: 10px 12px; border-radius: 8px; font-size: 14px; font-weight: 500;
    color: var(--ink-muted); text-decoration: none;
  }
  .dashboard-sidebar a:hover { background: var(--paper); color: var(--ink); }
  .dashboard-sidebar a.active { background: var(--success-tint); color: var(--sage-deep); font-weight: 700; }
  .dashboard-sidebar a.logout { margin-top: 12px; padding-top: 16px; border-top: 1px solid var(--sage-line); color: var(--clay); }
  .dashboard-main { min-width: 0; }

  .stat-tile { position: relative; }
  .stat-delta { display: inline-block; font-size: 11.5px; font-weight: 700; margin-top: 6px; }
  .stat-delta.up { color: var(--success); }
  .stat-delta.down { color: var(--error); }
  .stat-delta.flat { color: var(--ink-faint); }

  .chart-row { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; margin-bottom: 28px; }
  .chart-card {
    background: var(--card); border: 1px solid var(--sage-line); border-radius: var(--radius); padding: 20px 22px;
  }
  .chart-card h3 {
    margin: 0 0 16px; font-family: var(--font-body); font-size: 13px; font-weight: 700; color: var(--ink-muted);
    text-transform: uppercase; letter-spacing: 0.04em;
  }
  .chart-legend { display: flex; flex-direction: column; gap: 8px; margin-top: 14px; }
  .chart-legend-row { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--ink-muted); }
  .chart-legend-swatch { width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }
  .dashboard-section-title { font-family: var(--font-display); font-weight: 700; font-size: 16px; margin: 0 0 14px; color: var(--ink); }
  .activity-row { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--sage-line); font-size: 13.5px; }
  .activity-row:last-child { border-bottom: none; }
  .activity-row-main { color: var(--ink); }
  .activity-row-time { color: var(--ink-faint); font-size: 12px; white-space: nowrap; }

  .login-shell { max-width: 420px; margin: 80px auto; padding: 0 24px; }
  .login-card {
    background: var(--card); border: 1px solid var(--sage-line); border-radius: 14px; padding: 40px 36px;
  }
  .login-card .brand { margin-bottom: 22px; }
</style>
"""
