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
