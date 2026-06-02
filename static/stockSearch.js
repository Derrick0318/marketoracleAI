let searchTimer = null;
let lastSearchResults = [];

function looksLikeSymbol(value) {
  return /^[A-Z0-9.-]{1,12}$/i.test(value.trim()) && !value.trim().includes(" ");
}

async function searchStocks(query, limit = 8) {
  const response = await fetch(`/api/search?q=${encodeURIComponent(query)}&limit=${limit}`);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Search failed");
  return payload.results || [];
}

async function resolveSymbol(value) {
  const clean = value.trim();
  if (!clean) return "";
  if (looksLikeSymbol(clean)) return clean.toUpperCase();
  const results = await searchStocks(clean, 1);
  return results[0]?.symbol || clean.toUpperCase();
}

function renderSearchSuggestions(results) {
  const mount = document.querySelector("#searchSuggestions");
  if (!mount) return;
  lastSearchResults = results;
  if (!results.length) {
    mount.classList.remove("show");
    mount.innerHTML = "";
    return;
  }

  mount.innerHTML = results
    .map(
      (item) => `
        <button type="button" data-search-symbol="${item.symbol}">
          <span>
            <b>${item.name}</b>
            <small>${item.symbol} • ${item.market}</small>
          </span>
          <em>${item.source}</em>
        </button>
      `
    )
    .join("");
  mount.classList.add("show");

  mount.querySelectorAll("[data-search-symbol]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.querySelector("#symbolInput");
      input.value = button.dataset.searchSymbol;
      mount.classList.remove("show");
      document.querySelector("#symbolForm").requestSubmit();
    });
  });
}

function bindStockSearch() {
  const input = document.querySelector("#symbolInput");
  const mount = document.querySelector("#searchSuggestions");
  if (!input || !mount) return;

  input.addEventListener("input", () => {
    const query = input.value.trim();
    window.clearTimeout(searchTimer);
    if (query.length < 2) {
      renderSearchSuggestions([]);
      return;
    }
    searchTimer = window.setTimeout(async () => {
      try {
        renderSearchSuggestions(await searchStocks(query, 8));
      } catch {
        renderSearchSuggestions([]);
      }
    }, 220);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" && lastSearchResults[0]) {
      event.preventDefault();
      mount.querySelector("button")?.focus();
    }
    if (event.key === "Escape") {
      mount.classList.remove("show");
    }
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".search-wrap")) {
      mount.classList.remove("show");
    }
  });
}

document.addEventListener("DOMContentLoaded", bindStockSearch);

window.StockSearch = {
  resolveSymbol,
};
