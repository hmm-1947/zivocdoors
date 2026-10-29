'use strict';
const qtForm=document.querySelector('.qt-create');
if(qtForm&&!qtForm.hasAttribute('data-order')){
 const $=id=>document.getElementById(id);
 const code=$('qt-item-code'),itemName=$('qt-item-name'),itemQty=$('qt-item-qty'),itemPrice=$('qt-item-price'),message=$('qt-item-message'),rows=$('qt-product-rows');
 const discPer=$('qt-disc-per'),discAmt=$('qt-disc-amt'),discHidden=$('qt-discount');
 let serial=Date.now(),lastEdited='per';
 const money=value=>(Math.round(value*100)/100).toFixed(2);
 const number=value=>Number(value)||0;

 function summary(){
  let qty=0,subtotal=0,index=0;
  rows.querySelectorAll('tr').forEach(row=>{
   index++;
   const q=number(row.querySelector('[name$="[quantity]"]').value),p=number(row.querySelector('[name$="[unit_price]"]').value);
   qty+=q;subtotal+=q*p;
   const sl=row.querySelector('[data-qt-sl]');if(sl)sl.textContent=index;
  });
  let discount;
  if(lastEdited==='per'){discount=Math.round(subtotal*Math.min(100,Math.max(0,number(discPer.value))))/100;discAmt.value=money(discount);}
  else{discount=Math.max(0,number(discAmt.value));discPer.value=subtotal>0?String(Math.round(discount/subtotal*10000)/100):'0';}
  discHidden.value=money(discount);
  $('qt-total-qty').value=qty;$('qt-subtotal').value=money(subtotal);$('qt-grand').value=money(Math.max(0,subtotal-discount));
  return discount>subtotal;
 }
 function refresh(){const over=summary();qtForm.dispatchEvent(new Event('input',{bubbles:true}));if(over)message.textContent='Discount cannot exceed subtotal.';}

 code.addEventListener('change',()=>{
  const option=code.selectedOptions[0];
  itemName.value=option&&option.value?option.dataset.name:'';
  itemPrice.value=option&&option.value?money(number(option.dataset.price||7500)):'0.00';
 });

 function buildRow(codeValue,name,qty,price){
  const key=String(serial++),tr=document.createElement('tr');
  tr.insertCell().dataset.qtSl='';
   const actions=tr.insertCell();actions.className='zf-row-actions';
   for(const [cls,attr,text,title,hidden]of[['zf-icon-btn zf-edit','qtEdit','Edit','Edit',false],['zf-icon-btn zf-save','qtSave','Save','Save',true],['zf-icon-btn zf-del','qtRemove','Delete','Delete',false]]){
    const button=document.createElement('button');button.type='button';button.className=cls;button.dataset[attr]='';button.textContent=text;button.title=title;button.hidden=hidden;actions.append(button);
   }
   const codeCell=tr.insertCell(),codeText=document.createElement('span');codeText.dataset.qtCodeText='';codeText.textContent=codeValue;codeCell.append(codeText);
   const hiddenCode=document.createElement('input');hiddenCode.type='hidden';hiddenCode.name=`qt_items[${key}][code]`;hiddenCode.value=codeValue;codeCell.append(hiddenCode);
   const nameCell=tr.insertCell();nameCell.dataset.qtNameText='';nameCell.textContent=name;
  for(const [field,value,step,min]of[['quantity',qty,'1','1'],['unit_price',price,'0.01','0']]){
   const cell=tr.insertCell(),input=document.createElement('input');
   Object.assign(input,{type:'number',name:`qt_items[${key}][${field}]`,value,step,min,required:true,readOnly:true});
   input.setAttribute('aria-label',field==='quantity'?'Quantity':'Unit price');
   if(field==='quantity')input.max='10000';
   cell.append(input);
  }
  tr.insertCell().dataset.qtLineTotal='';
  return tr;
 }

 document.querySelector('[data-qt-add]').addEventListener('click',()=>{
  const option=code.selectedOptions[0];
  if(!option||!option.value||!itemQty.checkValidity()||!itemPrice.checkValidity()||number(itemQty.value)<1){message.textContent='Select an item, a whole quantity and a valid price.';return;}
  if(rows.querySelectorAll('tr').length>=100){message.textContent='Maximum 100 product rows.';return;}
  rows.append(buildRow(option.value,option.dataset.name,itemQty.value,itemPrice.value));
  code.value='';itemName.value='';itemQty.value='1';itemPrice.value='0.00';message.textContent='Item added.';
  refresh();
 });

 qtForm.addEventListener('click',event=>{
  const remove=event.target.closest('[data-qt-remove]'),edit=event.target.closest('[data-qt-edit]'),save=event.target.closest('[data-qt-save]');
  if(remove){remove.closest('tr').remove();refresh();}
  if(edit){
   const row=edit.closest('tr');
   row.querySelectorAll('input[type="number"]').forEach(input=>{input.readOnly=false;});
   const hidden=row.querySelector('[name$="[code]"]'),text=row.querySelector('[data-qt-code-text]');
   if(hidden&&text&&!row.querySelector('[data-qt-code-select]')){
    const select=code.cloneNode(true);select.removeAttribute('id');select.dataset.qtCodeSelect='';select.value=hidden.value;
    text.hidden=true;text.after(select);
   }
   edit.hidden=true;row.querySelector('[data-qt-save]').hidden=false;row.querySelector('[name$="[quantity]"]').focus();
  }
  if(save){
   const row=save.closest('tr'),inputs=row.querySelectorAll('input[type="number"]'),select=row.querySelector('[data-qt-code-select]');
   if(![...inputs].every(input=>input.checkValidity())||(select&&!select.value)){message.textContent='Enter a valid code, quantity and price.';return;}
   if(select){
    const hidden=row.querySelector('[name$="[code]"]'),text=row.querySelector('[data-qt-code-text]'),option=select.selectedOptions[0];
    if(hidden.value!==select.value){row.querySelector('[name$="[unit_price]"]').value=money(number(option.dataset.price||7500));}
    hidden.value=select.value;text.textContent=select.value;text.hidden=false;
    row.querySelector('[data-qt-name-text]').textContent=option.dataset.name;select.remove();
   }
   inputs.forEach(input=>{input.readOnly=true;});save.hidden=true;row.querySelector('[data-qt-edit]').hidden=false;refresh();
  }
 });
 qtForm.addEventListener('input',event=>{
  const target=event.target;
  if(target===discPer){lastEdited='per';summary();}
  else if(target===discAmt){lastEdited='amt';summary();}
  else if(target.closest&&target.closest('#qt-product-rows')){summary();}
 },true);
 qtForm.addEventListener('submit',event=>{
  if(!rows.querySelector('tr')){event.preventDefault();message.textContent='Add at least one item to the quotation.';return;}
  if(summary()){event.preventDefault();message.textContent='Discount cannot exceed subtotal.';return;}
  rows.querySelectorAll('input[type="number"]').forEach(input=>{input.readOnly=false;});
 });
 if(Number(discHidden.value)>0)lastEdited='amt';
 discAmt.value=money(number(discHidden.value));
 refresh();
}
if(qtForm&&qtForm.hasAttribute('data-order')){
 const num=value=>Number(value)||0,fmt=value=>(Math.round(value*100)/100).toFixed(2),$=id=>document.getElementById(id);
 let qty=0,subtotal=0,index=0;
 $('qt-product-rows').querySelectorAll('tr').forEach(row=>{
  index++;
  const q=num(row.querySelector('[name$="[quantity]"]').value),p=num(row.querySelector('[name$="[unit_price]"]').value);
  qty+=q;subtotal+=q*p;
  row.querySelector('[data-qt-sl]').textContent=index;
  row.querySelector('[data-qt-line-total]').textContent=fmt(q*p);
 });
 const discount=Math.max(0,num($('qt-discount').value));
 $('qt-total-qty').value=qty;$('qt-subtotal').value=fmt(subtotal);$('qt-disc-amt').value=fmt(discount);
 $('qt-disc-per').value=subtotal>0?String(Math.round(discount/subtotal*10000)/100):'0';
 $('qt-grand').value=fmt(Math.max(0,subtotal-discount));
 const lock=()=>qtForm.querySelectorAll('input,select,textarea').forEach(el=>{el.disabled=true;});
 lock();
 window.addEventListener('load',()=>{lock();setTimeout(lock,300);});
}
document.querySelectorAll('[data-qt-template]').forEach(select=>select.addEventListener('change',()=>{if(select.value)select.form.elements.terms.value=select.selectedOptions[0].dataset.terms||'';}));
if(qtForm&&(qtForm.hasAttribute('data-edit')||qtForm.hasAttribute('data-prefill'))){
 setTimeout(()=>{
  const existing=document.getElementById('party-existing'),franchise=document.getElementById('party-franchise'),lead=document.getElementById('party-lead-id');
  if(existing){existing.required=false;if(lead&&lead.value&&[...existing.options].some(o=>o.value===lead.value))existing.value=lead.value;}
  if(franchise)franchise.required=false;
 },0);
}
(function(){
 const menu=document.querySelector('[data-qt-menu]');
 if(menu){
  const button=menu.querySelector('[data-qt-menu-btn]'),list=menu.querySelector('[data-qt-menu-list]');
  const close=()=>{list.hidden=true;button.setAttribute('aria-expanded','false');};
  button.addEventListener('click',event=>{event.stopPropagation();list.hidden=!list.hidden;button.setAttribute('aria-expanded',String(!list.hidden));});
  document.addEventListener('click',event=>{if(!menu.contains(event.target))close();});
  document.addEventListener('keydown',event=>{if(event.key==='Escape')close();});
  menu.querySelectorAll('[data-qt-open]').forEach(item=>item.addEventListener('click',()=>{
   close();
   const dialog=document.getElementById(item.dataset.qtOpen);
   if(dialog&&!item.disabled&&dialog.showModal)dialog.showModal();
  }));
 }
 document.querySelectorAll('.qt-dialog').forEach(dialog=>{
  dialog.querySelectorAll('[data-qt-close]').forEach(item=>item.addEventListener('click',()=>dialog.close()));
  dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
 });
 const sched=document.getElementById('qt-schedule-dialog');
 if(sched){
  const form=sched.querySelector('[data-qt-schedule-form]'),day=form.elements.survey_date,clock=form.elements.survey_time,error=form.querySelector('[data-qt-schedule-error]');
  const offset=new Date(sched.dataset.now).getTime()-Date.now();
  const pad=n=>String(n).padStart(2,'0');
  const earliest=()=>{const t=new Date(Date.now()+offset+5*60000);if(t.getSeconds()||t.getMilliseconds())t.setMinutes(t.getMinutes()+1);t.setSeconds(0,0);return t;};
  const dateOf=t=>t.getFullYear()+'-'+pad(t.getMonth()+1)+'-'+pad(t.getDate());
  const sync=()=>{
   const min=earliest();
   day.min=dateOf(new Date(Date.now()+offset));
   clock.min=day.value===dateOf(min)?pad(min.getHours())+':'+pad(min.getMinutes()):'';
   if(clock.min&&clock.value&&clock.value<clock.min)clock.value='';
  };
  const show=text=>{error.textContent=text;error.hidden=!text;};
  day.addEventListener('change',()=>{sync();show('');});
  clock.addEventListener('change',()=>show(''));
  new MutationObserver(sync).observe(sched,{attributes:true,attributeFilter:['open']});
  form.addEventListener('submit',event=>{
   sync();
   const min=earliest();
   if(!day.value||!clock.value){event.preventDefault();show('Select a survey date and time.');return;}
   const chosen=new Date(day.value+'T'+clock.value);
   if(isNaN(chosen)||chosen<min){event.preventDefault();show('Choose today or a future date; the time must be at least 5 minutes from now.');}
  });
 }
})();
