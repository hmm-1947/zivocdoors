'use strict';
const qtForm=document.querySelector('.qt-create');
if(qtForm){
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
  for(const [cls,attr,text,title,hidden]of[['zf-icon-btn zf-del','qtRemove','✕','Delete',false],['zf-icon-btn','qtEdit','✎','Edit',false],['zf-icon-btn zf-save','qtSave','Save','Save',true]]){
   const button=document.createElement('button');button.type='button';button.className=cls;button.dataset[attr]='';button.textContent=text;button.title=title;button.hidden=hidden;actions.append(button);
  }
  const codeCell=tr.insertCell();codeCell.append(document.createTextNode(codeValue));
  const hiddenCode=document.createElement('input');hiddenCode.type='hidden';hiddenCode.name=`qt_items[${key}][code]`;hiddenCode.value=codeValue;codeCell.append(hiddenCode);
  tr.insertCell().textContent=name;
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
  if(edit){const row=edit.closest('tr');row.querySelectorAll('input[type="number"]').forEach(input=>{input.readOnly=false;});edit.hidden=true;row.querySelector('[data-qt-save]').hidden=false;row.querySelector('[name$="[quantity]"]').focus();}
  if(save){
   const row=save.closest('tr'),inputs=row.querySelectorAll('input[type="number"]');
   if(![...inputs].every(input=>input.checkValidity())){message.textContent='Enter a valid quantity and price.';return;}
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
document.querySelectorAll('[data-qt-template]').forEach(select=>select.addEventListener('change',()=>{if(select.value)select.form.elements.terms.value=select.selectedOptions[0].dataset.terms||'';}));
