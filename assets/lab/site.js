/* Small enhancements for static lab pages. The personal homepage uses its own script. */
"use strict";

const toggle = document.querySelector("[data-nav-toggle]");
const navigation = document.getElementById("lab-navigation");

if (toggle && navigation) {
  const setNavigation = (open) => {
    toggle.setAttribute("aria-expanded", String(open));
    toggle.classList.toggle("collapsed", !open);
    navigation.classList.toggle("in", open);
  };
  toggle.addEventListener("click", () => {
    setNavigation(toggle.getAttribute("aria-expanded") !== "true");
  });
  navigation.addEventListener("click", (event) => {
    if (event.target.closest("a")) setNavigation(false);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
      setNavigation(false);
      toggle.focus();
    }
  });
}

const filters = document.querySelector("[data-publication-filters]");
if (filters) {
  const search = document.getElementById("publication-search");
  const year = document.getElementById("publication-year");
  const types = Array.from(filters.querySelectorAll("[data-publication-type]"));
  const sections = Array.from(document.querySelectorAll(".publication-year"));
  const status = document.querySelector("[data-publication-count]");
  const empty = document.querySelector("[data-empty-results]");
  const normalize = (value) => value.toLocaleLowerCase().normalize("NFKC").trim();

  const filter = () => {
    const terms = normalize(search.value).split(/\s+/).filter(Boolean);
    const selectedTypes = new Set(types.filter((input) => input.checked).map((input) => input.value));
    let count = 0;
    for (const section of sections) {
      const matchesYear = year.value === "all" || section.dataset.year === year.value;
      let visible = 0;
      for (const paper of section.querySelectorAll("[data-publication]")) {
        const text = normalize(paper.dataset.search);
        paper.hidden = !matchesYear || !selectedTypes.has(paper.dataset.type) || !terms.every((term) => text.includes(term));
        if (!paper.hidden) visible += 1;
      }
      section.hidden = visible === 0;
      count += visible;
    }
    status.textContent = `${count} publication${count === 1 ? "" : "s"}`;
    empty.hidden = count !== 0;
  };

  filters.hidden = false;
  search.addEventListener("input", filter);
  year.addEventListener("change", filter);
  types.forEach((input) => input.addEventListener("change", filter));
  filters.addEventListener("submit", (event) => event.preventDefault());
  filters.addEventListener("reset", () => {
    // The browser restores form defaults after the reset event is dispatched.
    requestAnimationFrame(filter);
  });
  filter();
}
