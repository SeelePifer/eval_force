import "./styles.css";
import { compareRun, getRun, listRuns, type CompareResult, type RunDetail, type RunSummary, type TargetPoint } from "./api";

const KEY = "evalforge.apiKey";
const app = document.querySelector<HTMLDivElement>("#app");
if (!app) {
  throw new Error("Missing #app");
}

const state: { runs: RunSummary[]; selected: RunDetail | null; apiKey: string } = {
  runs: [],
  selected: null,
  apiKey: sessionStorage.getItem(KEY) ?? "",
};

app.innerHTML = `
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">
        <div class="mark" aria-hidden="true">EF</div>
        <div>
          <h1>EvalForge</h1>
          <p class="tagline">Release gate for quality, cost, and latency.</p>
        </div>
      </div>
      <form id="connect" class="connect">
        <label>API key<input id="api-key" type="password" autocomplete="off" placeholder="dev-key" /></label>
        <button id="load" class="primary" type="submit">Load runs</button>
      </form>
    </header>
    <p id="error" class="error"></p>
    <main class="workspace">
      <section class="panel">
        <div class="panel-head">
          <h2>Runs</h2>
          <span id="run-count" class="hint"></span>
        </div>
        <div id="runs" class="run-list"></div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <div>
            <h2>Quality versus cost</h2>
            <p class="hint">Up is better quality. Right is higher cost.</p>
          </div>
        </div>
        <div id="stats" class="stats"></div>
        <div id="chart" class="chart-card"></div>
        <div id="summary"></div>
        <form id="compare" class="compare">
          <label>Target A<select id="target-a"></select></label>
          <label>Target B<select id="target-b"></select></label>
          <button class="ghost" type="submit">Compare cases</button>
        </form>
        <div id="diff"></div>
      </section>
    </main>
  </div>
`;

const errorNode = required<HTMLParagraphElement>("#error");
const apiKeyInput = required<HTMLInputElement>("#api-key");
apiKeyInput.value = state.apiKey;

required<HTMLFormElement>("#connect").addEventListener("submit", (event) => {
  event.preventDefault();
  state.apiKey = apiKeyInput.value.trim();
  sessionStorage.setItem(KEY, state.apiKey);
  void refresh();
});

required<HTMLFormElement>("#compare").addEventListener("submit", (event) => {
  event.preventDefault();
  void showDiff();
});

function required<T extends Element>(selector: string): T {
  const node = document.querySelector<T>(selector);
  if (!node) {
    throw new Error(`Missing ${selector}`);
  }
  return node;
}

async function refresh(): Promise<void> {
  errorNode.textContent = "";
  const loadButton = required<HTMLButtonElement>("#load");
  if (!state.apiKey) {
    errorNode.textContent = "Enter the API key from EVALFORGE_API_KEY.";
    return;
  }
  loadButton.disabled = true;
  loadButton.textContent = "Loading…";
  try {
    state.runs = await listRuns(state.apiKey);
    renderRuns();
    if (state.runs[0]) {
      await selectRun(state.runs[0].id);
    } else {
      state.selected = null;
      required("#stats").innerHTML = "";
      required("#chart").innerHTML = `<p class="empty">No runs yet. Publish one with evalforge publish.</p>`;
      required("#summary").innerHTML = "";
      required("#diff").innerHTML = "";
    }
  } catch (error) {
    errorNode.textContent = error instanceof Error ? error.message : "Could not load runs.";
  } finally {
    loadButton.disabled = false;
    loadButton.textContent = "Load runs";
  }
}

function renderRuns(): void {
  const list = required("#runs");
  const count = required("#run-count");
  count.textContent = state.runs.length === 1 ? "1 run" : `${state.runs.length} runs`;
  list.innerHTML = "";
  if (state.runs.length === 0) {
    list.innerHTML = `<p class="empty">Nothing published yet.</p>`;
    return;
  }
  for (const run of state.runs) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `run-card ${run.passed ? "pass" : "fail"}`;
    if (state.selected?.id === run.id) {
      button.setAttribute("aria-current", "true");
    }
    const stripe = document.createElement("span");
    stripe.className = "stripe";
    const body = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = run.passed ? "Gate passed" : "Gate failed";
    title.className = run.passed ? "pass" : "fail";
    const when = document.createElement("span");
    when.className = "when";
    when.textContent = new Date(run.created_at).toLocaleString();
    const hash = document.createElement("span");
    hash.className = "hash";
    hash.textContent = run.dataset_sha256.slice(0, 12);
    body.append(title, when, hash);
    button.append(stripe, body);
    button.addEventListener("click", () => {
      void selectRun(run.id);
    });
    list.append(button);
  }
}

async function selectRun(id: string): Promise<void> {
  errorNode.textContent = "";
  try {
    state.selected = await getRun(state.apiKey, id);
    renderRuns();
    renderSelected();
  } catch (error) {
    errorNode.textContent = error instanceof Error ? error.message : "Could not load the run.";
  }
}

function renderSelected(): void {
  const detail = state.selected;
  if (!detail) {
    return;
  }
  const points = detail.results.targets.map((target) => ({
    name: target.name,
    model: target.model,
    quality: target.summary.quality,
    cost_usd: target.summary.cost_usd,
    latency_p95_ms: target.summary.latency_p95_ms,
    prompt_tokens: target.summary.prompt_tokens,
    completion_tokens: target.summary.completion_tokens,
  }));
  required("#stats").innerHTML = statCards(detail, points);
  required("#chart").innerHTML = scatter(points);
  required("#summary").innerHTML = summaryTable(points);
  fillTargets(points.map((point) => point.name));
  if (points.length > 1) {
    void showDiff();
    return;
  }
  required("#diff").innerHTML = `<p class="empty">Add a second target to compare cases.</p>`;
}

function fillTargets(names: string[]): void {
  for (const id of ["target-a", "target-b"]) {
    const select = required<HTMLSelectElement>(`#${id}`);
    select.innerHTML = "";
    for (const name of names) {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      select.append(option);
    }
  }
  const second = required<HTMLSelectElement>("#target-b");
  if (names[1]) {
    second.value = names[1];
  }
}

async function showDiff(): Promise<void> {
  const detail = state.selected;
  if (!detail) {
    return;
  }
  const targetA = required<HTMLSelectElement>("#target-a").value;
  const targetB = required<HTMLSelectElement>("#target-b").value;
  try {
    const result = await compareRun(state.apiKey, detail.id, targetA, targetB);
    required("#diff").innerHTML = diffTable(targetA, targetB, result);
  } catch (error) {
    errorNode.textContent = error instanceof Error ? error.message : "Could not compare targets.";
  }
}

function statCards(detail: RunDetail, points: TargetPoint[]): string {
  if (points.length === 0) {
    return "";
  }
  const best = points.reduce((left, right) => (right.quality > left.quality ? right : left));
  const cheapest = points.reduce((left, right) => (right.cost_usd < left.cost_usd ? right : left));
  const slowest = points.reduce((left, right) => (right.latency_p95_ms > left.latency_p95_ms ? right : left));
  return `
    <article class="stat">
      <span>Gate</span>
      <strong class="${detail.passed ? "pass" : "fail"}">${detail.passed ? "Passed" : "Failed"}</strong>
    </article>
    <article class="stat">
      <span>Best quality</span>
      <strong>${best.quality.toFixed(3)}</strong>
      <em>${escapeHtml(best.name)}</em>
    </article>
    <article class="stat">
      <span>Lowest cost</span>
      <strong>$${cheapest.cost_usd.toFixed(6)}</strong>
      <em>${escapeHtml(cheapest.name)}</em>
    </article>
    <article class="stat">
      <span>Slowest p95</span>
      <strong>${slowest.latency_p95_ms.toFixed(0)} ms</strong>
      <em>${escapeHtml(slowest.name)}</em>
    </article>
  `;
}

function summaryTable(points: TargetPoint[]): string {
  const rows = points
    .map(
      (point, index) => `<tr>
        <td data-label="Target"><i class="swatch" style="background:${palette[index % palette.length]}"></i> ${escapeHtml(point.name)}<div class="model">${escapeHtml(point.model)}</div></td>
        <td class="num" data-label="Quality">${point.quality.toFixed(3)}</td>
        <td class="num" data-label="Cost">${point.cost_usd.toFixed(6)}</td>
        <td class="num" data-label="p95 ms">${point.latency_p95_ms.toFixed(1)}</td>
        <td class="num" data-label="Tokens">${point.prompt_tokens + point.completion_tokens}</td>
      </tr>`,
    )
    .join("");
  return `<div class="table-wrap"><table>
      <thead><tr><th>Target</th><th class="num">Quality</th><th class="num">Cost</th><th class="num">p95 ms</th><th class="num">Tokens</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
}

function diffTable(targetA: string, targetB: string, result: CompareResult): string {
  const rows = result.cases
    .map(
      (item) => `<tr>
        <td data-label="Case">${escapeHtml(item.case_id)}</td>
        <td class="num" data-label="${escapeHtml(targetA)}">${item.quality_a.toFixed(3)}</td>
        <td class="num" data-label="${escapeHtml(targetB)}">${item.quality_b.toFixed(3)}</td>
        <td class="num" data-label="Delta">${item.quality_delta.toFixed(3)}</td>
        <td data-label="${escapeHtml(targetA)} output">${escapeHtml(item.output_a)}</td>
        <td data-label="${escapeHtml(targetB)} output">${escapeHtml(item.output_b)}</td>
      </tr>`,
    )
    .join("");
  return `<div class="delta-row">
      ${chip("Quality", result.quality_delta, result.quality_delta >= 0)}
      ${chip("Cost", result.cost_delta, result.cost_delta <= 0)}
      ${chip("p95 ms", result.latency_p95_delta_ms, result.latency_p95_delta_ms <= 0)}
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>Case</th><th class="num">${escapeHtml(targetA)}</th><th class="num">${escapeHtml(targetB)}</th><th class="num">Delta</th><th>${escapeHtml(targetA)} output</th><th>${escapeHtml(targetB)} output</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
}

function chip(label: string, delta: number, improved: boolean): string {
  const sign = delta > 0 ? "+" : "";
  const digits = label === "p95 ms" ? 1 : label === "Cost" ? 6 : 3;
  return `<span class="chip ${improved ? "up" : "down"}">${label} ${sign}${delta.toFixed(digits)}</span>`;
}

const palette = ["#ffb15a", "#7ee0c6", "#ff7a59", "#9db4ff"];

function scatter(points: TargetPoint[]): string {
  const width = 720;
  const height = 320;
  const padLeft = 48;
  const padRight = 28;
  const padTop = 36;
  const padBottom = 36;
  const costs = points.map((point) => point.cost_usd);
  const minCost = Math.min(...costs);
  const maxCost = Math.max(...costs);
  const span = maxCost - minCost || 1;
  const plotWidth = width - padLeft - padRight;
  const plotHeight = height - padTop - padBottom;
  const grid = [0.25, 0.5, 0.75, 1]
    .map((tick) => {
      const y = padTop + (1 - tick) * plotHeight;
      return `<line x1="${padLeft}" y1="${y}" x2="${width - padRight}" y2="${y}" stroke="rgba(246,239,230,0.08)" />
        <text x="8" y="${y + 4}" fill="#b3a79a" font-size="11">${tick.toFixed(2)}</text>`;
    })
    .join("");
  const circles = points
    .map((point, index) => {
      const color = palette[index % palette.length] ?? palette[0];
      const x = padLeft + ((point.cost_usd - minCost) / span) * plotWidth;
      const y = padTop + (1 - Math.min(Math.max(point.quality, 0), 1)) * plotHeight;
      const labelY = y < padTop + 28 ? y + 28 : y - 16;
      const label = document.documentElement.clientWidth > 720
        ? `<text x="${x.toFixed(1)}" y="${labelY.toFixed(1)}" text-anchor="middle" fill="#f6efe6" font-size="13">${escapeHtml(point.name)}</text>`
        : "";
      return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="14" fill="${color}" opacity="0.25" />
        <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="7" fill="${color}"><title>${escapeHtml(point.name)} quality ${point.quality.toFixed(3)} cost ${point.cost_usd.toFixed(6)}</title></circle>
        ${label}`;
    })
    .join("");
  const legend = points
    .map(
      (point, index) =>
        `<li><i style="background:${palette[index % palette.length]}"></i>${escapeHtml(point.name)}</li>`,
    )
    .join("");
  return `<div class="chart-wrap"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Quality versus cost">
    ${grid}
    <text x="${width - padRight}" y="${height - 10}" text-anchor="end" fill="#b3a79a" font-size="11">Cost</text>
    ${circles}
  </svg>
  <ul class="legend">${legend}</ul></div>`;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => {
    const entities: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return entities[char] ?? char;
  });
}

let resizeTimer = 0;
window.addEventListener("resize", () => {
  window.clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(() => {
    if (!state.selected) {
      return;
    }
    const points = state.selected.results.targets.map((target) => ({
      name: target.name,
      model: target.model,
      quality: target.summary.quality,
      cost_usd: target.summary.cost_usd,
      latency_p95_ms: target.summary.latency_p95_ms,
      prompt_tokens: target.summary.prompt_tokens,
      completion_tokens: target.summary.completion_tokens,
    }));
    required("#chart").innerHTML = scatter(points);
  }, 120);
});

if (state.apiKey) {
  void refresh();
}
