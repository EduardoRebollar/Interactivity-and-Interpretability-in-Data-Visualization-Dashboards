/* Enter commits a value typed into the map's coverage-range boxes.
 *
 * Dash 4's RangeSlider sends a typed value to the app only when its box loses focus. Enter moved
 * the handle but left the map unchanged, so a participant who typed 49 and pressed Enter saw the
 * slider agree with them and the chart ignore them. Blurring on Enter commits it the way they
 * expect. The boxes exist only in the interactive condition, above the map (src/layout.py).
 */
document.addEventListener("keydown", function (event) {
  var target = event.target;
  if (
    event.key === "Enter" &&
    target &&
    target.classList &&
    target.classList.contains("dash-range-slider-input")
  ) {
    target.blur();
  }
});
