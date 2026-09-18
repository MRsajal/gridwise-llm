const state = {
  apiBase: localStorage.getItem("gridwiseApi") || window.location.origin,
  lastResult: null
};
const demoHours = [
  [0,3.8,0.0,11.5],[1,3.5,0.0,11.2],[2,3.3,0.0,10.9],[3,3.2,0.0,10.7],
  [4,3.3,0.0,10.8],[5,3.7,0.2,11.0],[6,4.5,0.9,11.8],[7,5.3,2.1,12.6],
  [8,5.8,3.4,13.4],[9,5.9,4.8,13.8],[10,6.0,5.7,14.1],[11,6.2,6.1,14.5],
  [12,6.5,6.4,15.0],[13,6.7,6.2,15.2],[14,6.5,5.6,15.0],[15,6.1,4.8,14.4],
  [16,6.0,3.5,13.9],[17,6.3,2.0,14.8],[18,6.8,0.7,16.2],[19,7.2,0.1,17.4],
  [20,7.8,0.0,17.8],[21,7.1,0.0,16.5],[22,5.8,0.0,14.2],[23,4.7,0.0,12.6]
];

const $ = id => document.getElementById(id);
const money = n => "৳ " + Number(n).toLocaleString("en-BD",{maximumFractionDigits:2});
const num = (n,d=2) => Number(n).toFixed(d);

function toast(msg){ const el=$("toast"); el.textContent=msg; el.classList.add("show"); setTimeout(()=>el.classList.remove("show"),2800); }

function renderInputRows(){
  $("inputRows").innerHTML = demoHours.map((r,i)=>`
    <tr>
      <td>${String(r[0]).padStart(2,"0")}</td>
      <td><input class="hour-demand" data-i="${i}" type="number" min="0" step="0.1" value="${r[1]}"></td>
      <td><input class="hour-solar" data-i="${i}" type="number" min="0" step="0.1" value="${r[2]}"></td>
      <td><input class="hour-tariff" data-i="${i}" type="number" min="0" step="0.1" value="${r[3]}"></td>
    </tr>`).join("");
}
function getHours(){
  return demoHours.map((r,i)=>({
    hour:r[0],
    demand_kwh:Number(document.querySelector(`.hour-demand[data-i="${i}"]`).value),
    solar_kwh:Number(document.querySelector(`.hour-solar[data-i="${i}"]`).value),
    tariff_bdt_per_kwh:Number(document.querySelector(`.hour-tariff[data-i="${i}"]`).value)
  }));
}
function requestBody(){
  const notes=$("notes").value.split(/\n+/).map(x=>x.trim()).filter(Boolean).slice(0,3);
  return {
    scenario_id:$("scenarioId").value.trim() || "judge-demo-01",
    operator_notes:notes.length ? notes : ["Optimize the daily energy schedule."],
    hours:getHours(),
    battery:{
      capacity_kwh:Number($("capacity").value),
      initial_energy_kwh:Number($("initial").value),
      minimum_energy_kwh:Number($("minimum").value),
      max_charge_kwh_per_hour:Number($("maxCharge").value),
      max_discharge_kwh_per_hour:Number($("maxDischarge").value)
    }
  };
}

function renderDemo(){
  // A visually representative client-side demo when the API is not running.
  const h=getHours(), cap=Number($("capacity").value)||12, initial=Number($("initial").value)||7;
  let energy=initial, totalGrid=0,totalCost=0,peak=0;
  const plan=h.map(x=>{
    const solar=Math.min(x.solar_kwh,x.demand_kwh);
    let grid=Math.max(0,x.demand_kwh-solar), action="idle", delta=0;
    if(x.tariff_bdt_per_kwh>=16 && energy>Number($("minimum").value)+.1){delta=-Math.min(1.6,energy-Number($("minimum").value),grid);action=delta<0?"discharge":"idle";}
    else if(x.tariff_bdt_per_kwh<=11.5 && energy<cap-.1){delta=Math.min(1.4,cap-energy);action=delta>0?"charge":"idle";}
    energy=Math.max(0,Math.min(cap,energy+delta)); grid=Math.max(0,grid+delta);
    totalGrid+=grid; totalCost+=grid*x.tariff_bdt_per_kwh; peak=Math.max(peak,grid);
    return {hour:x.hour,grid_kwh:grid,solar_used_kwh:solar,battery_action:action,battery_kwh:Math.abs(delta),battery_energy_after_kwh:energy};
  });
  return {
    scenario_id:$("scenarioId").value || "judge-demo-01",
    directive_interpretation:[
      {note_index:0,applies:true,directive_type:"solar_reduction",explanation:"Solar availability reduced for the requested midday window."},
      {note_index:1,applies:true,directive_type:"minimum_battery_reserve",explanation:"A minimum evening battery reserve is maintained."},
      {note_index:2,applies:true,directive_type:"no_charge_window",explanation:"Charging is disabled during the specified evening window."}
    ],
    hourly_plan:plan,total_grid_kwh:totalGrid,total_cost_bdt:totalCost,peak_grid_kwh:peak,
    plan_summary:"Applied the validated operator directives, used available solar, and shifted battery energy toward lower-cost periods while preserving the configured reserve and battery limits."
  };
}

async function optimize() {
  $("optimizeBtn").disabled = true;
  $("optimizeBtn").innerHTML = "Optimizing…";
  $("resultStatus").textContent =
    "Interpreting directives and calculating the schedule…";

  try {
    const res = await fetch(
      state.apiBase.replace(/\/$/, "") + "/optimize-energy",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(requestBody())
      }
    );

    const data = await res.json();

    if (!res.ok) {
      throw new Error(
        data.message ||
        data.error ||
        `API request failed with status ${res.status}`
      );
    }

    state.lastResult = data;

    renderResult(
      data,
      "Live API"
    );

    toast(
      "Optimization completed successfully."
    );

  } catch (error) {

    console.error(error);

    $("resultStatus").textContent =
      "Optimization failed: " + error.message;

    toast(
      "Optimization failed. Check the API/server."
    );

  } finally {

    $("optimizeBtn").disabled = false;

    $("optimizeBtn").innerHTML =
      "Optimize Energy Plan <span>→</span>";
  }
}

function renderResult(data,mode){
  $("resultStatus").textContent=`${mode} · validated schedule generated for ${data.scenario_id}`;
  $("totalGrid").textContent=num(data.total_grid_kwh)+" kWh";
  $("totalCost").textContent=money(data.total_cost_bdt);
  $("peakGrid").textContent=num(data.peak_grid_kwh)+" kWh";
  $("resultScenario").textContent=data.scenario_id;
  $("heroGrid").textContent=num(data.total_grid_kwh,1); $("heroCost").textContent=money(data.total_cost_bdt); $("heroPeak").textContent=num(data.peak_grid_kwh,1);
  $("planSummary").textContent=data.plan_summary;
  $("outputRows").innerHTML=data.hourly_plan.map(x=>`<tr><td>${String(x.hour).padStart(2,"0")}</td><td>${num(x.grid_kwh)}</td><td>${num(x.solar_used_kwh)}</td><td class="action-${x.battery_action}">${x.battery_action}</td><td>${x.battery_kwh>0?(x.battery_action==="charge"?"+":"−")+num(x.battery_kwh):"—"}</td><td>${num(x.battery_energy_after_kwh)}</td></tr>`).join("");
  $("directives").innerHTML=(data.directive_interpretation||[]).map(d=>`<div class="directive ${d.applies?"":"off"}"><b>${d.applies?"Applied":"Not applied"} · ${d.directive_type.replaceAll("_"," ")}</b><span>${d.explanation||"No explanation supplied."}</span></div>`).join("") || `<div class="directive"><b>No directives</b><span>The optimizer used the base scenario constraints.</span></div>`;
  drawChart(data.hourly_plan);
  renderHeroBars(data.hourly_plan);
}

function drawChart(plan){
  const svg=$("energyChart"), W=900,H=300,pad=26;
  const max=Math.max(...plan.map(x=>Math.max(x.grid_kwh,x.solar_used_kwh)),1)*1.18;
  const x=i=>pad+i*(W-2*pad)/23, y=v=>H-pad-v/max*(H-2*pad);
  let gridPath="",solarPath="";
  plan.forEach((p,i)=>{gridPath+=(i?"L":"M")+x(i).toFixed(1)+" "+y(p.grid_kwh).toFixed(1)+" ";solarPath+=(i?"L":"M")+x(i).toFixed(1)+" "+y(p.solar_used_kwh).toFixed(1)+" ";});
  let marks="";
  [0,.25,.5,.75,1].forEach(v=>{const yy=y(max*v);marks+=`<line x1="${pad}" y1="${yy}" x2="${W-pad}" y2="${yy}" stroke="#eadfd3" stroke-width="1"/><text x="0" y="${yy+4}" font-size="10" fill="#a08c7f">${(max*v).toFixed(1)}</text>`});
  svg.innerHTML=`${marks}<path d="${solarPath}" fill="none" stroke="#9e8b67" stroke-width="3"/><path d="${gridPath}" fill="none" stroke="#a96f50" stroke-width="3"/><circle cx="${x(23)}" cy="${y(plan[23].grid_kwh)}" r="4" fill="#a96f50"/><circle cx="${x(23)}" cy="${y(plan[23].solar_used_kwh)}" r="4" fill="#9e8b67"/>`;
}
function renderHeroBars(plan){
  const vals=plan.map(x=>x.grid_kwh), mx=Math.max(...vals,1);
  $("heroBars").innerHTML=vals.map(v=>`<i style="height:${Math.max(8,v/mx*100)}%"></i>`).join("");
}

async function checkHealth(){
  try{const r=await fetch(state.apiBase.replace(/\/$/,"")+"/health"); if(!r.ok) throw 0; toast("API is healthy and reachable.");}
  catch{toast("Could not reach the API. Demo mode is still available.");}
}
function editApi(){
  const next=prompt("FastAPI base URL:",state.apiBase);
  if(next){state.apiBase=next.trim().replace(/\/$/,"");localStorage.setItem("gridwiseApi",state.apiBase);$("apiLabel").textContent=state.apiBase;toast("API URL updated.");}
}
function loadDemo(){
  $("scenarioId").value="judge-demo-01";
  $("notes").value="Reduce solar availability by 20% during hours 12-15.\nKeep at least 4 kWh in the battery during evening hours 18-22.\nAvoid battery charging between hours 18-20.";
  renderInputRows(); renderResult(renderDemo(),"Demo mode"); document.querySelector("#results").scrollIntoView({behavior:"smooth"}); toast("Demo scenario loaded.");
}
$("optimizeBtn").addEventListener("click",optimize); $("healthBtn").addEventListener("click",checkHealth); $("apiEdit").addEventListener("click",editApi); $("demoBtn").addEventListener("click",loadDemo);
$("exportBtn").addEventListener("click",()=>{if(!state.lastResult)return toast("Run the optimizer first."); const blob=new Blob([JSON.stringify(state.lastResult,null,2)],{type:"application/json"}); const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="gridwise-optimization-result.json";a.click();URL.revokeObjectURL(a.href);});
$("apiLabel").textContent=state.apiBase; renderInputRows(); renderHeroBars(demoHours.map(x=>({grid_kwh:x[1],solar_used_kwh:x[2]})));
