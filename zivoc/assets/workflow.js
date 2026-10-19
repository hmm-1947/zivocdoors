'use strict';
let wfNextIndex=Date.now();
document.querySelector('[data-wf-add-measurement]')?.addEventListener('click',()=>{
 const template=document.getElementById('wf-measurement-template');const container=document.getElementById('wf-measurements');
 if(container.querySelectorAll('.wf-measurement').length>=200)return;
 container.insertAdjacentHTML('beforeend',template.innerHTML.replaceAll('__INDEX__',String(wfNextIndex++)));
});
document.addEventListener('click',event=>{
 const remove=event.target.closest('[data-wf-remove-measurement]');if(remove)remove.closest('.wf-measurement').remove();
 const add=event.target.closest('[data-wf-add-annotation]');if(add){const form=add.closest('form');if(form.querySelectorAll('.wf-annotations').length>=8)return;const row=form.querySelector('.wf-annotations').cloneNode(true);row.querySelector('[name="labels[]"]').value='';add.before(row);}
 if(event.target.closest('[data-wf-print]'))window.print();
 const png=event.target.closest('[data-wf-png]');if(png){const svg=png.closest('.wf-door').querySelector('.wf-drawing svg');if(!svg)return;
  const source=new XMLSerializer().serializeToString(svg);const url=URL.createObjectURL(new Blob([source],{type:'image/svg+xml'}));const image=new Image();
  image.onload=()=>{const canvas=document.createElement('canvas');canvas.width=2000;canvas.height=1840;const ctx=canvas.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,2000,1840);ctx.drawImage(image,0,0,2000,1840);URL.revokeObjectURL(url);const a=document.createElement('a');a.download=png.dataset.filename;a.href=canvas.toDataURL('image/png');a.click();};image.onerror=()=>URL.revokeObjectURL(url);image.src=url;
 }
});
const quoteForm=document.querySelector('.wf-quote-form');
if(quoteForm){const format=n=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',minimumFractionDigits:2}).format(n);
 function calculate(){let subtotal=0,totalQty=0;quoteForm.querySelectorAll('[name$="[quantity]"]').forEach(input=>{const price=quoteForm.elements[input.name.replace('[quantity]','[unit_price]')];totalQty+=(Number(input.value)||0);subtotal+=(Number(input.value)||0)*(Number(price.value)||0);});
  const number=name=>Math.max(0,Number(quoteForm.elements[name].value)||0);const enteredDiscount=number('discount'),discount=quoteForm.elements.discount_type?.value==='percent'?Math.round(subtotal*enteredDiscount)/100:enteredDiscount,charges=number('installation')+number('transport')+number('additional');const taxable=subtotal-discount+charges;const tax=Math.round(taxable*number('tax_rate'))/100;const total=taxable+tax;
  quoteForm.querySelectorAll('[data-qt-line-total]').forEach(cell=>{const row=cell.closest('tr');cell.textContent=format((Number(row.querySelector('[name$="[quantity]"]').value)||0)*(Number(row.querySelector('[name$="[unit_price]"]').value)||0));});
  quoteForm.querySelector('[data-wf-quote-totals]').textContent=discount>subtotal?'Discount cannot exceed subtotal.':`Total quantity ${totalQty} · Subtotal ${format(subtotal)} · Discount ${format(discount)} · Charges ${format(charges)} · GST ${format(tax)} · Grand total ${format(total)}`;
 }quoteForm.addEventListener('input',calculate);calculate();
}
