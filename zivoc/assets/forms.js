'use strict';
const DISTRICTS={
 'Kerala':['Alappuzha','Ernakulam','Idukki','Kannur','Kasaragod','Kollam','Kottayam','Kozhikode','Malappuram','Palakkad','Pathanamthitta','Thiruvananthapuram','Thrissur','Wayanad'],
 'Karnataka':['Bagalkot','Ballari','Belagavi','Bengaluru Rural','Bengaluru Urban','Bidar','Chamarajanagar','Chikkaballapur','Chikkamagaluru','Chitradurga','Dakshina Kannada','Davanagere','Dharwad','Gadag','Hassan','Haveri','Kalaburagi','Kodagu','Kolar','Koppal','Mandya','Mysuru','Raichur','Ramanagara','Shivamogga','Tumakuru','Udupi','Uttara Kannada','Vijayapura','Yadgir','Vijayanagara'],
 'Tamil Nadu':['Ariyalur','Chengalpattu','Chennai','Coimbatore','Cuddalore','Dharmapuri','Dindigul','Erode','Kallakurichi','Kancheepuram','Kanyakumari','Karur','Krishnagiri','Madurai','Mayiladuthurai','Nagapattinam','Namakkal','Nilgiris','Perambalur','Pudukkottai','Ramanathapuram','Ranipet','Salem','Sivaganga','Tenkasi','Thanjavur','Theni','Thoothukudi','Tiruchirappalli','Tirunelveli','Tirupathur','Tiruppur','Tiruvallur','Tiruvannamalai','Tiruvarur','Vellore','Viluppuram','Virudhunagar']
};
Object.assign(DISTRICTS,{
 'Andra Pradesh':['Alluri Sitharama Raju','Anakapalli','Ananthapuramu','Annamayya','Bapatla','Chittoor','Dr. B.R. Ambedkar Konaseema','East Godavari','Eluru','Guntur','Kakinada','Krishna','Kurnool','Nandyal','NTR','Palnadu','Parvathipuram Manyam','Prakasam','Sri Potti Sriramulu Nellore','Sri Sathya Sai','Srikakulam','Tirupati','Visakhapatnam','Vizianagaram','West Godavari','YSR Kadapa'],
 'Arunachal Pradesh':['Anjaw','Changlang','East Kameng','East Siang','Kamle','Kra Daadi','Kurung Kumey','Lepa Rada','Lohit','Longding','Lower Dibang Valley','Lower Siang','Lower Subansiri','Namsai','Pakke Kessang','Papum Pare','Shi Yomi','Siang','Tawang','Tirap','Upper Dibang Valley','Upper Siang','Upper Subansiri','West Kameng','West Siang'],
 'Assam':['Baksa','Barpeta','Biswanath','Bongaigaon','Cachar','Charaideo','Chirang','Darrang','Dhemaji','Dhubri','Dibrugarh','Dima Hasao','Goalpara','Golaghat','Hailakandi','Hojai','Jorhat','Kamrup','Kamrup Metropolitan','Karbi Anglong','Karimganj','Kokrajhar','Lakhimpur','Majuli','Morigaon','Nagaon','Nalbari','Sivasagar','Sonitpur','South Salmara-Mankachar','Tinsukia','Udalguri','West Karbi Anglong'],
 'Bihar':['Araria','Arwal','Aurangabad','Banka','Begusarai','Bhagalpur','Bhojpur','Buxar','Darbhanga','East Champaran','Gaya','Gopalganj','Jamui','Jehanabad','Kaimur','Katihar','Khagaria','Kishanganj','Lakhisarai','Madhepura','Madhubani','Munger','Muzaffarpur','Nalanda','Nawada','Patna','Purnia','Rohtas','Saharsa','Samastipur','Saran','Sheikhpura','Sheohar','Sitamarhi','Siwan','Supaul','Vaishali','West Champaran'],
 'Chhattisgarh':['Balod','Baloda Bazar','Balrampur','Bastar','Bemetara','Bijapur','Bilaspur','Dantewada','Dhamtari','Durg','Gariaband','Gaurela-Pendra-Marwahi','Janjgir-Champa','Jashpur','Kabirdham','Kanker','Kondagaon','Korba','Koriya','Mahasamund','Mungeli','Narayanpur','Raigarh','Raipur','Rajnandgaon','Sukma','Surajpur','Surguja'],
 'Goa':['North Goa','South Goa'],
 'Gujarat':['Ahmedabad','Amreli','Anand','Aravalli','Banaskantha','Bharuch','Bhavnagar','Botad','Chhota Udaipur','Dahod','Dang','Devbhoomi Dwarka','Gandhinagar','Gir Somnath','Jamnagar','Junagadh','Kheda','Kutch','Mahisagar','Mehsana','Morbi','Narmada','Navsari','Panchmahal','Patan','Porbandar','Rajkot','Sabarkantha','Surat','Surendranagar','Tapi','Vadodara','Valsad'],
 'Haryana':['Ambala','Bhiwani','Charkhi Dadri','Faridabad','Fatehabad','Gurugram','Hisar','Jhajjar','Jind','Kaithal','Karnal','Kurukshetra','Mahendragarh','Nuh','Palwal','Panchkula','Panipat','Rewari','Rohtak','Sirsa','Sonipat','Yamunanagar'],
 'Himachal Pradesh':['Bilaspur','Chamba','Hamirpur','Kangra','Kinnaur','Kullu','Lahaul and Spiti','Mandi','Shimla','Sirmaur','Solan','Una'],
 'Jammu and Kashmir':['Anantnag','Bandipora','Baramulla','Budgam','Doda','Ganderbal','Jammu','Kathua','Kishtwar','Kulgam','Kupwara','Poonch','Pulwama','Rajouri','Ramban','Reasi','Samba','Shopian','Srinagar','Udhampur','Leh','Kargil'],
 'Jharkhand':['Bokaro','Chatra','Deoghar','Dhanbad','Dumka','East Singhbhum','Garhwa','Giridih','Godda','Gumla','Hazaribagh','Jamtara','Khunti','Koderma','Latehar','Lohardaga','Pakur','Palamu','Ramgarh','Ranchi','Sahibganj','Seraikela Kharsawan','Simdega','West Singhbhum'],
 'Madya Pradesh':['Agar Malwa','Alirajpur','Anuppur','Ashoknagar','Balaghat','Barwani','Betul','Bhind','Bhopal','Burhanpur','Chhatarpur','Chhindwara','Damoh','Datia','Dewas','Dhar','Dindori','Guna','Gwalior','Harda','Hoshangabad','Indore','Jabalpur','Jhabua','Katni','Khandwa','Khargone','Mandla','Mandsaur','Morena','Narsinghpur','Neemuch','Niwari','Panna','Raisen','Rajgarh','Ratlam','Rewa','Sagar','Satna','Sehore','Seoni','Shahdol','Shajapur','Sheopur','Shivpuri','Sidhi','Singrauli','Tikamgarh','Ujjain','Umaria','Vidisha'],
 'Maharashtra':['Ahmednagar','Akola','Amravati','Aurangabad','Beed','Bhandara','Buldhana','Chandrapur','Dhule','Gadchiroli','Gondia','Hingoli','Jalgaon','Jalna','Kolhapur','Latur','Mumbai City','Mumbai Suburban','Nagpur','Nanded','Nandurbar','Nashik','Osmanabad','Palghar','Parbhani','Pune','Raigad','Ratnagiri','Sangli','Satara','Sindhudurg','Solapur','Thane','Wardha','Washim','Yavatmal'],
 'Manipur':['Bishnupur','Chandel','Churachandpur','Imphal East','Imphal West','Jiribam','Kakching','Kamjong','Kangpokpi','Noney','Pherzawl','Senapati','Tamenglong','Tengnoupal','Thoubal','Ukhrul'],
 'Meghalaya':['East Garo Hills','East Jaintia Hills','East Khasi Hills','North Garo Hills','Ri Bhoi','South Garo Hills','South West Garo Hills','South West Khasi Hills','West Garo Hills','West Jaintia Hills','West Khasi Hills'],
 'Mizoram':['Aizawl','Champhai','Hnahthial','Khawzawl','Kolasib','Lawngtlai','Lunglei','Mamit','Saiha','Saitual','Serchhip'],
 'Nagaland':['Chumoukedima','Dimapur','Kiphire','Kohima','Longleng','Mokokchung','Mon','Noklak','Peren','Phek','Tuensang','Wokha','Zunheboto'],
 'Orissa':['Angul','Balangir','Balasore','Bargarh','Bhadrak','Boudh','Cuttack','Deogarh','Dhenkanal','Gajapati','Ganjam','Jagatsinghpur','Jajpur','Jharsuguda','Kalahandi','Kandhamal','Kendrapara','Kendujhar','Khordha','Koraput','Malkangiri','Mayurbhanj','Nabarangpur','Nayagarh','Nuapada','Puri','Rayagada','Sambalpur','Subarnapur','Sundargarh'],
 'Punjab':['Amritsar','Barnala','Bathinda','Faridkot','Fatehgarh Sahib','Fazilka','Ferozepur','Gurdaspur','Hoshiarpur','Jalandhar','Kapurthala','Ludhiana','Malerkotla','Mansa','Moga','Pathankot','Patiala','Rupnagar','Sahibzada Ajit Singh Nagar','Sangrur','Shaheed Bhagat Singh Nagar','Sri Muktsar Sahib','Tarn Taran'],
 'Rajasthan':['Ajmer','Alwar','Banswara','Baran','Barmer','Bharatpur','Bhilwara','Bikaner','Bundi','Chittorgarh','Churu','Dausa','Dholpur','Dungarpur','Hanumangarh','Jaipur','Jaisalmer','Jalore','Jhalawar','Jhunjhunu','Jodhpur','Karauli','Kota','Nagaur','Pali','Pratapgarh','Rajsamand','Sawai Madhopur','Sikar','Sirohi','Sri Ganganagar','Tonk','Udaipur'],
 'Sikkim':['East Sikkim','North Sikkim','Pakyong','Soreng','South Sikkim','West Sikkim'],
 'Telangana':['Adilabad','Bhadradri Kothagudem','Hanamkonda','Hyderabad','Jagtial','Jangaon','Jayashankar Bhupalpally','Jogulamba Gadwal','Kamareddy','Karimnagar','Khammam','Kumuram Bheem','Mahabubabad','Mahabubnagar','Mancherial','Medak','Medchal-Malkajgiri','Mulugu','Nagarkurnool','Nalgonda','Narayanpet','Nirmal','Nizamabad','Peddapalli','Rajanna Sircilla','Rangareddy','Sangareddy','Siddipet','Suryapet','Vikarabad','Wanaparthy','Warangal','Yadadri Bhuvanagiri'],
 'Tripura':['Dhalai','Gomati','Khowai','North Tripura','Sepahijala','South Tripura','Unakoti','West Tripura'],
 'Uttaranchal':['Almora','Bageshwar','Chamoli','Champawat','Dehradun','Haridwar','Nainital','Pauri Garhwal','Pithoragarh','Rudraprayag','Tehri Garhwal','Udham Singh Nagar','Uttarkashi'],
 'Uttar Pradesh':['Agra','Aligarh','Ambedkar Nagar','Amethi','Amroha','Auraiya','Ayodhya','Azamgarh','Baghpat','Bahraich','Ballia','Balrampur','Banda','Barabanki','Bareilly','Basti','Bhadohi','Bijnor','Budaun','Bulandshahr','Chandauli','Chitrakoot','Deoria','Etah','Etawah','Farrukhabad','Fatehpur','Firozabad','Gautam Buddha Nagar','Ghaziabad','Ghazipur','Gonda','Gorakhpur','Hamirpur','Hapur','Hardoi','Hathras','Jalaun','Jaunpur','Jhansi','Kannauj','Kanpur Dehat','Kanpur Nagar','Kasganj','Kaushambi','Kushinagar','Lakhimpur Kheri','Lalitpur','Lucknow','Maharajganj','Mahoba','Mainpuri','Mathura','Mau','Meerut','Mirzapur','Moradabad','Muzaffarnagar','Pilibhit','Pratapgarh','Prayagraj','Raebareli','Rampur','Saharanpur','Sambhal','Sant Kabir Nagar','Shahjahanpur','Shamli','Shravasti','Siddharthnagar','Sitapur','Sonbhadra','Sultanpur','Unnao','Varanasi'],
 'West Bengal':['Alipurduar','Bankura','Birbhum','Cooch Behar','Dakshin Dinajpur','Darjeeling','Hooghly','Howrah','Jalpaiguri','Jhargram','Kalimpong','Kolkata','Malda','Murshidabad','Nadia','North 24 Parganas','Paschim Bardhaman','Paschim Medinipur','Purba Bardhaman','Purba Medinipur','Purulia','South 24 Parganas','Uttar Dinajpur'],
 'Andaman and Nicobar Islands':['Nicobar','North and Middle Andaman','South Andaman'],
 'Chandigarh':['Chandigarh'],
 'Dadar and Nagar Haveli':['Dadra and Nagar Haveli'],
 'Daman and Diu':['Daman','Diu'],
 'Delhi':['Central Delhi','East Delhi','New Delhi','North Delhi','North East Delhi','North West Delhi','Shahdara','South Delhi','South East Delhi','South West Delhi','West Delhi'],
 'Lakshadeep':['Lakshadweep'],
 'Pondicherry':['Karaikal','Mahe','Puducherry','Yanam']
});
const STATE_ALIAS=
{'Andhra Pradesh':'Andra Pradesh','Madhya Pradesh':'Madya Pradesh','Odisha':'Orissa','Uttarakhand':'Uttaranchal','Puducherry':'Pondicherry','Lakshadweep':'Lakshadeep','Dadra and Nagar Haveli':'Dadar and Nagar Haveli','Dadra & Nagar Haveli and Daman & Diu':'Daman and Diu','Andaman & Nicobar Islands':'Andaman and Nicobar Islands','Jammu & Kashmir':'Jammu and Kashmir','NCT of Delhi':'Delhi'};

const partyForm=document.querySelector('[data-party]');
if(partyForm){
 let people=[];
 try{people=JSON.parse(document.getElementById('party-data').textContent)||[];}catch(error){people=[];}
 const self=Number(partyForm.dataset.self)||0;
 const $=id=>document.getElementById(id);
 const existingWrap=$('party-existing-wrap'),franchiseWrap=$('party-franchise-wrap'),mobileWrap=$('party-mobile-wrap');
 const existing=$('party-existing'),franchise=$('party-franchise'),phone=$('party-phone'),alertBox=$('party-alert');
 const nameField=$('party-name'),address1=$('party-address1'),address2=$('party-address2'),postal=$('party-postal'),office=$('party-post-office');
 const state=$('party-state'),district=$('party-district'),districtText=$('party-district-text'),leadId=$('party-lead-id');
 const salesman=partyForm.elements.salesman_id;
 const kind=()=>(partyForm.querySelector('input[name="customer_type"]:checked')||{}).value||'new';

 function setDistrictMode(){
  const list=DISTRICTS[state.value];
  if(list){
   const current=district.dataset.initial||district.value||districtText.value;
   district.replaceChildren(new Option('-- select one --',''));
   list.forEach(name=>district.append(new Option(name,name)));
   if(current&&!list.includes(current))district.append(new Option(current,current));
   district.value=current||'';
   district.hidden=false;district.disabled=false;district.name='district';
   districtText.hidden=true;districtText.disabled=true;districtText.removeAttribute('name');
  }else{
   const current=district.dataset.initial||districtText.value||'';
   district.hidden=true;district.disabled=true;district.removeAttribute('name');
   districtText.hidden=false;districtText.disabled=false;districtText.name='district';
   if(!districtText.value)districtText.value=current;
  }
  district.dataset.initial='';
 }
 function setDistrict(value){
  district.dataset.initial=value||'';districtText.value=value||'';setDistrictMode();
 }
 state.addEventListener('change',()=>{district.dataset.initial='';districtText.value='';setDistrictMode();});

 function lock(on){
  [nameField,phone,address1,address2,postal,office].forEach(input=>{input.readOnly=on;});
  state.style.pointerEvents=on?'none':'';district.style.pointerEvents=on?'none':'';districtText.readOnly=on;
 }
 function fill(person){
  nameField.value=person?person.name:'';phone.value=person?person.phone:'';
  address1.value=person?person.address:'';address2.value=person?person.address2:'';
  postal.value=person?person.postal_code:'';office.value=person?person.post_office:'';
  state.value=person?person.state:'';setDistrict(person?person.district:'');
  if(leadId)leadId.value=person?person.id:'';
  if(salesman){salesman.disabled=!!person;if(person)salesman.value=String(person.salesman_id);}
  lock(!!person);checkPhone();
 }
 function pick(select){
  const person=people.find(item=>String(item.id)===select.value);
  fill(person||null);
 }
 function toggle(reset){
  const type=kind();
  existingWrap.hidden=type!=='existing';franchiseWrap.hidden=type!=='franchise';
  mobileWrap.classList.toggle('zf-c6',type==='new');mobileWrap.classList.toggle('zf-c3',type!=='new');
  if(reset){existing.value='';franchise.value='';fill(null);}
  existing.required=type==='existing'&&!!leadId;franchise.required=type==='franchise'&&!!leadId;
 }
 partyForm.querySelectorAll('input[name="customer_type"]').forEach(radio=>radio.addEventListener('change',()=>toggle(true)));
 existing.addEventListener('change',()=>pick(existing));
 franchise.addEventListener('change',()=>pick(franchise));

 function checkPhone(){
  const digits=phone.value.replace(/\D/g,'').slice(-10);
  const match=digits.length>=7?people.find(item=>item.id!==self&&item.phone.replace(/\D/g,'').slice(-10)===digits):null;
  const selected=leadId&&leadId.value&&match&&String(match.id)===leadId.value;
  if(match&&!selected&&kind()==='new'){alertBox.querySelector('b').textContent=match.name;alertBox.hidden=false;}else alertBox.hidden=true;
 }
 phone.addEventListener('input',checkPhone);

 let lookupId=0;
 postal.addEventListener('input',()=>{
  const code=postal.value.replace(/\D/g,'');
  if(code.length!==6||postal.readOnly)return;
  const ticket=++lookupId;
  fetch('https://api.postalpincode.in/pincode/'+code).then(response=>response.json()).then(data=>{
   if(ticket!==lookupId||!data||!data[0]||data[0].Status!=='Success')return;
   const places=data[0].PostOffice||[];if(!places.length)return;
   const first=places[0];
   if(!office.value)office.value=first.Name||'';
   const stateName=STATE_ALIAS[first.State]||first.State;
   if([...state.options].some(option=>option.value===stateName)){state.value=stateName;}
   setDistrict(first.District||'');
  }).catch(()=>{});
 });

 setDistrictMode();toggle(false);
 if(existing.required&&leadId&&leadId.value){existing.value=leadId.value;if(!existing.value)franchise.value=leadId.value;}
 partyForm.addEventListener('submit',event=>{
  if(kind()==='existing'&&leadId&&!leadId.value){event.preventDefault();existing.focus();}
  else if(salesman&&salesman.disabled){salesman.disabled=false;}
 });
}

document.querySelectorAll('[data-autosubmit]').forEach(form=>{
 form.querySelectorAll('select').forEach(select=>select.addEventListener('change',()=>form.submit()));
 const search=form.querySelector('input[type="search"]');
 if(search)search.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();form.submit();}});
});

document.querySelectorAll('[data-table-csv]').forEach(button=>button.addEventListener('click',()=>{
 const table=document.getElementById(button.dataset.tableCsv);if(!table)return;
 const quote=text=>'"'+text.replace(/\s+/g,' ').trim().replace(/"/g,'""')+'"';
 const lines=[Array.from(table.tHead.rows[0].cells).map(cell=>quote(cell.textContent)).join(',')];
 table.querySelectorAll('tr.ol-main').forEach(row=>lines.push(Array.from(row.cells).map(cell=>quote(cell.textContent)).join(',')));
 const url=URL.createObjectURL(new Blob(['\ufeff'+lines.join('\r\n')],{type:'text/csv;charset=utf-8'}));
 const link=document.createElement('a');link.href=url;link.download=button.dataset.filename||'export.csv';document.body.append(link);link.click();link.remove();URL.revokeObjectURL(url);
}));
