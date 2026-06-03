async function fetchNewsJson(url) {
  const response = await fetch(url);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "News request failed");
  }
  return payload;
}

function sourceHost(item) {
  try {
    return new URL(item.link).hostname.replace("www.", "");
  } catch {
    return item.source || "news";
  }
}

function formatNewsTime(value) {
  if (!value) return "Latest";
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderNewsItems(items, compact = false) {
  if (!items || items.length === 0) {
    return `<p class="news-empty">No fresh headlines found from the active feeds.</p>`;
  }

  return `
    <div class="${compact ? "news-list compact" : "news-list"}">
      ${items
        .map(
          (item) => `
            <a class="news-item" href="${item.link}" target="_blank" rel="noopener noreferrer">
              <span>${item.source || sourceHost(item)} &bull; ${formatNewsTime(item.published_at)}</span>
              <b>${item.title}</b>
            </a>
          `
        )
        .join("")}
    </div>
  `;
}

async function loadMarketNews(market) {
  const mount = document.querySelector("#marketNews");
  if (!mount) return;

  mount.innerHTML = `
    <div class="section-title">
      <h2>Daily Market News</h2>
      <span>Collecting headlines</span>
    </div>
    <div class="news-placeholder"></div>
  `;

  try {
    const payload = await fetchNewsJson(`/api/news?market=${encodeURIComponent(market)}&limit=8`);
    mount.innerHTML = `
      <div class="section-title">
        <h2>Daily Market News</h2>
        <span>${payload.sources.join(", ")} &bull; Sentiment ${payload.sentiment.label}</span>
      </div>
      ${renderNewsItems(payload.items, true)}
    `;
  } catch (error) {
    mount.innerHTML = `
      <div class="section-title">
        <h2>Daily Market News</h2>
        <span>${error.message}</span>
      </div>
    `;
  }
}

function renderSymbolNews(news) {
  if (!news) return "";
  return `
    <div class="symbol-news">
      <div class="section-title">
        <h3>Daily Stock News</h3>
        <span>${news.sources.join(", ")} &bull; Sentiment ${news.sentiment.label}</span>
      </div>
      ${renderNewsItems(news.items, false)}
    </div>
  `;
}

window.MarketNews = {
  loadMarketNews,
  renderSymbolNews,
};
