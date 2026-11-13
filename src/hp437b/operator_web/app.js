"use strict";
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="operator-token"]').content;
let model = {profiles:[],jobs:[],active_id:null}, selectedProfile = null, busy = false, initialized = false;
let stepsSignature="", historySignature="", inflight=null, generation=0;
const setText=(id,value)=>{if($(id).textContent!==value)$(id).textContent=value;};
const titles = {"WF-01":"POWER REF baseline and output","WF-02":"Sustained output stability","WF-03":"Transmission-cycle repeatability","WF-04":"Output versus setting","WF-05":"Output versus frequency","WF-06":"Supply-voltage sensitivity"};
const node = (tag, text, cls) => {const element=document.createElement(tag);if(text!==undefined)element.textContent=text;if(cls)element.className=cls;return element;};
function error(message) {$("error").textContent=message||"";$("error").hidden=!message;if(message)$("error").focus();}
async function api(path, data) {
  const response = await fetch(path,{method:data===undefined?"GET":"POST",credentials:"same-origin",headers:{"X-Operator-Token":token,...(data===undefined?{}:{"Content-Type":"application/json"})},...(data===undefined?{}:{body:JSON.stringify(data)})});
  const result=await response.json();if(!response.ok)throw new Error(result.error||"The local operator request failed.");return result;
}
const preparation = {adapter_on_mac:"Adapter USB is on this Mac",direct_sensor_reference_path:"Sensor cable is on SENSOR; sensor RF input is directly on POWER REF",reference_off:"POWER REF is off",warmed_up:"Meter and sensor are warmed up",other_apps_closed:"Other control applications are closed",operator_available:"I am at the meter and can use PRESET/LOCAL for recovery"};
let confirmationJob=null;
function physicalMode(){return $("mode").value==="physical";}
function preparedValues(){return Object.fromEntries([...document.querySelectorAll('#prepared input')].map(input=>[input.value,input.checked]));}
function modeChanged(reset=true){
 const physical=physicalMode();$("page-title").textContent=physical?"Measure POWER REF":"Run an RF test suite";$("intro-text").textContent=physical?"Exercise the current meter and sensor with its internal reference.":"Choose a DUT profile and tests. Collect a traceable report.";$("fake-setup").hidden=physical;$("fake-tests").hidden=physical;$("reference-setup").hidden=!physical;
 if(reset)for(const input of document.querySelectorAll('#prepared input'))input.checked=false;
 $("environment").textContent=physical?"POWER REF · current meter":"Simulation · local session";
 $("scope").textContent=physical?"Controls the meter's internal reference. One workflow per run; no radio or supply control.":"Fakes only. No radio, meter, or supply is controlled.";
 $("mode-note").textContent=model.reference?"POWER REF uses the configured meter path; every run needs fresh confirmation.":"POWER REF must be explicitly enabled when launching this service.";
 selectionChanged();
}
for(const [key,labelText] of Object.entries(preparation)){const label=node("label",undefined,"test-option"),input=node("input");input.type="checkbox";input.value=key;input.addEventListener("change",selectionChanged);label.append(input,node("span",labelText));$("prepared").append(label);}
function canStart(){return !model.active_id&&!model.pending_reference&&!busy&&(physicalMode()?Boolean(model.reference)&&Object.values(preparedValues()).every(Boolean):chosen().length>0&&Boolean(selectedProfile));}
function chosen() {if(physicalMode())return [$("reference-workflow").value];return [...document.querySelectorAll('#test-options input:checked')].map(input=>input.value);}
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
  $("selection-note").textContent=physicalMode()?"One workflow per run. Confirm the setup again before each start.":count?`${count} ${count===1?"test":"tests"} selected. Runs in the order shown.`:"Select at least one test.";
  $("start").disabled=!canStart();
  if(!model.jobs.length)renderRun(null);
}
function formatResult(row) {
  if(!row)return "";
  const parts=[`${row.completed_points}/${row.requested_points} points`,row.acceptance];
  return parts.join(" · ");
}
function renderRun(job) {
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
    const previous=$("profile").value;
    if(!initialized||[...$("profile").options].map(option=>option.value).join()!==model.profiles.map(profile=>profile.key).join()){
      $("profile").replaceChildren(...model.profiles.map(profile=>{const option=node("option",`${profile.profile_id} · r${profile.revision}`);option.value=profile.key;return option;}));
      if(model.profiles.some(profile=>profile.key===previous))$("profile").value=previous;
      profileChanged();initialized=true;
    }
    $("issues-list").replaceChildren(...model.profile_issues.map(issue=>node("li",issue)));$("profile-issues").hidden=!model.profile_issues.length;
    modeChanged(false);renderRun(model.jobs.find(job=>job.job_id===model.active_id)||model.jobs.find(job=>job.job_id===model.pending_reference)||model.jobs[0]||null);renderHistory();
  }catch(exc){$("connection").textContent="Connection to the local operator service was lost. Existing worker runs are not restarted. Reload this page to reconnect and view their status.";$("connection").hidden=false;$("start").disabled=true;$("cancel").disabled=true;}
  })();inflight=task;try{await task;}finally{if(inflight===task)inflight=null;}
}
$("profile").addEventListener("change",profileChanged);
$("run-form").addEventListener("submit",async event=>{event.preventDefault();if(busy||model.active_id)return;busy=true;generation++;error("");$("start").disabled=true;try{const job=physicalMode()?await api("/api/reference",{workflow:$("reference-workflow").value,operator:$("operator").value.trim()||null,prepared:preparedValues()}):await api("/api/jobs",{profile_key:$("profile").value,workflows:chosen(),operator:$("operator").value.trim()||null});for(const input of document.querySelectorAll("#prepared input"))input.checked=false;model.active_id=job.job_id;model.jobs=[job,...model.jobs.filter(item=>item.job_id!==job.job_id)];renderRun(job);await refresh(true);}catch(exc){error(exc.message);}finally{busy=false;selectionChanged();}});
$("cancel").addEventListener("click",async()=>{if(!model.active_id)return;generation++;$("cancel").disabled=true;error("");try{await api("/api/cancel",{job_id:model.active_id});await refresh(true);}catch(exc){error(exc.message);await refresh();}});
$("import").addEventListener("click",()=>$("profile-file").click());
$("profile-file").addEventListener("change",async()=>{const file=$("profile-file").files[0];if(!file)return;generation++;error("");try{if(file.size>256*1024)throw new Error("Profile exceeds 256 KiB.");const raw=await file.text();const imported=await api("/api/profiles",{profile_json:raw});await refresh(true);$("profile").value=imported.key;profileChanged();}catch(exc){error("Profile was not imported: "+exc.message);}finally{$("profile-file").value="";}});
$("mode").addEventListener("change",()=>modeChanged());
$("reference-workflow").addEventListener("change",selectionChanged);
$("front-panel-check").addEventListener("change",()=>renderRun(model.jobs.find(job=>job.job_id===confirmationJob)));
$("front-panel-save").addEventListener("click",async()=>{try{await api("/api/reference-confirm",{job_id:confirmationJob,operator:$("operator").value.trim()||null,confirmed:$("front-panel-check").checked});await refresh(true);}catch(exc){error(exc.message);}});
refresh();setInterval(refresh,500);
