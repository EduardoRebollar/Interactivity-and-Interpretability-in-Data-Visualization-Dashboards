/* Sideways scrolling on a zoomed line chart: a touchpad's two-finger swipe (or a mouse's tilt
   wheel, or Shift with the wheel) moves the zoomed x axis left and right (docs/visual-spec.md
   section 7.5, 2026-09-27).

   Plotly zooms on the wheel's vertical motion and ignores its sideways motion, so a sideways swipe
   would only have zoomed by its small vertical wobble. This listener takes a gesture that is
   mostly sideways before Plotly sees it. Only where scroll zoom is on (the line chart, in the
   interactive condition: figures.graph_config) and only over the plotting area.

   - Only when zoomed in: the axis moves within the chart's own view (1999.5-2024.5, Plotly's
     initial range, which Reset axis also returns to), never past it. Not zoomed, a sideways
     swipe does nothing, rather than the browser's swipe-to-go-back leaving the study.
   - Logged as one view_change per swipe, like a wheel zoom. During the swipe the axis moves by
     Plotly.update, which dcc.Graph does not report; once the swipe has paused for REDRAW_DELAY,
     one Plotly.relayout reports where it stopped, which the app logs and keeps (app.control_step).
   - The direction is the one the participant's system scrolls: the browser's deltaX already
     carries their touchpad setting. */
(function () {
  "use strict";

  // Plotly waits as long after a wheel zoom before reporting it (constants REDRAWDELAY).
  var REDRAW_DELAY = 300;
  // A wheel event in lines (deltaMode 1), not pixels: roughly a line's height.
  var LINE = 16;

  var pending = new WeakMap();

  // The gesture's sideways motion in pixels, or 0 when it is mostly vertical (a zoom, Plotly's) or
  // a pinch (Ctrl with the wheel, also Plotly's). Shift with a plain wheel counts as sideways where
  // the browser has not already turned it into deltaX.
  function sideways(event) {
    var dx = event.deltaX;
    var dy = event.deltaY;
    if (event.shiftKey && !dx) {
      dx = dy;
      dy = 0;
    }
    if (event.ctrlKey || !dx || Math.abs(dx) <= Math.abs(dy)) {
      return 0;
    }
    return event.deltaMode === 1 ? dx * LINE : dx;
  }

  function report(plot) {
    var range = plot._fullLayout.xaxis.range.slice();
    window.Plotly.relayout(plot, { "xaxis.range": range });
  }

  document.addEventListener(
    "wheel",
    function (event) {
      var target = event.target;
      if (!(target instanceof Element) || !target.closest(".draglayer")) {
        return;
      }
      var plot = target.closest(".js-plotly-plot");
      if (!plot || !plot._context || !(plot._context._scrollZoom || {}).cartesian) {
        return;
      }
      var dx = sideways(event);
      if (!dx) {
        return;
      }
      // Ours from here: not Plotly's zoom, not the page's scroll, not the browser's back-swipe.
      event.preventDefault();
      event.stopPropagation();
      var axis = plot._fullLayout.xaxis;
      if (!axis || axis.fixedrange || !window.Plotly) {
        return;
      }
      var low = Number(axis.range[0]);
      var high = Number(axis.range[1]);
      var first = Number(axis._rangeInitial0);
      var last = Number(axis._rangeInitial1);
      if (!isFinite(first) || !isFinite(last) || high - low >= last - first - 1e-9) {
        return;
      }
      var shift = (dx * (high - low)) / axis._length;
      shift = Math.min(Math.max(shift, first - low), last - high);
      if (!shift) {
        return;
      }
      window.Plotly.update(plot, {}, { "xaxis.range": [low + shift, high + shift] });
      clearTimeout(pending.get(plot));
      pending.set(
        plot,
        setTimeout(function () {
          pending.delete(plot);
          report(plot);
        }, REDRAW_DELAY)
      );
    },
    { capture: true, passive: false }
  );
})();
