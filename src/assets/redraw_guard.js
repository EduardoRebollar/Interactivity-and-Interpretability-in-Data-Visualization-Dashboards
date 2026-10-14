/* The keyboard held while the chart is redrawn (docs/visual-spec.md section 7, 2026-10-13).

   Every control goes through one callback, which works each change out from the view the browser
   last had, and Dash draws its replies as they arrive, an older one after a newer one. So two
   changes made faster than the chart redraws could leave the chart at one and the control at the
   other, and log a `previous` the participant never saw. The pointer is already held then
   (zz-overrides.css); this holds the keyboard over the same elements.

   - While Dash marks the chart loading, a key on a control, a key's button or Reset view does
     nothing: no slider step, no radio move, no checkbox or button press.
   - Tab and the modifier keys still work, so focus can move on.
   - Everything else on the page (the answer, the justification, Submit) is untouched.
   - Held, an arrow key moves a slider one step per redraw, since its repeats are dropped until the
     chart is drawn. */
(function () {
  "use strict";

  // The elements zz-overrides.css takes the pointer from while the chart redraws.
  var HELD = ".ui-controls, .ui-key, .ui-hint-row button, #chart";

  // Keys that only move focus, or do nothing by themselves.
  var FREE = { Tab: true, Shift: true, Control: true, Alt: true, Meta: true, CapsLock: true };

  function redrawing() {
    var chart = document.getElementById("chart");
    return !!chart && chart.getAttribute("data-dash-is-loading") === "true";
  }

  // keyup too: a checkbox or button takes Space as it is let go.
  function hold(event) {
    var target = event.target;
    if (FREE[event.key] || !(target instanceof Element) || !target.closest(HELD)) {
      return;
    }
    if (!redrawing()) {
      return;
    }
    event.preventDefault();
    event.stopImmediatePropagation();
  }

  document.addEventListener("keydown", hold, true);
  document.addEventListener("keyup", hold, true);
})();
