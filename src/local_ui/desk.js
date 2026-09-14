"use strict";
const el = id => document.getElementById(id);
let page = 1, selectedTicker = null, requestId = 0, detailRequestId = 0;
const number = value => value === null || value === undefined ? "Unavailable" : Number(value).toLocaleString(undefined, {maximumFractionDigits: 1});
function node(tag, text, className) { const item = document.createElement(tag); if (text !== undefined) item.textContent = text; if (className) item.className = className; return item; }
function link(text, url) { const item = node("a", text); item.href = url; item.target = "_blank"; item.rel = "noopener noreferrer"; return item; }
async function read(url) { const response = await fetch(url); const data = await response.json(); if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "The local artifact request could not be completed."); return data; }
function list(items) { const ul = node("ul"); items.forEach(item => ul.append(node("li", item))); return ul; }
function showSources(sources) { const container = el("sources"); container.replaceChildren(); sources.forEach(source => { const card = node("article", undefined, "source-card"); card.append(node("h3", source.layer.replaceAll("_", " ")), node("p", source.status === "available" ? `Research cutoff ${source.as_of || "unknown"} · ${source.freshness}` : "Unavailable")); if (source.oldest_retrieved_at) card.append(node("p", `Oldest recorded retrieval ${source.oldest_retrieved_at}`)); if (source.retrieval_provenance) card.append(node("p", `Retrieval provenance: ${source.retrieval_provenance}`)); if (source.generated_at) card.append(node("p", `Artifact generated ${source.generated_at}`)); (source.warnings || []).forEach(w => card.append(node("p", w, "warning"))); (source.known_gaps || []).forEach(w => card.append(node("p", w))); container.append(card); }); }
async function load() {
  const currentRequest = ++requestId;
  el("notice").textContent = "Reading local research artifacts…";
  const params = new URLSearchParams({q: el("search").value, min_score: el("min-score").value || "0", eligibility: el("eligibility").value, coverage: el("coverage").value, page, page_size: 25});
  try {
    const data = await read(`/api/v1/predictions/watchlist?${params}`); if (currentRequest !== requestId) return;
    const base = data.sources.find(source => source.layer === "market_evaluation");
    el("notice").className = "notice";
    el("notice").textContent = `Saved research cutoff ${data.as_of}. ${base.warnings.length ? base.warnings.join(" ") : "Recorded source retrievals are within the review window; this remains a saved snapshot."} Missing company-specific evidence means unscreened, not low risk.`;
    el("count-companies").textContent = number(data.coverage.companies); el("count-eligible").textContent = number(data.coverage.eligible); el("count-evidence").textContent = number(data.coverage.with_company_specific_evidence); el("count-unscreened").textContent = number(data.coverage.unscreened);
    el("as-of").textContent = `RESEARCH CUTOFF ${data.as_of}`;
    const history = data.historical_training;
    el("training-status").textContent = history && history.status !== "unavailable" ? `${number(history.reviewed_positive_announcements)} source-reviewed acquisition announcements. The earlier pilot retains ${number(history.historical_financial_records || 0)} financial reports and ${number(history.reviewed_negative_company_windows)} reviewed non-acquisition windows; current cohort coverage appears below. No model trained on real historical data is available.` : "Historical training evidence is unavailable. No model trained on real historical data is available.";
    const panel = history?.historical_panel;
    const hasPanel = panel && panel.status !== "unavailable";
    el("panel-status").textContent = hasPanel ? `${number(panel.frame_companies)} companies in the fixed historical cohort · ${number(panel.planned_observations)} planned company-year observations · ${number(panel.reviewed_annual_financial_records)} source-verified annual reports · ${number(panel.reviewed_negative_corpus_windows)} archive-reviewed outcome windows · ${number(panel.eligible_feature_observations)} assembled observations. Training eligibility also depends on historical membership, pending deals and when the outcome evidence was available.` : "The historical cohort coverage report is unavailable.";
    if (hasPanel && panel.pre_test_training_support) {
      const support = panel.pre_test_training_support;
      el("panel-status").textContent += ` Before the ${support.test_start_year} test cutoff: ${number(support.distinct_positive_events)} qualifying acquisition events and ${number(support.distinct_negative_companies)} qualifying comparison companies. Training requires at least 5 and 20 respectively.`;
    }
    el("coverage-download").hidden = !hasPanel;
    el("result-summary").textContent = `${number(data.total)} matching companies · ${data.coverage.excluded} excluded from the full universe · ${data.coverage.with_matched_assets} with matched assets`;
    el("page-label").textContent = `Page ${page} of ${Math.max(1, Math.ceil(data.total / 25))}`;
    el("prev").disabled = page <= 1; el("next").disabled = page * 25 >= data.total;
    const tbody = el("companies"); tbody.replaceChildren();
    data.watchlist.forEach(company => {
      const row = node("tr"); row.dataset.ticker = company.ticker; if (company.ticker === selectedTicker) row.className = "selected";
      const companyCell = node("td"); const button = node("button", company.ticker, "company-link"); button.type = "button"; button.setAttribute("aria-label", `Open research file for ${company.company_name}`); button.addEventListener("click", () => openCompany(company.ticker)); companyCell.append(button, node("span", company.company_name, "company-name"));
      const score = node("td", number(company.research_score), "score"); const coverage = node("td"); coverage.append(node("span", company.risk_screened ? "EVIDENCE AVAILABLE" : company.risk_coverage === "unavailable" ? "UNAVAILABLE" : "UNSCREENED", `badge ${company.risk_screened ? "evidence" : ""}`));
      const eligibility = node("td"); eligibility.append(node("span", company.risk_set_eligible ? (company.risk_set_screening_current === false ? "PRIOR SCREEN" : "ELIGIBLE") : "EXCLUDED", `badge ${company.risk_set_eligible ? "" : "excluded"}`));
      row.append(companyCell, score, coverage, eligibility); tbody.append(row);
    });
    if (!data.watchlist.length) { const row = node("tr"); const cell = node("td", "No companies match these filters."); cell.colSpan = 4; row.append(cell); tbody.append(row); }
    showSources(data.sources);
  } catch (error) {
    if (currentRequest !== requestId) return;
    el("notice").className = "notice unavailable"; el("notice").textContent = `Research unavailable: ${error.message}`; el("companies").replaceChildren(); el("result-summary").textContent = "Restore or generate valid local research artifacts, then reload.";
    el("training-status").textContent = "Historical training evidence is unavailable.";
    el("panel-status").textContent = "Historical cohort coverage is unavailable."; el("coverage-download").hidden = true;
    ["count-companies", "count-eligible", "count-evidence", "count-unscreened"].forEach(id => el(id).textContent = "—"); el("prev").disabled = true; el("next").disabled = true; el("page-label").textContent = ""; el("sources").replaceChildren();
  }
}
async function openCompany(ticker) {
  selectedTicker = ticker; const currentRequest = ++detailRequestId; const container = el("detail"); container.replaceChildren(node("p", `Opening ${ticker}…`, "eyebrow"));
  document.querySelectorAll("tr[data-ticker]").forEach(row => row.classList.toggle("selected", row.dataset.ticker === ticker));
  try {
    const company = await read(`/api/v1/companies/${encodeURIComponent(ticker)}`); if (currentRequest !== detailRequestId) return;
    container.replaceChildren(node("p", `COMPANY FILE / ${ticker}`, "eyebrow"), node("h2", company.company_name), node("p", `${company.industry} · Research cutoff ${company.as_of}`, "small"));
    const score = node("div", undefined, "detail-score"); score.append(node("span", number(company.research_score), "score-value"), node("p", "RESEARCH SCORE / 100\nRanking only; no probability estimate.")); container.append(score);
    if (!company.risk_set_eligible) container.append(node("p", `EXCLUDED FROM RANKING: ${company.risk_set_exclusion_reason}`, "file-warning"));
    container.append(node("p", company.risk_screened ? "Company-specific diligence evidence is present. Review the source status and dates below." : "UNSCREENED: no company-specific evidence is available in the joined research snapshot. This does not imply low risk.", "file-warning"));
    const download = node("a", "Download research file ↓", "download"); download.href = `/api/v1/companies/${encodeURIComponent(ticker)}/report`; container.append(download);
    container.append(node("h3", "What drives the ranking")); container.append(company.score_drivers.length ? list(company.score_drivers) : node("p", "Score drivers unavailable."));
    container.append(node("p", `Market-data confidence: ${number(company.data_confidence)} / 100. Matched approved assets: ${number(company.approved_asset_count)}; clinical assets: ${number(company.clinical_asset_count)}.`, "small"));
    if (company.decision_rule) container.append(node("p", company.decision_rule));
    container.append(node("h3", "Matched assets & source documents"));
    if (company.assets.status === "unavailable") container.append(node("p", company.assets.reason, "file-warning"));
    else if (!company.assets.items.length) container.append(node("p", "No matched asset rows in this snapshot. Ownership coverage may be incomplete."));
    company.assets.items.forEach(asset => { const details = node("details"); details.append(node("summary", `${asset.asset_name} · ${asset.development_phase || "stage unavailable"}`)); details.append(node("p", `${asset.source_name} · Published ${asset.published_at || "date unavailable"}`, "asset-meta")); if (asset.indications.length) details.append(node("p", asset.indications.join(", "))); details.append(list(asset.score_drivers)); if (asset.source_url) details.append(link("Open source document ↗", asset.source_url)); else details.append(node("p", "Source link unavailable.")); container.append(details); });
    container.append(node("h3", "Diligence evidence"));
    company.evidence.forEach(layer => { container.append(node("p", `${layer.layer.replaceAll("_", " ")} · ${layer.status}`, "eyebrow")); if (layer.reason) container.append(node("p", layer.reason)); if (layer.status === "unscreened") container.append(node("p", "No company-specific evidence rows are present. This is not a low-risk finding.")); layer.signals.forEach(signal => { const item = node("div", undefined, "signal"); item.append(node("p", `${signal.evidence_status} · ${signal.source_date || signal.event_date || "date unavailable"}`, "asset-meta"), node("p", signal.summary)); if (signal.review_notes) item.append(node("p", signal.review_notes, "small")); if (signal.source_url) item.append(link(signal.source_title || "Open source document ↗", signal.source_url)); if (signal.response_url) item.append(node("p", "Company response: "), link("Open response ↗", signal.response_url)); container.append(item); }); });
    container.append(node("p", company.risk_interpretation, "small"));
  } catch (error) { if (currentRequest === detailRequestId) container.replaceChildren(node("h2", "Research file unavailable"), node("p", error.message)); }
}
el("filters").addEventListener("submit", event => { event.preventDefault(); page = 1; load(); });
el("prev").addEventListener("click", () => { if (page > 1) { page--; load(); } });
el("next").addEventListener("click", () => { page++; load(); });
load();
