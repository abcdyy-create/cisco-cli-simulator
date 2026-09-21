const $ = id => document.getElementById(id);
let current = 1;
let levels = [];

async function start(level=1){
  current = level;
  const r = await fetch('/api/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({level})});
  const d = await r.json();
  $('levelNo').textContent = `CASE ${String(d.level.id).padStart(2,'0')}`;
  $('title').textContent = d.level.title;
  $('brief').textContent = d.level.brief;
  $('goal').textContent = d.level.goal;
  $('output').innerHTML = '';
  $('success').classList.add('hidden');
  $('prompt').textContent = d.state.hostname + '>';
  renderLevels();
  $('cmd').focus();
}

async function loadLevels(){
  levels = [
    [1,'Interface Down','Gi0/1 復旧'],
    [2,'VLAN Trouble','Fa0/3 → VLAN 20'],
    [3,'Static Route','10.20.0.0/24'],
    [4,'OSPF Neighbor','OSPF area 0'],
    [5,'ACL Block','HTTPS permit']
  ];
  renderLevels();
  start(1);
}
function renderLevels(){
  $('levels').innerHTML = levels.map(x=>`<button class="level ${x[0]===current?'active':''}" onclick="start(${x[0]})"><strong>CASE ${String(x[0]).padStart(2,'0')} · ${x[1]}</strong><small>${x[2]}</small></button>`).join('');
}
function print(text){
  if(!text)return;
  const d=document.createElement('div');d.className='out';d.textContent=text;$('output').appendChild(d);
  $('terminal').scrollTop=$('terminal').scrollHeight;
}
async function command(){
  const input=$('cmd'), cmd=input.value.trim();
  if(!cmd)return;
  const oldPrompt=$('prompt').textContent;
  print(`${oldPrompt} ${cmd}`);
  input.value='';
  const r=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:cmd})});
  const d=await r.json();
  print(d.output);
  $('prompt').textContent=d.prompt;
  if(d.solved)$('success').classList.remove('hidden');
  input.focus();
}
$('cmd').addEventListener('keydown',e=>{if(e.key==='Enter')command()});
$('reset').onclick=()=>start(current);
$('clear').onclick=()=>{$('output').innerHTML='';$('cmd').focus()};
$('next').onclick=()=>start(Math.min(current+1,levels.length));
loadLevels();
