// Close the phone menu (<details id="app-menu">) after a link is followed or on
// a tap outside it. Page changes are client-side, so it would otherwise stay open
// over the new page. Dash can't close it: it never learns the menu was opened.
document.addEventListener("click", function (event) {
  var menu = document.getElementById("app-menu");
  if (!menu || !menu.open) return;
  if (event.target.closest(".app-menu-list a") || !menu.contains(event.target)) {
    menu.open = false;
  }
});
