'use strict';
(()=>{
const root=document.querySelector('[data-sv]');if(!root)return;
const form=root.closest('form');
const pills=[...root.querySelectorAll('[data-sv-pill]')];
const total=pills.length;
const field=(i,k)=>form.querySelector('[data-sv-field="'+k+'"][data-index="'+i+'"]');
const q=s=>root.querySelector(s);
const sideKeys=['top','bottom','left','right'];
const inputs={};
['top','bottom','left','right','inner'].forEach(k=>{inputs[k]=q('[data-sv-input="'+k+'"]');});
const radios=[...root.querySelectorAll('[name="sv_hinge"]')];
const svg=q('.sv-door'),backBtn=q('[data-sv-back]'),nextBtn=q('[data-sv-next]'),submitBtn=q('[data-sv-submit]');
const errorBox=q('[data-sv-error]'),countEl=q('[data-sv-count]'),nameEl=q('[data-sv-name]'),qtyEl=q('[data-sv-qty]'),statusEl=q('[data-sv-status]'),hintEl=q('[data-sv-hint]');
const dialog=q('[data-sv-dialog]'),brandList=q('[data-sv-brand-list]'),brandLabel=q('[data-sv-brand-label]');
let brands=[];try{brands=JSON.parse(root.dataset.brands||'[]');}catch(e){brands=[];}
const defaultHint=hintEl.textContent;
let current=Math.min(Math.max(Number(root.dataset.start)||0,0),total-1);
const unitOf=i=>field(i,'unit').value==='in'?'in':'cm';
const factor=i=>unitOf(i)==='in'?25.4:10;
const toCm=(v,i)=>{const t=String(v).trim(),n=Number(t);return t!==''&&Number.isFinite(n)?String(Number((n/factor(i)).toFixed(3))):v;};
const toMm=(v,i)=>{const t=String(v).trim(),n=Number(t);return t!==''&&Number.isFinite(n)?String(Number((n*factor(i)).toFixed(2))):v;};
const unitLabels=[...root.querySelectorAll('[data-sv-unit]')],unitBtns=[...root.querySelectorAll('[data-sv-unit-btn]')],frameBtns=[...root.querySelectorAll('[data-sv-frame]')];
const validNum=text=>{const n=Number(text);return String(text).trim()!==''&&Number.isFinite(n)&&n>=0.1&&n<=20000;};
const done=i=>sideKeys.every(k=>validNum(field(i,k).value))&&field(i,'inner').value.trim()!==''&&['Left','Right'].includes(field(i,'hinge').value);
const allDone=()=>pills.every((_,i)=>done(i));
const reachable=i=>pills.slice(0,i).every((_,k)=>done(k));
const firstIncomplete=()=>pills.findIndex((_,i)=>!done(i));
const brandName=i=>{const id=Number(field(i,'brand_id').value);if(!id)return '';const b=brands.find(x=>x.id===id);return b?b.name:(pills[i].dataset.brandName||'');};
function showError(text){errorBox.textContent=text;errorBox.hidden=!text;}
function refreshBrand(){const n=brandName(current);brandLabel.textContent=n||'No brand selected';}
function refresh(){
 const ok=done(current),last=current===total-1;
 backBtn.hidden=current===0;
 nextBtn.hidden=last;
 submitBtn.hidden=!last;
 nextBtn.disabled=!ok;
 submitBtn.disabled=!allDone();
 statusEl.textContent=ok?'Complete':'Incomplete';
 statusEl.classList.toggle('sv-ok',ok);
 pills.forEach((pill,i)=>{pill.classList.toggle('active',i===current);pill.classList.toggle('done',done(i));pill.disabled=!reachable(i);});
 svg.dataset.hinge=field(current,'hinge').value;
 const fm=field(current,'frame').value==='noframe'?'noframe':'frame',un=unitOf(current);
 svg.dataset.frame=fm==='noframe'?'0':'1';
 frameBtns.forEach(b=>b.classList.toggle('active',b.dataset.svFrame===fm));
 unitBtns.forEach(b=>b.classList.toggle('active',b.dataset.svUnitBtn===un));
 unitLabels.forEach(s=>{s.textContent=un;});
 if(last&&!allDone())hintEl.textContent='Every item needs the top, bottom, left, right and inner measurements and a hinge position before you can submit.';
 else hintEl.textContent=defaultHint;
 refreshBrand();
}
function render(){
 const pill=pills[current];
 countEl.textContent='ITEM '+(current+1)+' OF '+total;
 nameEl.textContent=pill.dataset.name;
 qtyEl.textContent='Quantity '+pill.dataset.qty+(Number(pill.dataset.qty)>1?' · these measurements apply to every door of this item.':'');
 Object.keys(inputs).forEach(k=>{inputs[k].value=toCm(field(current,k).value,current);});
 radios.forEach(r=>{r.checked=r.value===field(current,'hinge').value;});
 showError('');
 refresh();
}
function go(index){current=index;render();inputs.top.focus({preventScroll:true});window.scrollTo({top:root.getBoundingClientRect().top+window.scrollY-20,behavior:'smooth'});}
Object.keys(inputs).forEach(k=>inputs[k].addEventListener('input',()=>{field(current,k).value=toMm(inputs[k].value,current);showError('');refresh();}));
radios.forEach(r=>r.addEventListener('change',()=>{if(r.checked){field(current,'hinge').value=r.value;showError('');refresh();}}));
frameBtns.forEach(b=>b.addEventListener('click',()=>{field(current,'frame').value=b.dataset.svFrame;refresh();}));
unitBtns.forEach(b=>b.addEventListener('click',()=>{field(current,'unit').value=b.dataset.svUnitBtn;render();}));
backBtn.addEventListener('click',()=>{if(current>0)go(current-1);});
nextBtn.addEventListener('click',()=>{if(!done(current)){showError('Enter the top, bottom, left, right and inner measurements and the hinge position to continue.');return;}if(current<total-1)go(current+1);});
pills.forEach((pill,i)=>pill.addEventListener('click',()=>{if(reachable(i))go(i);}));
Object.values(inputs).forEach(input=>input.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();if(current<total-1&&done(current))go(current+1);}}));
function buildBrands(){
 brandList.textContent='';
 if(!brands.length){const p=document.createElement('p');p.className='muted';p.textContent='No lock brands have been added yet. Ask an admin to add them in the Door handle list.';brandList.appendChild(p);return;}
 const selected=Number(field(current,'brand_id').value)||0;
 brands.forEach(b=>{
  const btn=document.createElement('button');btn.type='button';btn.className='sv-brand-item'+(b.id===selected?' active':'');
  if(b.image){const im=document.createElement('img');im.src=b.image;im.alt=b.name;im.loading='lazy';btn.appendChild(im);}
  const s=document.createElement('strong');s.textContent=b.name;btn.appendChild(s);

  if(b.company){const c=document.createElement('span');c.textContent=b.company;btn.appendChild(c);}
  if(b.details){const d=document.createElement('small');d.textContent=b.details;btn.appendChild(d);}
  btn.addEventListener('click',()=>{field(current,'brand_id').value=String(b.id);pills[current].dataset.brandName=b.name;dialog.close();refresh();});
  brandList.appendChild(btn);
 });
}
q('[data-sv-brand-open]').addEventListener('click',()=>{buildBrands();dialog.showModal();});
q('[data-sv-brand-close]').addEventListener('click',()=>dialog.close());
q('[data-sv-brand-clear]').addEventListener('click',()=>{field(current,'brand_id').value='';pills[current].dataset.brandName='';dialog.close();refresh();});
dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close();});
form.addEventListener('submit',event=>{
 if(allDone())return;
 event.preventDefault();
 const index=firstIncomplete();
 go(index);
 showError('Complete the top, bottom, left, right and inner measurements and the hinge position for this item before submitting.');
});
if(!reachable(current))current=Math.max(firstIncomplete(),0);
render();
})();
