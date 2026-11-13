"use strict";
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="operator-token"]').content;
let model = {profiles:[],jobs:[],active_id:null}, selectedProfile = null, busy = false, initialized = false;
let stepsSignature="", inflight=null, generation=0, recoverySignature="",assessmentSignature="",assessmentFormSource=null;
let historyLoaded=false,historyBusy=false,historyOffset=0,historyTotal=0,historySelection=new Set(),comparisonBusy=false,detailGeneration=0;
const setText=(id,value)=>{if($(id).textContent!==value)$(id).textContent=value;};
const titles = {"GUIDED":"Operator-guided sweep","WF-01":"POWER REF baseline and output","WF-02":"Sustained output stability","WF-03":"Transmission-cycle repeatability","WF-04":"Output versus setting","WF-05":"Output versus frequency","WF-06":"Supply-voltage sensitivity"};
const node = (tag, text, cls) => {const element=document.createElement(tag);if(text!==undefined)element.textContent=text;if(cls)element.className=cls;return element;};
function error(message) {$("error").textContent=message||"";$("error").hidden=!message;if(message)$("error").focus();}
async function api(path, data) {
  const response = await fetch(path,{method:data===undefined?"GET":"POST",credentials:"same-origin",headers:{"X-Operator-Token":token,...(data===undefined?{}:{"Content-Type":"application/json"})},...(data===undefined?{}:{body:JSON.stringify(data)})});
  const result=await response.json();if(!response.ok)throw new Error(result.error||"The local operator request failed.");return result;
}
const preparation = {adapter_on_mac:"Adapter USB is on this Mac",direct_sensor_reference_path:"Sensor cable is on SENSOR; sensor RF input is directly on POWER REF",reference_off:"POWER REF is off",warmed_up:"Meter and sensor are warmed up",other_apps_closed:"Other control applications are closed",operator_available:"I am at the meter and can use PRESET/LOCAL for recovery"};
let confirmationJob=null, hydratedGuided=null, hydratedReferenceSuite=null;
function guidedMode(){return $("mode").value==="guided";}
function referenceSuiteMode(){return $("mode").value==="reference_suite";}
function referenceSuiteBench(){return referenceSuiteMode()&&$("reference-suite-source").value==="physical";}
function physicalMode(){return $("mode").value==="physical";}
function preparedValues(){return Object.fromEntries([...document.querySelectorAll('#prepared input')].map(input=>[input.value,input.checked]));}
function modeChanged(reset=true){
 const physical=physicalMode(), guided=guidedMode(), refSuite=referenceSuiteMode();
 $("reference-suite-setup").hidden=!refSuite;$("guided-setup").hidden=!guided;$("fake-setup").hidden=guided||physical;$("fake-tests").hidden=guided||physical;
 if(refSuite){
  $("guided-setup").hidden=true;$("fake-setup").hidden=true;$("fake-tests").hidden=true;$("reference-setup").hidden=!referenceSuiteBench();$("reference-workflow").parentElement.hidden=true;
  $("page-title").textContent="Run a POWER REF suite";$("intro-text").textContent="Choose reference tests, start once, and collect one traceable suite report.";
  $("environment").textContent=referenceSuiteBench()?"POWER REF suite · current meter":"POWER REF suite · simulation";
  $("scope").textContent=referenceSuiteBench()?"Keep the direct reference setup unchanged and remain available until the suite closes.":"Virtual-time reference tests; no meter connection or RF.";
  $("mode-note").textContent="Workflow captures remain separate; the suite joins progress, results, and evidence.";
  $("reference-suite-note").textContent=referenceSuiteBench()?"Runs in the order shown. All three usually take about 50 minutes; runner ceilings total 65 minutes. Reference off and local closure are verified between workflows.":"Runs in the order shown. Simulated time does not represent elapsed bench time.";
  if(reset)for(const input of document.querySelectorAll('#prepared input'))input.checked=false;
  selectionChanged();return;
 }
 $("reference-workflow").parentElement.hidden=false;
 if(guided){$("page-title").textContent="Measure a manual sweep";$("intro-text").textContent="Set the radio, confirm each point, and capture measured power.";$("reference-setup").hidden=true;$("environment").textContent=$("guided-meter").value==="physical"?"Operator-guided · bench meter":"Operator-guided · simulated meter";$("scope").textContent="One confirmed point at a time. Original measurements stay with the report.";$("mode-note").textContent="Choose frequency, drive setting, or a combined series.";guidedPlanChanged();selectionChanged();return;}
 $("page-title").textContent=physical?"Measure POWER REF":"Run an RF test suite";$("intro-text").textContent=physical?"Exercise the current meter and sensor with its internal reference.":"Choose a DUT profile and tests. Collect a traceable report.";$("fake-setup").hidden=physical;$("fake-tests").hidden=physical;$("reference-setup").hidden=!physical;
 if(reset)for(const input of document.querySelectorAll('#prepared input'))input.checked=false;
 $("environment").textContent=physical?"POWER REF · current meter":"Simulation · local session";
 $("scope").textContent=physical?"Measure the internal reference with one prepared workflow per run.":"Simulated measurements are explicitly marked in the report.";
 $("mode-note").textContent=model.reference?"POWER REF uses the configured meter path; every run needs fresh confirmation.":"POWER REF must be explicitly enabled when launching this service.";
 selectionChanged();
}
for(const [key,labelText] of Object.entries(preparation)){const label=node("label",undefined,"test-option"),input=node("input");input.type="checkbox";input.value=key;input.addEventListener("change",selectionChanged);label.append(input,node("span",labelText));$("prepared").append(label);}
function canStart(){if(referenceSuiteMode())return !model.active_id&&!model.pending_reference&&!busy&&chosen().length>0&&(!referenceSuiteBench()||(Boolean(model.reference)&&Object.values(preparedValues()).every(Boolean)));if(guidedMode())return !model.active_id&&!model.pending_reference&&!busy&&guidedValid()&&($("guided-meter").value!=="physical"||(Boolean(model.guided?.meter)&&Object.values(guidedPrepared()).every(Boolean)));return !model.active_id&&!model.pending_reference&&!busy&&(physicalMode()?Boolean(model.reference)&&Object.values(preparedValues()).every(Boolean):chosen().length>0&&Boolean(selectedProfile));}
function chosen() {if(referenceSuiteMode())return [...document.querySelectorAll("#reference-suite-tests input:checked")].map(input=>input.value);if(guidedMode())return ["GUIDED"];if(physicalMode())return [$("reference-workflow").value];return [...document.querySelectorAll('#test-options input:checked')].map(input=>input.value);}
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
  if(referenceSuiteMode())referenceSelectionChanged();
  const count=chosen().length;
  $("selection-note").hidden=guidedMode();
  $("selection-note").textContent=physicalMode()?"One workflow per run. Confirm the setup again before each start.":count?`${count} ${count===1?"test":"tests"} selected. Runs in the order shown.`:"Select at least one test.";
  $("start").disabled=!canStart();
  if(!model.active_id)$("start").textContent=referenceSuiteMode()?"Start POWER REF suite":guidedMode()?"Start guided sweep":physicalMode()?"Start POWER REF workflow":"Start suite";
  if(!model.jobs.length)renderRun(null);
}
function formatResult(row) {
  if(!row)return "";
  if(row.rows){const mean=row.rows.find(item=>item[0]==="Average RF power");return [mean?.[1],row.acceptance].filter(Boolean).join(" · ");}
  const parts=[`${row.completed_points}/${row.requested_points} points`,row.acceptance];
  return parts.join(" · ");
}
function renderRun(job) {
  renderProfileAssessment(job);
  if(job?.mode==="guided"||(!job&&guidedMode())){renderGuided(job);return;}
  $("guided-controls").hidden=true;$("boundary-text").parentElement.hidden=false;
  $("guided-point").hidden=true;$("guided-results").hidden=true;$("html-report").hidden=true;
  const assessing=job?.mode==="acceptance_review",recovering=job?.mode==="report_recovery"||assessing;
  const active=Boolean(model.active_id), selected=job?.workflows||chosen();
  const physical=job?(job.mode==="physical"||(job.mode==="reference_suite"&&job.meter_mode==="physical")):(physicalMode()||referenceSuiteBench());
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
      if(job.test_profile)description=`${job.profile_name}. ${completed}/${selected.length} tests complete. Original measurement results are retained; see the separate profile assessment below.`;
      if(job.cancel_requested&&job.outcome==="completed")description+=" All tests finished before cancellation could take effect.";
    }
    if(phase==="failed"){headline="The run needs attention";description=job.error||"The worker did not finish. Captured evidence is retained.";}
  }
  if(recovering){
    headline=phase==="failed"?"Report regeneration failed":phase==="finished"?"Reports regenerated":"Regenerating saved reports";
    description=phase==="failed"?(job.error+" Original evidence is retained. Select the saved capture to try a new report attempt."):"No new measurement. Original capture: "+job.source_job_id+". This is a separate report attempt.";
    $("run-title").textContent=assessing?"Saved-run acceptance assessment":"Report regeneration";
    if(assessing){headline=phase==="failed"?"Assessment report failed":phase==="finished"?"Supplied-limit result: "+job.assessment_outcome:"Assessing saved measurements";description=phase==="failed"?job.error:"Separate post-capture assessment. Original capture: "+job.source_job_id+". Criteria source: "+(job.assessment_source||"see decision record")+". No measurement repeated.";}
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
    const text=node("div");text.append(node("div",titles[kind],"step-name"));if(row)text.append(node("div",job?.mode==="reference_suite"?formatResult(row):physical?row.acceptance:formatResult(row),"step-result"));
    item.append(node("span",kind,"step-code"),text,node("span",status,"step-status"));$("steps").append(item);
  }
  }
  $("steps").hidden=recovering;
  if(recovering){$("progress-label").textContent="Report publication";$("progress-count").textContent=phase==="finished"?"1 / 1":"0 / 1";$("progress").max=1;$("progress").value=phase==="finished"?1:0;}
  $("boundary-text").parentElement.hidden=recovering;
  const pending=Boolean(job?.cancel_requested&&active&&["starting","running"].includes(phase));
  $("boundary-text").parentElement.classList.toggle("pending",pending);
  let boundary="The current test finishes and verifies RF off and supply restoration before cancellation takes effect. Later tests do not start.";
  if(job?.current){const next=selected[selected.indexOf(job.current)+1];boundary=`${pending?"Cancellation requested. ":""}${job.current} finishes and verifies RF off and restoration first. ${next?"The stop boundary is before "+next+".":"This is the final selected test."}`;}
  else if(pending)boundary="Cancellation requested. The worker will stop at the next test boundary. A test already in progress still finishes its cleanup first.";
  if(physical)boundary=`${pending?"Cancellation requested. ":""}The current capture stage finishes before cancellation is checked. WF-02's plateau can take 30 minutes. Existing healthy source-off cleanup then runs; uncertain I/O requires manual recovery. This is not an immediate RF-off control.`;
  if((job?.mode==="reference_suite"||(!job&&referenceSuiteMode()))&&!physical)boundary="The current virtual workflow finishes before cancellation takes effect. Later workflows do not start; no hardware or RF is involved.";
  $("boundary-text").textContent=boundary;
  $("cancel").disabled=!job?.active||!["starting","running"].includes(phase)||job.cancel_requested;
  $("cancel").textContent=pending?"Cancellation requested":"Request cancellation";
  $("pdf").hidden=!job?.pdf_ready;$("package").hidden=!job?.package_ready;
  if(job){$("pdf").href=`/artifacts/${job.job_id}/report.pdf`;$("package").href=`/artifacts/${job.job_id}/package.zip`;}
  $("report-note").textContent=job?.pdf_ready?"Open the one-page answer, or download reports and original evidence together.":"PDF and portable package appear after capture and reporting finish.";
  $("mode").disabled=active;$("reference-workflow").disabled=active;for(const input of document.querySelectorAll("#prepared input"))input.disabled=active;
  $("front-panel").hidden=!physical||job?.active||!["finished","failed"].includes(phase);
  if(confirmationJob!==job?.job_id){confirmationJob=job?.job_id;$("front-panel-check").checked=false;}
  $("front-panel-save").disabled=!physical||job?.active||job?.front_panel_confirmed||!$("front-panel-check").checked;
  $("front-panel-result").textContent=job?.front_panel_confirmed?"Separate operator confirmation recorded. Native capture remains unchanged.":"A new POWER REF run requires this confirmation.";
  $("front-panel-check").disabled=Boolean(job?.front_panel_confirmed);
  $("profile").disabled=active;$("operator").disabled=active;$("import").disabled=active;
  for(const input of document.querySelectorAll('#test-options input,#reference-suite-setup input,#reference-suite-setup select'))input.disabled=active;
  $("save-reference-profile").disabled=active||busy;
  $("start").textContent=active?"Run in progress…":referenceSuiteMode()?"Start POWER REF suite":physicalMode()?"Start POWER REF workflow":"Start suite";$("start").disabled=!canStart();
}
function renderHistory(){if(!historyLoaded&&!historyBusy)loadHistory();}
async function refresh(force=false) {
  if(inflight){if(!force)return inflight;await inflight;}
  const observed=generation;
  const task=(async()=>{
  try{
    const latest=await api("/api/state");if(observed!==generation)return;model=latest;$("connection").hidden=true;
    $("mode").querySelector('option[value="physical"]').disabled=!model.reference;
    $("reference-suite-source").querySelector('option[value="physical"]').disabled=!model.reference;
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
    const activeRefSuite=model.jobs.find(job=>job.job_id===model.active_id&&job.mode==="reference_suite");
    if(activeRefSuite&&hydratedReferenceSuite!==activeRefSuite.job_id){hydratedReferenceSuite=activeRefSuite.job_id;$("mode").value="reference_suite";$("reference-suite-source").value=activeRefSuite.meter_mode;for(const input of document.querySelectorAll('#reference-suite-tests input'))input.checked=activeRefSuite.workflows.includes(input.value);$("operator").value=activeRefSuite.operator||"";}
    const activeGuided=model.jobs.find(job=>job.job_id===model.active_id&&job.mode==="guided");
    if(activeGuided&&hydratedGuided!==activeGuided.job_id){const p=activeGuided.sweep_plan;hydratedGuided=activeGuided.job_id;$("mode").value="guided";for(const [id,value] of Object.entries({"guided-name":p.name,"guided-series":p.series,"guided-frequencies":p.frequencies.join(", "),"guided-drives":p.drives.join(", "),"guided-order":p.order,"guided-samples":p.samples,"guided-interval":p.interval_s,"guided-settling":p.settling_s,"guided-notes":p.measurement_notes,"guided-meter":activeGuided.meter_mode,"operator":activeGuided.operator||""}))$(id).value=value;}
    renderReferenceProfiles();modeChanged(false);renderRun(model.jobs.find(job=>job.job_id===model.active_id)||model.jobs.find(job=>job.job_id===model.pending_reference)||model.jobs[0]||null);renderHistory();renderRecoveryControls();renderAssessmentControls();
  }catch(exc){$("connection").textContent="Connection to the local operator service was lost. Existing worker runs are not restarted. Reload this page to reconnect and view their status.";$("connection").hidden=false;$("start").disabled=true;$("cancel").disabled=true;$("guided-capture").disabled=true;$("guided-stop").disabled=true;}
  })();inflight=task;try{await task;}finally{if(inflight===task)inflight=null;}
}
$("profile").addEventListener("change",profileChanged);
$("run-form").addEventListener("submit",async event=>{event.preventDefault();if(busy||model.active_id)return;busy=true;generation++;error("");$("start").disabled=true;try{const job=referenceSuiteMode()&&$("reference-profile").value?await api("/api/reference-profile-run",{profile_key:$("reference-profile").value,meter_mode:$("reference-suite-source").value,operator:$("operator").value.trim()||null,prepared:referenceSuiteBench()?preparedValues():{}}):referenceSuiteMode()?await api("/api/reference-suite",{workflows:chosen(),meter_mode:$("reference-suite-source").value,operator:$("operator").value.trim()||null,prepared:referenceSuiteBench()?preparedValues():{}}):guidedMode()?await api("/api/guided",{plan:guidedPlan(),operator:$("operator").value.trim()||null,meter_mode:$("guided-meter").value,prepared:$("guided-meter").value==="physical"?guidedPrepared():{}}):physicalMode()?await api("/api/reference",{workflow:$("reference-workflow").value,operator:$("operator").value.trim()||null,prepared:preparedValues()}):await api("/api/jobs",{profile_key:$("profile").value,workflows:chosen(),operator:$("operator").value.trim()||null});for(const input of document.querySelectorAll("#prepared input,#guided-prepared input"))input.checked=false;model.active_id=job.job_id;model.jobs=[job,...model.jobs.filter(item=>item.job_id!==job.job_id)];renderRun(job);await refresh(true);}catch(exc){error(exc.message);}finally{busy=false;selectionChanged();}});
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
 $("report-note").textContent=job?.pdf_ready?"The full report includes every point and both comparisons. The PDF summarizes the series.":"Reports and original point evidence appear when the series finishes or stops.";$("start").textContent=active?"Sweep in progress…":referenceSuiteMode()?"Start POWER REF suite":guidedMode()?"Start guided sweep":physicalMode()?"Start POWER REF workflow":"Start suite";$("start").disabled=!canStart();
}
for(const el of document.querySelectorAll('#guided-setup input,#guided-setup select,#guided-setup textarea'))el.addEventListener("input",()=>{if(el.id==="guided-meter")for(const input of document.querySelectorAll('#guided-prepared input'))input.checked=false;guidedPlanChanged();selectionChanged();if(!model.jobs.length)renderRun(null);});
$("guided-stop").addEventListener("click",()=>$("cancel").click());
for(const id of ["guided-frequency-confirm","guided-drive-confirm"])$(id).addEventListener("change",()=>{const job=model.jobs.find(x=>x.job_id===model.active_id);if(job)renderGuided(job);});
$("guided-capture").addEventListener("click",async()=>{const job=model.jobs.find(x=>x.job_id===model.active_id);if(!job?.prompt||guidedSubmit||$("guided-capture").disabled)return;guidedSubmit=true;$("guided-capture").disabled=true;generation++;try{await api("/api/guided-confirm",{job_id:job.job_id,confirmation:{...job.prompt,operator:$("operator").value.trim()||null,frequency_confirmed:$("guided-frequency-confirm").checked,drive_confirmed:$("guided-drive-confirm").checked}});await refresh(true);}catch(exc){error(exc.message);guidedSubmit=false;await refresh(true);}});
refresh();setInterval(refresh,500);

for(const input of document.querySelectorAll('#reference-suite-tests input'))input.addEventListener('change',selectionChanged);
$("reference-suite-source").addEventListener('change',()=>modeChanged(true));

function renderRecoveryControls(){
 const sources=model.report_sources||[],signature=JSON.stringify(sources);
 if(signature!==recoverySignature){
  recoverySignature=signature;const selected=$("recovery-source").value;
  $("recovery-source").replaceChildren(...sources.map(source=>{const option=node("option",`${new Date(source.started_utc).toLocaleString()} · ${source.workflows.join(" + ")} · ${source.outcome||"capture retained"} · ${source.job_id.slice(0,8)}`);option.value=source.job_id;return option;}));
  if(sources.some(x=>x.job_id===selected))$("recovery-source").value=selected;
 }
 const attempt=model.jobs.find(job=>job.mode==="report_recovery");
 setText("recovery-status",attempt?(attempt.phase==="failed"?"Report regeneration failed: "+attempt.error+" Original measurements are retained; select the capture to try again.":attempt.phase==="finished"?"Reports regenerated from saved capture "+attempt.source_job_id+". No new measurements.":"Validating saved evidence and generating reports. No meter connection."):"");
 $("recovery-pdf").hidden=!attempt?.pdf_ready;$("recovery-package").hidden=!attempt?.package_ready;
 if(attempt){$("recovery-pdf").href=`/artifacts/${attempt.job_id}/report.pdf`;$("recovery-package").href=`/artifacts/${attempt.job_id}/package.zip`;}
 const disabled=busy||Boolean(model.active_id)||!sources.length;
 $("recovery-source").disabled=disabled;$("recover-report").disabled=disabled;
 setText("recovery-note",!sources.length?"No sealed POWER REF captures are available in this run directory.":model.active_id?"Wait for the active run or report attempt to finish.":"Creates a separate report attempt. Interrupted captures keep their partial results; source files are validated before publication.");
}
$("recover-report").addEventListener("click",async()=>{
 if($("recover-report").disabled)return;busy=true;generation++;renderRecoveryControls();error("");
 try{await api("/api/report-recovery",{source_job_id:$("recovery-source").value});}
 catch(exc){error("Reports were not regenerated. "+exc.message+". Original measurements are retained; select another capture or repair a copy before retrying.");}
 finally{busy=false;await refresh(true);}
});

const measured=value=>value===null||value===undefined?"Not available":Number(value).toLocaleString(undefined,{maximumSignificantDigits:8});
const metric=(value,scale)=>value===null||value===undefined?"Not available":measured(Number(value)*scale);
function updateComparisonSelection(){
 setText("comparison-selection",`${historySelection.size} measurements selected${historySelection.size?": "+[...historySelection].map(x=>x.slice(0,8)).join(", "):""}. Choose two to four; report attempts are not measurements.`);
 $("compare-runs").disabled=comparisonBusy||historySelection.size<2||historySelection.size>4;
}
function reportLink(job,name,text){const link=node("a",text);link.href=`/artifacts/${job.job_id}/${name}`;link.target="_blank";link.rel="noopener";return link;}
async function loadHistory(){
 if(historyBusy)return;historyBusy=true;$("history-filter").disabled=true;$("history-prev").disabled=true;$("history-next").disabled=true;$("history-refresh").disabled=true;setText("history-note","Loading saved runs…");
 try{
  const data=await api("/api/run-history",{offset:historyOffset,category:$("history-filter").value});historyLoaded=true;historyTotal=data.total;
  const rows=data.entries.map(job=>{
   const tr=node("tr"),select=node("td"),box=node("input");box.type="checkbox";box.checked=historySelection.has(job.job_id);box.disabled=!job.report_recovery_available;box.setAttribute("aria-label",`Select measurement ${job.job_id.slice(0,8)}`);
   box.addEventListener("change",()=>{if(box.checked&&historySelection.size>=4){box.checked=false;setText("history-note","Select at most four measurements; clear a selection first.");return;}box.checked?historySelection.add(job.job_id):historySelection.delete(job.job_id);$("comparison").hidden=true;updateComparisonSelection();});select.append(box);
   const report=["report_recovery","acceptance_review"].includes(job.mode),assessment=job.mode==="acceptance_review",subject=node("td");subject.append(node("div",job.profile_name),node("small",`${assessment?"Acceptance assessment":report?"Report regeneration":"Measurement"} · ${job.job_id.slice(0,8)}${report?" · source "+job.source_job_id.slice(0,8):" · "+job.workflows.join(" + ")}`));
   const outcome=job.phase==="failed"?(report?"Report error":"Needs attention"):job.phase!=="finished"?job.phase:report?(assessment?"Assessed: "+job.assessment_outcome:"Reports ready"):job.outcome==="interrupted"?"Cancelled":job.outcome==="failed"?"Stopped":"Complete";
   tr.append(select,subject,node("td",new Date(job.started_utc).toLocaleString()),node("td",outcome));
   const actions=node("td",undefined,"history-links");if(job.pdf_ready)actions.append(reportLink(job,"report.pdf","PDF"));if(job.package_ready)actions.append(reportLink(job,"package.zip","Package"));if(job.assessment_ready){actions.append(reportLink(job,"assessment/report.pdf","Assessed PDF"),reportLink(job,"assessment/package.zip","Assessment package"));}
   if(job.report_recovery_available||report){const button=node("button","View details","text-button");button.type="button";button.setAttribute("aria-label",`View details for ${job.job_id.slice(0,8)}`);button.addEventListener("click",()=>showRunDetails(job.job_id));actions.append(button);}
   if(!actions.childNodes.length)actions.textContent="No report available";tr.append(actions);return tr;
  });$("history-body").replaceChildren(...rows);
  setText("history-note",data.total?`Showing ${historyOffset+1}–${Math.min(historyOffset+20,data.total)} of ${data.total} saved runs.${data.unreadable_jobs.length?" "+data.unreadable_jobs.length+" unreadable run records omitted.":""}`:"No saved runs match this filter.");
  $("history-prev").disabled=historyOffset===0;$("history-next").disabled=historyOffset+20>=historyTotal;
 }catch(exc){setText("history-note","History could not be loaded: "+exc.message);}
 finally{historyBusy=false;$("history-filter").disabled=false;$("history-refresh").disabled=false;updateComparisonSelection();}
}
async function showRunDetails(jobId){
 const detailRequest=++detailGeneration;
 $("run-detail").hidden=false;$("detail-body").replaceChildren();setText("detail-note","Validating saved POWER REF evidence…");setText("detail-context","");
 try{
  const data=await api("/api/run-details",{job_id:jobId});if(detailRequest!==detailGeneration)return;
  setText("detail-note",`${data.report_attempt?"Report attempt; original measurement":"Measurement"} ${data.source_job_id}. Capture SHA-256: ${data.source_inventory_sha256}.`);
  $("detail-body").replaceChildren(...data.workflows.map(row=>{const tr=node("tr"),label=node("td",`${row.workflow} · ${row.mode} · ${row.execution}`),identity=node("small",`Capture ${row.run_id.slice(0,8)}`);identity.title=row.run_id;label.append(identity);tr.append(label,node("td",metric(row.metrics.zero_W,1e6)),node("td",metric(row.metrics.mean_W,1e3)),node("td",String(row.metrics.valid_plateau)));return tr;}));
  setText("detail-context",data.workflows.map(row=>`${row.workflow}: meter ${row.meter_serial||"not recorded"}; sensor ${row.sensor_serial||"not recorded"}.`).join(" ")+` ${data.not_captured.length?"Not captured: "+data.not_captured.join(", ")+". ":""}Original front-panel confirmation: ${data.front_panel_confirmation?"recorded at "+data.front_panel_confirmation.confirmed_utc:"not recorded"}.`);
 }catch(exc){if(detailRequest===detailGeneration)setText("detail-note","Saved capture could not be verified: "+exc.message);}
}
$("history-refresh").addEventListener("click",()=>loadHistory());
$("history-filter").addEventListener("change",()=>{historyOffset=0;loadHistory();});
$("history-prev").addEventListener("click",()=>{historyOffset=Math.max(0,historyOffset-20);loadHistory();});
$("history-next").addEventListener("click",()=>{historyOffset+=20;loadHistory();});
$("comparison-workflow").addEventListener("change",()=>{$("comparison").hidden=true;});
$("compare-runs").addEventListener("click",async()=>{
 if($("compare-runs").disabled)return;comparisonBusy=true;updateComparisonSelection();$("comparison").hidden=false;$("comparison-body").replaceChildren();$("comparison-table").hidden=false;setText("comparison-caption",$("comparison-workflow").value+" · verifying saved measurements");setText("comparison-note","Validating selected captures…");
 try{
  const result=await api("/api/run-comparison",{job_ids:[...historySelection],workflow:$("comparison-workflow").value});setText("comparison-caption",`${result.workflow} · sensor-input measurements; changes relative to first selected run`);
  setText("comparison-note",result.verdict+". "+result.notes.map(note=>note.replace(/\.$/," ").trim()).join("; ")+". "+(result.changes_available?"":" Mean changes withheld because recorded conditions, completeness, or metadata differ."));
  $("comparison-body").replaceChildren(...result.rows.map(row=>{const tr=node("tr");tr.append(node("td",`${row.job_id.slice(0,8)} · ${row.mode} · ${row.execution} · ${new Date(row.started_utc).toLocaleString()}`),node("td",metric(row.metrics.zero_W,1e6)),node("td",metric(row.metrics.mean_W,1e3)),node("td",metric(row.mean_change_W,1e6)),node("td",metric(row.metrics.endpoint_change_percent,1)),node("td",metric(row.metrics.cycle_spread_W,1e6)),node("td",`Meter ${row.meter_serial||"unknown"}; sensor ${row.sensor_serial||"unknown"}. `+(row.flags.join("; ")||"Recorded context matches first selection")));return tr;}));
 }catch(exc){$("comparison-table").hidden=true;setText("comparison-note","Comparison unavailable: "+exc.message);}
 finally{comparisonBusy=false;updateComparisonSelection();}
});

function buildCriteriaFields(){
 const source=(model.report_sources||[]).find(x=>x.job_id===$("assessment-source").value);assessmentFormSource=source?.job_id;$("saved-assessment-profile").value="";
 criteriaFields("criteria-workflows",source?.workflows||[]);
}
function criteriaFields(target,kinds,values={}){
 $(target).replaceChildren();
 for(const kind of kinds){
  const group=node("details");group.open=kinds.length===1;group.append(node("summary",kind+" · optional criteria"));
  const grid=node("div",undefined,"capture-fields");
  const fields=[["mean_min_mW","Mean minimum (mW)"],["mean_max_mW","Mean maximum (mW)"],["min_valid_samples",kind==="WF-02"?"Minimum valid samples per bin":kind==="WF-03"?"Minimum valid samples per cycle":"Minimum valid plateau samples"],["max_gap_s","Maximum gap (s)"]];
  if(kind==="WF-02")fields.push(["max_abs_endpoint_change_percent","Maximum absolute endpoint change (%)"]);if(kind==="WF-03")fields.push(["max_cycle_spread_percent","Maximum cycle-mean spread (%)"]);
  for(const [key,text] of fields){const field=node("div",undefined,"field"),label=node("label",kind+" "+text),input=node("input");input.id=`${target}-${kind}-${key}`;label.htmlFor=input.id;input.type=key==="min_valid_samples"?"number":"text";input.inputMode=key==="min_valid_samples"?"numeric":"decimal";if(key==="min_valid_samples"){input.min="1";input.max="1000000";input.step="1";}input.maxLength=64;input.value=values[kind]?.[key]??"";input.dataset.workflow=kind;input.dataset.limit=key;field.append(label,input);grid.append(field);}group.append(grid);$(target).append(group);
 }
}
function renderAssessmentControls(){
 const sources=model.report_sources||[],signature=JSON.stringify(sources);
 if(signature!==assessmentSignature){assessmentSignature=signature;const selected=$("assessment-source").value;$("assessment-source").replaceChildren(...sources.map(source=>{const option=node("option",`${new Date(source.started_utc).toLocaleString()} · ${source.workflows.join(" + ")} · ${source.outcome||"capture retained"} · ${source.job_id.slice(0,8)}`);option.value=source.job_id;return option;}));if(sources.some(x=>x.job_id===selected))$("assessment-source").value=selected;}
 if(assessmentFormSource!==$("assessment-source").value)buildCriteriaFields();
 const disabled=busy||Boolean(model.active_id)||!sources.length;for(const input of document.querySelectorAll('#assessment-form input,#assessment-form select,#assessment-form button'))input.disabled=disabled;
 assessmentProfileControls(disabled);
 const attempt=model.jobs.find(job=>job.mode==="acceptance_review");setText("assessment-status",!sources.length?"No sealed POWER REF capture is available.":attempt?attempt.phase==="failed"?"Assessment report failed: "+attempt.error+". Original evidence is retained.":attempt.phase==="finished"?"Latest assessment of "+attempt.source_job_id.slice(0,8)+": "+attempt.assessment_outcome+". Criteria source: "+(attempt.assessment_source||"see decision record")+". Separate post-capture review; original reports unchanged.":"Validating saved evidence and applying supplied criteria. No meter connection.":"No acceptance assessment has been created.");
 $("assessment-pdf").hidden=!attempt?.pdf_ready;$("assessment-package").hidden=!attempt?.package_ready;$("assessment-json").hidden=!attempt?.pdf_ready;if(attempt){$("assessment-pdf").href=`/artifacts/${attempt.job_id}/report.pdf`;$("assessment-package").href=`/artifacts/${attempt.job_id}/package.zip`;$("assessment-json").href=`/artifacts/${attempt.job_id}/results.json`;}
}
$("assessment-source").addEventListener("change",buildCriteriaFields);
$("assessment-form").addEventListener("submit",async event=>{
 event.preventDefault();if(busy||model.active_id||$("assess-run").disabled)return;
 const workflows={};for(const input of document.querySelectorAll('#criteria-workflows input')){const value=input.value.trim();(workflows[input.dataset.workflow]??={})[input.dataset.limit]=value?(input.dataset.limit==="min_valid_samples"?Number(value):value):null;}
 const criteria={schema:"hp437b.acceptance-criteria.v1",source:$("criteria-source").value.trim()||null,decision_rule:"inclusive-no-guard-band",workflows};
 busy=true;generation++;error("");renderAssessmentControls();
 try{const job=$("saved-assessment-profile").value?await api("/api/reference-profile-assessment",{source_job_id:$("assessment-source").value,profile_key:$("saved-assessment-profile").value,assessor:$("assessment-assessor").value.trim()||null}):await api("/api/acceptance-review",{source_job_id:$("assessment-source").value,criteria,assessor:$("assessment-assessor").value.trim()||null});model.active_id=job.job_id;model.jobs=[job,...model.jobs.filter(x=>x.job_id!==job.job_id)];renderRun(job);historyLoaded=false;}
 catch(exc){error("Assessment was not started: "+exc.message);}
 finally{busy=false;await refresh(true);}
});

let referenceProfileSignature="",referenceCriteriaSignature="",savedProfileSignature="";
const referenceDocuments=()=>model.reference_profiles||[];
const referenceDocument=key=>referenceDocuments().find(x=>x.key===key)?.document;
function readCriteria(target,source){
 const workflows={};for(const input of document.querySelectorAll(`#${target} input`)){const value=input.value.trim();(workflows[input.dataset.workflow]??={})[input.dataset.limit]=value?(input.dataset.limit==="min_valid_samples"?Number(value):value):null;}
 return {schema:"hp437b.acceptance-criteria.v1",source:source.trim()||null,decision_rule:"inclusive-no-guard-band",workflows};
}
function referenceSelectionChanged(){
 const kinds=[...document.querySelectorAll('#reference-suite-tests input:checked')].map(x=>x.value),signature=kinds.join();
 if(signature!==referenceCriteriaSignature){const values=readCriteria("reference-criteria-workflows","").workflows;referenceCriteriaSignature=signature;criteriaFields("reference-criteria-workflows",kinds,values);}
}
function renderReferenceProfiles(){
 const rows=referenceDocuments(),signature=JSON.stringify(rows);
 if(signature!==referenceProfileSignature){referenceProfileSignature=signature;const selected=$("reference-profile").value;$("reference-profile").replaceChildren(new Option("Unsaved selection — no automatic assessment",""),...rows.map(x=>new Option(`${x.document.profile_id} · r${x.document.revision}`,x.key)));if(referenceDocument(selected))$("reference-profile").value=selected;}
 const active=model.jobs.find(x=>x.job_id===model.active_id&&x.mode==="reference_suite");
 if(active?.test_profile)$("reference-profile").value=active.test_profile.profile_sha256;
 const doc=referenceDocument($("reference-profile").value);
 setText("reference-profile-note",doc?`${doc.description}. Saved tests and limits will be frozen at Start; the operator below may override the saved name. Subject: Internal POWER REF.`:"Choose a saved profile to reuse its tests, operator, and optional limits. POWER REF measures the internal reference, not a transmitter.");
 referenceSelectionChanged();
 const issues=model.reference_profile_issues||[];if(issues.length)setText("reference-profile-status","Some reference profiles could not be read: "+issues.join("; "));
}
function referenceProfileChanged(){
 const doc=referenceDocument($("reference-profile").value);
 if(doc){
  for(const input of document.querySelectorAll('#reference-suite-tests input'))input.checked=doc.workflows.includes(input.value);
  $("operator").value=doc.operator||"";$("reference-profile-id").value=doc.profile_id;$("reference-profile-revision").value=doc.revision;$("reference-profile-description").value=doc.description;$("reference-criteria-source").value=doc.criteria.source||"";
  referenceCriteriaSignature=doc.workflows.join();criteriaFields("reference-criteria-workflows",doc.workflows,doc.criteria.workflows);
 }
 setText("reference-profile-status",doc?`Loaded ${doc.profile_id} r${doc.revision}. Changes require a new revision.`:"Unsaved selection. Save a revision to enable automatic assessment.");
 for(const input of document.querySelectorAll('#prepared input'))input.checked=false;
 renderReferenceProfiles();selectionChanged();
}
$("reference-profile").addEventListener("change",referenceProfileChanged);
for(const input of document.querySelectorAll('#reference-suite-tests input'))input.addEventListener("change",()=>{$("reference-profile").value="";setText("reference-profile-status","Selection changed. Save a profile revision to enable automatic assessment.");renderReferenceProfiles();});
$("reference-profile-editor").addEventListener("input",()=>{$("reference-profile").value="";setText("reference-profile-status","Unsaved edits. Save this revision before using it for automatic assessment.");renderReferenceProfiles();});
$("save-reference-profile").addEventListener("click",async()=>{
 if(busy||model.active_id)return;busy=true;generation++;error("");$("save-reference-profile").disabled=true;
 const profile={schema:"hp437b.reference-test-profile.v1",profile_id:$("reference-profile-id").value.trim(),revision:Number($("reference-profile-revision").value),description:$("reference-profile-description").value.trim(),subject:"Internal POWER REF",operator:$("operator").value.trim()||null,workflows:chosen(),criteria:readCriteria("reference-criteria-workflows",$("reference-criteria-source").value)};
 try{const result=await api("/api/reference-profiles",{profile});await refresh(true);$("reference-profile").value=result.key;referenceProfileChanged();setText("reference-profile-status",`Saved ${profile.profile_id} r${profile.revision}. No measurement started.`);}
 catch(exc){error("Profile was not saved: "+exc.message);}
 finally{busy=false;$("save-reference-profile").disabled=Boolean(model.active_id);selectionChanged();}
});
function assessmentProfileControls(disabled){
 const source=(model.report_sources||[]).find(x=>x.job_id===$("assessment-source").value),rows=referenceDocuments().filter(x=>JSON.stringify(x.document.workflows)===JSON.stringify(source?.workflows));
 const signature=JSON.stringify(rows.map(x=>x.key))+":"+source?.job_id;
 if(signature!==savedProfileSignature){savedProfileSignature=signature;const selected=$("saved-assessment-profile").value;$("saved-assessment-profile").replaceChildren(new Option("Enter criteria below",""),...rows.map(x=>new Option(`${x.document.profile_id} · r${x.document.revision}`,x.key)));if(rows.some(x=>x.key===selected))$("saved-assessment-profile").value=selected;}
 const doc=referenceDocument($("saved-assessment-profile").value);
 $("criteria-source").disabled=disabled||Boolean(doc);for(const input of document.querySelectorAll('#criteria-workflows input'))input.disabled=disabled||Boolean(doc);
 setText("saved-assessment-profile-note",doc?`Use ${doc.profile_id} r${doc.revision}. Applied now as post-capture criteria; original measurement operator and reports remain unchanged.`:"Only profiles with the same selected workflows can assess this capture. Applied now, these remain post-capture criteria.");
}
$("saved-assessment-profile").addEventListener("change",()=>{
 const doc=referenceDocument($("saved-assessment-profile").value),source=(model.report_sources||[]).find(x=>x.job_id===$("assessment-source").value);
 $("criteria-source").value=doc?.criteria.source||"";criteriaFields("criteria-workflows",source?.workflows||[],doc?.criteria.workflows||{});renderAssessmentControls();
});
function renderProfileAssessment(job){
 const binding=job?.mode==="reference_suite"&&job?.test_profile;$("profile-assessment").hidden=!binding;
 if(!binding)return;
 const doc=binding.profile;setText("profile-assessment-note",`${doc.profile_id} r${doc.revision}: `+(job.assessment_error?"Assessment publication failed: "+job.assessment_error+". The original measurement report is retained; retry from the saved capture below.":job.assessment_outcome?job.assessment_outcome+". Post-capture decision using the profile selected before capture; original measurements are unchanged.":"The saved profile will be assessed after capture and native reporting finish."));
 for(const [id,name] of [["profile-assessment-pdf","report.pdf"],["profile-assessment-package","package.zip"]]){$(id).hidden=!job.assessment_ready;$(id).href=`/artifacts/${job.job_id}/assessment/${name}`;}
}

$("reference-profile-editor").addEventListener("keydown",event=>{if(event.key==="Enter"&&event.target.tagName==="INPUT")event.preventDefault();});
