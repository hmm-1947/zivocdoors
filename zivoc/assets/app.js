'use strict';
document.querySelectorAll('[data-search]').forEach(input => {
 input.addEventListener('input', () => {
  const term = input.value.toLowerCase();
  document.getElementById(input.dataset.search).querySelectorAll('[data-record]').forEach(record => { record.hidden = !record.textContent.toLowerCase().includes(term); });
 });
});
const locationButton = document.getElementById('get-location');
if (locationButton) {
 const form = document.getElementById('attendance-form');
 const status = document.getElementById('location-status');
 locationButton.addEventListener('click', () => {
  if (!navigator.geolocation) {status.textContent='Location is unavailable in this browser.';return;}
  locationButton.disabled=true;status.textContent='Finding your location…';
  navigator.geolocation.getCurrentPosition(position => {
   form.elements.latitude.value=position.coords.latitude;
   form.elements.longitude.value=position.coords.longitude;
   form.elements.accuracy.value=position.coords.accuracy;
   status.textContent=`Location captured · accuracy ±${Math.round(position.coords.accuracy)} m`;
   document.getElementById('punch-submit').disabled=false;locationButton.disabled=false;
  }, error => {status.textContent='Location access failed. Enable location permissions and try again. '+error.message;locationButton.disabled=false;}, {enableHighAccuracy:true,timeout:20000,maximumAge:0});
 });
 let previewURL;
 form.elements.selfie.addEventListener('change', event => {
  const file=event.target.files[0];const image=document.getElementById('selfie-preview');
  if(previewURL)URL.revokeObjectURL(previewURL);
  if(!file){image.hidden=true;return;}
  if(file.size>5*1024*1024){status.textContent='Choose a selfie below 5 MB.';event.target.value='';image.hidden=true;return;}
  previewURL=URL.createObjectURL(file);image.src=previewURL;image.hidden=false;
 });
}
// Poll in-app reminders while signed in; no background notification service is required.
if(document.querySelector('.bottom-nav')) {
 const shown=new Set();
 async function checkReminders(){
  try {
   const response=await fetch('/reminders',{headers:{Accept:'application/json'}});
   if(!response.ok)return;const data=await response.json();
   const fresh=data.filter(item=>!shown.has(item.id));
   if(!fresh.length)return;fresh.forEach(item=>shown.add(item.id));
   let box=document.getElementById('live-reminder');
   if(!box){box=document.createElement('div');box.id='live-reminder';box.className='notice';box.setAttribute('role','status');document.querySelector('.shell main').prepend(box);}
   box.replaceChildren();const link=document.createElement('a');link.href='?page=reminders';link.textContent=`${data.length} follow-up${data.length===1?'':'s'} due · ${fresh[0].title} →`;box.append(link);
  }catch(error){/* A later poll retries temporary connection failures. */}
 }
 checkReminders();setInterval(checkReminders,60000);
}

const leadSelect=document.getElementById('order-lead');
if(leadSelect){
 const form=leadSelect.form;
 function fillLead(){const option=leadSelect.selectedOptions[0], existing=!!leadSelect.value;
 for(const [field,key] of [['customer','name'],['phone','phone'],['address','address']]){form.elements[field].value=existing?option.dataset[key]:'';form.elements[field].readOnly=existing;}
 const salesman=form.elements.salesman_id;if(salesman){salesman.value=existing?option.dataset.salesman:'';salesman.disabled=existing;}
 }
 leadSelect.addEventListener('change',fillLead);if(leadSelect.value)fillLead();
 function total(){let value=0;form.querySelectorAll('input[name^="items["]').forEach(input=>value+=(Number(input.value)||0)*(Number(input.dataset.price)||0));document.getElementById('order-total').textContent='Total: '+new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0}).format(value);}
 form.addEventListener('input',total);total();
}

document.getElementById('print-salary')?.addEventListener('click',()=>window.print());

const attendanceCalendar=document.querySelector('.attendance-month');
if(attendanceCalendar){attendanceCalendar.addEventListener('click',event=>{
 const button=event.target.closest('[data-calendar-date]');if(!button)return;
 attendanceCalendar.querySelectorAll('[aria-pressed]').forEach(day=>day.setAttribute('aria-pressed',day===button?'true':'false'));
 const parts=[new Date(button.dataset.calendarDate+'T12:00:00').toLocaleDateString('en-IN',{weekday:'long',day:'numeric',month:'long',year:'numeric'}),button.dataset.calendarLabel];
 if(button.dataset.calendarPunch)parts.push('Checked in: '+button.dataset.calendarPunch);
 if(button.dataset.calendarPending==='1')parts.push('Leave request pending');
 document.getElementById('calendar-day-details').textContent=parts.join(' · ');
});}

// Missing or inaccessible ERP images keep the product selectable.
document.querySelectorAll('.product-image').forEach(image=>{
 const showFallback=()=>{image.hidden=true;const placeholder=image.parentElement.querySelector('.product-image-fallback');if(placeholder)placeholder.hidden=false;};
 image.addEventListener('error',showFallback);
 if(image.complete && image.naturalWidth===0)showFallback();
});

document.querySelector('[data-orders-csv]')?.addEventListener('click',()=>{
 const table=document.getElementById('orders-table');if(!table)return;
 const quote=text=>'"'+text.replace(/\s+/g,' ').trim().replace(/"/g,'""')+'"';
 const lines=[Array.from(table.tHead.rows[0].cells).filter((cell,index)=>index!==1).map(cell=>quote(cell.textContent)).join(',')];
 table.querySelectorAll('tr.ol-main').forEach(row=>lines.push(Array.from(row.cells).filter((cell,index)=>index!==1).map(cell=>quote(cell.textContent)).join(',')));
 const url=URL.createObjectURL(new Blob(['\ufeff'+lines.join('\r\n')],{type:'text/csv;charset=utf-8'}));
 const link=document.createElement('a');link.href=url;link.download='orders.csv';document.body.append(link);link.click();link.remove();URL.revokeObjectURL(url);
});

(function(){const toggle=document.getElementById('sidebar-toggle');if(!toggle)return;const root=document.documentElement;const sync=()=>toggle.setAttribute('aria-expanded',root.classList.contains('sb-collapsed')?'false':'true');sync();toggle.addEventListener('click',()=>{root.classList.toggle('sb-collapsed');try{localStorage.setItem('zv-sidebar',root.classList.contains('sb-collapsed')?'1':'0')}catch(e){}sync();});})();
document.addEventListener('submit', event => {
  const button = event.submitter;
  const message = button && button.getAttribute('data-confirm');
  if (message && !window.confirm(message)) {
    event.preventDefault();
  }
});
(function(){
  const d=document.getElementById('survey-date'),t=document.getElementById('survey-time');
  if(!d||!t)return;
  const pad=n=>String(n).padStart(2,'0');
  const sync=()=>{
    const n=new Date(Date.now()+300000);
    const day=n.getFullYear()+'-'+pad(n.getMonth()+1)+'-'+pad(n.getDate());
    d.min=day;
    if(d.value===day){t.min=pad(n.getHours())+':'+pad(n.getMinutes());}else{t.removeAttribute('min');}
    d.setCustomValidity(d.value&&d.value<day?'Choose today or a future date.':'');
    t.setCustomValidity(d.value===day&&t.value&&t.value<t.min?'Choose a time at least 5 minutes from now.':'');
  };
  d.addEventListener('input',sync);t.addEventListener('input',sync);setInterval(sync,30000);sync();
})();
(function(){
  const root=document.documentElement;
  if(!document.querySelector('.sidebar'))return;
  const mobile=()=>window.matchMedia('(max-width:700px)').matches;
  const back=document.createElement('div');back.className='nav-backdrop';document.body.appendChild(back);
  const setOpen=v=>root.classList.toggle('nav-open',v);
  back.addEventListener('click',()=>setOpen(false));
  document.querySelectorAll('.sidebar nav a').forEach(a=>a.addEventListener('click',()=>setOpen(false)));
  window.addEventListener('resize',()=>{if(!mobile())setOpen(false);});
  let sx=0,sy=0,ok=false;
  const blocked=el=>{for(;el&&el!==document.body;el=el.parentElement){if(/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)||el.isContentEditable)return true;if(el.scrollWidth>el.clientWidth+4&&/(auto|scroll)/.test(getComputedStyle(el).overflowX))return true;}return false;};
  document.addEventListener('touchstart',e=>{if(!mobile()||e.touches.length!==1){ok=false;return;}const t=e.touches[0];sx=t.clientX;sy=t.clientY;ok=!blocked(e.target)||root.classList.contains('nav-open');},{passive:true});
  document.addEventListener('touchend',e=>{if(!ok)return;ok=false;const t=e.changedTouches[0],dx=t.clientX-sx,dy=t.clientY-sy;if(Math.abs(dx)<70||Math.abs(dy)>Math.abs(dx)*0.6)return;if(dx>0&&!root.classList.contains('nav-open'))setOpen(true);else if(dx<0&&root.classList.contains('nav-open'))setOpen(false);},{passive:true});
})();
document.addEventListener('click',e=>{const b=e.target.closest&&e.target.closest('[data-coming-soon]');if(b){e.preventDefault();alert('Coming Soon');}});

