const $=x=>document.getElementById(x);let history=[],hi=0,done=false;
async function start(){
 const r=await fetch('/api/start',{method:'POST'}),d=await r.json();
 $('brief').textContent=d.mission.brief;$('ticket').textContent=d.mission.ticket;$('missionTitle').textContent=d.mission.title;
 $('prompt').textContent=d.prompt;$('output').innerHTML='';$('score').textContent='1000';$('complete').classList.add('hidden');
 $('hintText').textContent='ヒントは必要な時だけ使いや。';history=[];hi=0;done=false;topo(d.topology);$('cmd').focus();
}
function print(t,cls='out'){if(!t)return;let d=document.createElement('div');d.className=cls;d.textContent=t;$('output').appendChild(d);$('terminal').scrollTop=$('terminal').scrollHeight}
function topo(t){$('wanwire').className='wire '+(t.r1wan==='up'?'ok':'bad');$('wanwire').innerHTML=t.r1wan==='up'?'':'<em>×</em>';if(t.server==='reachable')$('serverIcon').style.borderColor='var(--green)'}
async function send(){
 let i=$('cmd'),c=i.value.trim();if(!c)return;print($('prompt').textContent+' '+c,'echo');history.push(c);hi=history.length;i.value='';
 let r=await fetch('/api/cmd',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:c})}),d=await r.json();
 print(d.output);$('prompt').textContent=d.prompt;$('score').textContent=d.score;topo(d.topology);
 if(d.solved&&!done){done=true;setTimeout(()=>{$('finalScore').textContent=d.score;$('complete').classList.remove('hidden')},650)}i.focus()
}
function completion(v){
 const cmds=['enable','configure terminal','show running-config','show ip interface brief','show interfaces GigabitEthernet0/0','show interfaces GigabitEthernet0/1','show ip route','copy running-config startup-config','interface GigabitEthernet0/0','interface GigabitEthernet0/1','no shutdown','shutdown'];
 let m=cmds.filter(x=>x.toLowerCase().startsWith(v.toLowerCase()));return m.length===1?m[0]:v
}
$('cmd').addEventListener('keydown',e=>{
 if(e.key==='Enter')send();
 else if(e.key==='ArrowUp'){e.preventDefault();if(history.length){hi=Math.max(0,hi-1);$('cmd').value=history[hi]}}
 else if(e.key==='ArrowDown'){e.preventDefault();if(history.length){hi=Math.min(history.length,hi+1);$('cmd').value=hi===history.length?'':history[hi]}}
 else if(e.key==='Tab'){e.preventDefault();$('cmd').value=completion($('cmd').value)}
});
$('hint').onclick=async()=>{let r=await fetch('/api/hint',{method:'POST'}),d=await r.json();$('hintText').textContent=d.hint};
$('reset').onclick=start;$('again').onclick=start;start();
