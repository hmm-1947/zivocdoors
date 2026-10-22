'use strict';
(()=>{
const root=document.querySelector('[data-sv]');if(!root)return;
const form=root.closest('form');
const pills=[...root.querySelectorAll('[data-sv-pill]')];
const total=pills.length;
const field=(i,k)=>form.querySelector('[data-sv-field="'+k+'"][data-index="'+i+'"]');
const q=s=>root.querySelector(s);
const lengthInput=q('[data-sv-input="length"]'),heightInput=q('[data-sv-input="height"]');
const radios=[...root.querySelectorAll('[name="sv_hinge"]')];
const svg=q('.sv-door'),backBtn=q('[data-sv-back]'),nextBtn=q('[data-sv-next]'),submitBtn=q('[data-sv-submit]');
const errorBox=q('[data-sv-error]'),countEl=q('[data-sv-count]'),nameEl=q('[data-sv-name]'),qtyEl=q('[data-sv-qty]'),statusEl=q('[data-sv-status]'),hintEl=q('[data-sv-hint]');
const defaultHint=hintEl.textContent;
let current=Math.min(Math.max(Number(root.dataset.start)||0,0),total-1);
const valid=text=>{const n=Number(text);return text!==''&&Number.isFinite(n)&&n>=0.1&&n<=20000;};
const done=i=>valid(field(i,'length').value)&&valid(field(i,'height').value)&&['Left','Right'].includes(field(i,'hinge').value);
const allDone=()=>pills.every((_,i)=>done(i));
const reachable=i=>pills.slice(0,i).every((_,k)=>done(k));
const firstIncomplete=()=>pills.findIndex((_,i)=>!done(i));
function showError(text){errorBox.textContent=text;errorBox.hidden=!text;}
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
 if(last&&!allDone())hintEl.textContent='Every item needs a length, height and hinge position before you can submit.';
 else hintEl.textContent=defaultHint;
}
function render(){
 const pill=pills[current];
 countEl.textContent='ITEM '+(current+1)+' OF '+total;
 nameEl.textContent=pill.dataset.name;
 qtyEl.textContent='Quantity '+pill.dataset.qty+(Number(pill.dataset.qty)>1?' · these measurements apply to every door of this item.':'');
 lengthInput.value=field(current,'length').value;
 heightInput.value=field(current,'height').value;
 radios.forEach(r=>{r.checked=r.value===field(current,'hinge').value;});
 showError('');
 refresh();
}
function go(index){current=index;render();lengthInput.focus({preventScroll:true});window.scrollTo({top:root.getBoundingClientRect().top+window.scrollY-20,behavior:'smooth'});}
lengthInput.addEventListener('input',()=>{field(current,'length').value=lengthInput.value;showError('');refresh();});
heightInput.addEventListener('input',()=>{field(current,'height').value=heightInput.value;showError('');refresh();});
radios.forEach(r=>r.addEventListener('change',()=>{if(r.checked){field(current,'hinge').value=r.value;showError('');refresh();}}));
backBtn.addEventListener('click',()=>{if(current>0)go(current-1);});
nextBtn.addEventListener('click',()=>{if(!done(current)){showError('Enter the length, height and hinge position to continue.');return;}if(current<total-1)go(current+1);});
pills.forEach((pill,i)=>pill.addEventListener('click',()=>{if(reachable(i))go(i);}));
[lengthInput,heightInput].forEach(input=>input.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();if(current<total-1&&done(current))go(current+1);}}));
form.addEventListener('submit',event=>{
 if(allDone())return;
 event.preventDefault();
 const index=firstIncomplete();
 go(index);
 showError('Complete the length, height and hinge position for this item before submitting.');
});
if(!reachable(current))current=Math.max(firstIncomplete(),0);
render();
})();
