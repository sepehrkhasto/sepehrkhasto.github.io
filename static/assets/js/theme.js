/* Night is the default. Sets a saved day choice before the page paints, so there is no flash.
   Also marks the page as "js", so controls that need scripting stay hidden without it. */
(function () {
  document.documentElement.classList.add("js");
  try {
    var t = localStorage.getItem("theme");
    if (t === "day" || t === "night") document.documentElement.setAttribute("data-theme", t);
  } catch (e) { /* storage blocked: stay in night */ }
  var day = document.documentElement.getAttribute("data-theme") === "day";
  var m = document.querySelector('meta[name="theme-color"]');
  if (m) m.setAttribute("content", day ? "#F6F0E3" : "#070B1F");
})();
