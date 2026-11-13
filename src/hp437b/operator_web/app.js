"use strict";
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="operator-token"]').content;
let model = {profiles:[],jobs:[],active_id:null}, selectedProfile = null, busy = false, initialized = false;
let stepsSignature="", historySignature="", inflight=null, generation=0;
const setText=(id,value)=>{if($(id).textContent!==value)$(id).textContent=value;};
const titles = {"GUIDED":"Operator-guided sweep","WF-01":"POWER REF baseline and output","WF-02":"Sustained output stability","WF-03":"Transmission-cycle repeatability","WF-04":"Output versus setting","WF-05":"Output versus frequency","WF-06":"Supply-voltage sensitivity"};
const node = (tag, text, cls) => {const element=document.createElement(tag);if(text!==undefined)element.textContent=text;if(cls)element.className=cls;return element;};
function error(message) {$("error").textContent=message||"";$("error").hidden=!message;if(message)$("error").focus();}
async function api(path, data) {
  const response = await fetch(path,{method:data===undefined?"GET":"POST",credentials:"same-origin",headers:{"X-Operator-Token":token,...(data===undefined?{}:{"Content-Type":"application/json"})},...(data===undefined?{}:{body:JSON.stringify(data)})});
  const result=await response.json();if(!response.ok)throw new Error(result.error||"The local operator request failed.");return result;
}
const preparation = {adapter_on_mac:"Adapter USB is on this Mac",direct_sensor_reference_path:"Sensor cable is on SENSOR; sensor RF input is directly on POWER REF",reference_off:"POWER REF is off",warmed_up:"Meter and sensor are warmed up",other_apps_closed:"Other control applications are closed",operator_available:"I am at the meter and can use PRESET/LOCAL for recovery"};
let confirmationJob=null, hydratedGuided=null;
function guidedMode(){return $("mode").value==="guided";}
function physicalMode(){return $("mode").value==="physical";}
function preparedValues(){return Object.fromEntries([...document.querySelectorAll('#prepared input')].map(input=>[input.value,input.checked]));}
function modeChanged(reset=true){
 const physical=physicalMode(), guided=guidedMode();$("guided-setup").hidden=!guided;$("fake-setup").hidden=guided||physical;$("fake-tests").hidden=guided||physical;
 if(guided){$("page-title").textContent="Measure a manual sweep";$("intro-text").textContent="Set the radio, confirm each point, and capture measured power.";$("reference-setup").hidden=true;$("environment").textContent=$("guided-meter").value==="physical"?"Operator-guided · bench meter":"Operator-guided · simulated meter";$("scope").textContent="One confirmed point at a time. Original measurements stay with the report.";$("mode-note").textContent="Choose frequency, drive setting, or a combined series.";guidedPlanChanged();selectionChanged();return;}
 $("page-title").textContent=physical?"Measure POWER REF":"Run an RF test suite";$("intro-text").textContent=physical?"Exercise the current meter and sensor with its internal reference.":"Choose a DUT profile and tests. Collect a traceable report.";$("fake-setup").hidden=physical;$("fake-tests").hidden=physical;$("reference-setup").hidden=!physical;
 if(reset)for(const input of document.querySelectorAll('#prepared input'))input.checked=false;
 $("environment").textContent=physical?"POWER REF · current meter":"Simulation · local session";
 $("scope").textContent=physical?"Measure the internal reference with one prepared workflow per run.":"Simulated measurements are explicitly marked in the report.";
 $("mode-note").textContent=model.reference?"POWER REF uses the configured meter path; every run needs fresh confirmation.":"POWER REF must be explicitly enabled when launching this service.";
 selectionChanged();
}
for(const [key,labelText] of Object.entries(preparation)){const label=node("label",undefined,"test-option"),input=node("input");input.type="checkbox";input.value=key;input.addEventListener("change",selectionChanged);label.append(input,node("span",labelText));$("prepared").append(label);}
function canStart(){if(guidedMode())return !model.active_id&&!model.pending_reference&&!busy&&guidedValid()&&($("guided-meter").value!=="physical"||(Boolean(model.guided?.meter)&&Object.values(guidedPrepared()).every(Boolean)));return !model.active_id&&!model.pending_reference&&!busy&&(physicalMode()?Boolean(model.reference)&&Object.values(preparedValues()).every(Boolean):chosen().length>0&&Boolean(selectedProfile));}
function chosen() {if(guidedMode())return ["GUIDED"];if(physicalMode())return [$("reference-workflow").value];return [...document.querySelectorAll('#test-options input:checked')].map(input=>input.value);}
function profileChanged() {
  selectedProfile=model.profiles.find(profile=>profile.key===$("profile").value);
  $("test-options").replaceChildren();
  if(!selectedProfile)return;
  $("profile-description").textContent=selectedProfile.name+". "+selectedProfile.description;
  $("operator").value=selectedProfile.operator||"";
  for(const test of selectedProfile.workflows){
    const label=node("label",undefined,"test-option"), input=node("input");input.type="checkbox";input.value=test.id;input.checked=true;input.addEventListener("change",selectionChanged);
    const text=node("span");text.append(node("strong",test.label),node("small",`${test.id} · ${test.points} points`));label.append(input,text);$("test-options").append(label);
  }
  selectionChanged();
}
function selectionChanged() {
  const count=chosen().length;
  $("selection-note").hidden=guidedMode();
  $("selection-note").textContent=physicalMode()?"One workflow per run. Confirm the setup again before each start.":count?`${count} ${count===1?"test":"tests"} selected. Runs in the order shown.`:"Select at least one test.";
  $("start").disabled=!canStart();
  if(!model.active_id)$("start").textContent=guidedMode()?"Start guided sweep":physicalMode()?"Start POWER REF workflow":"Start suite";
  if(!model.jobs.length)renderRun(null);
}
function formatResult(row) {
  if(!row)return "";
  const parts=[`${row.completed_points}/${row.requested_points} points`,row.acceptance];
  return parts.join(" · ");
}
function renderRun(job) {
  if(job?.mode==="guided"||(!job&&guidedMode())){renderGuided(job);return;}
  $("guided-controls").hidden=true;$("boundary-text").parentElement.hidden=false;
  $("guided-point").hidden=true;$("guided-results").hidden=true;$("html-report").hidden=true;
  const active=Boolean(model.active_id), selected=job?.workflows||chosen();
  const physical=job?job.mode==="physical":physicalMode();
  const phase=job?.phase||"ready", results=job?.results||[], completed=results.filter(row=>row.execution==="completed").length;
  const stateLabels={ready:"Ready",starting:"Starting",running:"Running",reporting:"Preparing reports",finished:"Finished",failed:"Needs attention"};
  $("run-title").textContent=job&&!active?"Latest suite":"Suite progress";
  $("run-state").textContent=stateLabels[phase]||phase;$("run-state").className="state "+phase;
  let headline="No test is running", description="Start a suite when your selection is ready.";
  if(job){
    if(phase==="starting"){headline="Starting the suite";description=`${job.profile_name}. No further action is needed.`;}
    if(phase==="running"){headline=job.current?`${titles[job.current]} is running`:"At a test boundary";description=physical?`${job.profile_name}. Stage: ${job.stage||"preflight / capture"}. Progress is recorded at stage boundaries.`:`${job.profile_name}. Progress updates as each test starts and finishes.`;}
    if(phase==="reporting"){headline="Capture finished. Preparing reports.";description="Native results are saved. Creating the PDF and portable package.";}
    if(phase==="finished"){
      headline=job.outcome==="interrupted"?"Suite cancelled":job.outcome==="failed"?"Suite stopped":"Suite complete";
      description=`${job.profile_name}. ${completed}/${selected.length} tests complete. ${job.acceptance==="NOT EVALUATED"?"No complete acceptance decision; see the report for supplied limits and coverage.":"Acceptance: "+job.acceptance+"."}`;
      if(job.cancel_requested&&job.outcome==="completed")description+=" All tests finished before cancellation could take effect.";
    }
    if(phase==="failed"){headline="The run needs attention";description=job.error||"The worker did not finish. Captured evidence is retained.";}
  }
  setText("run-headline",headline);setText("run-description",description);
  $("progress-label").textContent=job?"Workflow completion":"Selected tests";$("progress-count").textContent=`${completed} / ${selected.length}`;
  $("progress").max=Math.max(selected.length,1);$("progress").value=completed;
  const nextSteps=JSON.stringify({selected,phase,results,current:job?.current,physical});
  if(nextSteps!==stepsSignature){
  stepsSignature=nextSteps;$("steps").replaceChildren();
  for(const kind of selected){
    const row=results.find(item=>item.workflow===kind), current=job?.current===kind&&phase==="running", unfinished=job?.current===kind&&phase==="failed";
    const item=node("li",undefined,"step"+(current?" current":"")+(row?.execution==="failed"?" failed":""));
    let status=current?"Running":unfinished?"Unfinished":row?row.execution==="completed"?"Complete":row.execution==="interrupted"?"Interrupted":"Stopped":job&&["finished","failed","reporting"].includes(phase)?"Not run":"Waiting";
    const text=node("div");text.append(node("div",titles[kind],"step-name"));if(row)text.append(node("div",physical?row.acceptance:formatResult(row),"step-result"));
    item.append(node("span",kind,"step-code"),text,node("span",status,"step-status"));$("steps").append(item);
  }
  }
  const pending=Boolean(job?.cancel_requested&&active&&["starting","running"].includes(phase));
  $("boundary-text").parentElement.classList.toggle("pending",pending);
  let boundary="The current test finishes and verifies RF off and supply restoration before cancellation takes effect. Later tests do not start.";
  if(job?.current){const next=selected[selected.indexOf(job.current)+1];boundary=`${pending?"Cancellation requested. ":""}${job.current} finishes and verifies RF off and restoration first. ${next?"The stop boundary is before "+next+".":"This is the final selected test."}`;}
  else if(pending)boundary="Cancellation requested. The worker will stop at the next test boundary. A test already in progress still finishes its cleanup first.";
  if(physical)boundary=`${pending?"Cancellation requested. ":""}The current capture stage finishes before cancellation is checked. WF-02's plateau can take 30 minutes. Existing healthy source-off cleanup then runs; uncertain I/O requires manual recovery. This is not an immediate RF-off control.`;
  $("boundary-text").textContent=boundary;
  $("cancel").disabled=!job?.active||!["starting","running"].includes(phase)||job.cancel_requested;
  $("cancel").textContent=pending?"Cancellation requested":"Request cancellation";
  $("pdf").hidden=!job?.pdf_ready;$("package").hidden=!job?.package_ready;
  if(job){$("pdf").href=`/artifacts/${job.job_id}/report.pdf`;$("package").href=`/artifacts/${job.job_id}/package.zip`;}
  $("report-note").textContent=job?.pdf_ready?"Open the one-page answer, or download reports and original evidence together.":"PDF and portable package appear after capture and reporting finish.";
  $("mode").disabled=active;$("reference-workflow").disabled=active;for(const input of document.querySelectorAll("#prepared input"))input.disabled=active;
  $("front-panel").hidden=job?.mode!=="physical"||job?.active||!["finished","failed"].includes(phase);
  if(confirmationJob!==job?.job_id){confirmationJob=job?.job_id;$("front-panel-check").checked=false;}
  $("front-panel-save").disabled=!physical||job?.active||job?.front_panel_confirmed||!$("front-panel-check").checked;
  $("front-panel-result").textContent=job?.front_panel_confirmed?"Separate operator confirmation recorded. Native capture remains unchanged.":"A new POWER REF run requires this confirmation.";
  $("front-panel-check").disabled=Boolean(job?.front_panel_confirmed);
  $("profile").disabled=active;$("operator").disabled=active;$("import").disabled=active;
  for(const input of document.querySelectorAll('#test-options input'))input.disabled=active;
  $("start").textContent=active?"Run in progress…":physicalMode()?"Start POWER REF workflow":"Start suite";$("start").disabled=!canStart();
}
function renderHistory() {
  const past=model.jobs.filter(job=>job.phase==="finished"||job.phase==="failed").slice(0,5);$("history").hidden=!past.length;
  const signature=JSON.stringify(past.map(job=>[job.job_id,job.phase,job.outcome,job.pdf_ready]));if(signature===historySignature)return;historySignature=signature;$("history-body").replaceChildren();
  for(const job of past){
    const tr=node("tr");tr.append(node("td",job.profile_name),node("td",new Date(job.started_utc).toLocaleString()),node("td",job.phase==="failed"?(job.outcome?"Report error":"Run error"):job.outcome==="interrupted"?"Cancelled":job.outcome==="failed"?"Stopped":"Complete"));
    const cell=node("td");if(job.pdf_ready){const link=node("a","Open PDF");link.href=`/artifacts/${job.job_id}/report.pdf`;link.target="_blank";link.rel="noopener";cell.append(link);}else cell.textContent="Not available";
    tr.append(cell);$("history-body").append(tr);
  }
}
async function refresh(force=false) {
  if(inflight){if(!force)return inflight;await inflight;}
  const observed=generation;
  const task=(async()=>{
  try{
    const latest=await api("/api/state");if(observed!==generation)return;model=latest;$("connection").hidden=true;
    $("mode").querySelector('option[value="physical"]').disabled=!model.reference;
    if(model.reference){$("reference-identity").textContent=`Meter ${model.reference.meter_serial}; sensor ${model.reference.sensor_serial}. ${model.reference.resource}`;$("reference-issues").textContent="Known issues: "+(model.reference.known_issues.join("; ")||"None reported");}
    $("guided-meter").querySelector('option[value="physical"]').disabled=!model.guided?.meter;
    $("guided-meter-note").textContent=model.guided?.meter?`Meter ${model.guided.meter.meter_serial}; sensor ${model.guided.meter.sensor_serial}. ${model.guided.meter.fixture}${model.guided.meter.signal_source==="power_ref"?" POWER REF repeats only: start with reference off; switch it on before capture and off after finishing or stopping.":""}`:"Configure the bench meter at service launch to enable measured captures.";
    const previous=$("profile").value;
    if(!initialized||[...$("profile").options].map(option=>option.value).join()!==model.profiles.map(profile=>profile.key).join()){
      $("profile").replaceChildren(...model.profiles.map(profile=>{const option=node("option",`${profile.profile_id} · r${profile.revision}`);option.value=profile.key;return option;}));
      if(model.profiles.some(profile=>profile.key===previous))$("profile").value=previous;
      profileChanged();initialized=true;
    }
    $("issues-list").replaceChildren(...model.profile_issues.map(issue=>node("li",issue)));$("profile-issues").hidden=!model.profile_issues.length;
    const activeGuided=model.jobs.find(job=>job.job_id===model.active_id&&job.mode==="guided");
    if(activeGuided&&hydratedGuided!==activeGuided.job_id){const p=activeGuided.sweep_plan;hydratedGuided=activeGuided.job_id;$("mode").value="guided";for(const [id,value] of Object.entries({"guided-name":p.name,"guided-series":p.series,"guided-frequencies":p.frequencies.join(", "),"guided-drives":p.drives.join(", "),"guided-order":p.order,"guided-samples":p.samples,"guided-interval":p.interval_s,"guided-settling":p.settling_s,"guided-notes":p.measurement_notes,"guided-meter":activeGuided.meter_mode,"operator":activeGuided.operator||""}))$(id).value=value;}
    modeChanged(false);renderRun(model.jobs.find(job=>job.job_id===model.active_id)||model.jobs.find(job=>job.job_id===model.pending_reference)||model.jobs[0]||null);renderHistory();
  }catch(exc){$("connection").textContent="Connection to the local operator service was lost. Existing worker runs are not restarted. Reload this page to reconnect and view their status.";$("connection").hidden=false;$("start").disabled=true;$("cancel").disabled=true;$("guided-capture").disabled=true;$("guided-stop").disabled=true;}
  })();inflight=task;try{await task;}finally{if(inflight===task)inflight=null;}
}
$("profile").addEventListener("change",profileChanged);
$("run-form").addEventListener("submit",async event=>{event.preventDefault();if(busy||model.active_id)return;busy=true;generation++;error("");$("start").disabled=true;try{const job=guidedMode()?await api("/api/guided",{plan:guidedPlan(),operator:$("operator").value.trim()||null,meter_mode:$("guided-meter").value,prepared:$("guided-meter").value==="physical"?guidedPrepared():{}}):physicalMode()?await api("/api/reference",{workflow:$("reference-workflow").value,operator:$("operator").value.trim()||null,prepared:preparedValues()}):await api("/api/jobs",{profile_key:$("profile").value,workflows:chosen(),operator:$("operator").value.trim()||null});for(const input of document.querySelectorAll("#prepared input,#guided-prepared input"))input.checked=false;model.active_id=job.job_id;model.jobs=[job,...model.jobs.filter(item=>item.job_id!==job.job_id)];renderRun(job);await refresh(true);}catch(exc){error(exc.message);}finally{busy=false;selectionChanged();}});
$("cancel").addEventListener("click",async()=>{if(!model.active_id)return;generation++;$("cancel").disabled=true;error("");try{await api("/api/cancel",{job_id:model.active_id});await refresh(true);}catch(exc){error(exc.message);await refresh();}});
$("import").addEventListener("click",()=>$("profile-file").click());
$("profile-file").addEventListener("change",async()=>{const file=$("profile-file").files[0];if(!file)return;generation++;error("");try{if(file.size>256*1024)throw new Error("Profile exceeds 256 KiB.");const raw=await file.text();const imported=await api("/api/profiles",{profile_json:raw});await refresh(true);$("profile").value=imported.key;profileChanged();}catch(exc){error("Profile was not imported: "+exc.message);}finally{$("profile-file").value="";}});
$("mode").addEventListener("change",()=>modeChanged());
$("reference-workflow").addEventListener("change",selectionChanged);
$("front-panel-check").addEventListener("change",()=>renderRun(model.jobs.find(job=>job.job_id===confirmationJob)));
$("front-panel-save").addEventListener("click",async()=>{try{await api("/api/reference-confirm",{job_id:confirmationJob,operator:$("operator").value.trim()||null,confirmed:$("front-panel-check").checked});await refresh(true);}catch(exc){error(exc.message);}});

const guidedSetup={rf_path_ready:"RF path and sensor input level are suitable for this test",meter_prepared:"Meter and sensor are warmed up; zero/CAL and correction settings are prepared and recorded",reference_off:"POWER REF is off",operator_available:"I am at the bench and ready to change and confirm each point"};
for(const [key,labelText] of Object.entries(guidedSetup)){const label=node("label",undefined,"test-option"),input=node("input");input.type="checkbox";input.value=key;input.addEventListener("change",selectionChanged);label.append(input,node("span",labelText));$("guided-prepared").append(label);}
function guidedPrepared(){return Object.fromEntries([...document.querySelectorAll('#guided-prepared input')].map(input=>[input.value,input.checked]));}
const guidedLabels=id=>$(id).value.split(',').map(x=>x.trim()).filter(Boolean);
function guidedPlan(){let frequencies=guidedLabels("guided-frequencies"),drives=guidedLabels("guided-drives");const series=$("guided-series").value;if(series==="drive")frequencies=frequencies.slice(0,1);if(series==="frequency")drives=drives.slice(0,1);return {schema:"hp437b.guided-sweep.v1",name:$("guided-name").value.trim(),series,order:$("guided-order").value,frequencies,drives,samples:Number($("guided-samples").value),interval_s:Number($("guided-interval").value),settling_s:Number($("guided-settling").value),timeout_s:10,measurement_notes:$("guided-notes").value.trim()};}
function guidedValid(){const p=guidedPlan();return p.name.length>0&&p.measurement_notes.length>0&&p.frequencies.length>0&&p.frequencies.length<=32&&p.drives.length>0&&p.drives.length<=16&&new Set(p.frequencies).size===p.frequencies.length&&new Set(p.drives).size===p.drives.length&&[...p.frequencies,...p.drives].every(x=>x.length<=60)&&Number.isInteger(p.samples)&&p.samples>=1&&p.samples<=1000&&p.interval_s>=.1&&p.interval_s<=60&&p.settling_s>=0&&p.settling_s<=120&&p.samples*p.interval_s<=3600;}
function guidedPlanChanged(){const p=guidedPlan();$("guided-plan").textContent=guidedValid()?`${p.frequencies.length} frequencies × ${p.drives.length} drive settings = ${p.frequencies.length*p.drives.length} points. Confirmation is required before every capture.`:"Check the labels and capture limits before starting.";$("guided-order").disabled=Boolean(model.active_id)||p.series!=="combined";$("guided-frequency-hint").textContent=p.series==="drive"?"The first frequency label is held fixed for this series.":"Comma-separated labels; up to 32. Include exact frequencies in the labels as needed.";$("guided-drive-hint").textContent=p.series==="frequency"?"The first drive label is held fixed for this series.":"Comma-separated labels; up to 16, including custom setting names.";$("guided-prepared").hidden=$("guided-meter").value!=="physical";}
function guidedReference(job){return (job?.meter_mode||$("guided-meter").value)==="physical"&&(job?.sweep_config||model.guided?.meter)?.signal_source==="power_ref";}
let guidedPromptKey=null, guidedSubmit=false;
function renderGuided(job){
 const active=Boolean(model.active_id),p=job?.sweep_plan||guidedPlan(),prompt=job?.prompt,phase=job?.phase||"ready",rows=job?.point_results||[],completed=rows.filter(x=>x.status==="completed").length;
 setText("run-title","Point capture");setText("run-state",({ready:"Ready",starting:"Starting",waiting:"Waiting for you",running:"Settling / capturing",reporting:"Preparing reports",finished:"Finished",failed:"Needs attention"})[phase]||phase);$("run-state").className="state "+phase;
 setText("run-headline",phase==="waiting"?"Confirm the next point":phase==="running"?"Capturing measured power":phase==="finished"?(job.outcome==="completed"?"Series complete":"Series stopped"):phase==="failed"?"The run needs attention":phase==="reporting"?"Capture saved. Preparing reports.":"Prepare the sweep and start when ready.");
 setText("run-description",job?.error||`${p.name}. ${completed} of ${p.frequencies.length*p.drives.length} points captured. ${job?.meter_mode==="synthetic"||(!job&&$("guided-meter").value==="synthetic")?"Simulated measurements.":"Meter-indicated power at sensor input."}`);
 $("guided-point").hidden=!prompt||phase!=="waiting";const key=job?.job_id+":"+prompt?.token;
 if(key!==guidedPromptKey){guidedPromptKey=key;$("guided-frequency-confirm").checked=false;$("guided-drive-confirm").checked=false;guidedSubmit=false;}
 const ref=guidedReference(job);
 setText("environment",ref?"Operator-guided · POWER REF":(job?.meter_mode||$("guided-meter").value)==="physical"?"Operator-guided · bench meter":"Operator-guided · simulated meter");
 if(prompt){setText("guided-target",`${prompt.point_id} · ${prompt.frequency} / ${prompt.drive}`);setText("guided-frequency-label",ref?`I confirm the fixed reference label: ${prompt.frequency}`:`I set the frequency to ${prompt.frequency}`);setText("guided-drive-label",ref?`I confirm capture ${prompt.drive} with POWER REF on`:`I set the drive to ${prompt.drive}`);}
 setText("guided-instruction",ref?"Fixed POWER REF bench exercise. Turn POWER REF on and allow 20 seconds to settle before the first capture. Repeat labels do not change frequency or drive. Turn POWER REF off when finished or stopped.":"Set the radio to these labels and enable the test signal. Confirm both labels to begin settling and capture.");
 $("guided-capture").disabled=guidedSubmit||!active||phase!=="waiting"||job?.cancel_requested||!$("guided-frequency-confirm").checked||!$("guided-drive-confirm").checked;
 $("progress-label").textContent="Point completion";$("progress-count").textContent=`${completed} / ${p.frequencies.length*p.drives.length}`;$("progress").max=p.frequencies.length*p.drives.length;$("progress").value=completed;$("steps").replaceChildren();
 $("guided-controls").hidden=false;$("boundary-text").parentElement.hidden=true;$("guided-stop").disabled=!job?.active||!["starting","waiting","running"].includes(phase)||job?.cancel_requested;setText("guided-stop-note",job?.cancel_requested?"Stop requested. Saved points are retained; another point will not start.":ref?"Capture stops before the next measurement. Turn POWER REF off manually when finished or stopped.":"Capture stops before the next measurement. Turn radio RF off when finished.");
 $("guided-results").hidden=false;const head=node("tr");head.append(node("th","Frequency"));for(const d of p.drives)head.append(node("th",d));$("guided-results-head").replaceChildren(head);
 const body=p.frequencies.map(f=>{const tr=node("tr");tr.append(node("th",f));for(const d of p.drives){const row=rows.find(x=>x.frequency===f&&x.drive===d),current=prompt?.frequency===f&&prompt?.drive===d&&phase==="waiting";const td=node("td",row?.mean_W!==null&&row?.mean_W!==undefined?`${(Number(row.mean_W)*1000).toPrecision(5)}${row.status!=="completed"?" (partial)":""}`:current?"Next":row?.status==="failed"?"Failed":"—",current?"current":undefined);tr.append(td);}return tr;});$("guided-results-body").replaceChildren(...body);
 $("boundary-text").textContent=job?.cancel_requested?"Stop requested. Saved points are retained; another point will not start.":ref?"Stop ends the series before the next measurement. Turn POWER REF off manually.":"Stop ends the series before the next measurement. Turn radio RF off when the series finishes.";$("cancel").textContent="Stop series";$("cancel").disabled=!job?.active||!["starting","waiting","running"].includes(phase)||job?.cancel_requested;
 for(const el of document.querySelectorAll('#guided-setup input,#guided-setup select,#guided-setup textarea'))el.disabled=active;$("guided-order").disabled=active||p.series!=="combined";
 for(const id of ["mode","profile","operator","import","reference-workflow"])$(id).disabled=active;for(const input of document.querySelectorAll('#prepared input,#test-options input'))input.disabled=active;
 $("front-panel").hidden=true;$("pdf").hidden=!job?.pdf_ready;$("package").hidden=!job?.package_ready;$("html-report").hidden=!job?.pdf_ready;
 if(job){$("pdf").href=`/artifacts/${job.job_id}/report.pdf`;$("html-report").href=`/artifacts/${job.job_id}/report.html`;$("package").href=`/artifacts/${job.job_id}/package.zip`;}
 $("report-note").textContent=job?.pdf_ready?"The full report includes every point and both comparisons. The PDF summarizes the series.":"Reports and original point evidence appear when the series finishes or stops.";$("start").textContent=active?"Sweep in progress…":guidedMode()?"Start guided sweep":physicalMode()?"Start POWER REF workflow":"Start suite";$("start").disabled=!canStart();
}
for(const el of document.querySelectorAll('#guided-setup input,#guided-setup select,#guided-setup textarea'))el.addEventListener("input",()=>{if(el.id==="guided-meter")for(const input of document.querySelectorAll('#guided-prepared input'))input.checked=false;guidedPlanChanged();selectionChanged();if(!model.jobs.length)renderRun(null);});
$("guided-stop").addEventListener("click",()=>$("cancel").click());
for(const id of ["guided-frequency-confirm","guided-drive-confirm"])$(id).addEventListener("change",()=>{const job=model.jobs.find(x=>x.job_id===model.active_id);if(job)renderGuided(job);});
$("guided-capture").addEventListener("click",async()=>{const job=model.jobs.find(x=>x.job_id===model.active_id);if(!job?.prompt||guidedSubmit||$("guided-capture").disabled)return;guidedSubmit=true;$("guided-capture").disabled=true;generation++;try{await api("/api/guided-confirm",{job_id:job.job_id,confirmation:{...job.prompt,operator:$("operator").value.trim()||null,frequency_confirmed:$("guided-frequency-confirm").checked,drive_confirmed:$("guided-drive-confirm").checked}});await refresh(true);}catch(exc){error(exc.message);guidedSubmit=false;await refresh(true);}});
refresh();setInterval(refresh,500);
