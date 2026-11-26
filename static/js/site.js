(function(){
var $=function(s){return document.querySelector(s)},$$=function(s){return Array.prototype.slice.call(document.querySelectorAll(s))};
document.documentElement.classList.add('js');
/* scroll reveal */
var rv=$$('.step,.icard,.grp,.roles>div,section h2,.sub');
rv.forEach(function(el,i){el.classList.add('rv');el.style.transitionDelay=(i%6)*70+'ms'});
if('IntersectionObserver' in window){
 var io=new IntersectionObserver(function(es){es.forEach(function(x){if(x.isIntersecting){x.target.classList.add('in');io.unobserve(x.target)}})},{threshold:.15});
 rv.forEach(function(el){io.observe(el)});
}else rv.forEach(function(el){el.classList.add('in')});

/* live leaderboard */
var rows=$$('.board .rows .row'),list=$('.board .rows');
if($('.board[data-demo]')&&rows.length&&!matchMedia('(prefers-reduced-motion:reduce)').matches){
 function sc(r){return +r.querySelector('.score').textContent}
 function paint(r){r.querySelector('.bar i').style.width=Math.min(100,sc(r)/2)+'%'}
 setInterval(function(){
  var r=rows[Math.floor(Math.random()*rows.length)],s=r.querySelector('.score');
  var first=rows.map(function(x){return x.getBoundingClientRect().top});
  s.textContent=sc(r)+3+Math.floor(Math.random()*8);
  r.classList.add('up');setTimeout(function(){r.classList.remove('up')},900);paint(r);
  rows.sort(function(a,b){return sc(b)-sc(a)});
  var old=$$('.board .rows .row');
  rows.forEach(function(x,i){list.appendChild(x);x.querySelector('.pos').textContent=i+1});
  rows.forEach(function(x){var i0=old.indexOf(x),dy=first[i0]-x.getBoundingClientRect().top;
   if(dy){x.style.transition='none';x.style.transform='translateY('+dy+'px)';x.getBoundingClientRect();x.style.transition='transform .6s cubic-bezier(.2,.8,.2,1)';x.style.transform=''}});
 },2600);
}
/* ---- separate teacher cabinet page ---- */
function el(t,c,x){var e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e}
function cu(){return users[sess]}
function showLand(){['header','main','footer'].forEach(function(s){$(s).hidden=false});$('#cabinet').hidden=true}
function panel(p){
 ['pProf','pData','pRecs','pRate'].forEach(function(id){$('#'+id).hidden=id!==p});
 $$('.side button').forEach(function(b){b.classList.toggle('on',b.dataset.p===p)});
 if(p==='pData'){$('#entry').hidden=true;$('#catWrap').hidden=false}
 if(p==='pRecs')renderRecs();
 if(p==='pRate')renderRate();
 window.scrollTo(0,0);
}
function showCab(){
 var u=cu();if(!u)return;
 $$('dialog[open]').forEach(function(d){d.close()});
 ['header','main','footer'].forEach(function(s){$(s).hidden=true});
 $('#cabinet').hidden=false;
 $('#cName').textContent=u.last+' '+u.first;
 $('#pName').textContent=[u.last,u.first,u.mid].filter(Boolean).join(' ');
 $('#pRole').textContent=u.role+', '+u.school;
 var dl=$('#pDl');dl.textContent='';
 [['Туған күні',u.dob],['Пәні',u.subject],['Санаты',u.cat],['Жұмыс өтілі',u.exp+' жыл'],['Білімі',u.edu],['Email',u.email],['Телефон',u.phone||'—']].forEach(function(r){dl.appendChild(el('dt',0,r[0]));dl.appendChild(el('dd',0,r[1]))});
 var g=$('#catGrid');g.textContent='';
 $$('section .icard').forEach(function(c){var k=c.cloneNode(true);k.className='icard';k.style.cssText='';k.tabIndex=0;k.setAttribute('role','button');
  var go=function(){openEntry(k.querySelector('b').textContent)};k.addEventListener('click',go);k.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();go()}});g.appendChild(k)});
 if(location.hash!=='#kabinet'){try{location.hash='kabinet'}catch(e){}}
 panel('pProf');
}
function openEntry(name){$('#entCat').textContent=name;$('#catWrap').hidden=true;$('#entry').reset();$('#entry').hidden=false;$('#entDate').max=new Date().toISOString().slice(0,10)}
$('#entCancel').addEventListener('click',function(){panel('pData')});
$('#entry').addEventListener('submit',function(e){
 e.preventDefault();var f=e.target,u=cu();if(!u)return;
 var fl=f.file.files[0];
 (u.recs=u.recs||[]).unshift({id:Date.now(),cat:$('#entCat').textContent,title:f.title.value.trim(),level:f.level.value,date:f.date.value,desc:f.desc.value.trim(),file:fl?fl.name:'',status:'Күтуде'});
 persist();panel('pRecs');
});
function renderRecs(){
 var u=cu(),box=$('#recList');box.textContent='';var rs=(u&&u.recs)||[];
 if(!rs.length){box.appendChild(el('p','sub','Әзірге жазба жоқ. «Деректерді енгізу» бөлімінен алғашқы жетістікті қосыңыз.'));return}
 rs.forEach(function(r){
  var row=el('div','rec'),t=el('div');
  t.appendChild(el('b',0,r.title));
  t.appendChild(el('small',0,[r.cat,r.level,r.date].join(', ')));
  if(r.desc){t.appendChild(el('div',0,r.desc)).style.fontSize='14px'}
  if(r.file){var fl=el('small',0,'Файл: '+r.file);fl.style.display='block';t.appendChild(fl)}
  var d=el('button','del','×');d.type='button';d.setAttribute('aria-label','Жою');
  d.addEventListener('click',function(){u.recs=u.recs.filter(function(x){return x.id!==r.id});persist();renderRecs()});
  row.appendChild(t);row.appendChild(el('span','badge',r.status));row.appendChild(d);box.appendChild(row);
 });
}
function renderRate(){
 var u=cu(),rs=(u&&u.recs)||[],ok=rs.filter(function(r){return r.status==='Расталды'}).length;
 var st=$('#rStat');st.textContent='';
 [['0','жалпы ұпай'],['—','мектептегі орын'],[String(rs.length),'жіберілген жазба'],[String(ok),'расталған']].forEach(function(s){var d=el('div');d.appendChild(el('strong',0,s[0]));d.appendChild(el('span',0,s[1]));st.appendChild(d)});
 var bx=$('#rBars');bx.textContent='';
 $$('section .icard b').forEach(function(b){
  var n=rs.filter(function(r){return r.cat===b.textContent}).length,row=el('div','rbar'),w=el('div'),bar=el('div','bar'),i=el('i');
  w.appendChild(el('span',0,b.textContent));i.style.width=Math.min(100,n*20)+'%';bar.appendChild(i);w.appendChild(bar);
  row.appendChild(w);row.appendChild(el('span',0,String(n)));bx.appendChild(row);
 });
}
$$('.side button').forEach(function(b){b.addEventListener('click',function(){panel(b.dataset.p)})});
$('#cOut').addEventListener('click',function(){setSess(null);refreshNav();showLand();try{history.replaceState(null,'',location.pathname+location.search)}catch(e){}});
window.addEventListener('hashchange',function(){if(location.hash==='#kabinet'&&sess&&users[sess])showCab();else showLand()});
if(sess&&users[sess]&&location.hash==='#kabinet')showCab();
})();
(function(){
document.querySelectorAll('[data-open]').forEach(function(b){b.addEventListener('click',function(){var d=document.getElementById(b.dataset.open);if(d&&d.showModal)d.showModal()})});
document.querySelectorAll('dialog [data-close]').forEach(function(b){b.addEventListener('click',function(){b.closest('dialog').close()})});
document.querySelectorAll('dialog.dlg').forEach(function(d){d.addEventListener('click',function(e){if(e.target===d)d.close()})});
})();
