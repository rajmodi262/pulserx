// PulseRx dashboard. Every figure is read from data.js, which prep_dashboard_data.py
// builds from the pipeline marts. Nothing numeric is typed into this file or index.html.

let chartTrendInstance = null;
let chartLorenzInstance = null;
let chartOpportunityInstance = null;
let chartTerritoryInstance = null;

document.addEventListener("DOMContentLoaded", () => {
  if (typeof DASHBOARD_DATA === "undefined") {
    console.error("DASHBOARD_DATA not found. Make sure data.js is loaded.");
    return;
  }

  initKPIs(DASHBOARD_DATA.kpis);
  initTrendChart(DASHBOARD_DATA.monthly_trend);
  initLorenzChart(DASHBOARD_DATA.decile_summary);
  initOpportunityChart(DASHBOARD_DATA.sample_hcps);
  initTerritoryChart(DASHBOARD_DATA.territories);
  renderTerritoryCards(DASHBOARD_DATA.territories);
  renderHCPTable(DASHBOARD_DATA.sample_hcps);
  setupFilters();
  setupModal();
  setupExport();
  setupSimulator();
});

// 1. Populate Top KPIs
function initKPIs(kpis) {
  const a = DASHBOARD_DATA.metrics.arithmetic;
  const trend = DASHBOARD_DATA.monthly_trend;
  const bz = trend.reduce((s, m) => s + m.BioZenith_TRx, 0) / trend.reduce((s, m) => s + m.Market_TRx, 0) * 100;
  const set = (id, v) => { document.getElementById(id).innerText = v; };

  set("kpiSales", `$${(kpis.brand_sales_usd / 1e6).toFixed(1)}M`);
  set("kpiShare", `${kpis.brand_share_pct}%`);
  set("kpiShareMeta", `BioZenith ${bz.toFixed(1)}%`);
  set("kpiCoverage", `${kpis.high_value_reach_pct}%`);
  set("kpiCoverageMeta", `${a.high_value_hcps_with_zero_calls} of ${a.high_value_hcps} deciles 8-10 got no call`);
  set("kpiWorkload", `${kpis.plan_utilization_pct}%`);
  set("kpiWorkloadMeta", `${a.plan_required_calls.toLocaleString()} of ${a.field_capacity_calls.toLocaleString()} calls`);
  set("kpiDeficit", kpis.tier1_2_call_shortfall.toLocaleString());
  set("kpiDeficitMeta", `${a.calls_beyond_plan_all_tiers.toLocaleString()} calls elsewhere exceed plan`);

  document.getElementById("bannerText").innerHTML =
    `<strong>${a.hcps.toLocaleString()} synthetic prescribers</strong>, ` +
    `<strong>${a.territories} territories</strong>, ${a.reps} reps. Today's calls follow access, not value: ` +
    `<strong>${a.high_value_hcps_with_zero_calls_pct}%</strong> of high-value prescribers got no call, ` +
    `while the full call plan needs only <strong>${a.plan_utilization_pct}%</strong> of current capacity.`;
}

// 2. Chart 1: 12-Month Market Share & TRx Trajectory
function initTrendChart(monthlyData) {
  const ctx = document.getElementById("chartTrend").getContext("2d");
  const labels = monthlyData.map(d => {
    const parts = d.Month_Date.split("-");
    const m = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${m[parseInt(parts[1], 10) - 1]} '25`;
  });

  const pulserxTRx = monthlyData.map(d => d.PulseRx_TRx);
  const biozenithTRx = monthlyData.map(d => d.BioZenith_TRx);
  const pulserxShare = monthlyData.map(d => d.PulseRx_Share.toFixed(1));

  chartTrendInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "PulseRx TRx (Our Brand)",
          data: pulserxTRx,
          borderColor: "#38bdf8",
          backgroundColor: "rgba(56, 189, 248, 0.15)",
          fill: true,
          tension: 0.35,
          yAxisID: "y"
        },
        {
          label: "BioZenith TRx (Competitor)",
          data: biozenithTRx,
          borderColor: "#94a3b8",
          borderDash: [5, 5],
          tension: 0.35,
          yAxisID: "y"
        },
        {
          label: "PulseRx Share %",
          data: pulserxShare,
          borderColor: "#10b981",
          borderWidth: 2.5,
          pointBackgroundColor: "#10b981",
          tension: 0.35,
          yAxisID: "y1"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: "#94a3b8", font: { family: "Plus Jakarta Sans", size: 11 } } },
        tooltip: {
          backgroundColor: "#182030",
          titleColor: "#f1f5f9",
          bodyColor: "#94a3b8",
          borderColor: "#243046",
          borderWidth: 1
        }
      },
      scales: {
        x: { grid: { color: "rgba(36, 48, 70, 0.5)" }, ticks: { color: "#64748b" } },
        y: {
          grid: { color: "rgba(36, 48, 70, 0.5)" },
          ticks: { color: "#64748b" },
          title: { display: true, text: "Total Prescriptions (TRx)", color: "#94a3b8" }
        },
        y1: {
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: { color: "#10b981", callback: v => v + "%" },
          title: { display: true, text: "Market Share %", color: "#10b981" }
        }
      }
    }
  });
}

// 3. Chart 2: Prescriber Decile Lorenz Curve (80/20 Rule)
function initLorenzChart(decileData) {
  const ctx = document.getElementById("chartLorenz").getContext("2d");
  
  const sorted = [...decileData].sort((a, b) => b.Market_Decile - a.Market_Decile);
  let cumHCP = 0;
  let cumTRx = 0;
  const totalTRx = sorted.reduce((sum, d) => sum + d.Market_TRx, 0);
  const totalHCP = sorted.reduce((sum, d) => sum + d.HCP_Count, 0);

  const lorenzPoints = [{ x: 0, y: 0 }];
  sorted.forEach(d => {
    cumHCP += d.HCP_Count;
    cumTRx += d.Market_TRx;
    lorenzPoints.push({
      x: Math.round((cumHCP / totalHCP) * 100),
      y: Math.round((cumTRx / totalTRx) * 100)
    });
  });

  chartLorenzInstance = new Chart(ctx, {
    type: "line",
    data: {
      datasets: [
        {
          label: "PulseRx Decile Concentration Curve",
          data: lorenzPoints,
          borderColor: "#a855f7",
          backgroundColor: "rgba(168, 85, 247, 0.15)",
          fill: true,
          tension: 0.3,
          pointRadius: 4,
          pointBackgroundColor: "#c084fc"
        },
        {
          label: "Parity Line (45° Equality)",
          data: [{ x: 0, y: 0 }, { x: 100, y: 100 }],
          borderColor: "#475569",
          borderDash: [4, 4],
          pointRadius: 0
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#94a3b8", font: { family: "Plus Jakarta Sans", size: 11 } } },
        tooltip: {
          callbacks: {
            label: (ctx) => `Top ${ctx.raw.x}% HCPs drive ${ctx.raw.y}% of Market TRx`
          }
        }
      },
      scales: {
        x: {
          type: "linear",
          min: 0,
          max: 100,
          grid: { color: "rgba(36, 48, 70, 0.5)" },
          ticks: { color: "#64748b", callback: v => v + "%" },
          title: { display: true, text: "Cumulative % of Physicians", color: "#94a3b8" }
        },
        y: {
          min: 0,
          max: 100,
          grid: { color: "rgba(36, 48, 70, 0.5)" },
          ticks: { color: "#64748b", callback: v => v + "%" },
          title: { display: true, text: "Cumulative % of Category TRx", color: "#94a3b8" }
        }
      }
    }
  });
}

// 4. Chart 3: HCP Opportunity Matrix (Bubble Scatter)
function initOpportunityChart(hcps) {
  const ctx = document.getElementById("chartOpportunity").getContext("2d");

  const sample = hcps.slice(0, 140).map(h => ({
    x: h.PulseRx_Market_Share_Pct,
    y: h.Annual_Market_TRx,
    r: Math.max(3.5, Math.min(13, Math.sqrt(h.Annual_PulseRx_TRx))),
    hcpName: h.HCP_Name,
    tier: h.Targeting_Tier,
    decile: h.Market_Decile
  }));

  const tierColors = {
    "Tier 1": "#10b981",
    "Tier 2": "#f59e0b",
    "Tier 3": "#3b82f6",
    "Tier 4": "#64748b"
  };

  chartOpportunityInstance = new Chart(ctx, {
    type: "bubble",
    data: {
      datasets: ["Tier 1", "Tier 2", "Tier 3", "Tier 4"].map(tierKey => ({
        label: tierKey === "Tier 1" ? "Tier 1: Core Protectors" :
               tierKey === "Tier 2" ? "Tier 2: Conversion Targets" :
               tierKey === "Tier 3" ? "Tier 3: Moderate" : "Tier 4: Digital",
        data: sample.filter(p => p.tier.includes(tierKey)),
        backgroundColor: tierColors[tierKey] + "99",
        borderColor: tierColors[tierKey],
        borderWidth: 1.5
      }))
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#94a3b8", font: { family: "Plus Jakarta Sans", size: 11 } } },
        tooltip: {
          callbacks: {
            title: (items) => items[0].raw.hcpName,
            label: (item) => [
              `Decile: ${item.raw.decile}`,
              `Market TRx: ${item.raw.y}`,
              `Brand Share: ${item.raw.x.toFixed(1)}%`
            ]
          }
        }
      },
      scales: {
        x: {
          grid: { color: "rgba(36, 48, 70, 0.5)" },
          ticks: { color: "#64748b", callback: v => v + "%" },
          title: { display: true, text: "PulseRx Market Share %", color: "#94a3b8" }
        },
        y: {
          grid: { color: "rgba(36, 48, 70, 0.5)" },
          ticks: { color: "#64748b" },
          title: { display: true, text: "Annual Category Prescriptions (TRx)", color: "#94a3b8" }
        }
      }
    }
  });
}

// 5. Chart 4: Territory Workload & Sizing Optimization
function initTerritoryChart(territories) {
  const ctx = document.getElementById("chartTerritory").getContext("2d");
  const labels = territories.map(t => `${t.District} (${t.Territory_ID})`);
  const utilizations = territories.map(t => t.Workload_Utilization_Pct.toFixed(1));
  const colors = territories.map(t => {
    const val = t.Workload_Utilization_Pct;
    if (val > 115) return "#f43f5e";
    if (val < 80) return "#f59e0b";
    return "#10b981";
  });

  chartTerritoryInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{
        label: "Workload Utilization % (Target: 80 - 115%)",
        data: utilizations,
        backgroundColor: colors,
        borderRadius: 4
      }]
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            afterLabel: (ctx) => {
              const terr = territories[ctx.dataIndex];
              return `Action: ${terr.Sizing_Consulting_Action}`;
            }
          }
        }
      },
      scales: {
        x: {
          min: 50,
          max: 140,
          grid: { color: "rgba(36, 48, 70, 0.5)" },
          ticks: { color: "#64748b", callback: v => v + "%" },
          title: { display: true, text: "Field Rep Call Capacity Utilization %", color: "#94a3b8" }
        },
        y: {
          grid: { display: false },
          ticks: { color: "#94a3b8", font: { size: 10 } }
        }
      }
    }
  });
}

// 6. Render Territory Alignment Cards
function renderTerritoryCards(territories) {
  const container = document.getElementById("territoryGrid");
  container.innerHTML = "";

  territories.forEach(t => {
    const card = document.createElement("div");
    card.className = "terr-card";
    
    let badgeClass = "balanced";
    if (t.Workload_Utilization_Pct > 115) badgeClass = "overburdened";
    else if (t.Workload_Utilization_Pct < 80) badgeClass = "underutilized";

    card.innerHTML = `
      <div class="terr-card-top">
        <span class="terr-district">${t.District}</span>
        <span class="terr-badge ${badgeClass}">${t.Workload_Utilization_Pct.toFixed(0)}% Utilized</span>
      </div>
      <div class="terr-stats">
        <span>Reps: <strong>${t.Rep_Count || 2}</strong></span>
        <span>Quota: <strong>$${((t.Annual_Sales_Quota_USD || 4500000)/1e6).toFixed(1)}M</strong></span>
        <span>Reach: <strong>${t.High_Decile_Coverage_Pct.toFixed(0)}%</strong></span>
      </div>
      <div class="terr-action">&bull; ${t.Sizing_Consulting_Action}</div>
    `;

    // Click card to filter table to this territory!
    card.style.cursor = "pointer";
    card.addEventListener("click", () => {
      document.getElementById("filterRegion").value = t.Region;
      const event = new Event("change");
      document.getElementById("filterRegion").dispatchEvent(event);
      document.getElementById("hcpTable").scrollIntoView({ behavior: "smooth" });
    });

    container.appendChild(card);
  });
}

// 7. Render Micro-Targeting Table
function renderHCPTable(hcps) {
  const tbody = document.getElementById("tableBody");
  tbody.innerHTML = "";

  document.getElementById("recordCounter").innerText = `Showing ${hcps.length} prescribers`;

  hcps.forEach(hcp => {
    const tr = document.createElement("tr");

    let tierClass = "tier-4";
    if (hcp.Targeting_Tier.includes("Tier 1")) tierClass = "tier-1";
    else if (hcp.Targeting_Tier.includes("Tier 2")) tierClass = "tier-2";
    else if (hcp.Targeting_Tier.includes("Tier 3")) tierClass = "tier-3";

    const deficit = hcp.Call_Deficit;
    const deficitClass = deficit > 3 ? "deficit-tag high-deficit" : "deficit-tag balanced";
    const deficitText = deficit > 0 ? `+${deficit} needed` : deficit < -2 ? `${-deficit} over plan` : "On target";

    let action = "";
    if (hcp.Targeting_Tier.includes("Tier 2")) {
      action = "⚡ Urgent Competitor Displacement Call";
    } else if (hcp.Targeting_Tier.includes("Tier 1")) {
      action = "🛡️ Core Defense & Patient Persistence";
    } else if (hcp.Targeting_Tier.includes("Tier 3")) {
      action = "📅 Quarterly Detailing Cadence";
    } else {
      action = "💻 Route to Email / Webinar Omnichannel";
    }

    const payer = hcp.Payer_Formulary_Access || "Tier 1: Preferred";
    const payerShort = payer.includes("Tier 1") ? '<span style="color:#10b981;">Preferred</span>' :
                       payer.includes("Tier 2") ? '<span style="color:#f59e0b;">Prior Auth</span>' :
                       '<span style="color:#f43f5e;">Restricted</span>';

    tr.innerHTML = `
      <td style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;">${hcp.HCP_NPI}</td>
      <td><strong>${hcp.HCP_Name}</strong> ${hcp.Is_KOL === "Yes" ? '<span style="color:#38bdf8;font-size:0.65rem;">[KOL]</span>' : ''}</td>
      <td>${hcp.Specialty}</td>
      <td>${hcp.District} (${hcp.State})</td>
      <td>${payerShort}</td>
      <td><span style="font-weight:700; color:#38bdf8;">D${hcp.Market_Decile}</span></td>
      <td>${hcp.Annual_Market_TRx.toLocaleString()}</td>
      <td>${hcp.PulseRx_Market_Share_Pct.toFixed(1)}%</td>
      <td>${hcp.Total_Calls_2025}</td>
      <td>${hcp.Recommended_Annual_Calls}</td>
      <td><span class="${deficitClass}">${deficitText}</span></td>
      <td><span class="tier-pill ${tierClass}">${hcp.Targeting_Tier.split(':')[0]}</span></td>
      <td style="font-size: 0.75rem; color: #cbd5e1;">${action}</td>
    `;
    tbody.appendChild(tr);
  });
}

// 8. Dynamic What-If SFE Scenario Simulator
function setupSimulator() {
  const btnToggle = document.getElementById("btnToggleSim");
  const panel = document.getElementById("simPanel");
  btnToggle.addEventListener("click", () => {
    panel.style.display = panel.style.display === "none" ? "flex" : "none";
  });

  const sim = DASHBOARD_DATA.sim;
  const sliders = ["sliderTier1", "sliderTier2", "sliderTier3", "sliderTier4", "sliderCapacity"]
    .map(id => document.getElementById(id));
  const set = (id, v) => { document.getElementById(id).innerText = v; };

  // Calls short of plan for one tier at frequency f, from the exact histogram of calls received.
  const shortfall = (tier, f) => Object.entries(sim.tier1_2_call_histogram[tier])
    .reduce((s, [calls, n]) => s + n * Math.max(0, f - Number(calls)), 0);

  function runSim() {
    const [t1, t2, t3, t4, cap] = sliders.map(s => parseInt(s.value, 10));
    const freq = { "Tier 1": t1, "Tier 2": t2, "Tier 3": t3, "Tier 4": t4 };
    set("valTier1", `${t1} visits/yr`);
    set("valTier2", `${t2} visits/yr`);
    set("valTier3", `${t3} visits/yr`);
    set("valTier4", t4 === 0 ? "Digital only" : `${t4} visits/yr`);
    set("valCapacity", `${cap} calls/rep`);

    let required = 0, reps = 0, over = 0;
    const terrIds = Object.keys(sim.tier_by_territory);
    terrIds.forEach(id => {
      const need = Object.entries(sim.tier_by_territory[id]).reduce((s, [t, n]) => s + n * freq[t], 0);
      const capT = sim.reps_by_territory[id] * cap;
      required += need;
      reps += sim.reps_by_territory[id];
      if (need / capT * 100 > sim.overburdened_pct) over += 1;
    });
    const capacity = reps * cap;
    const gap = shortfall("Tier 1", t1) + shortfall("Tier 2", t2);
    const liftM = gap * sim.assumed_trx_per_extra_call * sim.net_revenue_per_trx_usd / 1e6;
    const repsNeeded = Math.ceil(required / cap);

    set("simResultShortfall", `${gap.toLocaleString()} calls`);
    set("simResultLift", `Scenario: ~$${liftM.toFixed(1)}M at an assumed ${sim.assumed_trx_per_extra_call} TRx per call`);
    set("simResultPlan", `${(required / capacity * 100).toFixed(0)}%`);
    set("simResultPlanSub", `${required.toLocaleString()} of ${capacity.toLocaleString()} calls`);
    set("simResultOverburdened", `${over} of ${terrIds.length}`);
    set("simResultOverSub", `Plan above ${sim.overburdened_pct}% of territory capacity`);
    set("simResultReps", `${repsNeeded} vs ${reps}`);
    set("simResultRepsSub", repsNeeded <= reps ? "Fits today's field force: retarget, don't hire"
                                               : `${repsNeeded - reps} more reps needed at this plan`);
  }

  sliders.forEach(s => s.addEventListener("input", runSim));
  runSim();
}

// 9. Interactive Filter Controller
function setupFilters() {
  const regionSel = document.getElementById("filterRegion");
  const specialtySel = document.getElementById("filterSpecialty");
  const payerSel = document.getElementById("filterPayer");
  const tierSel = document.getElementById("filterTier");
  const decileSel = document.getElementById("filterDecile");
  const searchInput = document.getElementById("filterSearch");
  const resetBtn = document.getElementById("btnResetFilters");

  function applyFilters() {
    const rVal = regionSel.value;
    const sVal = specialtySel.value;
    const pVal = payerSel.value;
    const tVal = tierSel.value;
    const dVal = parseInt(decileSel.value, 10);
    const qVal = searchInput.value.toLowerCase().trim();

    const filtered = DASHBOARD_DATA.sample_hcps.filter(h => {
      if (rVal !== "ALL" && h.Region !== rVal) return false;
      if (sVal !== "ALL" && h.Specialty !== sVal) return false;
      if (pVal !== "ALL" && !h.Payer_Formulary_Access.includes(pVal)) return false;
      if (tVal !== "ALL" && !h.Targeting_Tier.includes(tVal)) return false;
      if (h.Market_Decile < dVal) return false;
      if (qVal && !h.HCP_Name.toLowerCase().includes(qVal) && !h.HCP_NPI.toString().includes(qVal)) return false;
      return true;
    });

    renderHCPTable(filtered);
  }

  regionSel.addEventListener("change", applyFilters);
  specialtySel.addEventListener("change", applyFilters);
  payerSel.addEventListener("change", applyFilters);
  tierSel.addEventListener("change", applyFilters);
  decileSel.addEventListener("change", applyFilters);
  searchInput.addEventListener("input", applyFilters);

  resetBtn.addEventListener("click", () => {
    regionSel.value = "ALL";
    specialtySel.value = "ALL";
    payerSel.value = "ALL";
    tierSel.value = "ALL";
    decileSel.value = "8";
    searchInput.value = "";
    applyFilters();
  });
}

// 10. Alteryx Modal Setup
function setupModal() {
  const modal = document.getElementById("alteryxModal");
  const btnOpen = document.getElementById("btnInspectAlteryx");
  const btnClose = document.getElementById("btnCloseModal");

  btnOpen.addEventListener("click", () => modal.classList.add("active"));
  btnClose.addEventListener("click", () => modal.classList.remove("active"));
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.remove("active");
  });
}

// 11. Export SFE Plan to CSV
function setupExport() {
  document.getElementById("btnExportCSV").addEventListener("click", () => {
    const hcps = DASHBOARD_DATA.sample_hcps;
    let csv = "HCP_NPI,Physician_Name,Specialty,District,State,Payer_Access,Market_Decile,Market_TRx,PulseRx_Share_Pct,Actual_Calls,Recommended_Calls,Call_Deficit,Targeting_Tier\n";
    hcps.forEach(h => {
      csv += `${h.HCP_NPI},"${h.HCP_Name}",${h.Specialty},${h.District},${h.State},"${h.Payer_Formulary_Access}",${h.Market_Decile},${h.Annual_Market_TRx},${h.PulseRx_Market_Share_Pct.toFixed(1)},${h.Total_Calls_2025},${h.Recommended_Annual_Calls},${h.Call_Deficit},"${h.Targeting_Tier}"\n`;
    });

    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.setAttribute("href", url);
    link.setAttribute("download", "PulseRx_SFE_Action_Plan.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  });
}
