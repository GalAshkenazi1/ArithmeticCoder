// Simple / detailed view of the coding animation, shared by every page and remembered.
// Simple hides the decimal bounds and the binary-fraction labels; detailed shows everything.
// The choice lives on <html data-view="simple|detailed"> so CSS does the hiding.

const KEY = "arith.view";

export const currentView = () => (localStorage.getItem(KEY) === "detailed" ? "detailed" : "simple");

function apply(view) {
  document.documentElement.dataset.view = view;
  document.querySelectorAll(".view-toggle button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
}

/** Render the Simple | Detailed switch into container and keep every switch on the page in step. */
export function initViewToggle(container) {
  container.classList.add("view-toggle");
  container.setAttribute("role", "group");
  container.setAttribute("aria-label", "how much detail");
  container.innerHTML = `<button type="button" data-view="simple" title="letters, boxes and bits only">Simple</button>` +
    `<button type="button" data-view="detailed" title="also the decimal bounds and the binary fraction">Detailed</button>`;
  container.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    localStorage.setItem(KEY, b.dataset.view);
    apply(b.dataset.view);
  }));
  apply(currentView());
}

apply(currentView());
