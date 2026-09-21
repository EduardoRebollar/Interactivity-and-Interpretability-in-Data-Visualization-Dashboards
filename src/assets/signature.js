// Signature pad for the consent screen (src/layout.py consent_screen, src/consent.py).
//
// Dash serves every file in src/assets/ on every page, so this attaches itself to #signature-pad
// whenever the consent screen is rendered, and does nothing on any other screen.
//
// A signature is kept as strokes -- lists of [x, y] points in the canvas's own coordinate space --
// and pushed into the `signature-strokes` store after every stroke, where the consent callback reads
// it. Pointer events cover mouse, pen and touch alike; the canvas has `touch-action: none` so a
// finger signs instead of scrolling. Points are mapped from screen pixels back into the canvas's
// fixed size, so a signature means the same thing however wide the page is.
(function () {
  "use strict";

  var MAX_POINTS = 5000; // src/consent.py MAX_POINTS; the server refuses anything larger.

  function publish(strokes) {
    if (!window.dash_clientside || !window.dash_clientside.set_props) {
      return;
    }
    window.dash_clientside.set_props("signature-strokes", {
      data: strokes.length ? strokes.map(function (s) { return s.slice(); }) : null,
    });
  }

  function attach(canvas) {
    if (canvas.dataset.signatureReady) {
      return;
    }
    canvas.dataset.signatureReady = "1";

    var ctx = canvas.getContext("2d");
    var strokes = [];
    var current = null;
    var total = 0;

    function pen() {
      ctx.lineWidth = 2.5;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.strokeStyle = window.getComputedStyle(canvas).color || "#1A1A1A";
      ctx.fillStyle = ctx.strokeStyle;
    }

    function at(event) {
      var box = canvas.getBoundingClientRect();
      return [
        Math.round(((event.clientX - box.left) * canvas.width) / box.width),
        Math.round(((event.clientY - box.top) * canvas.height) / box.height),
      ];
    }

    canvas.addEventListener("pointerdown", function (event) {
      if (total >= MAX_POINTS) {
        return;
      }
      event.preventDefault();
      canvas.setPointerCapture(event.pointerId);
      pen();
      var p = at(event);
      current = [p];
      strokes.push(current);
      total += 1;
      ctx.beginPath();
      ctx.arc(p[0], p[1], 1.25, 0, 2 * Math.PI);
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(p[0], p[1]);
    });

    canvas.addEventListener("pointermove", function (event) {
      if (!current || total >= MAX_POINTS) {
        return;
      }
      var p = at(event);
      var last = current[current.length - 1];
      if (p[0] === last[0] && p[1] === last[1]) {
        return;
      }
      current.push(p);
      total += 1;
      ctx.lineTo(p[0], p[1]);
      ctx.stroke();
    });

    function finish() {
      if (current) {
        current = null;
        publish(strokes);
      }
    }
    canvas.addEventListener("pointerup", finish);
    canvas.addEventListener("pointercancel", finish);

    canvas._clearSignature = function () {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      strokes = [];
      current = null;
      total = 0;
      publish(strokes);
    };

    // A new pad is a blank pad. The store outlives the screen (declining and coming back renders a
    // fresh canvas), and must never hold a signature the participant can no longer see.
    publish(strokes);
  }

  // The clear button is a native <button>, so Enter and Space reach this as a click too.
  document.addEventListener("click", function (event) {
    if (!event.target || event.target.id !== "signature-clear") {
      return;
    }
    var canvas = document.getElementById("signature-pad");
    if (canvas && canvas._clearSignature) {
      canvas._clearSignature();
    }
  });

  function scan() {
    var canvas = document.getElementById("signature-pad");
    if (canvas) {
      attach(canvas);
    }
  }

  // Screens are swapped in by Dash long after load, so watch for the pad to appear.
  new MutationObserver(scan).observe(document.documentElement, { childList: true, subtree: true });
  scan();
})();
