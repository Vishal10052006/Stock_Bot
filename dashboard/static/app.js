var S={data:null,view:"overview",inspect:null,chat:[],chatBusy:false};

function esc(v){
  return String(v==null?"":v).replace(/[&<>"']/g,function(c){
    return({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])
  })
}

function get(p){
  return fetch(p,{cache:"no-store"}).then(function(r){
    if(!r.ok)throw Error(r.status);
    return r.json()
  })
}

function st(s){return '<span class="state '+esc(s)+'">● '+esc(s)+'</span>'}

function panel(t,b,c){
  return '<section class="panel '+(c||"")+'"><h2>'+t+'</h2>'+b+'</section>'
}

function agent(a){
  return '<article class="agent" onclick="inspectAgent(\''+esc(a.agent_id)+'\')">'+
    '<div class="head"><span>'+esc(a.name)+'</span>'+st(a.status)+'</div>'+
    '<div class="sub">'+esc(a.role)+'</div>'+
    '<div class="sub">CONTRACT: '+esc(a.output_contract)+'</div>'+
    '<div class="sub">EVENTS: '+a.event_count+'</div>'+
    '<div class="sub">'+(a.last_event?esc(a.last_event.event_type):"WAITING FOR TELEMETRY")+'</div>'+
  '</article>'
}

function pipe(){
  return S.data.pipeline.map(function(p){
    return '<div class="stage"><small>'+p.stage_id+'</small><b>'+esc(p.name)+'</b>'+
      st(p.status)+'<div class="sub">'+esc(p.detail)+'</div></div>'
  }).join('<div class="pipe-arrow">→</div>')
}

function ev(){
  if(!S.data.events.length)
    return '<div class="notice">No telemetry recorded yet. Configure the runtime to write the shared MonitoringJournal.</div>';
  return S.data.events.map(function(e){
    return '<div class="event"><span>'+esc(e.timestamp).slice(11,23)+'</span>'+
      '<span class="source">'+esc(e.source)+'</span>'+
      '<span>'+esc(e.event_type)+'</span>'+
      '<span class="sev">'+esc(e.severity)+'</span></div>'
  }).join("")
}

function overview(){
  var s=S.data.summary,l=S.data.learning;
  return '<div class="grid">'+
    panel("01 | PIPELINE TRACE / CURRENT CASCADE",'<div class="pipeline">'+pipe()+'</div>','full')+
    panel("02 | AGENT ACTIVE ROSTER",'<div class="cards">'+S.data.agents.map(agent).join("")+'</div>')+
    panel("03 | TELEMETRY STREAM",'<div class="sub">REAL EVENTS • SYNTHETIC REPLAY MUST BE EXPLICIT</div>'+ev())+
    panel("04 | CONTROLLED SELF-LEARNING & MODEL EVOLUTION",
      '<div class="metric-grid">'+l.stages.map(function(x){
        return '<div class="metric"><b>'+x.count+'</b><small>'+esc(x.name)+'</small></div>'
      }).join("")+'</div><div class="sub">AUTHORITY: NON-AUTHORITATIVE</div>','full')+
    panel("05 | SYSTEM STATE",
      '<div class="metric-grid">'+
      '<div class="metric"><b>'+s.registered_agents+'</b><small>AGENTS</small></div>'+
      '<div class="metric"><b>'+s.events+'</b><small>EVENTS</small></div>'+
      '<div class="metric"><b class="green">ENFORCED</b><small>CAUSALITY</small></div>'+
      '<div class="metric"><b class="red">LOCKED</b><small>LIVE TRADING</small></div>'+
      '</div>','full')+
    panel("06 | AI COMMAND CENTER",
      '<div class="ai-preview"><div><b>JARVIS ONLINE</b><span>Ask about system state, market context, models or what is happening now.</span></div>'+
      '<button class="primary" onclick="openAI()">OPEN AI</button></div>','full')+
  '</div>'
}

function agents(){return panel("AGENT REGISTRY",'<div class="cards">'+S.data.agents.map(agent).join("")+'</div>')}

function pipeline(){
  return panel("PIPELINE TRACE",'<div class="pipeline">'+pipe()+
    '</div><div class="notice">Missing telemetry is WAITING, never fabricated as ACTIVE.</div>')
}

function models(){
  var m=S.data.models;
  if(!m.length)return panel("MODEL OBSERVABILITY",'<div class="notice">No ModelRegistry object is attached. This is a real empty state.</div>');
  var h='<table><tr><th>VERSION</th><th>FAMILY</th><th>FEATURES</th><th>DATASET</th><th>STATUS</th></tr>';
  m.forEach(function(x){
    h+='<tr><td>'+esc(x.model_version)+'</td><td>'+esc(x.model_family)+'</td><td>'+
      esc(x.feature_version)+'</td><td>'+esc(x.dataset_version)+'</td><td>'+
      esc(x.approval_status)+'</td></tr>'
  });
  return panel("MODEL OBSERVABILITY",h+'</table>')
}

function health(){
  return panel("SYSTEM HEALTH",
    '<div class="metric-grid"><div class="metric"><b class="green">ENFORCED</b><small>CAUSALITY</small></div>'+
    '<div class="metric"><b class="red">LOCKED</b><small>LIVE BROKER</small></div>'+
    '<div class="metric"><b>YES</b><small>PAPER MODE</small></div>'+
    '<div class="metric"><b>'+S.data.health.event_count+'</b><small>JOURNAL EVENTS</small></div></div>'+
    '<div class="json">'+esc(JSON.stringify(S.data.health.monitoring||{},null,2))+'</div>')
}

function learning(){
  return panel("CONTROLLED SELF-LEARNING & MODEL EVOLUTION",
    '<div class="metric-grid">'+S.data.learning.stages.map(function(x){
      return '<div class="metric"><b>'+x.count+'</b><small>'+esc(x.name)+'</small></div>'
    }).join("")+'</div>'+
    '<div class="notice">Learning telemetry is observational; promotion remains governed by existing validation and registry gates.</div>')
}

function decisions(){
  var d=S.data.decisions||[];
  if(!d.length)return panel("DECISION INSPECTOR",'<div class="notice">No correlated decision trace is present in the MonitoringJournal.</div>');
  return panel("DECISION INSPECTOR",d.map(function(x){
    return '<article class="agent" onclick="inspectDecision(\''+esc(x.decision_id)+'\')">'+
      '<div class="head"><b>'+esc(x.decision_id)+'</b><span>'+x.event_count+' events</span></div>'+
      '<div class="sub">'+esc(x.timestamp)+'</div></article>'
  }).join(""))
}

function events(){return panel("EVENT LOG",ev())}

function chatBubble(item){
  var cls=item.role==="user"?"chat-user":"chat-assistant";
  return '<div class="chat-message '+cls+'"><div class="chat-role">'+
    (item.role==="user"?"YOU":"JARVIS")+'</div><div class="chat-text">'+esc(item.content).replace(/\n/g,"<br>")+
    '</div>'+(item.sources&&item.sources.length?'<div class="chat-sources">'+
    item.sources.map(function(s){return '<a href="'+esc(s.url)+'" target="_blank" rel="noreferrer">'+esc(s.title)+'</a>'}).join("")+
    '</div>':"")+'</div>'
}

function ai(){
  var body='<div class="ai-shell">'+
    '<div class="ai-header"><div><b>JARVIS / STOCK_BOT INTELLIGENCE</b>'+
    '<span>Dashboard-aware • market-aware • execution-safe</span></div>'+
    '<span class="ai-status">● READY</span></div>'+
    '<div class="ai-suggestions">'+
      '<button onclick="askAI(\'Give me the current overall market picture.\')">OVERALL MARKET</button>'+
      '<button onclick="askAI(\'What is happening in the market right now?\')">WHAT\'S HAPPENING</button>'+
      '<button onclick="askAI(\'Give me the current STOCK_BOT system status.\')">SYSTEM STATUS</button>'+
      '<button onclick="askAI(\'Explain the current pipeline and any missing telemetry.\')">PIPELINE HEALTH</button>'+
    '</div>'+
    '<div id="chat-log" class="chat-log">'+
      (S.chat.length?S.chat.map(chatBubble).join(""):'<div class="chat-empty"><b>JARVIS READY</b><span>Try: “What is going on in the market?” or “Give me the overall STOCK_BOT status.”</span></div>')+
    '</div>'+
    '<form class="chat-form" onsubmit="sendAI(event)">'+
      '<input id="chat-input" autocomplete="off" placeholder="Give JARVIS a command or ask a question...">'+
      '<button class="primary" type="submit" '+(S.chatBusy?"disabled":"")+'>SEND</button>'+
    '</form>'+
    '<div class="chat-disclaimer">AI is an intelligence/observability layer. It cannot authorize, size, or execute trades.</div>'+
  '</div>';
  return panel("AI COMMAND CENTER",body,"full")
}

function inspectAgent(id){
  S.inspect={title:id,data:S.data.agents.find(function(x){return x.agent_id===id})};
  render()
}

function inspectDecision(id){
  S.inspect={title:"DECISION / "+id,data:(S.data.decisions||[]).find(function(x){return x.decision_id===id})};
  render()
}

function render(){
  if(!S.data)return;
  document.getElementById("env").textContent=S.data.environment;
  document.getElementById("registered").textContent=S.data.summary.registered_agents+" AGENTS REGISTERED";
  document.getElementById("agent-count").textContent=S.data.summary.registered_agents;
  document.getElementById("active-count").textContent=S.data.summary.active;
  document.getElementById("waiting-count").textContent=S.data.summary.waiting;
  document.getElementById("locked-count").textContent=S.data.summary.locked;
  document.getElementById("telemetry").textContent=S.data.summary.events?"LIVE":"WAITING";

  var f={overview:overview,agents:agents,pipeline:pipeline,decisions:decisions,models:models,health:health,learning:learning,events:events,ai:ai};
  document.getElementById("view").innerHTML=f[S.view]();

  var slot=document.getElementById("inspector-slot");
  if(S.inspect){
    slot.classList.remove("hidden");
    slot.innerHTML='<button class="close" onclick="S.inspect=null;render()">✕</button>'+
      '<h2>'+esc(S.inspect.title)+'</h2>'+
      '<div class="json">'+esc(JSON.stringify(S.inspect.data,null,2))+'</div>';
  }else{
    slot.classList.add("hidden");
    slot.innerHTML="";
  }

  if(S.view==="ai"){
    var log=document.getElementById("chat-log");
    if(log)log.scrollTop=log.scrollHeight;
    var input=document.getElementById("chat-input");
    if(input&&!S.chatBusy)input.focus();
  }
}

function refresh(){
  Promise.all([get("/api/overview"),get("/api/decisions")]).then(function(x){
    S.data=x[0];
    S.data.decisions=x[1];
    render()
  }).catch(function(e){
    document.getElementById("view").innerHTML='<div class="notice">Dashboard backend unavailable: '+esc(e.message)+'</div>'
  })
}

function askAI(text){
  S.view="ai";
  document.querySelectorAll(".nav").forEach(function(x){x.classList.toggle("active",x.dataset.view==="ai")});
  render();
  var input=document.getElementById("chat-input");
  if(input){input.value=text;input.focus()}
  sendAI({preventDefault:function(){}})
}

function sendAI(event){
  if(event&&event.preventDefault)event.preventDefault();
  if(S.chatBusy)return;
  var input=document.getElementById("chat-input");
  if(!input)return;
  var message=input.value.trim();
  if(!message)return;

  S.chat.push({role:"user",content:message});
  input.value="";
  S.chatBusy=true;
  render();

  fetch("/api/chat",{
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({message:message,history:S.chat.slice(0,-1).slice(-12)})
  }).then(function(r){
    return r.json().then(function(body){
      if(!r.ok)throw Error(body.error||r.status);
      return body
    })
  }).then(function(body){
    S.chat.push({
      role:"assistant",
      content:body.answer||"No answer returned.",
      sources:body.sources||[]
    });
  }).catch(function(error){
    S.chat.push({
      role:"assistant",
      content:"JARVIS error: "+error.message
    });
  }).finally(function(){
    S.chatBusy=false;
    render();
  });
}

function openAI(){
  S.view="ai";
  S.inspect=null;
  document.querySelectorAll(".nav").forEach(function(x){
    x.classList.toggle("active",x.dataset.view==="ai")
  });
  render();
}

document.querySelectorAll(".nav").forEach(function(button){
  button.onclick=function(){
    document.querySelectorAll(".nav").forEach(function(x){x.classList.remove("active")});
    button.classList.add("active");
    S.view=button.dataset.view;
    S.inspect=null;
    refresh();
  }
});

setInterval(function(){
  document.getElementById("clock").textContent=
    new Date().toLocaleTimeString("en-IN",{hour12:false,timeZone:"Asia/Kolkata"})+" IST"
},1000);

refresh();
try{
  var es=new EventSource("/api/stream");
  es.addEventListener("telemetry",refresh)
}catch(e){}
