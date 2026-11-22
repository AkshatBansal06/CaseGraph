(() => {
  const $ = (s, root=document) => root.querySelector(s);
  const $$ = (s, root=document) => [...root.querySelectorAll(s)];
  const state = { caseId: window.CASEGRAPH_BOOT?.selectedCaseId || null, dashboard: null, graph: null, graphInstance: null, evidenceFilter: false, evidenceQuery: '', sessionData: null, selectedPersonId: null };
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const initials = name => String(name || '?').trim().split(/\s+/).slice(0,2).map(v=>v[0]||'').join('').toUpperCase();
  const fmtDate = value => { if(!value) return '—'; const d=new Date(value); return Number.isNaN(+d)?String(value):d.toLocaleDateString(undefined,{day:'2-digit',month:'short',year:'numeric'}); };
  const fmtDateTime = value => { if(!value) return 'Time not recorded'; const d=new Date(value); return Number.isNaN(+d)?String(value):d.toLocaleString(undefined,{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}); };
  const statusClass = value => ['open','investigating','closed'].includes(String(value||'').toLowerCase()) ? String(value).toLowerCase() : '';
  const statusPill = value => `<span class="status-pill ${statusClass(value)}">${esc(value||'unknown')}</span>`;
  const setStatus = (el, value) => { if (!el) return; el.className = `status-pill ${statusClass(value)}`; el.textContent = value || 'unknown'; };
  const verifyPill = value => `<span class="verify-pill ${esc(String(value||'unverified').toLowerCase())}">${esc(value||'unverified')}</span>`;
  async function api(url, options={}) { const res=await fetch(url,options); let data; try{data=await res.json()}catch{data={error:'The server returned an unreadable response.'}} if(!res.ok) throw new Error(data.error||`Request failed (${res.status})`); return data; }
  function toast(message, error=false){const el=document.createElement('div');el.className='toast'+(error?' error':'');el.innerHTML=`<i data-lucide="${error?'alert-circle':'check-circle-2'}"></i><span>${esc(message)}</span>`;$('#toastRegion').append(el);if(window.lucide)lucide.createIcons({nodes:[el]});setTimeout(()=>el.remove(),3600)}
  function iconRefresh(){if(window.lucide)lucide.createIcons();}
  function go(view){
    const target=$(`#view-${view}`);
    if(!target)return;
    $$('.page-view').forEach(v=>v.classList.toggle('active',v===target));
    $$('.nav-item[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
    const names={
      dashboard:'Overview',
      interviews:'Interview Room',
      board:'Evidence Board',
      search:'Search Terminal',
      people:'People',
      evidence:'Evidence vault',
      relationships:'Relationship graph',
      timeline:'Timeline',
      analysis:'Analysis lab',
      dbms:'DBMS Query Lab',
      reports:'Reports'
    };
    $('#crumbCurrent').textContent=names[view]||'Overview';
    $('#sidebar').classList.remove('mobile-open');
    if(view==='interviews')loadInterviewView();
    if(view==='board')loadBoardView();
    if(view==='search')loadSearchView();
    if(view==='relationships')loadGraph(true);
    if(view==='timeline')loadTimeline();
    if(view==='analysis')loadConflicts();
    if(view==='dbms')loadDBMSLabView();
    if(view==='reports')loadReport();
    if(view==='evidence')renderAllEvidence();
    if(view==='people')renderAllPeople();
    location.hash=view;
  }
  async function loadDashboard(){if(!state.caseId){$('#heroCaseTitle').textContent='No cases found';$('#heroCaseDescription').textContent='Create a case record in PostgreSQL to get started.';return;}try{state.dashboard=await api(`/api/dashboard?case_id=${state.caseId}`);const d=state.dashboard,c=d.case;$('#heroCaseTitle').textContent=c.title;$('#heroCaseDescription').textContent=c.description;$('#heroCaseNumber').textContent=`CASE / ${String(c.case_id).padStart(3,'0')}`;$('#heroCreated').textContent=fmtDate(c.created_at);setStatus($('#heroStatus'),c.status);$('#miniCaseTitle').textContent=c.title;$('#miniCaseId').textContent=`CASE ${String(c.case_id).padStart(3,'0')}`;setStatus($('#miniCaseStatus'),c.status);$('#statPeople').textContent=d.stats.people;$('#statEvidence').textContent=d.stats.evidence;$('#statEvents').textContent=d.stats.events;$('#statConflicts').textContent=d.stats.contradictions;$('#peopleCount').textContent=d.people.length;renderPeople(d.people,$('#peopleGrid'),true);renderEvidencePreview(d.evidence);renderTimelinePreview(d.timeline);iconRefresh();if($('#view-people').classList.contains('active'))renderAllPeople();if($('#view-evidence').classList.contains('active'))renderAllEvidence();if($('#view-reports').classList.contains('active'))loadReport();loadMiniGraph();}catch(e){toast(e.message,true);$('#heroCaseTitle').textContent='Could not load case';$('#heroCaseDescription').textContent='Check that Flask is running and DATABASE_URL points to the casegraph database.';}}
 function renderPeople(people,container,compact=false){if(!people?.length){container.innerHTML='<div class="empty-state">No people are linked to this case yet.</div>';return;}container.innerHTML=people.map(p=>`<article class="person-card" style="--person-accent:${p.role==='suspect'?'#ff7f91':p.role==='witness'?'#72baff':p.role==='investigator'?'#53e0d0':'#b6a1ff'}" data-person="${p.person_id}"><div class="person-top">${personAvatar(p,52)}<span class="role-chip ${esc(p.role)}">${esc(p.role)}</span></div><h3>${esc(p.full_name)}</h3><p class="occupation">${esc(p.occupation||'Occupation not recorded')}</p><div class="person-foot"><span><i data-lucide="files"></i>${Number(p.evidence_count||0)} linked evidence</span><span>View dossier <i data-lucide="arrow-up-right"></i></span></div>${!compact?`<div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap"><button type="button" data-edit-person="${p.person_id}" style="background:rgba(83,224,208,.12);color:#53e0d0;border:1px solid rgba(83,224,208,.35);border-radius:8px;padding:8px 13px;font-size:12px;font-weight:600;cursor:pointer">✎ Edit</button><button type="button" data-remove-person="${p.person_id}" style="background:rgba(255,127,145,.08);color:#ff9aaa;border:1px solid rgba(255,127,145,.28);border-radius:8px;padding:8px 13px;font-size:12px;font-weight:600;cursor:pointer">Remove from case</button></div>`:''}</article>`).join('');$$('[data-person]',container).forEach(card=>card.addEventListener('click',event=>{if(event.target.closest('button'))return;openPerson(card.dataset.person);}));$$('[data-edit-person]',container).forEach(button=>button.addEventListener('click',async event=>{event.stopPropagation();const person=people.find(p=>Number(p.person_id)===Number(button.dataset.editPerson));if(!person)return;const full_name=prompt('Enter full name:',person.full_name);if(full_name===null)return;if(!full_name.trim()){alert('Name cannot be empty.');return;}const occupation=prompt('Enter occupation:',person.occupation||'');if(occupation===null)return;const gender=prompt('Gender for default avatar (male, female, or blank for initials):',person.gender||'');if(gender===null)return;const normalizedGender=gender.trim().toLowerCase();if(normalizedGender&&!['male','female'].includes(normalizedGender)){alert('Enter male, female, or leave blank.');return;}const role=prompt('Enter role (suspect, witness, investigator, other):',person.role);if(role===null)return;if(!['suspect','witness','investigator','other'].includes(role.trim().toLowerCase())){alert('Invalid role.');return;}try{const response=await fetch(`/api/people/${person.person_id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({case_id:state.caseId,full_name:full_name.trim(),occupation:occupation.trim(),gender:normalizedGender||null,role:role.trim().toLowerCase()})});const result=await response.json();if(!response.ok)throw new Error(result.error||'Could not update person.');toast('Person updated successfully.');await loadDashboard();renderAllPeople();}catch(error){alert(error.message);}}));$$('[data-remove-person]',container).forEach(button=>button.addEventListener('click',async event=>{event.stopPropagation();const person=people.find(p=>Number(p.person_id)===Number(button.dataset.removePerson));if(!person)return;if(!confirm(`Remove ${person.full_name} from this case?`))return;try{const response=await fetch(`/api/people/${person.person_id}?case_id=${state.caseId}`,{method:'DELETE'});const result=await response.json();if(!response.ok)throw new Error(result.error||'Could not remove person from case.');toast('Person removed from case.');await loadDashboard();renderAllPeople();}catch(error){alert(error.message);}}));if(!compact)container.classList.add('expanded-grid');iconRefresh();}
   function personAvatar(person,size=64){const name=person.full_name||person.name||'Unknown';const fallback=initials(name);const src=person.photo_path?`/static/${String(person.photo_path).replace(/^\/+/, '')}`:(['male','female'].includes(String(person.gender||'').toLowerCase())?`/static/images/avatar-${String(person.gender).toLowerCase()}.svg`:null);return `<div class="person-avatar" style="width:${size}px;height:${size}px;min-width:${size}px;overflow:hidden;display:flex;align-items:center;justify-content:center">${src?`<img src="${esc(src)}" alt="${esc(name)}" data-fallback="${esc(fallback)}" style="width:100%;height:100%;object-fit:cover" onerror="this.onerror=null;this.replaceWith(Object.assign(document.createElement('span'),{textContent:this.dataset.fallback,style:'display:flex;width:100%;height:100%;align-items:center;justify-content:center'}))">`:esc(fallback)}</div>`;}
 function renderEvidencePreview(items){const box=$('#evidencePreview');if(!items?.length){box.innerHTML='<div class="empty-state">No evidence records found for this case.</div>';return;}box.innerHTML=items.slice(0,5).map(e=>`<div class="evidence-row"><div class="file-icon"><i data-lucide="file-text"></i></div><div class="evidence-row-main"><strong>${esc(e.title)}</strong><small>${esc(e.evidence_type)} · ${fmtDate(e.recorded_at)}</small></div>${verifyPill(e.verification_status)}</div>`).join('');iconRefresh();}
  function renderTimelinePreview(items){const box=$('#timelinePreview');if(!items?.length){box.innerHTML='<div class="empty-state">No timeline events recorded.</div>';return;}box.innerHTML=items.slice(0,4).map(t=>`<div class="timeline-row"><div class="timeline-rail"><span class="timeline-dot"></span></div><div><strong>${esc(t.full_name)} · ${esc(t.location_name)}</strong><p>${esc(t.description)}</p><time>${fmtDateTime(t.event_time)} · ${t.is_verified?'VERIFIED':'UNVERIFIED'}</time></div></div>`).join('');}
  async function loadMiniGraph(){try{const data=await api(`/api/graph?case_id=${state.caseId}`);const box=$('#miniGraph');if(!box||!window.cytoscape)return;box.innerHTML='';if(!data.nodes.length){box.innerHTML='<div class="empty-state">No people to map yet.</div>';return;}cytoscape({container:box,elements:[...data.nodes.map(n=>({data:{id:String(n.person_id),label:n.full_name,role:n.role}})),...data.edges.map((e,i)=>({data:{id:`m${i}`,source:String(e.source),target:String(e.target),label:e.label}}))],layout:{name:'cose',animate:false,fit:true,padding:25,randomize:true,nodeRepulsion:5000,idealEdgeLength:70},style:[{selector:'node',style:{'background-color':'#164d50','border-color':'#53e0d0','border-width':1.5,'label':'data(label)','color':'#c9efeb','font-size':9,'text-wrap':'wrap','text-max-width':70,'text-valign':'bottom','text-margin-y':7,'width':20,'height':20}},{selector:'edge',style:{'width':1,'line-color':'#3b7779','curve-style':'bezier','target-arrow-shape':'none','label':'data(label)','font-size':7,'color':'#78969d','text-background-color':'#0d1920','text-background-opacity':.8,'text-background-padding':2}}],userZoomingEnabled:false,userPanningEnabled:false,autoungrabify:true});}catch(e){/* mini graph is decorative enhancement; main data still works */}}
  async function openPerson(id){try{const p=await api(`/api/person/${id}?case_id=${state.caseId}`);$('#drawerId').textContent=`PERSON RECORD / ${String(p.person_id).padStart(3,'0')}`;$('#personDetailContent').innerHTML=`<div class="drawer-person-head">${personAvatar(p,52)}<div><h2>${esc(p.full_name)}</h2><p>${esc(p.occupation||'Occupation not recorded')}</p><span class="role-chip ${esc(p.role)}">${esc(p.role)}</span><div class="person-photo-actions" style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap"><input type="file" id="personPhotoInput" accept="image/png,image/jpeg,image/webp" style="max-width:220px"><button type="button" id="uploadPersonPhotoBtn">Upload / Change Photo</button><button type="button" id="removePersonPhotoBtn">Remove Photo</button></div></div></div><div class="drawer-section"><h3><i data-lucide="files"></i> Linked evidence <span class="count-badge">${p.evidence.length}</span></h3>${p.evidence.length?p.evidence.map(e=>`<div class="drawer-evidence"><strong>${esc(e.title)} <span class="muted">· ${esc(e.evidence_type)}</span></strong><p>${esc(e.description)}</p>${verifyPill(e.verification_status)}</div>`).join(''):'<div class="empty-state">No linked evidence for this person in this case.</div>'}</div><div class="drawer-section"><h3><i data-lucide="network"></i> Direct connections <span class="count-badge">${p.connections.length}</span></h3>${p.connections.length?p.connections.map(c=>`<button class="connection-chip" data-person="${c.connected_person_id}"><i data-lucide="user-round"></i>${esc(c.connected_person)} <span class="muted">· ${esc(c.relationship_type)}</span></button>`).join(''):'<div class="empty-state">No relationship records found.</div>'}</div><div class="drawer-section"><h3><i data-lucide="git-commit-horizontal"></i> Timeline events <span class="count-badge">${p.timeline.length}</span></h3>${p.timeline.length?p.timeline.map(t=>`<div class="drawer-evidence"><strong>${esc(t.location_name)} · ${fmtDateTime(t.event_time)}</strong><p>${esc(t.description)}</p><span class="verify-pill ${t.is_verified?'verified':'unverified'}">${t.is_verified?'verified':'unverified'}</span></div>`).join(''):'<div class="empty-state">No timeline events found.</div>'}</div>`;$('#detailBackdrop').classList.remove('hidden');$('#detailDrawer').classList.add('open');$('#uploadPersonPhotoBtn')?.addEventListener('click',()=>uploadPersonPhoto(p.person_id));$('#removePersonPhotoBtn')?.addEventListener('click',()=>removePersonPhoto(p.person_id));$$('[data-person]',$('#personDetailContent')).forEach(b=>b.addEventListener('click',()=>openPerson(b.dataset.person)));iconRefresh();}catch(e){toast(e.message,true);}}
  function closeDrawer(){$('#detailDrawer').classList.remove('open');$('#detailBackdrop').classList.add('hidden');}
  async function loadGraph(force=false){if(state.graph&&!force)return;try{const data=await api(`/api/graph?case_id=${state.caseId}`);state.graph=data;$('#graphCounts').textContent=`${data.nodes.length} NODES · ${data.edges.length} RELATIONSHIPS`;const box=$('#fullGraph');box.innerHTML='';if(!window.cytoscape){box.innerHTML='<div class="empty-state">Graph library unavailable. Check your internet connection.</div>';return;}if(!data.nodes.length){box.innerHTML='<div class="empty-state">No people or relationship records exist for this case.</div>';return;}if(state.graphInstance)state.graphInstance.destroy();state.graphInstance=cytoscape({container:box,elements:[...data.nodes.map(n=>({data:{id:String(n.person_id),label:n.full_name,role:n.role,occupation:n.occupation}})),...data.edges.map((e,i)=>({data:{id:`e${i}`,source:String(e.source),target:String(e.target),label:e.label}}))],layout:{name:'cose',animate:true,animationDuration:500,fit:true,padding:55,nodeRepulsion:8500,idealEdgeLength:130,edgeElasticity:100,gravity:.4},style:[{selector:'node',style:{'background-color':'#153e43','border-color':'#53e0d0','border-width':1.5,'label':'data(label)','color':'#d4f5ef','font-size':11,'font-family':'Manrope','font-weight':600,'text-wrap':'wrap','text-max-width':110,'text-valign':'bottom','text-margin-y':10,'width':36,'height':36,'overlay-opacity':0}},{selector:'node[role="suspect"]',style:{'border-color':'#ff7f91','background-color':'#44232e'}},{selector:'node[role="witness"]',style:{'border-color':'#72baff'}},{selector:'edge',style:{'width':1.5,'line-color':'#3e7477','curve-style':'bezier','label':'data(label)','font-size':9,'color':'#8da9b0','text-background-color':'#0b151d','text-background-opacity':.9,'text-background-padding':3}},{selector:'node:selected',style:{'border-width':4,'border-color':'#e6fff8','background-color':'#258b84'}}],minZoom:.2,maxZoom:2.5});state.graphInstance.on('tap','node',evt=>openPerson(evt.target.id()));await loadRelationships();}catch(e){toast(e.message,true)}}
  async function loadRelationships(){
    const graphBox = $('#fullGraph');
    if (!graphBox) return;
    let panel = $('#relationshipManager');
    if (!panel) {
      panel = document.createElement('section');
      panel.id = 'relationshipManager';
      panel.className = 'relationship-manager panel';
      graphBox.insertAdjacentElement('afterend', panel);
    }
    panel.innerHTML = '<div class="relationship-manager-head"><div><div class="eyebrow">CASE RECORDS</div><h3>Manage relationships</h3><p class="muted">Delete an incorrect relationship without deleting either person.</p></div><button type="button" class="btn btn-quiet" id="refreshRelationshipsBtn">Refresh</button></div><div class="relationship-list" id="relationshipList"><div class="empty-state">Loading relationships…</div></div>';
    $('#refreshRelationshipsBtn', panel)?.addEventListener('click', loadRelationships);
    try {
      const rows = await api(`/api/relationships?case_id=${state.caseId}`);
      const list = $('#relationshipList', panel);
      if (!rows.length) {
        list.innerHTML = '<div class="empty-state">No relationships recorded for this case.</div>';
        return;
      }
      list.innerHTML = rows.map(r => `<div class="relationship-row"><div class="relationship-row-copy"><strong>${esc(r.person_name)} <span class="relationship-arrow">↔</span> ${esc(r.related_person)}</strong><span class="relationship-type">${esc(r.relationship_type)}</span><small>Relationship ID: ${r.relationship_id}</small></div><button type="button" class="btn btn-danger-quiet" data-delete-relationship="${r.relationship_id}">Delete relationship</button></div>`).join('');
      $$('[data-delete-relationship]', list).forEach(button => button.addEventListener('click', async () => {
        const row = rows.find(r => Number(r.relationship_id) === Number(button.dataset.deleteRelationship));
        if (!row) return;
        if (!confirm(`Delete this relationship?\n\n${row.person_name} ↔ ${row.related_person}\nRelationship: ${row.relationship_type}\n\nNeither person will be deleted.`)) return;
        button.disabled = true;
        try {
          await api(`/api/relationships/${row.relationship_id}?case_id=${state.caseId}`, {method:'DELETE'});
          toast('Relationship deleted.');
          state.graph = null;
          await loadDashboard();
          await loadGraph(true);
          await loadRelationships();
        } catch (error) {
          toast(error.message, true);
          button.disabled = false;
        }
      }));
    } catch (error) {
      $('#relationshipList', panel).innerHTML = `<div class="empty-state">${esc(error.message)}</div>`;
    }
  }
  async function loadTimeline(){try{const rows=await api(`/api/timeline?case_id=${state.caseId}`);$('#timelineCount').textContent=`${rows.length} EVENTS`;const box=$('#fullTimeline');if(!rows.length){box.innerHTML='<div class="empty-state">No timeline events recorded for this case.</div>';return;}box.innerHTML=rows.map(t=>`<div class="timeline-row"><div class="timeline-rail"><span class="timeline-dot" style="${t.is_verified?'':'background:#ffca7a'}"></span></div><div><strong>${esc(t.full_name)} <span class="muted">at</span> ${esc(t.location_name)}</strong><p>${esc(t.description)}</p><time>${fmtDateTime(t.event_time)} · ${t.is_verified?'VERIFIED':'UNVERIFIED'}${t.source_evidence_title?' · SOURCE: '+esc(t.source_evidence_title):''}</time></div></div>`).join('');}catch(e){toast(e.message,true)}}
  function conflictMarkup(c,potential=false){return `<article class="conflict-card ${potential?'potential':'confirmed'}"><div class="conflict-top"><strong>${esc(c.full_name)}</strong><span class="verify-pill ${potential?'unverified':'disputed'}">${potential?'Needs review':'Confirmed conflict'}</span></div><p>Two records place the same person at different locations at the exact same timestamp.</p><div class="conflict-locations"><div class="conflict-location"><small>LOCATION A</small>${esc(c.location_one)}</div><span class="conflict-vs">VS</span><div class="conflict-location"><small>LOCATION B</small>${esc(c.location_two)}</div></div><p class="muted">${fmtDateTime(c.event_time)}<br>${esc(c.event_one)} / ${esc(c.event_two)}</p></article>`}
  async function loadConflicts(){try{const d=await api(`/api/contradictions?case_id=${state.caseId}`);$('#confirmedCount').textContent=d.confirmed.length;$('#potentialCount').textContent=d.potential.length;$('#confirmedConflicts').innerHTML=d.confirmed.length?d.confirmed.map(c=>conflictMarkup(c)).join(''):'<div class="empty-state">No confirmed conflicts match the strict rule.</div>';$('#potentialConflicts').innerHTML=d.potential.length?d.potential.map(c=>conflictMarkup(c,true)).join(''):'<div class="empty-state">No potential conflicts found for review.</div>';}catch(e){toast(e.message,true)}}
  async function runAnalysis(){go('analysis');await loadConflicts();toast('Timeline conflict analysis completed.');}
  function renderAllPeople(){if(!state.dashboard)return;renderPeople(state.dashboard.people,$('#allPeopleGrid'));}
  async function renderAllEvidence(){if(!state.dashboard)return;try{const all=await api(`/api/evidence?case_id=${state.caseId}`);const q=state.evidenceQuery.toLowerCase();const rows=all.filter(e=>(!state.evidenceFilter||e.verification_status==='verified')&&(!q||`${e.title} ${e.description} ${e.evidence_type} ${e.verification_status}`.toLowerCase().includes(q)));$('#evidenceTotal').textContent=`${rows.length} RECORD${rows.length===1?'':'S'}`;$('#allEvidence').innerHTML=rows.length?`<table class="data-table"><thead><tr><th>RECORD</th><th>TYPE</th><th>RECORDED</th><th>LINKED PEOPLE</th><th>STATUS / ACTIONS</th></tr></thead><tbody>${rows.map(e=>`<tr><td><strong>${esc(e.title)}</strong><small>${esc(e.description)}</small></td><td>${esc(e.evidence_type)}</td><td>${fmtDate(e.recorded_at)}</td><td>${(e.linked_people||[]).length}</td><td>${verifyPill(e.verification_status)}<div class="row-actions"><select aria-label="Change evidence status" data-evidence-status="${e.evidence_id}"><option value="">Change status…</option><option value="unverified">Unverified</option><option value="verified">Verified</option><option value="disputed">Disputed</option></select><button class="text-action" data-delete-evidence="${e.evidence_id}">Delete</button></div></td></tr>`).join('')}</tbody></table>`:'<div class="empty-state">No evidence matches these filters.</div>';$$('[data-evidence-status]').forEach(el=>el.addEventListener('change',async()=>{if(!el.value)return;try{await api(`/api/evidence/${el.dataset.evidenceStatus}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({case_id:state.caseId,verification_status:el.value})});toast('Evidence status updated.');await loadDashboard();await renderAllEvidence();if($('#view-analysis').classList.contains('active'))loadConflicts();}catch(e){toast(e.message,true)}}));$$('[data-delete-evidence]').forEach(el=>el.addEventListener('click',async()=>{if(!confirm('Delete this evidence record? A record referenced by a timeline event cannot be deleted.'))return;try{await api(`/api/evidence/${el.dataset.deleteEvidence}?case_id=${state.caseId}`,{method:'DELETE'});toast('Evidence deleted.');await loadDashboard();await renderAllEvidence();}catch(e){toast(e.message,true)}}));}catch(e){$('#allEvidence').innerHTML=`<div class="empty-state">${esc(e.message)}</div>`}}
  async function loadReport(){try{const d=await api(`/api/report?case_id=${state.caseId}`);const c=d.case;$('#reportPreview').innerHTML=`<div class="report-cover"><div class="eyebrow">CASEGRAPH · INVESTIGATION REPORT</div><h2>${esc(c.title)}</h2><p>${esc(c.description)}</p><div class="report-meta">Case #${c.case_id} · Status: ${esc(c.status)} · Created ${fmtDate(c.created_at)}</div></div><section class="report-section"><h3>People of interest (${d.people.length})</h3>${d.people.length?`<ul>${d.people.map(p=>`<li><strong>${esc(p.full_name)}</strong> — ${esc(p.occupation||'Occupation not recorded')}; role: ${esc(p.role)}</li>`).join('')}</ul>`:'<p>No people linked to this case.</p>'}</section><section class="report-section"><h3>Evidence inventory (${d.evidence.length})</h3>${d.evidence.length?`<ul>${d.evidence.map(e=>`<li><strong>${esc(e.title)}</strong> (${esc(e.evidence_type)}) — ${esc(e.verification_status)}. ${esc(e.description)}</li>`).join('')}</ul>`:'<p>No evidence recorded.</p>'}</section><section class="report-section"><h3>Timeline (${d.timeline.length} events)</h3>${d.timeline.length?`<ul>${d.timeline.map(t=>`<li><strong>${fmtDateTime(t.event_time)}</strong> — ${esc(t.full_name)} at ${esc(t.location_name)}: ${esc(t.description)} [${t.is_verified?'verified':'unverified'}]</li>`).join('')}</ul>`:'<p>No timeline events recorded.</p>'}</section><p class="muted">Generated from the CaseGraph PostgreSQL database. This is an educational report based on recorded data, not a real-world finding.</p>`;}catch(e){$('#reportPreview').innerHTML=`<div class="empty-state">${esc(e.message)}</div>`}}
  async function postJSON(url,data){return api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});}
  async function addPerson(){const full_name=prompt('Full name of the person:');if(!full_name)return;const occupation=prompt('Occupation (optional):','')||'';const genderInput=prompt('Gender for default avatar: male, female, or blank for initials','');if(genderInput===null)return;const gender=genderInput.trim().toLowerCase();if(gender&&!['male','female'].includes(gender)){toast('Enter male, female, or leave blank.',true);return;}const role=prompt('Case role: suspect, witness, investigator, or other','witness')||'other';try{await postJSON('/api/people',{case_id:state.caseId,full_name,occupation,gender:gender||null,role});toast('Person created and linked to the case.');await loadDashboard();renderAllPeople();}catch(e){toast(e.message,true)}}
  async function addEvidence(){const title=prompt('Evidence title:');if(!title)return;const description=prompt('Describe what this record says (avoid conclusions not supported by it):');if(!description)return;const evidence_type=prompt('Type (e.g. access_log, statement, message, photograph, document):','document')||'document';const verification_status=prompt('Status: unverified, verified, or disputed','unverified')||'unverified';const people=state.dashboard?.people||[];let linked=[];if(people.length){const list=people.map(p=>`${p.person_id}: ${p.full_name}`).join('\\n');const ids=prompt(`Optional linked person IDs, comma-separated. Available:
${list}`,'');if(ids)linked=ids.split(',').map(x=>parseInt(x.trim(),10)).filter(Number.isInteger).map(person_id=>({person_id,involvement:'associated'}));}try{await postJSON('/api/evidence',{case_id:state.caseId,title,description,evidence_type,verification_status,people:linked});toast('Evidence saved to PostgreSQL.');await loadDashboard();await renderAllEvidence();}catch(e){toast(e.message,true)}}
  async function addRelationship(){const people=state.dashboard?.people||[];if(people.length<2){toast('Add at least two people first.',true);return;}const choices=people.map(p=>`${p.person_id}: ${p.full_name}`).join('\\n');const person_id=Number(prompt(`First person ID:
${choices}`,'')||0);if(!person_id)return;const related_person_id=Number(prompt(`Second person ID:
${choices}`,'')||0);if(!related_person_id)return;const relationship_type=prompt('Describe the recorded relationship (e.g. colleague, messaged, supervisor of):','known associate');if(!relationship_type)return;try{await postJSON('/api/relationships',{case_id:state.caseId,person_id,related_person_id,relationship_type});toast('Relationship saved.');state.graph=null;await loadDashboard();await loadGraph(true);await loadRelationships();}catch(e){toast(e.message,true)}}
  async function addTimeline(){const people=state.dashboard?.people||[];if(!people.length){toast('Add a person first.',true);return;}const choices=people.map(p=>`${p.person_id}: ${p.full_name}`).join('\\n');const person_id=Number(prompt(`Person ID for event:
${choices}`,'')||0);if(!person_id)return;const event_time=prompt('Event timestamp (YYYY-MM-DD HH:MM:SS):',new Date().toISOString().slice(0,19).replace('T',' '));if(!event_time)return;const location_name=prompt('Location name:');if(!location_name)return;const description=prompt('What does the record say?');if(!description)return;const source_evidence_id=prompt('Source evidence ID (optional; leave blank if none):','');const is_verified=confirm('Mark this timeline event verified? Only do this if the source has been reviewed.');try{await postJSON('/api/timeline',{case_id:state.caseId,person_id,event_time,location_name,description,source_evidence_id:source_evidence_id||null,is_verified});toast('Timeline event saved.');await loadDashboard();loadTimeline();loadConflicts();}catch(e){toast(e.message,true)}}
  async function findPath(){const people=state.dashboard?.people||[];if(people.length<2){toast('Need at least two people.',true);return;}const choices=people.map(p=>`${p.person_id}: ${p.full_name}`).join('\\n');const from=Number(prompt(`Start person ID:
${choices}`,'')||0);if(!from)return;const to=Number(prompt(`Target person ID:
${choices}`,'')||0);if(!to)return;try{const result=await api(`/api/analysis/paths?case_id=${state.caseId}&from_person=${from}&to_person=${to}`);if(result.found)alert(`Relationship path (${result.depth} connection(s)):

${result.names.join(' → ')}

Recorded relationship labels: ${result.relationships.join(' → ')}`);else alert(result.message);}catch(e){toast(e.message,true)}}
  async function uploadPersonPhoto(personId){const input=$('#personPhotoInput');if(!input?.files?.length){toast('Choose a photo first.',true);return;}const file=input.files[0];if(!['image/png','image/jpeg','image/webp'].includes(file.type)){toast('Choose a PNG, JPG, or WEBP image.',true);return;}if(file.size>5*1024*1024){toast('Photo must be 5 MB or smaller.',true);return;}const data=new FormData();data.append('photo',file);try{await api(`/api/people/${personId}/photo`,{method:'POST',body:data});toast('Person photo updated.');await loadDashboard();await openPerson(personId);}catch(e){toast(e.message,true);}}
  async function removePersonPhoto(personId){if(!confirm("Remove this person's photo?"))return;try{await api(`/api/people/${personId}/photo`,{method:'DELETE'});toast('Person photo removed.');await loadDashboard();await openPerson(personId);}catch(e){toast(e.message,true);}}

  function getActiveSessionStorageKey(){
    return `casegraph_active_session_${state.caseId || 6}`;
  }

  async function loadInterviewView(forceReload = false){
    const storedSessionId = localStorage.getItem(getActiveSessionStorageKey());
    if(!storedSessionId){
      state.sessionData = null;
      renderInterviewRoom();
      return;
    }
    if(state.sessionData && state.sessionData.session?.session_id === storedSessionId && !forceReload){
      renderInterviewRoom();
      return;
    }
    try{
      const data = await api(`/api/game/session/${storedSessionId}`);
      state.sessionData = data;
      renderInterviewRoom();
    }catch(e){
      console.warn('Could not load session from storage:', e);
      localStorage.removeItem(getActiveSessionStorageKey());
      state.sessionData = null;
      renderInterviewRoom();
    }
  }

  function renderInterviewRoom(){
    const data = state.sessionData;
    const sessionBadge = $('#sessionBadge');
    const startBtn = $('#startSessionBtn');
    const scoreEl = $('#gameScore');
    const charsEl = $('#gameChars');
    const cluesEl = $('#gameClues');
    const insightsEl = $('#gameInsights');
    const rosterList = $('#rosterList');
    const rosterCount = $('#rosterCount');
    const transcript = $('#dialogueTranscript');
    const questionInput = $('#interviewQuestion');
    const askBtn = $('#interviewSubmitBtn');
    const quickChips = $('#quickChips');
    const insightSel = $('#insightDialogueSelect');
    const catSel = $('#insightCategorySelect');
    const notesInput = $('#insightNotes');
    const insightBtn = $('#insightSubmitBtn');
    const notesCount = $('#sessionNotesCount');
    const notesList = $('#sessionNotesList');

    if(!data || !data.session){
      if(sessionBadge){
        sessionBadge.textContent = 'NO ACTIVE SESSION';
        sessionBadge.className = 'status-pill';
      }
      if(startBtn) startBtn.innerHTML = '<i data-lucide="play"></i> Start / Resume Session';
      if(scoreEl) scoreEl.textContent = '0';
      if(charsEl) charsEl.textContent = '0 / 10';
      if(cluesEl) cluesEl.textContent = '0 / 12';
      if(insightsEl) insightsEl.textContent = '0';
      if(rosterCount) rosterCount.textContent = '0';
      if(rosterList) rosterList.innerHTML = '<div class="empty-state" style="padding:15px;text-align:center">Click <strong>Start / Resume Session</strong> above to begin your investigation.</div>';
      if(transcript) transcript.innerHTML = '<div class="empty-state">Start or resume an investigation session to interview witnesses.</div>';
      if(questionInput) { questionInput.disabled = true; questionInput.value = ''; }
      if(askBtn) askBtn.disabled = true;
      if(quickChips) quickChips.innerHTML = '<span class="muted" style="font-size:11px">Start a session to view specialized inquiry topics.</span>';
      if(insightSel) { insightSel.disabled = true; insightSel.innerHTML = '<option value="">Select a statement from transcript...</option>'; }
      if(catSel) { catSel.disabled = true; catSel.value = ''; }
      if(notesInput) { notesInput.disabled = true; notesInput.value = ''; }
      if(insightBtn) insightBtn.disabled = true;
      if(notesCount) notesCount.textContent = '0';
      if(notesList) notesList.innerHTML = '<div class="empty-state">No notes documented yet.</div>';
      $('#interrogatedRole').textContent = 'SELECT A CHARACTER';
      $('#interrogatedName').textContent = 'No person selected';
      $('#interrogatedBio').textContent = 'Choose a character from the directory to begin questioning.';
      if($('#progressPercent')) $('#progressPercent').textContent = '0%';
      if($('#progressBarFill')) $('#progressBarFill').style.width = '0%';
      if($('#investigationStageBadge')){
        $('#investigationStageBadge').textContent = 'INITIAL RECONNAISSANCE';
        $('#investigationStageBadge').className = 'status-pill';
      }
      iconRefresh();
      return;
    }

    // Session is active
    const isSolved = data.session.status === 'solved';
    if(sessionBadge){
      sessionBadge.textContent = `${data.session.player_label || 'INVESTIGATOR'} · ${String(data.session.status||'active').toUpperCase()}`;
      sessionBadge.className = `status-pill ${isSolved ? 'open' : 'investigating'}`;
    }
    if(startBtn) startBtn.innerHTML = '<i data-lucide="rotate-ccw"></i> Session Options';
    if(scoreEl) scoreEl.textContent = String(data.score ?? 0);
    if(charsEl) charsEl.textContent = `${data.characters_found ?? 0} / ${data.characters_total ?? 10}`;
    if(cluesEl) cluesEl.textContent = `${data.clues_found ?? 0} / ${data.clues_total ?? 12}`;
    if(insightsEl) insightsEl.textContent = String(data.insights_count ?? data.insights?.length ?? 0);

    // Compute Case Readiness Meter
    const charsFound = data.characters_found || 0;
    const cluesFound = data.clues_found || 0;
    const insightsValid = (data.insights || []).filter(i => i.is_valid).length;
    const officialRecords = (data.evidence_count || 0) + (data.relationship_count || 0) + (data.timeline_count || 0);

    const pct = isSolved ? 100 : Math.min(100, Math.round(
      (cluesFound / 12) * 35 +
      (charsFound / 9) * 25 +
      (insightsValid / 6) * 20 +
      (officialRecords / 3) * 20
    ));

    let stageLabel = 'INITIAL RECONNAISSANCE';
    let stageClass = 'status-pill';
    if(isSolved){
      stageLabel = 'CASE SOLVED · CONVICTION SECURED';
      stageClass = 'status-pill open';
    } else if(pct >= 75){
      stageLabel = 'READY FOR FINAL ACCUSATION';
      stageClass = 'status-pill open';
    } else if(pct >= 45){
      stageLabel = 'CASE FORMING · KEY LEADS UNLOCKED';
      stageClass = 'status-pill open';
    } else if(pct >= 20){
      stageLabel = 'EVIDENCE ACCUMULATION';
      stageClass = 'status-pill';
    }

    if($('#progressPercent')) $('#progressPercent').textContent = `${pct}%`;
    if($('#progressBarFill')) $('#progressBarFill').style.width = `${pct}%`;
    if($('#investigationStageBadge')){
      $('#investigationStageBadge').textContent = stageLabel;
      $('#investigationStageBadge').className = stageClass;
    }

    // Characters Roster
    const chars = data.characters || [];
    if(rosterCount) rosterCount.textContent = String(chars.length);
    if(!state.selectedPersonId && chars.length > 0){
      state.selectedPersonId = chars[0].person_id;
    }

    if(rosterList){
      rosterList.innerHTML = chars.map(c => {
        const isSel = Number(c.person_id) === Number(state.selectedPersonId);
        const name = esc(c.full_name);
        const role = esc(c.occupation || 'Witness');
        return `<button type="button" class="roster-item ${isSel ? 'active' : ''}" data-person-id="${c.person_id}">
          ${personAvatar(c, 34)}
          <div style="flex:1;min-width:0;text-align:left">
            <strong style="display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:12px">${name}</strong>
            <small class="muted" style="display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:10px">${role}</small>
          </div>
          ${c.discovered ? '<span class="status-pill open" style="font-size:9px;padding:2px 6px">DISCOVERED</span>' : ''}
        </button>`;
      }).join('');

      $$('.roster-item', rosterList).forEach(btn => {
        btn.addEventListener('click', () => {
          state.selectedPersonId = Number(btn.dataset.personId);
          renderInterviewRoom();
        });
      });
    }

    // Active character details
    const activeChar = chars.find(c => Number(c.person_id) === Number(state.selectedPersonId));
    if(activeChar){
      $('#interrogatedRole').textContent = (activeChar.occupation || 'WITNESS').toUpperCase();
      $('#interrogatedName').textContent = activeChar.full_name;
      $('#interrogatedBio').textContent = activeChar.public_bio || 'No public background recorded.';
      if(questionInput) questionInput.disabled = false;
      if(askBtn) askBtn.disabled = false;
      if(insightSel) insightSel.disabled = false;
      if(catSel) catSel.disabled = false;
      if(notesInput) notesInput.disabled = false;
      if(insightBtn) insightBtn.disabled = false;

      // Populate Dynamic Character Topic Chips
      if(quickChips){
        const topics = activeChar.topics || [];
        if(!topics.length){
          quickChips.innerHTML = '<span class="muted" style="font-size:11px">Dr. Voss is deceased. His recorded files and notebook contain his statements.</span>';
        } else {
          quickChips.innerHTML = topics.map(t => {
            const q = esc(t.sample_question || t.display_label);
            const isAsked = t.asked;
            return `<button type="button" class="topic-chip ${isAsked ? 'asked' : ''}" data-q="${q}">
              <i data-lucide="${isAsked ? 'check' : 'help-circle'}" style="width:11px;height:11px;display:inline-block;vertical-align:-1px"></i>
              <span>${esc(t.display_label)}</span>
              ${isAsked ? '<small style="opacity:.7;font-size:9px">(Asked)</small>' : ''}
            </button>`;
          }).join('');

          $$('.topic-chip', quickChips).forEach(b => {
            b.addEventListener('click', () => {
              if(b.dataset.q) handleAskQuestion(b.dataset.q);
            });
          });
        }
      }
    } else {
      $('#interrogatedRole').textContent = 'SELECT A CHARACTER';
      $('#interrogatedName').textContent = 'No person selected';
      $('#interrogatedBio').textContent = 'Choose a character from the directory to begin questioning.';
      if(questionInput) questionInput.disabled = true;
      if(askBtn) askBtn.disabled = true;
      if(quickChips) quickChips.innerHTML = '<span class="muted" style="font-size:11px">Select a character above to view specialized inquiry topics.</span>';
      if(insightSel) insightSel.disabled = true;
      if(catSel) catSel.disabled = true;
      if(notesInput) notesInput.disabled = true;
      if(insightBtn) insightBtn.disabled = true;
    }

    // Render Transcript for selected character
    const charHistory = (data.history || []).filter(h => Number(h.person_id) === Number(state.selectedPersonId));
    if(transcript){
      if(!charHistory.length){
        transcript.innerHTML = `<div class="empty-state">No testimony recorded for ${activeChar ? esc(activeChar.full_name) : 'this person'} yet. Click any topic chip above or type your question to interrogate them.</div>`;
      } else {
        transcript.innerHTML = charHistory.map(h => `
          <div class="chat-bubble player">
            <span class="chat-bubble-speaker">Investigator</span>
            <div>${esc(h.player_question)}</div>
          </div>
          <div class="chat-bubble character">
            <span class="chat-bubble-speaker">${esc(h.person_name || 'Witness')}${h.topic_label ? ` · <span style="color:var(--cyan)">${esc(h.topic_label)}</span>` : ''}</span>
            <div>${esc(h.response_shown)}</div>
            <div class="chat-bubble-actions">
              <button type="button" class="chat-flag-btn" data-dialogue-id="${h.dialogue_id}" data-topic-id="${h.topic_id || ''}" data-label="${esc((h.topic_label || h.response_shown).slice(0, 40))}">
                <i data-lucide="flag" style="width:10px;height:10px;display:inline-block;vertical-align:-1px;margin-right:3px"></i>Flag Insight
              </button>
            </div>
          </div>
        `).join('');
        transcript.scrollTop = transcript.scrollHeight;

        $$('.chat-flag-btn', transcript).forEach(btn => {
          btn.addEventListener('click', () => {
            const did = btn.dataset.dialogueId;
            if(insightSel){
              insightSel.value = did;
            }
            if(catSel){
              catSel.focus();
            }
            toast(`Cited statement #${did}. Choose an insight category.`);
          });
        });
      }
    }

    // Populate insight statement dropdown
    if(insightSel){
      const currentVal = insightSel.value;
      if(!charHistory.length){
        insightSel.innerHTML = '<option value="">No statements for this person yet</option>';
      } else {
        insightSel.innerHTML = '<option value="">Select a statement from transcript...</option>' +
          charHistory.map(h => `<option value="${h.dialogue_id}" data-topic-id="${h.topic_id || ''}" ${String(h.dialogue_id) === String(currentVal) ? 'selected' : ''}>[#${h.dialogue_id}] ${esc((h.topic_label ? `${h.topic_label}: ` : '') + h.response_shown.slice(0, 75))}...</option>`).join('');
      }
    }

    // Render session notes list
    const insights = data.insights || [];
    if(notesCount) notesCount.textContent = String(insights.length);
    if(notesList){
      if(!insights.length){
        notesList.innerHTML = '<div class="empty-state" style="padding:10px;text-align:center">No insights or case notes documented yet.</div>';
      } else {
        notesList.innerHTML = [...insights].reverse().map(ins => `
          <article class="insight-card ${ins.is_valid ? 'verified' : 'unverified'}">
            <div class="insight-card-top">
              <strong>${esc(ins.person_name)}</strong>
              <span class="mono" style="font-size:9px;color:${ins.is_valid ? 'var(--cyan)' : 'var(--amber)'}">${ins.is_valid ? '✓ VERIFIED (+10)' : '• NOTE (0)'}</span>
            </div>
            <div style="margin-bottom:3px">
              <span class="tag tag-quiet" style="font-size:9px;padding:2px 6px">${esc(ins.category || ins.insight_type || 'note')}</span>
              ${ins.topic_label ? `<span class="muted" style="margin-left:4px;font-size:10px">· ${esc(ins.topic_label)}</span>` : ''}
            </div>
            ${ins.matched_clue_key ? `<div style="color:var(--cyan);font-weight:600;font-size:10px;margin-top:2px">Clue lead: ${esc(ins.matched_clue_key)} - ${esc(ins.matched_clue_title || '')}</div>` : ''}
            ${ins.player_notes ? `<p class="muted" style="margin:4px 0 0;font-style:italic;font-size:10px">"${esc(ins.player_notes)}"</p>` : ''}
          </article>
        `).join('');
      }
    }

    // Render Subtab: Clues & Connections
    const cluesGrid = $('#cluesListGrid');
    const cluesFoundCount = $('#subtabCluesCount');
    const cluesFoundBadge = $('#cluesFoundBadge');
    if(cluesFoundCount) cluesFoundCount.textContent = `${data.clues_found || 0}`;
    if(cluesFoundBadge) cluesFoundBadge.textContent = `${data.clues_found || 0} / ${data.clues_total || 12} UNLOCKED`;

    if(cluesGrid){
      const clues = data.clues || [];
      if(!clues.length){
        cluesGrid.innerHTML = '<div class="empty-state">No clues unlocked yet. Question witnesses and flag deductions to discover leads.</div>';
      } else {
        cluesGrid.innerHTML = clues.map(c => {
          const isDisc = c.discovered;
          const isRec = c.recorded;
          return `
            <article class="clue-card ${isDisc ? 'discovered' : 'locked'}">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <div style="display:flex;gap:6px;align-items:center">
                  <span class="clue-badge" style="background:#153638;color:var(--cyan);border:1px solid #285e5b">${esc(c.clue_key)}</span>
                  <span class="tag tag-quiet" style="font-size:9px">${esc(c.clue_category || 'clue')}</span>
                </div>
                ${isDisc 
                  ? (isRec ? '<span class="status-pill open" style="font-size:9px;padding:2px 7px">RECORDED IN POSTGRESQL</span>' : '<span class="status-pill" style="font-size:9px;padding:2px 7px;color:var(--amber)">UNFILED LEAD (+5 PTS)</span>')
                  : '<span class="status-pill" style="font-size:9px;padding:2px 7px;opacity:.6">LOCKED</span>'}
              </div>
              <strong style="font-size:13px;color:${isDisc ? 'var(--text)' : 'var(--muted)'}">${esc(c.title)}</strong>
              <p class="muted" style="font-size:11px;line-height:1.5;margin:0">
                ${isDisc ? esc(c.public_description) : 'Discover this clue by interrogating suspects and flagging verified insights at the Deduction Desk.'}
              </p>
              ${isDisc ? `
                <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:auto;padding-top:8px;border-top:1px solid #162633">
                  ${!isRec ? `
                    <button type="button" class="btn btn-primary btn-sm file-clue-btn" data-clue-id="${c.clue_id}" data-title="${esc(c.title)}" data-desc="${esc(c.public_description)}" data-cat="${esc(c.clue_category || 'document')}">
                      <i data-lucide="folder-plus"></i> File in Evidence Vault (+5 pts)
                    </button>
                  ` : `
                    <button type="button" class="btn btn-quiet btn-sm" data-go="evidence">
                      <i data-lucide="eye"></i> View in Evidence Vault
                    </button>
                  `}
                  <button type="button" class="btn btn-quiet btn-sm add-clue-timeline-btn" data-clue-id="${c.clue_id}" data-title="${esc(c.title)}" data-desc="${esc(c.public_description)}">
                    <i data-lucide="calendar-plus"></i> Add to Timeline
                  </button>
                </div>
              ` : ''}
            </article>
          `;
        }).join('');

        $$('.file-clue-btn', cluesGrid).forEach(btn => {
          btn.addEventListener('click', async () => {
            await handleFileClueAsEvidence(Number(btn.dataset.clueId), btn.dataset.title, btn.dataset.desc, btn.dataset.cat);
          });
        });

        $$('.add-clue-timeline-btn', cluesGrid).forEach(btn => {
          btn.addEventListener('click', async () => {
            await handleAddClueToTimeline(Number(btn.dataset.clueId), btn.dataset.title, btn.dataset.desc);
          });
        });
      }
    }

    // Render Subtab: Detective Notebook Suspect Matrix
    const notebookGrid = $('#notebookSuspectsGrid');
    if(notebookGrid && data.characters){
      $('#notebookSuspectsCount').textContent = `${data.characters.length} STAFF`;
      notebookGrid.innerHTML = data.characters.map(c => `
        <article class="panel" style="padding:14px;background:#0d1720;border-radius:10px">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
            ${personAvatar(c, 36)}
            <div>
              <strong style="font-size:12px;display:block">${esc(c.full_name)}</strong>
              <small class="muted" style="font-size:10px">${esc(c.occupation || 'Staff')}</small>
            </div>
          </div>
          <p style="font-size:11px;color:var(--text);margin:0 0 8px;line-height:1.5">${esc(c.public_bio || 'No public statement recorded.')}</p>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span class="tag ${c.discovered ? 'tag-cyan' : 'tag-quiet'}" style="font-size:9px">
              ${c.discovered ? 'INTERROGATED' : 'NOT INTERVIEWED'}
            </span>
            <button type="button" class="btn btn-quiet btn-sm switch-to-interrogate-btn" data-person-id="${c.person_id}">Question Person ↗</button>
          </div>
        </article>
      `).join('');

      $$('.switch-to-interrogate-btn', notebookGrid).forEach(b => {
        b.addEventListener('click', () => {
          state.selectedPersonId = Number(b.dataset.personId);
          $$('.game-subnav-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.subtab === 'interrogate'));
          $$('.game-subtab').forEach(st => st.classList.add('hidden'));
          $('#subtab-interrogate')?.classList.remove('hidden');
          renderInterviewRoom();
        });
      });
    }

    // If case is solved, show modal trigger banner or auto-show
    if(isSolved && data.solution){
      if(!$('#solvedBannerAction')){
        const btn = document.createElement('button');
        btn.id = 'solvedBannerAction';
        btn.className = 'btn btn-primary';
        btn.style.background = 'linear-gradient(90deg,#208985,#53e0d0)';
        btn.innerHTML = '<i data-lucide="award"></i> View Solved Case Verdict ↗';
        btn.addEventListener('click', () => renderVerdictModal(data));
        $('.heading-actions', $('#view-interviews'))?.prepend(btn);
      }
    }

    iconRefresh();
  }

  async function handleStartSession(){
    const storedId = localStorage.getItem(getActiveSessionStorageKey());
    if(!state.sessionData && !storedId){
      try{
        const res = await api('/api/game/001/start', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ player_label: 'Lead Investigator' })
        });
        localStorage.setItem(getActiveSessionStorageKey(), res.session.session_id);
        state.sessionData = res;
        state.selectedPersonId = res.characters[0]?.person_id || null;
        renderInterviewRoom();
        toast('Investigation session started.');
      }catch(e){
        toast(e.message, true);
      }
      return;
    }

    // If session is already loaded or stored
    const currentId = state.sessionData?.session?.session_id || storedId;
    const choice = prompt(
      `Active Session:\n${currentId}\n\n- Click OK to resume this session\n- Type "NEW" to start a fresh investigation\n- Or paste an existing Session UUID to switch:`,
      ''
    );
    if(choice === null) return;
    const trimmed = choice.trim();

    if(!trimmed){
      if(storedId && (!state.sessionData || state.sessionData.session?.session_id !== storedId)){
        await loadInterviewView(true);
      }
      toast('Resumed active session.');
      return;
    }

    if(trimmed.toUpperCase() === 'NEW'){
      try{
        const res = await api('/api/game/001/start', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ player_label: 'Lead Investigator' })
        });
        localStorage.setItem(getActiveSessionStorageKey(), res.session.session_id);
        state.sessionData = res;
        state.selectedPersonId = res.characters[0]?.person_id || null;
        renderInterviewRoom();
        toast('New investigation session started.');
      }catch(e){
        toast(e.message, true);
      }
      return;
    }

    try{
      const res = await api(`/api/game/session/${trimmed}`);
      localStorage.setItem(getActiveSessionStorageKey(), res.session.session_id);
      state.sessionData = res;
      state.selectedPersonId = res.characters[0]?.person_id || null;
      renderInterviewRoom();
      toast('Switched to session ' + trimmed.slice(0, 8) + '...');
    }catch(e){
      toast('Invalid session ID or session not found.', true);
    }
  }

  async function handleAskQuestion(customQuestion = null){
    if(!state.sessionData?.session?.session_id){
      toast('Start or resume an investigation session first.', true);
      return;
    }
    if(!state.selectedPersonId){
      toast('Select a character to interview.', true);
      return;
    }
    const qInput = $('#interviewQuestion');
    const question = customQuestion || qInput?.value?.trim();
    if(!question){
      toast('Please enter a question.', true);
      return;
    }

    const askBtn = $('#interviewSubmitBtn');
    if(askBtn) askBtn.disabled = true;
    if(qInput) qInput.disabled = true;

    try{
      const res = await api(`/api/game/session/${state.sessionData.session.session_id}/interview`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          person_id: state.selectedPersonId,
          question: question
        })
      });

      if(res.state){
        state.sessionData = res.state;
      }
      if(qInput) qInput.value = '';
      renderInterviewRoom();

      if(res.dialogue_id){
        const insightSel = $('#insightDialogueSelect');
        if(insightSel) insightSel.value = String(res.dialogue_id);
      }

      toast('Testimony recorded.');
    }catch(e){
      toast(e.message, true);
    }finally{
      if(askBtn) askBtn.disabled = false;
      if(qInput){
        qInput.disabled = false;
        qInput.focus();
      }
    }
  }

  async function handleSubmitInsight(e){
    if(e) e.preventDefault();
    if(!state.sessionData?.session?.session_id){
      toast('Start or resume an investigation session first.', true);
      return;
    }
    if(!state.selectedPersonId){
      toast('Select a character first.', true);
      return;
    }

    const catSel = $('#insightCategorySelect');
    const category = catSel?.value;
    if(!category){
      toast('Please select an insight category.', true);
      return;
    }

    const insightSel = $('#insightDialogueSelect');
    const selectedOpt = insightSel?.selectedOptions?.[0];
    const dialogueId = insightSel?.value ? Number(insightSel.value) : null;
    const topicId = selectedOpt?.dataset?.topicId ? Number(selectedOpt.dataset.topicId) : null;
    const notesInput = $('#insightNotes');
    const notes = notesInput?.value?.trim() || '';

    const btn = $('#insightSubmitBtn');
    if(btn) btn.disabled = true;

    try{
      const res = await api(`/api/game/session/${state.sessionData.session.session_id}/insight`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          person_id: state.selectedPersonId,
          dialogue_id: dialogueId,
          topic_id: topicId,
          category: category,
          player_notes: notes
        })
      });

      const fb = $('#insightFeedback');
      if(fb){
        fb.style.display = 'block';
        if(res.is_valid){
          fb.className = 'panel';
          fb.style.borderColor = 'var(--cyan)';
          fb.style.background = 'rgba(83, 224, 208, 0.08)';
          fb.style.padding = '10px 12px';
          fb.style.borderRadius = '8px';
          fb.innerHTML = `
            <div style="display:flex;align-items:flex-start;gap:8px">
              <i data-lucide="check-circle-2" style="color:var(--cyan);width:16px;height:16px;min-width:16px;margin-top:2px"></i>
              <div>
                <strong style="color:var(--cyan);font-size:12px">Breakthrough Validated! (+${res.points_awarded || 10} pts)</strong>
                <p style="font-size:11px;margin:3px 0 0;color:var(--text)">${esc(res.explanation || res.message)}</p>
              </div>
            </div>`;
        } else if(res.status === 'already_verified'){
          fb.className = 'panel';
          fb.style.borderColor = 'var(--amber)';
          fb.style.background = 'rgba(224, 184, 83, 0.08)';
          fb.style.padding = '10px 12px';
          fb.style.borderRadius = '8px';
          fb.innerHTML = `
            <div style="display:flex;align-items:flex-start;gap:8px">
              <i data-lucide="alert-triangle" style="color:var(--amber);width:16px;height:16px;min-width:16px;margin-top:2px"></i>
              <div>
                <strong style="color:var(--amber);font-size:12px">Already Verified</strong>
                <p style="font-size:11px;margin:3px 0 0;color:var(--text)">${esc(res.message)}</p>
              </div>
            </div>`;
        } else {
          fb.className = 'panel';
          fb.style.borderColor = 'var(--line)';
          fb.style.background = 'rgba(255, 255, 255, 0.03)';
          fb.style.padding = '10px 12px';
          fb.style.borderRadius = '8px';
          fb.innerHTML = `
            <div style="display:flex;align-items:flex-start;gap:8px">
              <i data-lucide="info" style="color:var(--muted);width:16px;height:16px;min-width:16px;margin-top:2px"></i>
              <div>
                <strong style="font-size:12px">Case Note Recorded (0 pts)</strong>
                <p style="font-size:11px;margin:3px 0 0;color:var(--muted)">${esc(res.message)}</p>
              </div>
            </div>`;
        }
      }

      if(res.state){
        state.sessionData = res.state;
      }
      renderInterviewRoom();

      if(res.is_valid){
        toast('Insight validated! Clue unlocked.');
      } else {
        toast('Note documented in file.');
      }

      if(notesInput) notesInput.value = '';
    }catch(e){
      toast(e.message, true);
    }finally{
      if(btn) btn.disabled = false;
      iconRefresh();
    }
  }
  async function handleFileClueAsEvidence(clueId, title, desc, cat){
    if(!state.sessionData?.session?.session_id){
      toast('Start or resume an investigation session first.', true);
      return;
    }
    try{
      const res = await api(`/api/game/session/${state.sessionData.session.session_id}/record-official`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          action: 'evidence',
          title: title,
          description: desc,
          evidence_type: cat || 'document',
          verification_status: 'verified',
          clue_id: clueId,
          people: []
        })
      });
      toast('Official evidence record created in PostgreSQL (+5 pts).');
      if(res.state) state.sessionData = res.state;
      renderInterviewRoom();
      await loadDashboard();
    }catch(e){
      toast(e.message, true);
    }
  }

  async function handleAddClueToTimeline(clueId, title, desc){
    if(!state.sessionData?.session?.session_id){
      toast('Start or resume an investigation session first.', true);
      return;
    }
    const chars = state.sessionData?.characters || [];
    const charChoices = chars.map(c => `${c.person_id}: ${c.full_name}`).join('\n');
    const personIdStr = prompt(`Link timeline event to which person?\n${charChoices}`, String(chars[0]?.person_id || ''));
    if(!personIdStr) return;
    const personId = Number(personIdStr);
    if(!personId) return;

    const eventTime = prompt('Event timestamp (YYYY-MM-DD HH:MM:SS):', '2026-10-29 22:15:00');
    if(!eventTime) return;
    const loc = prompt('Location name:', 'Blackridge Observatory');
    if(!loc) return;

    try{
      const res = await api(`/api/game/session/${state.sessionData.session.session_id}/record-official`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          action: 'timeline',
          person_id: personId,
          event_time: eventTime,
          location_name: loc,
          description: desc || title,
          is_verified: true
        })
      });
      toast('Timeline event saved to PostgreSQL (+5 pts).');
      if(res.state) state.sessionData = res.state;
      renderInterviewRoom();
      await loadDashboard();
    }catch(e){
      toast(e.message, true);
    }
  }

  function populateAccuseModal(){
    const sel = $('#accusePersonSelect');
    if(!sel) return;
    const chars = state.sessionData?.characters || [];
    sel.innerHTML = '<option value="">Select suspect from interrogated roster...</option>' +
      chars.map(c => `<option value="${c.person_id}">${esc(c.full_name)} (${esc(c.occupation || 'Staff')})${c.discovered ? ' · [Interrogated]' : ' · [Not yet interviewed]'}</option>`).join('');
  }

  function renderVerdictModal(data){
    if(!data) return;
    const isSolved = data.session?.status === 'solved' || data.correct;
    const modal = $('#verdictModalBackdrop');
    if(!modal) return;

    const eyebrow = $('#verdictEyebrow');
    const heading = $('#verdictHeading');
    const sub = $('#verdictSub');
    const finalScoreEl = $('#verdictFinalScore');
    const rankBadge = $('#verdictRankBadge');
    const banner = $('#verdictBanner');
    const solutionSec = $('#verdictSolutionSection');
    const scoreList = $('#verdictScoreEventsList');

    const score = data.score ?? data.state?.score ?? 0;
    if(finalScoreEl) finalScoreEl.textContent = `${score} PTS`;

    // Rank determination
    let rank = 'RANK: JUNIOR SLEUTH (C)';
    if(score >= 180) rank = 'RANK: MASTER INVESTIGATOR (A+)';
    else if(score >= 140) rank = 'RANK: SENIOR DETECTIVE (A)';
    else if(score >= 100) rank = 'RANK: DETECTIVE INSPECTOR (B+)';
    else if(score >= 60) rank = 'RANK: INVESTIGATIVE ANALYST (B)';
    if(rankBadge) rankBadge.textContent = rank;

    if(isSolved){
      if(eyebrow) { eyebrow.textContent = 'CASE STATUS: SOLVED'; eyebrow.style.color = 'var(--green)'; }
      if(heading) { heading.textContent = 'CONVICTION SECURED'; heading.style.color = 'var(--cyan)'; }
      if(sub) sub.textContent = 'The charges and evidence have been verified by university oversight.';
      if(banner) { banner.style.borderLeftColor = 'var(--green)'; banner.style.background = '#08181a'; }
      if(solutionSec) solutionSec.style.display = 'block';

      const sol = data.solution || data.state?.solution;
      if(sol){
        if($('#truthCulprit')) $('#truthCulprit').textContent = sol.culprit || 'Adrian Cole';
        if($('#truthMotive')) $('#truthMotive').textContent = sol.motive || '';
        if($('#truthMethod')) $('#truthMethod').textContent = sol.method || '';
        if($('#truthTransmission')) $('#truthTransmission').textContent = sol.transmission || '';
      }
    } else {
      if(eyebrow) { eyebrow.textContent = 'PROSECUTION STATUS: REJECTED'; eyebrow.style.color = 'var(--red)'; }
      if(heading) { heading.textContent = 'CHARGES DISMISSED (-10 PTS)'; heading.style.color = 'var(--red)'; }
      if(sub) sub.textContent = data.message || 'The indictment does not fit the evidence. Re-examine your case records.';
      if(banner) { banner.style.borderLeftColor = 'var(--red)'; banner.style.background = '#1a0d11'; }
      if(solutionSec) solutionSec.style.display = 'none';
    }

    // Render score events audit trail
    const events = data.score_events || data.state?.score_events || [];
    if(scoreList){
      if(!events.length){
        scoreList.innerHTML = '<div class="empty-state">No score events recorded.</div>';
      } else {
        scoreList.innerHTML = [...events].reverse().map(ev => `
          <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 8px;background:#0d1822;border-radius:6px;border:1px solid #1a2a38">
            <div>
              <strong style="color:var(--text);font-size:11px">${esc(ev.reason || 'Investigation event')}</strong>
              ${ev.related_key ? `<span class="muted" style="margin-left:6px;font-size:10px">(${esc(ev.related_key)})</span>` : ''}
            </div>
            <span class="mono" style="font-weight:700;color:${ev.points > 0 ? 'var(--cyan)' : 'var(--red)'}">${ev.points > 0 ? `+${ev.points}` : ev.points} pts</span>
          </div>
        `).join('');
      }
    }

    modal.classList.remove('hidden');
    iconRefresh();
  }

  async function handleSubmitAccusation(e){
    if(e) e.preventDefault();
    if(!state.sessionData?.session?.session_id){
      toast('No active investigation session.', true);
      return;
    }
    const personId = Number($('#accusePersonSelect')?.value);
    const motive = $('#accuseMotiveSelect')?.value;
    const method = $('#accuseMethodSelect')?.value;
    const explanation = $('#accuseExplanation')?.value || '';

    if(!personId){
      toast('Please select an accused suspect.', true);
      return;
    }
    if(!motive){
      toast('Please select the proven motive.', true);
      return;
    }
    if(!method){
      toast('Please select the method of murder.', true);
      return;
    }

    const btn = $('#submitAccusationBtn');
    if(btn) btn.disabled = true;

    try{
      const res = await api(`/api/game/session/${state.sessionData.session.session_id}/submit`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          accused_person_id: personId,
          motive_key: motive,
          method_key: method,
          explanation: explanation
        })
      });

      $('#accuseModalBackdrop')?.classList.add('hidden');
      if(res.state) state.sessionData = res.state;
      renderInterviewRoom();

      renderVerdictModal(res);

      if(res.correct){
        toast('CASE SOLVED! Conviction secured.');
      } else {
        toast('Accusation rejected (-10 pts). Re-examine your case records.', true);
      }
    }catch(err){
      toast(err.message, true);
    }finally{
      if(btn) btn.disabled = false;
    }
  }

  // =====================================================================
  // ADVANCED FEATURES: EVIDENCE BOARD, SEARCH TERMINAL, DBMS LAB
  // =====================================================================

  async function ensureSessionData(){
    if (state.sessionData?.session?.session_id) return state.sessionData;
    const storedSessionId = localStorage.getItem(getActiveSessionStorageKey());
    if (!storedSessionId) return null;
    try {
      state.sessionData = await api(`/api/game/session/${storedSessionId}`);
      return state.sessionData;
    } catch (e) {
      return null;
    }
  }

  // --- FEATURE 1: INTERACTIVE EVIDENCE BOARD ---
  const boardState = {
    entities: null,
    connections: null,
    activeFilter: 'all',
    activeTab: 'theories'
  };

  async function loadBoardView(){
    await ensureSessionData();
    const sid = state.sessionData?.session?.session_id || localStorage.getItem(getActiveSessionStorageKey()) || '';
    const badge = $('#boardSessionBadge');
    if (badge) {
      if (sid) {
        badge.textContent = `SESSION: ${sid.slice(0, 8)}…`;
        badge.className = 'status-pill open';
      } else {
        badge.textContent = 'NO ACTIVE SESSION (READ-ONLY)';
        badge.className = 'status-pill closed';
      }
    }

    try {
      const data = await api(`/api/game/board?case_id=${state.caseId}&session_id=${sid}`);
      boardState.entities = data.entities;
      boardState.connections = data.connections;

      renderBoardCounts();
      populateBoardDropdowns();
      renderBoardGrid();
      renderBoardConnections();
      iconRefresh();
    } catch (e) {
      toast('Failed to load board: ' + e.message, true);
    }
  }

  function renderBoardCounts(){
    const e = boardState.entities || {};
    const persons = e.persons?.length || 0;
    const evidence = e.evidence?.length || 0;
    const clues = e.clues?.length || 0;
    const timeline = e.timeline?.length || 0;
    const locations = e.locations?.length || 0;
    const total = persons + evidence + clues + timeline + locations;

    if ($('#boardTotalCount')) $('#boardTotalCount').textContent = total;
    if ($('#boardPersonCount')) $('#boardPersonCount').textContent = persons;
    if ($('#boardEvidenceCount')) $('#boardEvidenceCount').textContent = evidence;
    if ($('#boardClueCount')) $('#boardClueCount').textContent = clues;
    if ($('#boardTimelineCount')) $('#boardTimelineCount').textContent = timeline;
    if ($('#boardLocationCount')) $('#boardLocationCount').textContent = locations;

    const conns = boardState.connections || {};
    if ($('#boardTheoryCount')) $('#boardTheoryCount').textContent = conns.player_theories?.length || 0;
    if ($('#boardOfficialCount')) $('#boardOfficialCount').textContent = conns.official?.length || 0;
  }

  function populateBoardDropdowns(){
    const srcSel = $('#boardSourceSelect');
    const tgtSel = $('#boardTargetSelect');
    if (!srcSel || !tgtSel) return;

    const prevSrc = srcSel.value;
    const prevTgt = tgtSel.value;

    let html = '<option value="">Select entity…</option>';
    const e = boardState.entities || {};

    if (e.persons?.length) {
      html += '<optgroup label="Suspects & Staff">';
      e.persons.forEach(p => {
        html += `<option value="person:${p.person_id}">[Person] ${esc(p.full_name)} (${esc(p.occupation || 'Staff')})</option>`;
      });
      html += '</optgroup>';
    }

    if (e.evidence?.length) {
      html += '<optgroup label="Vault Evidence Records">';
      e.evidence.forEach(ev => {
        html += `<option value="evidence:${ev.evidence_id}">[Evidence] #${ev.evidence_id} ${esc(ev.title)}</option>`;
      });
      html += '</optgroup>';
    }

    if (e.clues?.length) {
      html += '<optgroup label="Discovered Clues">';
      e.clues.forEach(c => {
        html += `<option value="clue:${c.clue_id}">[Clue ${esc(c.clue_key)}] ${esc(c.title)}</option>`;
      });
      html += '</optgroup>';
    }

    if (e.timeline?.length) {
      html += '<optgroup label="Timeline Events">';
      e.timeline.forEach(t => {
        html += `<option value="timeline:${t.event_id}">[Timeline] ${fmtDateTime(t.event_time)} - ${esc(t.person_name)}</option>`;
      });
      html += '</optgroup>';
    }

    if (e.locations?.length) {
      html += '<optgroup label="Station Locations">';
      e.locations.forEach(l => {
        html += `<option value="location:${l.location_id}">[Location] ${esc(l.location_name)}</option>`;
      });
      html += '</optgroup>';
    }

    srcSel.innerHTML = html;
    tgtSel.innerHTML = html;

    if (prevSrc) srcSel.value = prevSrc;
    if (prevTgt) tgtSel.value = prevTgt;
  }

  function renderBoardGrid(){
    const grid = $('#boardEntitiesGrid');
    if (!grid) return;
    const e = boardState.entities || {};
    const f = boardState.activeFilter;

    let items = [];

    if (f === 'all' || f === 'person') {
      (e.persons || []).forEach(p => items.push({
        type: 'person',
        id: p.person_id,
        title: p.full_name,
        subtitle: p.occupation || 'Staff member',
        desc: p.public_bio || 'Observatory staff member of interest.',
        badge: p.character_key ? `CORE: ${p.character_key}` : 'STAFF',
        tagClass: 'tag-cyan'
      }));
    }

    if (f === 'all' || f === 'evidence') {
      (e.evidence || []).forEach(ev => items.push({
        type: 'evidence',
        id: ev.evidence_id,
        title: ev.title,
        subtitle: `Vault #${ev.evidence_id} · ${ev.evidence_type}`,
        desc: ev.description,
        badge: ev.verification_status,
        tagClass: ev.verification_status === 'verified' ? 'tag-cyan' : 'tag-neutral'
      }));
    }

    if (f === 'all' || f === 'clue') {
      (e.clues || []).forEach(c => items.push({
        type: 'clue',
        id: c.clue_id,
        title: `[${c.clue_key}] ${c.title}`,
        subtitle: `Discovered Clue · ${c.clue_category}`,
        desc: c.public_description,
        badge: c.is_filed ? 'FILED TO VAULT' : 'DISCOVERED',
        tagClass: c.is_filed ? 'tag-cyan' : 'tag-neutral'
      }));
    }

    if (f === 'all' || f === 'timeline') {
      (e.timeline || []).forEach(t => items.push({
        type: 'timeline',
        id: t.event_id,
        title: `${t.person_name} at ${t.location_name}`,
        subtitle: fmtDateTime(t.event_time),
        desc: t.description,
        badge: t.is_verified ? 'VERIFIED' : 'UNVERIFIED',
        tagClass: t.is_verified ? 'tag-cyan' : 'tag-neutral'
      }));
    }

    if (f === 'all' || f === 'location') {
      (e.locations || []).forEach(l => items.push({
        type: 'location',
        id: l.location_id,
        title: l.location_name,
        subtitle: 'Observatory Facility Zone',
        desc: `Zone location #${l.location_id}: ${l.location_name}`,
        badge: 'FACILITY',
        tagClass: 'tag-neutral'
      }));
    }

    if (!items.length) {
      grid.innerHTML = '<div class="empty-state">No entities match this filter.</div>';
      return;
    }

    const srcVal = $('#boardSourceSelect')?.value;
    const tgtVal = $('#boardTargetSelect')?.value;

    grid.innerHTML = items.map(it => {
      const valStr = `${it.type}:${it.id}`;
      const isSrc = srcVal === valStr;
      const isTgt = tgtVal === valStr;
      let selClass = '';
      if (isSrc) selClass = 'selected-src';
      else if (isTgt) selClass = 'selected-tgt';

      return `
        <div class="board-entity-card ${selClass}" data-type="${it.type}" data-id="${it.id}">
          <div class="board-card-head">
            <span class="board-card-type">${esc(it.type)}</span>
            <span class="tag ${it.tagClass}" style="font-size:8px;padding:2px 5px">${esc(it.badge)}</span>
          </div>
          <div class="board-card-title">${esc(it.title)}</div>
          <div style="font-size:10px;color:var(--dim);font-family:'DM Mono',monospace">${esc(it.subtitle)}</div>
          <div class="board-card-desc">${esc(it.desc)}</div>
          <div class="board-card-actions">
            <button type="button" class="board-pin-btn" data-set-source="${valStr}"><i data-lucide="arrow-right-circle" style="width:11px;height:11px;vertical-align:-1px;display:inline-block"></i> Source</button>
            <button type="button" class="board-pin-btn" data-set-target="${valStr}"><i data-lucide="target" style="width:11px;height:11px;vertical-align:-1px;display:inline-block"></i> Target</button>
          </div>
        </div>
      `;
    }).join('');

    $$('[data-set-source]', grid).forEach(b => b.addEventListener('click', (ev) => {
      ev.stopPropagation();
      const val = b.dataset.setSource;
      if ($('#boardSourceSelect')) $('#boardSourceSelect').value = val;
      renderBoardGrid();
    }));

    $$('[data-set-target]', grid).forEach(b => b.addEventListener('click', (ev) => {
      ev.stopPropagation();
      const val = b.dataset.setTarget;
      if ($('#boardTargetSelect')) $('#boardTargetSelect').value = val;
      renderBoardGrid();
    }));

    $$('.board-entity-card', grid).forEach(card => card.addEventListener('click', (ev) => {
      if (ev.target.closest('button')) return;
      const valStr = `${card.dataset.type}:${card.dataset.id}`;
      const srcEl = $('#boardSourceSelect');
      const tgtEl = $('#boardTargetSelect');
      if (!srcEl.value) {
        srcEl.value = valStr;
      } else if (!tgtEl.value && srcEl.value !== valStr) {
        tgtEl.value = valStr;
      } else {
        srcEl.value = valStr;
      }
      renderBoardGrid();
    }));

    iconRefresh();
  }

  function getEntityDisplayName(type, id){
    const e = boardState.entities || {};
    id = Number(id);
    if (type === 'person') {
      const p = (e.persons || []).find(x => Number(x.person_id) === id);
      return p ? p.full_name : `Person #${id}`;
    }
    if (type === 'evidence') {
      const ev = (e.evidence || []).find(x => Number(x.evidence_id) === id);
      return ev ? ev.title : `Evidence #${id}`;
    }
    if (type === 'clue') {
      const c = (e.clues || []).find(x => Number(x.clue_id) === id);
      return c ? `[${c.clue_key}] ${c.title}` : `Clue #${id}`;
    }
    if (type === 'timeline') {
      const t = (e.timeline || []).find(x => Number(x.event_id) === id);
      return t ? `${t.person_name} (${fmtDateTime(t.event_time)})` : `Event #${id}`;
    }
    if (type === 'location') {
      const l = (e.locations || []).find(x => Number(x.location_id) === id);
      return l ? l.location_name : `Location #${id}`;
    }
    return `${type} #${id}`;
  }

  function renderBoardConnections(){
    const tList = $('#boardTheoryList');
    const oList = $('#boardOfficialList');
    if (!tList || !oList) return;

    const conns = boardState.connections || {};
    const theories = conns.player_theories || [];
    const officials = conns.official || [];

    if (!theories.length) {
      tList.innerHTML = '<div class="empty-state">No theory connections recorded in this session. Select two entities to establish a theory.</div>';
    } else {
      tList.innerHTML = theories.map(th => {
        const srcName = getEntityDisplayName(th.source_type, th.source_id);
        const tgtName = getEntityDisplayName(th.target_type, th.target_id);
        const status = th.evaluation_status || 'unverified';
        return `
          <div class="board-conn-item">
            <div class="board-conn-top">
              <span class="board-eval-badge ${status}">${esc(status)}</span>
              <button type="button" class="btn btn-danger-quiet" style="padding:2px 7px;font-size:9px" data-delete-theory="${th.connection_id}">Remove</button>
            </div>
            <div class="board-conn-entities">
              <strong>${esc(srcName)}</strong>
              <span style="color:var(--cyan);margin:0 4px">--[ ${esc(th.connection_type.replace(/_/g, ' '))} ]--></span>
              <strong>${esc(tgtName)}</strong>
            </div>
            <div style="font-size:10px;color:#a0b8c4;line-height:1.4">${esc(th.evaluation_reason || '')}</div>
            ${th.notes ? `<div style="font-size:9px;color:var(--dim);font-style:italic">Notes: "${esc(th.notes)}"</div>` : ''}
          </div>
        `;
      }).join('');

      $$('[data-delete-theory]', tList).forEach(b => b.addEventListener('click', async () => {
        const id = b.dataset.deleteTheory;
        const sid = state.sessionData?.session?.session_id || localStorage.getItem(getActiveSessionStorageKey());
        if (!sid) {
          toast('Session required to delete theories.', true);
          return;
        }
        b.disabled = true;
        try {
          await api(`/api/game/board/connection/${id}?session_id=${sid}`, { method: 'DELETE' });
          toast('Theory connection removed.');
          await loadBoardView();
        } catch (e) {
          toast(e.message, true);
          b.disabled = false;
        }
      }));
    }

    if (!officials.length) {
      oList.innerHTML = '<div class="empty-state">No official DBMS links found.</div>';
    } else {
      oList.innerHTML = officials.map(ofc => {
        const srcName = getEntityDisplayName(ofc.source_type, ofc.source_id);
        const tgtName = getEntityDisplayName(ofc.target_type, ofc.target_id);
        return `
          <div class="board-conn-item" style="border-left:3px solid var(--cyan)">
            <div class="board-conn-top">
              <span class="board-eval-badge verified">OFFICIAL CORE RECORD</span>
              <span style="font:9px 'DM Mono',monospace;color:var(--dim)">ID: ${ofc.relationship_id}</span>
            </div>
            <div class="board-conn-entities">
              <strong>${esc(srcName)}</strong>
              <span style="color:var(--cyan);margin:0 4px">--[ ${esc(ofc.connection_type)} ]--></span>
              <strong>${esc(tgtName)}</strong>
            </div>
            <div style="font-size:10px;color:#8ba3b0">${esc(ofc.notes || ofc.evaluation_reason || '')}</div>
          </div>
        `;
      }).join('');
    }
  }

  async function handleCreateBoardConnection(ev){
    ev.preventDefault();
    await ensureSessionData();
    const sid = state.sessionData?.session?.session_id || localStorage.getItem(getActiveSessionStorageKey());
    if (!sid) {
      toast('Start or resume an investigation session first to persist theories.', true);
      go('interviews');
      return;
    }

    const srcVal = $('#boardSourceSelect').value;
    const tgtVal = $('#boardTargetSelect').value;
    const connType = $('#boardConnectionTypeSelect').value;
    const notes = ($('#boardNotesInput').value || '').trim();

    if (!srcVal || !tgtVal) {
      toast('Please select both a source entity and a target entity.', true);
      return;
    }

    const [srcType, srcId] = srcVal.split(':');
    const [tgtType, tgtId] = tgtVal.split(':');

    if (srcType === tgtType && srcId === tgtId) {
      toast('An entity cannot connect to itself.', true);
      return;
    }

    const submitBtn = $('#saveBoardConnectionBtn');
    if (submitBtn) submitBtn.disabled = true;

    try {
      const res = await api('/api/game/board/connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sid,
          case_id: state.caseId,
          source_entity_type: srcType,
          source_entity_id: Number(srcId),
          target_entity_type: tgtType,
          target_entity_id: Number(tgtId),
          connection_type: connType,
          player_notes: notes
        })
      });

      const fb = $('#boardTheoryFeedback');
      if (fb) {
        fb.style.display = 'block';
        if (res.evaluation_status === 'supported') {
          fb.style.background = '#143528';
          fb.style.color = '#75dfaa';
          fb.style.border = '1px solid #2a694e';
          fb.innerHTML = `<strong>SUPPORTED THEORY:</strong> ${esc(res.evaluation_reason)}`;
        } else if (res.evaluation_status === 'contradicted') {
          fb.style.background = '#371a23';
          fb.style.color = '#ff8597';
          fb.style.border = '1px solid #6c2b3c';
          fb.innerHTML = `<strong>CONTRADICTED BY EVIDENCE:</strong> ${esc(res.evaluation_reason)}`;
        } else {
          fb.style.background = '#332717';
          fb.style.color = '#ffd07d';
          fb.style.border = '1px solid #634b29';
          fb.innerHTML = `<strong>THEORY DOCUMENTED:</strong> ${esc(res.evaluation_reason)}`;
        }
      }

      toast(res.message || 'Theory connection saved to PostgreSQL.');
      $('#boardNotesInput').value = '';
      await loadBoardView();
    } catch (err) {
      toast(err.message, true);
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  }

  // --- FEATURE 2: INVESTIGATION SEARCH TERMINAL ---
  const searchState = {
    query: '',
    activeCategory: 'all',
    results: []
  };

  function loadSearchView(){
    const input = $('#terminalSearchInput');
    if (input) {
      input.focus();
      if (searchState.query && !input.value) {
        input.value = searchState.query;
      }
    }
  }

  let terminalDebounceTimer;
  async function runTerminalSearch(rawQuery){
    const q = (rawQuery || '').trim();
    searchState.query = q;
    if (q.length < 2) {
      searchState.results = [];
      updateSearchCategoryCounts();
      renderTerminalResults();
      return;
    }

    await ensureSessionData();
    const sid = state.sessionData?.session?.session_id || localStorage.getItem(getActiveSessionStorageKey()) || '';

    try {
      const data = await api(`/api/game/search-terminal?case_id=${state.caseId}&session_id=${sid}&q=${encodeURIComponent(q)}`);
      searchState.results = data.results || [];
      updateSearchCategoryCounts();
      renderTerminalResults();
    } catch (e) {
      toast('Search failed: ' + e.message, true);
    }
  }

  function updateSearchCategoryCounts(){
    const all = searchState.results;
    const counts = { all: all.length, person: 0, evidence: 0, clue: 0, testimony: 0, timeline: 0, location: 0 };
    all.forEach(r => {
      if (counts[r.kind] !== undefined) counts[r.kind]++;
    });

    if ($('#searchCatCountAll')) $('#searchCatCountAll').textContent = counts.all;
    if ($('#searchCatCountPerson')) $('#searchCatCountPerson').textContent = counts.person;
    if ($('#searchCatCountEvidence')) $('#searchCatCountEvidence').textContent = counts.evidence;
    if ($('#searchCatCountClue')) $('#searchCatCountClue').textContent = counts.clue;
    if ($('#searchCatCountTestimony')) $('#searchCatCountTestimony').textContent = counts.testimony;
    if ($('#searchCatCountTimeline')) $('#searchCatCountTimeline').textContent = counts.timeline;
    if ($('#searchCatCountLocation')) $('#searchCatCountLocation').textContent = counts.location;
  }

  function renderTerminalResults(){
    const container = $('#terminalResultsGrid');
    if (!container) return;
    const cat = searchState.activeCategory;
    const filtered = cat === 'all' ? searchState.results : searchState.results.filter(r => r.kind === cat);

    if (!searchState.query || searchState.query.length < 2) {
      container.innerHTML = '<div class="empty-state">Enter a search keyword above or click a suggested query to search PostgreSQL case records.</div>';
      return;
    }

    if (!filtered.length) {
      container.innerHTML = `<div class="empty-state">No matching records found for "${esc(searchState.query)}" in ${esc(cat)} category.</div>`;
      return;
    }

    const kindIcons = {
      person: 'user-round',
      evidence: 'file-text',
      clue: 'search',
      testimony: 'messages-square',
      timeline: 'git-commit-horizontal',
      location: 'map-pin'
    };

    container.innerHTML = filtered.map(r => {
      const icon = kindIcons[r.kind] || 'file';
      return `
        <article class="search-result-card" data-kind="${r.kind}" data-nav="${r.navigate_view}" data-target="${r.target_id}">
          <div class="search-card-meta">
            <span class="role-chip ${r.kind === 'person' ? 'suspect' : ''}"><i data-lucide="${icon}" style="width:11px;height:11px;vertical-align:-1px;display:inline-block"></i> ${esc(r.kind)}</span>
            <span class="tag tag-cyan" style="font-size:8px;padding:2px 5px">${esc(r.status || 'found')}</span>
          </div>
          <div class="search-card-title">${esc(r.title)}</div>
          <div class="search-card-sub">${esc(r.subtitle)}</div>
          <p class="search-card-excerpt">${esc(r.excerpt)}</p>
          <div style="margin-top:auto;padding-top:8px;display:flex;justify-content:flex-end">
            <button type="button" class="btn btn-quiet" style="padding:4px 9px;font-size:10px" data-open-result="${r.kind}:${r.target_id}">
              Inspect Record <i data-lucide="arrow-up-right"></i>
            </button>
          </div>
        </article>
      `;
    }).join('');

    $$('[data-open-result]', container).forEach(b => b.addEventListener('click', () => {
      const [kind, targetId] = b.dataset.openResult.split(':');
      if (kind === 'person') {
        openPerson(targetId);
      } else if (kind === 'evidence') {
        go('evidence');
      } else if (kind === 'clue') {
        go('interviews');
        $$('.game-subnav-btn[data-subtab="clues"]')[0]?.click();
      } else if (kind === 'testimony') {
        go('interviews');
        selectCharacter(Number(targetId));
      } else if (kind === 'timeline') {
        go('timeline');
      } else {
        go('dashboard');
      }
    }));

    iconRefresh();
  }

  // --- FEATURE 3: DBMS QUERY LAB ---
  const dbmsState = {
    activeTab: 'explorer',
    selectedTable: null,
    tables: [],
    queries: [],
    schemaGraphInstance: null
  };

  async function loadDBMSLabView(){
    if (dbmsState.activeTab === 'explorer') {
      await loadDBMSTables();
    } else if (dbmsState.activeTab === 'library') {
      await loadDBMSQueryLibrary();
    } else if (dbmsState.activeTab === 'schema') {
      await loadDBMSSchemaGraph();
    }
  }

  async function loadDBMSTables(){
    try {
      const res = await api('/api/dbms/tables');
      dbmsState.tables = res.tables || [];
      if ($('#dbmsTotalTables')) $('#dbmsTotalTables').textContent = res.total || dbmsState.tables.length;
      renderDBMSTableList();
      if (!dbmsState.selectedTable && dbmsState.tables.length) {
        inspectDBMSTable(dbmsState.tables[0].table_name);
      }
    } catch (e) {
      toast('Failed to load DBMS tables: ' + e.message, true);
    }
  }

  function renderDBMSTableList(){
    const list = $('#dbmsTableList');
    if (!list) return;
    const filter = ($('#dbmsTableFilter')?.value || '').toLowerCase().trim();
    const filtered = dbmsState.tables.filter(t => !filter || t.table_name.toLowerCase().includes(filter));

    if (!filtered.length) {
      list.innerHTML = '<div class="empty-state">No tables match filter.</div>';
      return;
    }

    list.innerHTML = filtered.map(t => `
      <button type="button" class="dbms-table-item ${dbmsState.selectedTable === t.table_name ? 'active' : ''}" data-table-name="${t.table_name}">
        <span style="font-size:11px;font-family:'DM Mono',monospace">${esc(t.table_name)}</span>
        <span class="count-badge" style="margin:0;font-size:9px">${t.row_count}</span>
      </button>
    `).join('');

    $$('[data-table-name]', list).forEach(b => b.addEventListener('click', () => {
      inspectDBMSTable(b.dataset.tableName);
    }));
  }

  async function inspectDBMSTable(tableName){
    dbmsState.selectedTable = tableName;
    renderDBMSTableList();
    const detail = $('#dbmsTableDetail');
    if (!detail) return;
    detail.innerHTML = '<div class="loading-card"><span class="loader"></span> Inspecting PostgreSQL schema & records…</div>';

    try {
      const data = await api(`/api/dbms/table/${tableName}`);
      const cols = data.columns || [];
      const pks = new Set(data.primary_keys || []);
      const fks = data.foreign_keys || [];
      const sample = data.sample_rows || [];

      detail.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px;border-bottom:1px solid var(--line);padding-bottom:12px">
          <div>
            <div class="eyebrow"><i data-lucide="table" style="width:11px;height:11px;vertical-align:-1px;display:inline-block"></i> POSTGRESQL TABLE</div>
            <h2 style="font-size:20px;margin:4px 0 0;font-family:'DM Mono',monospace;color:var(--cyan)">${esc(data.table_name)}</h2>
          </div>
          <div style="display:flex;gap:8px;align-items:center">
            <span class="status-pill open">${cols.length} COLUMNS</span>
            <span class="tag tag-cyan">${sample.length} ROWS DISPLAYED</span>
          </div>
        </div>

        <div>
          <div class="eyebrow" style="margin-bottom:8px">COLUMN DEFINITIONS & CONSTRAINTS</div>
          <div style="overflow-x:auto">
            <table class="data-table">
              <thead>
                <tr>
                  <th>COLUMN NAME</th>
                  <th>DATA TYPE</th>
                  <th>NULLABLE</th>
                  <th>KEY / CONSTRAINT</th>
                  <th>DEFAULT</th>
                </tr>
              </thead>
              <tbody>
                ${cols.map(c => {
                  const isPk = pks.has(c.column_name);
                  const fk = fks.find(f => f.column_name === c.column_name);
                  let keyBadge = '<span class="muted">—</span>';
                  if (isPk) keyBadge = '<span class="status-pill open" style="font-size:8px;padding:2px 5px">PRIMARY KEY</span>';
                  else if (fk) keyBadge = `<span class="tag tag-neutral" style="font-size:8px;padding:2px 5px">FK -> ${esc(fk.foreign_table)}.${esc(fk.foreign_column)}</span>`;

                  return `
                    <tr>
                      <td><strong style="font-family:'DM Mono',monospace;color:#edf4f7">${esc(c.column_name)}</strong></td>
                      <td><span style="font-family:'DM Mono',monospace;color:#85c2c0">${esc(c.data_type)}</span></td>
                      <td>${c.is_nullable === 'YES' ? '<span class="muted">YES</span>' : '<span style="color:var(--amber)">NO</span>'}</td>
                      <td>${keyBadge}</td>
                      <td><small style="font-family:'DM Mono',monospace">${esc(c.column_default || '—')}</small></td>
                    </tr>
                  `;
                }).join('')}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <div class="eyebrow" style="margin-bottom:8px">LIVE SAMPLE DATA (FIRST 25 ROWS)</div>
          ${!sample.length ? '<div class="empty-state">No rows currently in this table.</div>' : `
            <div class="dbms-result-table-wrap">
              <table class="data-table">
                <thead>
                  <tr>
                    ${Object.keys(sample[0]).map(k => `<th>${esc(k)}</th>`).join('')}
                  </tr>
                </thead>
                <tbody>
                  ${sample.map(row => `
                    <tr>
                      ${Object.values(row).map(val => `<td>${esc(val === null ? 'NULL' : typeof val === 'object' ? JSON.stringify(val) : val)}</td>`).join('')}
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          `}
        </div>
      `;
      iconRefresh();
    } catch (e) {
      detail.innerHTML = `<div class="empty-state">${esc(e.message)}</div>`;
    }
  }

  async function loadDBMSQueryLibrary(){
    try {
      const res = await api('/api/dbms/queries');
      dbmsState.queries = res.queries || [];
      renderDBMSQueryGrid();
    } catch (e) {
      toast('Failed to load query library: ' + e.message, true);
    }
  }

  function renderDBMSQueryGrid(){
    const grid = $('#dbmsQueryGrid');
    if (!grid) return;
    grid.innerHTML = dbmsState.queries.map(q => `
      <div class="dbms-query-card">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span class="role-chip suspect" style="background:#132832;border-color:#2a555f;color:var(--cyan)">${esc(q.category)}</span>
        </div>
        <strong style="font-size:13px;color:#edf4f7">${esc(q.name)}</strong>
        <p class="muted" style="margin:0;line-height:1.5">${esc(q.description)}</p>
        <div style="margin-top:auto;display:flex;justify-content:flex-end">
          <button type="button" class="btn btn-primary" style="padding:6px 12px;font-size:10px" data-execute-query="${q.query_id}">
            <i data-lucide="play"></i> Run Live Query ↗
          </button>
        </div>
      </div>
    `).join('');

    $$('[data-execute-query]', grid).forEach(b => b.addEventListener('click', () => {
      executePredefinedQuery(b.dataset.executeQuery);
    }));

    iconRefresh();
  }

  async function executePredefinedQuery(queryId){
    const outPanel = $('#dbmsQueryOutputPanel');
    if (!outPanel) return;
    outPanel.classList.remove('hidden');
    outPanel.scrollIntoView({ behavior: 'smooth' });

    $('#dbmsExecutedName').textContent = 'Executing query…';
    $('#dbmsExecTimeBadge').textContent = '…';
    $('#dbmsExecRowsBadge').textContent = '…';
    $('#dbmsExecutedSql').textContent = 'Running SQL in PostgreSQL…';
    $('#dbmsExecutedTableWrap').innerHTML = '<div class="loading-card"><span class="loader"></span> Executing analytical query…</div>';

    try {
      const res = await api('/api/dbms/execute-predefined', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query_id: queryId, case_id: state.caseId })
      });

      $('#dbmsExecutedName').textContent = res.name;
      $('#dbmsExecutedCategory').textContent = `ANALYTICAL QUERY: ${res.query_id.toUpperCase()}`;
      $('#dbmsExecTimeBadge').textContent = `${res.execution_time_ms} ms`;
      $('#dbmsExecRowsBadge').textContent = `${res.row_count} ROWS`;
      $('#dbmsExecutedSql').textContent = res.sql_executed;

      if (!res.rows?.length) {
        $('#dbmsExecutedTableWrap').innerHTML = '<div class="empty-state">Query returned 0 rows.</div>';
        return;
      }

      $('#dbmsExecutedTableWrap').innerHTML = `
        <table class="data-table">
          <thead>
            <tr>${res.columns.map(c => `<th>${esc(c)}</th>`).join('')}</tr>
          </thead>
          <tbody>
            ${res.rows.map(row => `
              <tr>${row.map(val => `<td>${esc(val === null ? 'NULL' : typeof val === 'object' ? JSON.stringify(val) : val)}</td>`).join('')}</tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (e) {
      $('#dbmsExecutedTableWrap').innerHTML = `<div class="empty-state" style="color:var(--red)">${esc(e.message)}</div>`;
    }
  }

  async function handleExecuteCustomSql(ev){
    if (ev) ev.preventDefault();
    const sqlText = ($('#dbmsCustomSqlInput')?.value || '').trim();
    if (!sqlText) {
      toast('Please enter a SQL query.', true);
      return;
    }

    const resBox = $('#dbmsCustomResultBox');
    const tableWrap = $('#dbmsCustomTableWrap');
    if (resBox) resBox.style.display = 'block';
    if (tableWrap) tableWrap.innerHTML = '<div class="loading-card"><span class="loader"></span> Running sandboxed SQL query…</div>';

    try {
      const res = await api('/api/dbms/execute-custom', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sql: sqlText })
      });

      if ($('#dbmsCustomTimingBadge')) $('#dbmsCustomTimingBadge').textContent = `${res.execution_time_ms} ms`;
      if ($('#dbmsCustomCountBadge')) $('#dbmsCustomCountBadge').textContent = `${res.row_count} ROWS`;

      if (!res.rows?.length) {
        tableWrap.innerHTML = '<div class="empty-state">Query returned 0 rows.</div>';
        return;
      }

      tableWrap.innerHTML = `
        <table class="data-table">
          <thead>
            <tr>${res.columns.map(c => `<th>${esc(c)}</th>`).join('')}</tr>
          </thead>
          <tbody>
            ${res.rows.map(row => `
              <tr>${row.map(val => `<td>${esc(val === null ? 'NULL' : typeof val === 'object' ? JSON.stringify(val) : val)}</td>`).join('')}</tr>
            `).join('')}
          </tbody>
        </table>
      `;
    } catch (e) {
      if ($('#dbmsCustomTimingBadge')) $('#dbmsCustomTimingBadge').textContent = 'ERROR';
      if ($('#dbmsCustomCountBadge')) $('#dbmsCustomCountBadge').textContent = '0 ROWS';
      tableWrap.innerHTML = `<div class="panel" style="padding:14px;background:#351f27;border-color:#673541;color:#ffc0c8">${esc(e.message)}</div>`;
    }
  }

  async function loadDBMSSchemaGraph(){
    const box = $('#schemaCytoscapeGraph');
    if (!box || !window.cytoscape) return;
    try {
      const data = await api('/api/dbms/schema-graph');
      if ($('#schemaGraphCounts')) $('#schemaGraphCounts').textContent = `${data.nodes.length} TABLES · ${data.edges.length} FOREIGN KEYS`;
      if (dbmsState.schemaGraphInstance) dbmsState.schemaGraphInstance.destroy();

      dbmsState.schemaGraphInstance = cytoscape({
        container: box,
        elements: [...data.nodes, ...data.edges],
        layout: {
          name: 'cose',
          animate: false,
          fit: true,
          padding: 40,
          nodeRepulsion: 7000,
          idealEdgeLength: 100
        },
        style: [
          {
            selector: 'node',
            style: {
              'background-color': '#133a41',
              'border-color': '#53e0d0',
              'border-width': 1.5,
              'label': 'data(label)',
              'color': '#d2f6f1',
              'font-size': 10,
              'font-family': 'DM Mono',
              'text-valign': 'center',
              'text-halign': 'center',
              'width': 95,
              'height': 32,
              'shape': 'roundrectangle'
            }
          },
          {
            selector: 'edge',
            style: {
              'width': 1.2,
              'line-color': '#3b7074',
              'curve-style': 'bezier',
              'target-arrow-shape': 'triangle',
              'target-arrow-color': '#3b7074',
              'arrow-scale': 0.8
            }
          },
          {
            selector: 'node:selected',
            style: {
              'background-color': '#1f656c',
              'border-color': '#ffffff',
              'border-width': 2.5
            }
          }
        ]
      });

      dbmsState.schemaGraphInstance.on('tap', 'node', evt => {
        const tname = evt.target.id();
        $$('.dbms-nav-btn[data-dbms-tab="explorer"]')[0]?.click();
        inspectDBMSTable(tname);
      });
    } catch (e) {
      box.innerHTML = `<div class="empty-state">${esc(e.message)}</div>`;
    }
  }

  $('#addPersonBtn')?.addEventListener('click',addPerson);$('#addEvidenceBtn')?.addEventListener('click',addEvidence);$('#addRelationshipBtn')?.addEventListener('click',addRelationship);$('#addTimelineBtn')?.addEventListener('click',addTimeline);$('#findPathBtn')?.addEventListener('click',findPath);
  $('#startSessionBtn')?.addEventListener('click',handleStartSession);
  $('#interviewForm')?.addEventListener('submit',(e)=>{e.preventDefault();handleAskQuestion();});
  $('#insightForm')?.addEventListener('submit',handleSubmitInsight);

  // Close Modals
  $$('[data-close-modal]').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.dataset.closeModal;
      $(`#${targetId}`)?.classList.add('hidden');
    });
  });

  // Briefing Modal Opener
  $('#openBriefingBtn')?.addEventListener('click', () => {
    $('#briefingModalBackdrop')?.classList.remove('hidden');
    iconRefresh();
  });

  // Accuse Modal Opener
  $('#openAccuseBtn')?.addEventListener('click', () => {
    if(!state.sessionData?.session?.session_id){
      toast('Start or resume an investigation session first.', true);
      return;
    }
    populateAccuseModal();
    $('#accuseModalBackdrop')?.classList.remove('hidden');
    iconRefresh();
  });

  // Accuse Form Submit
  $('#accuseForm')?.addEventListener('submit', handleSubmitAccusation);

  // Replay / New Investigation from Verdict Screen
  $('#verdictReplayBtn')?.addEventListener('click', async () => {
    $('#verdictModalBackdrop')?.classList.add('hidden');
    try{
      const res = await api('/api/game/001/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ player_label: 'Lead Investigator' })
      });
      localStorage.setItem(getActiveSessionStorageKey(), res.session.session_id);
      state.sessionData = res;
      state.selectedPersonId = res.characters[0]?.person_id || null;
      renderInterviewRoom();
      toast('New investigation started.');
    }catch(e){
      toast(e.message, true);
    }
  });

  // Subtab navigation
  $$('.game-subnav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      $$('.game-subnav-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.subtab;
      $$('.game-subtab').forEach(st => st.classList.add('hidden'));
      $(`#subtab-${tab}`)?.classList.remove('hidden');
      iconRefresh();
    });
  });
  let searchTimer;$('#globalSearch').addEventListener('input',()=>{clearTimeout(searchTimer);const q=$('#globalSearch').value.trim();if(q.length<2){$('#searchResults').classList.add('hidden');return;}searchTimer=setTimeout(async()=>{try{const rows=await api(`/api/search?case_id=${state.caseId}&q=${encodeURIComponent(q)}`);const box=$('#searchResults');box.innerHTML=rows.length?rows.map(r=>`<button class="search-result" data-kind="${r.kind}" data-id="${r.id}"><i data-lucide="${r.kind==='person'?'user-round':r.kind==='evidence'?'file-text':'map-pin'}"></i><span><strong>${esc(r.title)}</strong><small>${esc(r.kind)} · ${esc(r.subtitle)}</small></span><i data-lucide="arrow-up-right"></i></button>`).join(''):'<div class="empty-state">No matching records found.</div>';box.classList.remove('hidden');$$('.search-result',box).forEach(b=>b.addEventListener('click',()=>{if(b.dataset.kind==='person')openPerson(b.dataset.id);else if(b.dataset.kind==='evidence')go('evidence');else go('timeline');box.classList.add('hidden');$('#globalSearch').value='';}));iconRefresh();}catch(e){toast(e.message,true)}},180);});document.addEventListener('click',e=>{if(!e.target.closest('.global-search'))$('#searchResults').classList.add('hidden')});
  $('#caseSelect').addEventListener('change',async e=>{state.caseId=Number(e.target.value);state.sessionData=null;state.selectedPersonId=null;state.graph=null;if(state.graphInstance){state.graphInstance.destroy();state.graphInstance=null;}history.replaceState(null,'',`/?case_id=${state.caseId}`);await loadDashboard();if($('#view-interviews').classList.contains('active'))loadInterviewView(true);if($('#view-relationships').classList.contains('active'))loadGraph(true);if($('#view-analysis').classList.contains('active'))loadConflicts();if($('#view-timeline').classList.contains('active'))loadTimeline();toast('Case switched. Data refreshed.');});
  document.addEventListener('click',e=>{const nav=e.target.closest('[data-view]');if(nav){go(nav.dataset.view);return;}const g=e.target.closest('[data-go]');if(g)go(g.dataset.go);});
  $('#closeDrawer').addEventListener('click',closeDrawer);$('#detailBackdrop').addEventListener('click',closeDrawer);$('#menuBtn').addEventListener('click',()=>$('#sidebar').classList.toggle('mobile-open'));$('#themeBtn').addEventListener('click',()=>{document.body.classList.toggle('light-theme');localStorage.setItem('casegraph-theme',document.body.classList.contains('light-theme')?'light':'dark')});if(localStorage.getItem('casegraph-theme')==='light')document.body.classList.add('light-theme');
  $('#fitGraphBtn').addEventListener('click',()=>state.graphInstance?.fit(undefined,55));$('#zoomIn').addEventListener('click',()=>state.graphInstance?.zoom({level:state.graphInstance.zoom()*1.2,renderedPosition:{x:$('#fullGraph').clientWidth/2,y:$('#fullGraph').clientHeight/2}}));$('#zoomOut').addEventListener('click',()=>state.graphInstance?.zoom({level:state.graphInstance.zoom()/1.2,renderedPosition:{x:$('#fullGraph').clientWidth/2,y:$('#fullGraph').clientHeight/2}}));$('#runAnalysisBtn').addEventListener('click',runAnalysis);$('#runAnalysisBtn2').addEventListener('click',runAnalysis);$('#evidenceSearch').addEventListener('input',e=>{state.evidenceQuery=e.target.value;renderAllEvidence()});$('#evidenceFilterBtn').addEventListener('click',()=>{state.evidenceFilter=!state.evidenceFilter;$('#evidenceFilterBtn').innerHTML=`<i data-lucide="list-filter"></i> ${state.evidenceFilter?'Show all evidence':'Filter verified'}`;iconRefresh();renderAllEvidence()});$('#exportBtn').addEventListener('click',()=>{go('reports');setTimeout(()=>window.print(),300)});$('#printReportBtn').addEventListener('click',()=>window.print());document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('#globalSearch').focus()}if(e.key==='Escape'){closeDrawer();$('#searchResults').classList.add('hidden')}});
  if(location.hash){const v=location.hash.slice(1);if($(`#view-${v}`))go(v)}
  iconRefresh();loadDashboard();
})();