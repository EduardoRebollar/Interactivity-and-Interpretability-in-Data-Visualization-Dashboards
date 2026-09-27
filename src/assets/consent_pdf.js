/* The participant's signed consent form as a PDF, laid out exactly as the consent sheet is on the
   page.

   The markup is `layout.signed_sheet_html`: the sheet's own components, with the participant's
   fields filled from the stored record. It is laid out here, off screen, by the page's own
   stylesheets at the width the sheet has on a wide screen; html2canvas draws it, and jsPDF puts
   the drawing on Letter pages. A page breaks only between the sheet's paragraphs, never through a
   line. The countersignature's date is today's, in this browser, as the screen shows it.

   The two libraries are vendored (scripts/vendor_pdf_libs.py) and not loaded with the page
   (app.create_app, assets_path_ignore); they are loaded here the first time a PDF is made.

   `app.COPY_DOWNLOAD_JS` calls window.studyConsentPdf(markup), which resolves once the PDF is
   saved. */
(function () {
  "use strict";

  // The sheet's width on the page (.sheet--form's max-width) and a Letter page at that width, in
  // CSS pixels; the sheet's own top and bottom padding is each page's margin.
  var WIDTH = 1240;
  var HEIGHT = Math.round((WIDTH * 11) / 8.5);
  var MARGIN = 80;
  // Pixels drawn per CSS pixel, so text stays sharp when printed.
  var SCALE = 2;
  var FILENAME = "signed-consent-form.pdf";

  // Beside this file, wherever Dash serves the assets from.
  var script = document.currentScript;
  var base = script ? script.src.replace(/[^/]*$/, "") : "/assets/";
  var loading = {};

  function load(name, ready) {
    if (ready()) {
      return Promise.resolve();
    }
    if (!loading[name]) {
      loading[name] = new Promise(function (resolve, reject) {
        var tag = document.createElement("script");
        tag.src = base + "vendor/" + name;
        tag.onload = resolve;
        tag.onerror = function () {
          delete loading[name];
          tag.remove();
          reject(new Error("Could not load " + name));
        };
        document.head.appendChild(tag);
      });
    }
    return loading[name];
  }

  function today() {
    return new Date().toLocaleDateString("en-US", {
      month: "2-digit",
      day: "2-digit",
      year: "numeric",
    });
  }

  // [top, bottom] of each page's slice of the sheet, in CSS pixels from its top edge. A block that
  // would run past the page's bottom margin starts the next page.
  function slices(sheet) {
    var origin = sheet.getBoundingClientRect().top;
    var room = HEIGHT - 2 * MARGIN;
    var pages = [];
    var start = MARGIN;
    var end = MARGIN;
    Array.prototype.forEach.call(sheet.children, function (block) {
      var box = block.getBoundingClientRect();
      var top = Math.floor(box.top - origin);
      var bottom = Math.ceil(box.bottom - origin);
      if (bottom - start > room && end > start) {
        pages.push([start, end]);
        start = top;
      }
      end = Math.max(end, bottom);
    });
    pages.push([start, end]);
    return pages;
  }

  function render(markup) {
    var holder = document.createElement("div");
    holder.setAttribute("aria-hidden", "true");
    holder.style.cssText =
      "position: absolute; left: -100000px; top: 0; width: " + WIDTH + "px; pointer-events: none;";
    holder.innerHTML = markup;
    var sheet = holder.querySelector(".sheet");
    sheet.style.width = WIDTH + "px";
    sheet.style.maxWidth = WIDTH + "px";
    sheet.style.boxShadow = "none";
    var date = holder.querySelector("#countersign-date");
    if (date) {
      date.removeAttribute("id");
      date.textContent = today();
    }
    document.body.appendChild(holder);
    var images = Array.prototype.map.call(holder.querySelectorAll("img"), function (image) {
      return image.decode ? image.decode().catch(function () {}) : null;
    });
    return Promise.all(images.concat([document.fonts ? document.fonts.ready : null]))
      .then(function () {
        return window.html2canvas(sheet, {
          scale: SCALE,
          backgroundColor: "#FFFFFF",
          logging: false,
        });
      })
      .then(function (drawn) {
        var pdf = new window.jspdf.jsPDF({ unit: "pt", format: "letter", orientation: "portrait" });
        pdf.setProperties({ title: "Signed consent form" });
        var width = pdf.internal.pageSize.getWidth();
        var height = pdf.internal.pageSize.getHeight();
        slices(sheet).forEach(function (slice, index) {
          var page = document.createElement("canvas");
          page.width = WIDTH * SCALE;
          page.height = HEIGHT * SCALE;
          var context = page.getContext("2d");
          context.fillStyle = "#FFFFFF";
          context.fillRect(0, 0, page.width, page.height);
          var tall = (slice[1] - slice[0]) * SCALE;
          context.drawImage(
            drawn, 0, slice[0] * SCALE, drawn.width, tall, 0, MARGIN * SCALE, drawn.width, tall
          );
          if (index) {
            pdf.addPage("letter", "portrait");
          }
          pdf.addImage(page.toDataURL("image/jpeg", 0.92), "JPEG", 0, 0, width, height);
        });
        pdf.save(FILENAME);
      })
      .finally(function () {
        holder.remove();
      });
  }

  window.studyConsentPdf = function (markup) {
    return load("html2canvas.min.js", function () {
      return !!window.html2canvas;
    })
      .then(function () {
        return load("jspdf.umd.min.js", function () {
          return !!(window.jspdf && window.jspdf.jsPDF);
        });
      })
      .then(function () {
        return render(markup);
      });
  };
})();
