const form = document.querySelector("#predictForm");
const statusBox = document.querySelector("#status");
const dashboard = document.querySelector("#dashboard");
const bestScore = document.querySelector("#bestScore");
const lambdaText = document.querySelector("#lambdaText");
const qualityText = document.querySelector("#qualityText");
const outcomes = document.querySelector("#outcomes");
const topScores = document.querySelector("#topScores");
const insuranceScores = document.querySelector("#insuranceScores");
const candidateScores = document.querySelector("#candidateScores");
const upsetScores = document.querySelector("#upsetScores");
const confidenceNote = document.querySelector("#confidenceNote");
const matrixEl = document.querySelector("#matrix");
const sourceSummary = document.querySelector("#sourceSummary");
const backtestSummary = document.querySelector("#backtestSummary");
const backtestTable = document.querySelector("#backtestTable");
const refreshBacktest = document.querySelector("#refreshBacktest");

function pct(value) {
  return `${(value * 100).toFixed(1)}%`;
}

function setStatus(text, isError = false) {
  statusBox.textContent = text;
  statusBox.style.color = isError ? "#b42318" : "#66747d";
}

function renderBars(data, homeName, awayName) {
  const rows = [
    [homeName + "胜", data.homeWin],
    ["平局", data.draw],
    [awayName + "胜", data.awayWin],
    ["大于 2.5 球", data.over25],
    ["双方进球", data.btts],
  ];
  outcomes.innerHTML = rows
    .map(([label, value]) => `
      <div class="bar-row">
        <span>${label}</span>
        <div class="bar"><span style="width:${Math.max(2, value * 100)}%"></span></div>
        <strong>${pct(value)}</strong>
      </div>
    `)
    .join("");
}

function renderTopScores(scores) {
  topScores.innerHTML = scores
    .map((item) => `
      <div class="score-item">
        <div>
          <strong>${item.score}</strong>
          <em>${item.label || "推荐"}</em>
        </div>
        <span>${pct(item.prob)}</span>
      </div>
    `)
    .join("");
}

function renderScoreList(target, scores) {
  target.innerHTML = scores.length
    ? scores
        .map((item) => `
          <div class="score-item">
            <div>
              <strong>${item.score}</strong>
              <em>${item.label || "候选"}</em>
            </div>
            <span>${pct(item.prob)}</span>
          </div>
        `)
        .join("")
    : '<p class="copy">暂无可用比分。</p>';
}

function renderMatrix(matrix) {
  const flatMax = Math.max(...matrix.flat());
  let html = "<thead><tr><th>主\\客</th>";
  for (let a = 0; a < matrix[0].length; a += 1) html += `<th>${a}</th>`;
  html += "</tr></thead><tbody>";
  matrix.forEach((row, h) => {
    html += `<tr><th>${h}</th>`;
    row.forEach((value) => {
      const heat = 0.08 + (value / flatMax) * 0.62;
      html += `<td style="--heat:${heat.toFixed(3)}">${pct(value)}</td>`;
    });
    html += "</tr>";
  });
  html += "</tbody>";
  matrixEl.innerHTML = html;
}

function itemText(item) {
  if (!item) return "无摘要";
  const snippet = item.snippet ? `：${item.snippet}` : "";
  return `${item.title || "搜索结果"}${snippet}`;
}

function renderSources(data) {
  const [homeProfile, awayProfile] = data.sources.profiles;
  const [homeNews, awayNews] = data.sources.webSignals;
  sourceSummary.innerHTML = `
    <div class="source-card">
      <strong>淘汰赛球队</strong>
      <p>${homeProfile.zh}（${homeProfile.en}）：${homeProfile.status}，强度 ${homeProfile.rating.toFixed(0)}；${awayProfile.zh}（${awayProfile.en}）：${awayProfile.status}，强度 ${awayProfile.rating.toFixed(0)}</p>
    </div>
    <div class="source-card">
      <strong>模型因子</strong>
      <p>使用国家队基础强度、本届赛事状态、东道主优势、淘汰赛保守系数、历史淘汰赛比分先验、是否同洲际对手、联网搜索中的近况和伤停关键词来修正预期进球。</p>
      <p>搜索质量：${pct(data.dataQuality.searchQuality || 0)}。${data.dataQuality.searchNote || ""}</p>
    </div>
    <div class="source-card">
      <strong>伤停与阵容搜索</strong>
      <p>${data.homeInput}：${itemText(homeNews.items && homeNews.items[0])}</p>
      <p>${data.awayInput}：${itemText(awayNews.items && awayNews.items[0])}</p>
    </div>
  `;
}

function outcomeName(code) {
  return code === "H" ? "主胜" : code === "A" ? "客胜" : "平局";
}

function renderBacktest(data) {
  backtestSummary.innerHTML = `
    <div class="metric"><span>胜平负方向</span><strong>${pct(data.resultAccuracy)}</strong></div>
    <div class="metric"><span>最可能比分命中</span><strong>${pct(data.exactAccuracy)}</strong></div>
    <div class="metric"><span>主推3个覆盖</span><strong>${pct(data.recommendedTop3Accuracy)}</strong></div>
    <div class="metric"><span>保险5个覆盖</span><strong>${pct(data.recommendedTop5Accuracy)}</strong></div>
    <div class="metric"><span>Top10覆盖</span><strong>${pct(data.top10Accuracy)}</strong></div>
  `;
  let html = `
    <thead>
      <tr>
        <th>比赛</th>
        <th>实际比分</th>
        <th>模型首选</th>
        <th>实际排名</th>
        <th>主推3覆盖</th>
        <th>保险5覆盖</th>
        <th>Top10覆盖</th>
        <th>方向</th>
      </tr>
    </thead>
    <tbody>
  `;
  data.rows.forEach((row) => {
    html += `
      <tr>
        <td>${row.match}</td>
        <td>${row.actualScore}</td>
        <td>${row.topScore}（${pct(row.topScoreProb)}）</td>
        <td>第 ${row.actualScoreRank}（${pct(row.actualScoreProb)}）</td>
        <td class="${row.recommendedTop3Hit ? "hit" : "miss"}">${row.recommendedTop3Hit ? "命中" : "未命中"}</td>
        <td class="${row.recommendedTop5Hit ? "hit" : "miss"}">${row.recommendedTop5Hit ? "命中" : "未命中"}</td>
        <td class="${row.top10Hit ? "hit" : "miss"}">${row.top10Hit ? "命中" : "未命中"}</td>
        <td class="${row.outcomeHit ? "hit" : "miss"}">${outcomeName(row.predictedOutcome)} / ${outcomeName(row.actualOutcome)}</td>
      </tr>
    `;
  });
  html += "</tbody>";
  backtestTable.innerHTML = html;
}

async function loadBacktest() {
  refreshBacktest.disabled = true;
  backtestSummary.textContent = "正在计算已结束淘汰赛回测...";
  try {
    const response = await fetch("/api/backtest");
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "回测失败");
    renderBacktest(data);
  } catch (error) {
    backtestSummary.textContent = error.message;
  } finally {
    refreshBacktest.disabled = false;
  }
}

async function runPrediction(event) {
  event.preventDefault();
  const button = form.querySelector("button");
  const home = document.querySelector("#homeTeam").value.trim();
  const away = document.querySelector("#awayTeam").value.trim();
  const neutral = document.querySelector("#neutral").checked ? "1" : "0";
  if (!home || !away) {
    setStatus("请输入两支球队名称。", true);
    return;
  }

  button.disabled = true;
  dashboard.hidden = true;
  setStatus("正在联网搜索世界杯近况、伤停和预计阵容摘要...");
  try {
    const response = await fetch(`/api/predict?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}&neutral=${neutral}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "请求失败");

    bestScore.textContent = `${data.coverageScores.recommendedTop3[0].score}（3选覆盖）`;
    lambdaText.textContent = `${data.homeLambda.toFixed(2)} : ${data.awayLambda.toFixed(2)}`;
    qualityText.textContent = `${data.coverageScores.confidence}（3:${pct(data.coverageScores.top3ProbabilityMass)} / 5:${pct(data.coverageScores.top5ProbabilityMass)} / 10:${pct(data.coverageScores.top10ProbabilityMass)}）`;
    renderBars(data.probabilities, home, away);
    renderTopScores(data.coverageScores.recommendedTop3);
    renderScoreList(insuranceScores, data.coverageScores.recommendedTop5);
    renderScoreList(candidateScores, data.coverageScores.candidateTop10);
    renderScoreList(upsetScores, data.coverageScores.upsetProtection);
    confidenceNote.textContent = `${data.coverageScores.confidenceNote} ${data.coverageScores.coverageAdvice || ""}`;
    renderMatrix(data.matrix);
    renderSources(data);
    dashboard.hidden = false;
    setStatus(`预测完成：${data.generatedAt}。${data.dataQuality.note}`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    button.disabled = false;
  }
}

form.addEventListener("submit", runPrediction);
refreshBacktest.addEventListener("click", loadBacktest);
loadBacktest();
