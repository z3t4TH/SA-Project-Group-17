'use strict';
const $ = s => document.querySelector(s);
const E = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = n => (Number(n || 0)/100).toLocaleString('th-TH',{minimumFractionDigits:2,maximumFractionDigits:2});
const dt = s => new Date(s).toLocaleString('th-TH',{timeZone:'Asia/Bangkok',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
const day = s => new Date(s+'T00:00:00+07:00').toLocaleDateString('th-TH',{timeZone:'Asia/Bangkok',day:'numeric',month:'long',year:'numeric'});
const uuid = () => Array.from(crypto.getRandomValues(new Uint8Array(16)),v=>v.toString(16).padStart(2,'0')).join('');
let config, state, view, selectedDate, slots=[], chosenSlot='', cart=[], guest, bill, lastResult;
let toastTimer, bookingStep=1, kitchenFilter='ACTIVE';
let menuCategory='',menuSearch='',guestCategory='',guestSearch='',guestPanel='menu';
const pending = new Map();
const labels={AVAILABLE:'ว่าง',HELD:'จัดสรรแล้ว',OCCUPIED:'กำลังใช้บริการ',CONFIRMED:'รอเช็คอิน',CHECKED_IN:'เช็คอินแล้ว',CANCELLED:'ยกเลิก',NO_SHOW:'ไม่มาตามนัด',WAITING:'รอเรียก',CALLED:'เรียกแล้ว',SEATED:'เข้าที่นั่งแล้ว',SKIPPED:'ข้ามคิว',PENDING:'รอพิมพ์',PRINTED:'ยืนยันพิมพ์แล้ว',FAILED:'พิมพ์ไม่สำเร็จ',CASH:'เงินสด',MOCK_QR:'Mock QR'};
const kinds={QUEUE:'บัตรคิว',SESSION:'QR ประจำโต๊ะ',KITCHEN:'ใบรายการครัว',RECEIPT:'ใบเสร็จ'};
function badge(s){return `<span class="badge ${['HELD','WAITING','CALLED','PENDING','FAILED','CONFIRMED'].includes(s)?'warn':''}">${E(labels[s]||s)}</span>`;}
function toast(message,error=false){if($('#modal').open&&error){let alert=$('#modal-status');if(!alert){alert=document.createElement('p');alert.id='modal-status';alert.setAttribute('role','alert');$('#modal-content').append(alert);}alert.className='notice error';alert.textContent=message;return;}const t=$('#toast');t.textContent=message;t.className=error?'error':'';t.style.display='block';clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.style.display='none',6000);}
async function get(path){const r=await fetch(path);const data=await r.json();if(!r.ok)throw Object.assign(new Error(data.error),{data,status:r.status});return data;}
async function post(action,body){
 const fingerprint=action+JSON.stringify(body);if(!pending.has(fingerprint))pending.set(fingerprint,uuid());
 let r;try{r=await fetch('/api/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-SA-Request':'1','Idempotency-Key':pending.get(fingerprint)},body:JSON.stringify(body)});}catch{throw new Error('การเชื่อมต่อขาดหาย กรุณาลองรายการเดิมอีกครั้ง ระบบใช้รหัสเดิมป้องกันการบันทึกซ้ำ');}
 const data=await r.json();if(!r.ok){pending.delete(fingerprint);throw Object.assign(new Error(data.error),{data,status:r.status});}
 pending.delete(fingerprint);return data;
}
const button=(label,action,attrs='',cls='secondary small')=>`<button type="button" class="${cls}" data-action="${action}" ${attrs}>${label}</button>`;
const field=(label,name,type='text',value='',attrs='')=>`<div class="field"><label for="f-${name}">${label}</label><input id="f-${name}" name="${name}" type="${type}" value="${E(value)}" ${attrs}></div>`;
const empty=(text='ยังไม่มีรายการ')=>`<div class="empty">${text}</div>`;
const metric=(label,value,hint='')=>`<div class="card metric"><div class="label">${label}</div><div class="value">${value}</div><div class="hint">${hint}</div></div>`;
function modal(content){$('#modal-content').innerHTML=content;if(!$('#modal').open)$('#modal').showModal();}
function closeModal(){$('#modal').close();bill=null;}
const modalFoot=()=>`<div class="actions">${button('กลับ','modal-close')}</div>`;
function publicHeader(){return `<header class="public-header"><a class="brand" href="/"><span class="brand-mark"><svg viewBox="0 0 24 24" width="23" height="23" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M5 3v6c0 3 5 3 5 0V3M7.5 3v18M17 3c-4 0-4 9 0 10v8M17 3v10"/></svg></span>${E(config?.restaurant?.short_name||'ส้มตำ เมี่ยงคำ')}<small>ทุ่งสง · นครศรีธรรมราช</small></a><div class="row"><a href="/book">จองโต๊ะ</a><a href="/cancel">ค้นหาการจอง</a><a href="/login">สำหรับร้าน</a></div></header>`;}
function demoNotice(){return config.demo?`<div class="notice">${config.presentation?'โหมด Presentation · วันจำลอง '+E(config.today)+' เวลา 13:30 น. · ': 'โหมดทดสอบ · '}ข้อมูลบุคคลและธุรกรรมสมมุติ · การชำระ QR เป็นการจำลอง</div>`:'';}
function menuPhoto(m){const media=config.menu_images||{},src=media.by_key?.[m.catalog_key]||media.by_name?.[m.name]||media.fallback||'/static/menu-images/placeholder.svg';return `<figure class="menu-photo"><img data-menu-image src="${E(src)}" alt="ภาพประกอบ ${E(m.name)} ไม่ใช่ภาพจากร้าน" loading="lazy" width="800" height="500"><figcaption>ภาพประกอบ</figcaption></figure>`;}

document.addEventListener('error',e=>{const img=e.target;if(img instanceof HTMLImageElement&&img.hasAttribute('data-menu-image')&&!img.dataset.fallback){img.dataset.fallback='1';img.src='/static/menu-images/placeholder.svg';}},true);

async function boot(){
 try{config=await get('/api/config');document.title=config.restaurant.name+' • จองโต๊ะและจัดการร้าน';selectedDate=config.today;
 const path=location.pathname;
 if(path.startsWith('/order/')){await loadGuest();return;}
 if(path==='/login'){renderLogin();return;}
 if(path==='/cancel'){renderCancel();return;}
 if(path==='/app'){if(!config.user){location.href='/login';return;}view=location.hash==='#kitchen'?'kitchen':'tables';await refresh();return;}
 renderBooking();await loadSlots();
 }catch(e){$('#app').innerHTML=publicHeader()+`<main class="public-main"><div class="notice error">${E(e.message)}</div><a href="/">กลับหน้าหลัก</a></main>`;}
}
function renderLogin(){return LoginForm.render();}
function renderBooking(){return BookingForm.render();}
function syncBookingParty(){const value=$('[name=guests]').value;document.querySelectorAll('.party-options button').forEach(b=>{const selected=value!==''&&Number(b.dataset.count)===Number(value);b.classList.toggle('selected',selected);b.classList.toggle('secondary',!selected);b.setAttribute('aria-pressed',String(selected));});}
function bookingNext(){const form=$('form[data-form="reserve"]');if(!form.reportValidity())return;bookingStep=2;$('#booking-details').hidden=true;$('#booking-times').hidden=false;$('#booking-summary').textContent=$('[name=name]').value+' • '+$('[name=guests]').value+' ท่าน';renderSlots();const heading=$('#booking-times h1');heading.tabIndex=-1;heading.focus();}

async function loadSlots(){const count=$('[name=guests]')?.value||1;try{slots=(await get('/api/slots?guests='+encodeURIComponent(count))).slots;renderSlots();}catch(e){toast(e.message,true);}}
function renderSlots(){return BookingForm.renderAlternativeSlots();}
function renderCancel(){return CancellationForm.render();}
async function refresh(){const previousToday=config.today;config=await get('/api/config');if(!config.user){location.href='/login';return;}if(selectedDate===previousToday&&previousToday!==config.today)selectedDate=config.today;state=await get('/api/state?date='+selectedDate);renderShell();}
const navItems=[['dashboard','◷','ภาพรวมยอดขาย',true],['tables','▦','รายการโต๊ะ'],['reservations','▤','รายการจอง'],['queues','≋','คิวหน้าร้าน'],['kitchen','♨','หน้าจอครัว'],['history','▤','ประวัติบิล',true],['menu','♧','จัดการเมนู',true],['settlement','◈','ปิดบัญชีประจำวัน',true],['reports','▥','รายงานและจัดสรร',true],['printing','▧','เอกสารและงานพิมพ์'],['settings','⚙','ตั้งค่าร้าน',true]];
const titles={kitchen:['หน้าจอครัว','ติดตามแต่ละออร์เดอร์จนเสิร์ฟครบ • อัปเดตอัตโนมัติทุก 10 วินาที'],dashboard:['ภาพรวมร้านวันนี้','ติดตามยอดรับชำระและสถานะหน้าร้าน'],history:['ประวัติบิล','ตรวจสอบรายการรับชำระย้อนหลัง'],tables:['รายการโต๊ะ','เลือกโต๊ะเพื่อเปิด QR ดูรายการ หรือรับชำระ'],reservations:['รายการจองล่วงหน้า','ตรวจสอบรายชื่อ เช็คอิน และบันทึกผู้ไม่มาตามนัด'],queues:['คิวหน้าร้าน','ออกบัตร เรียกคิว และจัดโต๊ะให้ลูกค้า'],menu:['จัดการเมนูอาหาร','ปรับราคาและความพร้อมขายให้ตรงกับหน้าร้าน'],settlement:['ปิดบัญชีประจำวัน','ตรวจนับเงินสด บันทึกต้นทุน และค่าแรง'],reports:['รายงานและจัดสรรเงิน','รายรับ ค่าใช้จ่าย และส่วนแบ่งหุ้นส่วน 4 ส่วน'],printing:['เอกสารและงานพิมพ์','เปิดเอกสารเพื่อพิมพ์หรือบันทึก PDF แล้วบันทึกผลการพิมพ์'],settings:['ตั้งค่าร้าน','จัดการโควตา โต๊ะ พนักงาน และบัญชีเข้าใช้งาน']};
function renderShell(){return ApplicationShell.render();}
function renderView(){return ({dashboard:dashboardView,tables:tablesView,reservations:reservationsView,queues:queuesView,menu:menuView,settlement:settlementView,reports:reportsView,printing:printingView,settings:settingsView,history:historyView,kitchen:kitchenView})[view]();}
function dashboardView(){return DashboardView.render();}
function paymentTable(payments){return payments.length?`<div class="table-wrap"><table><thead><tr><th>ใบรับเงิน</th><th>เวลา</th><th>โต๊ะ</th><th>ช่องทาง</th><th>ยอดสุทธิ</th></tr></thead><tbody>${payments.map(p=>`<tr><td>#${p.payment_id}</td><td>${dt(p.payment_time)}</td><td>${E(p.table_number)}</td><td>${badge(p.payment_method)}</td><td>${money(p.total_paid)}</td></tr>`).join('')}</tbody></table></div>`:empty('ยังไม่มีรายการรับชำระในวันที่เลือก');}
function statusSummary(entries){return `<div class="status-summary">${entries.map(([label,value,color])=>`<div class="status-tile ${color}"><span>${label}</span><strong>${value}</strong></div>`).join('')}</div>`;}
function tablesView(){return TableManagementForm.render();}
function receiptLink(id){const job=state.print_jobs.find(j=>j.kind==='RECEIPT'&&JSON.parse(j.payload).payment_id===id);return job?`<a class="receipt-link" href="/print/job?id=${job.job_id}" target="_blank" rel="noopener" aria-label="ดูใบเสร็จ ${id}">ดูใบเสร็จ ↗</a>`:'';}
function historyView(){return ReceiptHistoryView.render();}

function reservationsView(){return AdminReservationView.render();}
function reservationRows(filter='',search=''){return AdminReservationView.renderRows(filter,search);}

function queueForm(){return QueueForm.renderIntake();}
function queuesView(){return QueueForm.render();}
function menuToolbar(menu,scope){const category=scope==='owner'?menuCategory:guestCategory;const search=scope==='owner'?menuSearch:guestSearch;return `<div class="menu-toolbar"><div><label for="${scope}-menu-search">ค้นหาเมนู</label><input id="${scope}-menu-search" type="search" placeholder="เช่น ตำไทย ข้าวผัด เมี่ยงคำ" value="${E(search)}"></div><div><label for="${scope}-menu-category">หมวดอาหาร</label><select id="${scope}-menu-category"><option value="">ทุกหมวด</option>${[...new Set(menu.map(m=>m.category))].map(c=>`<option value="${E(c)}" ${c===category?'selected':''}>${E(c)}</option>`).join('')}</select></div></div>`;}
function filteredMenu(menu,category,search){return menu.filter(m=>(!category||m.category===category)&&(!search||m.name.toLowerCase().includes(search.toLowerCase())));}
function ownerMenuCards(){return MenuAdminForm.renderMenu();}
function menuView(){return MenuAdminForm.render();}

function settlementView(){return SettlementForm.render();}
function reportsView(){return SettlementReportView.render();}
const batchLabels={RECEIVED:'รับออร์เดอร์แล้ว',PREPARING:'กำลังทำ',READY:'พร้อมเสิร์ฟ',SERVED:'เสิร์ฟแล้ว'};
const batchNext={RECEIVED:['PREPARING','เริ่มทำอาหาร'],PREPARING:['READY','อาหารพร้อมเสิร์ฟ'],READY:['SERVED','ยืนยันเสิร์ฟแล้ว']};
function batchProgress(status){const stages=Object.keys(batchLabels),current=stages.indexOf(status);return `<ol class="batch-progress" aria-label="สถานะออร์เดอร์">${stages.map((s,i)=>`<li class="${i<=current?'complete':''} ${i===current?'current':''}">${i<current?'✓':i+1} ${batchLabels[s]}</li>`).join('')}</ol>`;}
function kitchenView(){return KitchenView.render();}
function guestBatches(){return MobileOrderForm.renderOrderStatus();}
function printingView(){return PrintJobsView.render();}
function settingsView(){return SettingsForm.render();}
async function showBill(id){return PaymentForm.renderBill(id);}
function showSession(token,orderId){const link=config.base_url+'/order/'+token;const job=state?.print_jobs.find(j=>j.kind==='SESSION'&&JSON.parse(j.payload).order_id===orderId);modal(`<h2>QR สั่งอาหาร • บิล #${orderId}</h2><p class="muted">ลูกค้าเปิดลิงก์หรือสแกน QR เพื่อสั่งอาหาร</p><div class="qrbox"><img alt="QR สั่งอาหาร" src="/qr.svg?text=${encodeURIComponent(link)}"></div><p class="hint">QR จะหมดอายุเมื่อปิดโต๊ะ</p><div class="actions"><a href="${E(link)}" target="_blank" rel="noopener">เปิดหน้าสั่งอาหาร ↗</a>${job?`<a href="/print/job?id=${job.job_id}" target="_blank" rel="noopener">เปิดเอกสาร QR / PDF ↗</a>`:''}${button('กลับ','modal-close')}</div>`);}
function tableOptions(guests){return state.tables.filter(t=>t.status==='AVAILABLE'&&t.capacity>=guests).map(t=>`<option value="${t.table_id}">${E(t.table_number)} · ${t.capacity} ที่นั่ง</option>`).join('');}
function assignModal(kind,id,guests,name){return CheckInForm.render(kind,id,guests,name);}
async function loadGuest(silent=false){
 const token=location.pathname.split('/').pop();
 try{guest=await get('/api/guest?token='+encodeURIComponent(token));renderGuest();}
 catch(e){if(silent){toast(e.message,true);return;}throw e;}
}
function guestMenuCards(){return MobileOrderForm.renderMenu();}
function renderGuest(){return MobileOrderForm.render();}
function cartHTML(){return MobileOrderForm.renderCart();}
async function actionClick(el){
 const a=el.dataset.action,id=Number(el.dataset.id);
 if(a==='booking-party'){$('[name=guests]').value=el.dataset.count;syncBookingParty();await loadSlots();return;}
 if(a==='booking-next'){bookingNext();return;}
 if(a==='booking-back'){bookingStep=1;$('#booking-details').hidden=false;$('#booking-times').hidden=true;$('[name=guests]').focus();return;}
 if(a==='modal-close'){closeModal();return;}
 if(a==='slot'){chosenSlot=el.dataset.value;renderSlots();return;}
 if(a==='nav'){view=el.dataset.view;history.replaceState(null,'',view==='kitchen'?'#kitchen':location.pathname);if(view==='settlement')selectedDate=config.today;await refresh();return;}
 if(a==='batch-filter'){kitchenFilter=el.dataset.filter;$('#view').innerHTML=kitchenView();return;}
 if(a==='batch-status'){try{await run('batch_status',{id,status:el.dataset.status,expected_status:el.dataset.expected});}catch(e){if(e.status===409)await refresh();throw e;}return;}
 if(a==='queue-new'){modal(queueForm());return;}
 if(a==='refresh'){await refresh();return;}
 if(a==='logout'){await post('logout',{});location.href='/login';return;}
 if(a==='open-table'){
  const t=state.tables.find(t=>t.table_id===id);
  modal(`<h2>เปิดโต๊ะ ${E(t.table_number)}</h2><p>${t.capacity} ที่นั่ง • ยืนยันว่าลูกค้านั่งที่โต๊ะแล้ว</p><div class="actions">${button('ยืนยันเปิดโต๊ะ + QR','confirm-open',`data-id="${id}"`,'')}${button('กลับ','modal-close')}</div>`);return;
 }
 if(a==='confirm-open'){const r=await post('open_table',{table_id:id});closeModal();await refresh();showSession(r.token,r.id);return;}
 if(a==='bill'){await showBill(id);return;}
 if(a==='session-qr'){const o=bill.order;showSession(o.session_token,o.order_id);return;}
 if(a==='close-empty'){await run('close_empty',{id});return;}
 if(a==='checkin'){const r=state.reservations.find(r=>r.reservation_id===id);assignModal('checkin',id,r.guest_count,r.customer_name);return;}
 if(a==='queue-seat'){const q=state.queues.find(q=>q.queue_id===id);assignModal('queue_seat',id,q.guest_count,q.customer_name);return;}
 if(a==='no-show'){const r=state.reservations.find(r=>r.reservation_id===id);modal(`<h2>บันทึกไม่มาตามนัด</h2><p>${E(r.customer_name)} • ${dt(r.reservation_datetime)}</p><p class="muted">ยืนยันหลังตรวจสอบแล้วว่าไม่มาและพ้นเวลาผ่อนผัน 15 นาที</p><div class="actions">${button('ยืนยันตัดสิทธิ์','confirm-no-show',`data-id="${id}"`,'danger')}${button('กลับ','modal-close')}</div>`);return;}
 if(a==='confirm-no-show'){await run('no_show',{id});return;}
 if(['queue-call','queue-skip','queue-cancel'].includes(a)){await run(a.replace('-','_'),{id});return;}
 if(a==='menu-edit'){const m=state.menu.find(m=>m.menu_id===id)||{};modal(`<h2>${id?'แก้ไขเมนู':'เพิ่มเมนูใหม่'}</h2><form data-form="menu"><input type="hidden" name="id" value="${m.menu_id||''}">${field('ชื่ออาหาร','name','text',m.name||'','required maxlength="150"')}${field('หมวดหมู่','category','text',m.category||'จานเดียว','required maxlength="50"')}${field('ราคา (บาท)','price','number',m.review_note?'':m.price!==undefined?(m.price/100).toFixed(2):'','required min="0" step="0.01"')}${m.review_note?`<div class="notice">${E(m.review_note)}</div><label class="check"><input type="checkbox" name="review_confirmed">ยืนยันว่าได้ราคาจริงจากเจ้าของร้านแล้ว</label>`:''}<label class="check"><input type="checkbox" name="available" ${m.is_available!==0?'checked':''}>พร้อมขาย</label><div class="actions"><button type="submit">บันทึกเมนู</button>${button('กลับ','modal-close')}</div></form>`);return;}
 if(a==='menu-toggle'){const m=state.menu.find(m=>m.menu_id===id);await run('menu_save',{id,name:m.name,category:m.category,price:(m.price/100).toFixed(2),available:!m.is_available});return;}
 if(a==='print-status'){await run('print_status',{id,status:el.dataset.status});return;}
 if(a==='table-edit'){const t=state.tables.find(t=>t.table_id===id)||{};modal(`<h2>${id?'แก้ไขโต๊ะ':'เพิ่มโต๊ะ'}</h2><form data-form="table"><input type="hidden" name="id" value="${t.table_id||''}">${field('หมายเลขโต๊ะ','number','text',t.table_number||'','required maxlength="10"')}${field('ที่นั่งสูงสุด','capacity','number',t.capacity||4,'required min="1" max="20"')}<button type="submit">บันทึกโต๊ะ</button></form>${modalFoot()}`);return;}
 if(a==='staff-edit'){const s=state.staff.find(s=>s.staff_id===id)||{};modal(`<h2>${id?'แก้ไขพนักงาน':'เพิ่มพนักงาน'}</h2><form data-form="staff"><input type="hidden" name="id" value="${s.staff_id||''}">${field('ชื่อ','name','text',s.name||'','required maxlength="100"')}${field('ตำแหน่ง','role','text',s.role||'บริการ','required maxlength="50"')}${field('ค่าแรงรายวัน (บาท)','rate','number',s.daily_rate!==undefined?(s.daily_rate/100).toFixed(2):400,'required min="0" step="0.01"')}<label class="check"><input type="checkbox" name="active" ${s.is_active!==0?'checked':''}>ทำงานอยู่</label><div class="actions"><button type="submit">บันทึกพนักงาน</button>${button('กลับ','modal-close')}</div></form>`);return;}
 if(a==='confirm-settle'){await run('settle',lastResult);view='reports';await refresh();return;}
 if(a==='guest-panel'){guestPanel=el.dataset.panel;renderGuest();return;}
 if(a==='guest-refresh'){await loadGuest();return;}
 if(a==='cart-add'){
  const m=guest.menu.find(m=>m.menu_id===id),qty=Number($('#qty-'+id).value);if(!Number.isInteger(qty)||qty<1||qty>99)throw new Error('จำนวนต้องอยู่ระหว่าง 1 ถึง 99');
  if(cart.length>=50)throw new Error('ตะกร้ารองรับสูงสุด 50 รายการ');cart.push({menu_id:id,name:m.name,expected_price:m.price,quantity:qty,note:$('#note-'+id).value});$('#cart-content').innerHTML=cartHTML();toast('เพิ่ม '+m.name+' ลงตะกร้าแล้ว');return;
 }
 if(a==='cart-remove'){cart.splice(Number(el.dataset.index),1);$('#cart-content').innerHTML=cartHTML();return;}
 if(a==='cart-submit'){
  if(!cart.length)return;
  const r=await post('place_order',{token:location.pathname.split('/').pop(),items:cart.map(({name,...i})=>i)});cart=[];guestPanel='status';toast(r.message);await loadGuest();return;
 }
 if(a==='confirm-cancel'){const r=await post('cancel',lastResult);toast(r.message);closeModal();$('#booking-result').innerHTML=`<div class="notice success" style="margin-top:20px">${E(r.message)}</div>`;return;}
}
async function run(action,body){const r=await post(action,body);closeModal();toast(r.message||'บันทึกแล้ว');await refresh();return r;}
document.addEventListener('click',async e=>{const el=e.target.closest('[data-action]');if(!el)return;el.disabled=true;try{await actionClick(el);}catch(error){toast(error.message,true);}finally{if(el.isConnected)el.disabled=false;}});
document.addEventListener('submit',async e=>{
 const form=e.target.closest('form[data-form]');if(!form)return;e.preventDefault();const submit=form.querySelector('[type=submit]');if(submit.disabled)return;submit.disabled=true;
 const f=new FormData(form),b=Object.fromEntries(f.entries());
 try{
 switch(form.dataset.form){
  case 'login':await post('login',b);location.href='/app';break;
  case 'reserve':{
   if(bookingStep===1){bookingNext();break;}
   if(!chosenSlot)throw new Error('กรุณาเลือกรอบเวลาที่ว่าง');
   const r=await post('reserve',{...b,slot:chosenSlot});modal(`<div class="booking-confirm">✓</div><h2>จองโต๊ะสำเร็จ</h2><div class="notice success"><h1>${E(r.code)}</h1><p>${E(b.name)} • ${b.guests} ท่าน<br>${dt(r.slot)}</p></div><p>เก็บรหัสนี้พร้อมเบอร์โทรไว้เช็คอินหรือยกเลิกการจอง</p><a href="/cancel">ค้นหาการจอง</a>${modalFoot()}`);form.reset();chosenSlot='';bookingStep=1;renderBooking();await loadSlots();break;
  }
  case 'lookup':{
   const r=(await post('lookup',b)).reservation;lastResult=b;
   $('#booking-result').innerHTML=`<hr class="divider"><h3>${E(r.customer_name)}</h3><p>${dt(r.reservation_datetime)} • ${r.guest_count} ท่าน</p>${badge(r.status)}${r.status==='CONFIRMED'?`<div class="actions">${button('ยืนยันยกเลิกการจอง','confirm-cancel-dialog','','danger')}</div>`:''}`;break;
  }
  case 'queue':{const r=await run('queue_create',b);modal(`<h2>${E(r.message)}</h2><a href="/print/job?id=${r.job_id}" target="_blank" rel="noopener">เปิดบัตรคิว / พิมพ์ PDF ↗</a>${modalFoot()}`);break;}
  case 'assign':await run(b.kind,{id:b.id,table_id:b.table_id});view='tables';await refresh();break;
  case 'menu':await run('menu_save',{...b,available:f.has('available'),review_confirmed:f.has('review_confirmed')});break;
  case 'table':await run('table_save',b);break;
  case 'staff':await run('staff_save',{...b,active:f.has('active')});break;
  case 'settings':await run('settings',b);break;
  case 'user':await run('user_save',b);break;
  case 'pay':{
   const r=await post('pay',{id:Number(b.id),method:b.method,received:b.received,confirmed:f.has('confirmed'),expected_total:bill.order.total_amount});closeModal();await refresh();modal(`<h2>รับชำระสำเร็จ</h2><div class="notice success">${E(r.message)}<br>เงินทอน ${money(r.change)} บาท</div><a href="/print/job?id=${r.job_id}" target="_blank" rel="noopener">เปิดใบเสร็จ / บันทึก PDF ↗</a>${modalFoot()}`);break;
  }
  case 'settle':{
   lastResult={...b,staff_ids:f.getAll('staff_ids')};const labor=state.staff.filter(s=>lastResult.staff_ids.includes(String(s.staff_id))).reduce((sum,s)=>sum+s.daily_rate,0);
   modal(`<h2>ตรวจสอบก่อนปิดบัญชี</h2><p>ยอดขาย ${money(state.sales.total)} บาท<br>ต้นทุน ${E(b.material)} บาท<br>ค่าแรง ${money(labor)} บาท<br>เงินสดนับจริง ${E(b.actual_cash)} บาท</p><div class="notice">ยืนยันแล้วจะปิดรับรายการหน้าร้านของวันนี้และแก้ย้อนหลังไม่ได้</div><div class="actions">${button('ยืนยันปิดบัญชี','confirm-settle','','')}${button('กลับไปแก้ไข','modal-close')}</div>`);break;
  }
 }
 }catch(error){toast(error.message,true);if(error.data?.alternatives){slots=error.data.alternatives;await loadSlots();}}finally{if(submit.isConnected)submit.disabled=false;}
});
document.addEventListener('click',e=>{if(e.target.closest('[data-action="confirm-cancel-dialog"]'))modal(`<h2>ยกเลิกการจองนี้?</h2><p>รหัส ${E(lastResult.code)} จะคืนโควตาให้รอบนี้</p><div class="actions">${button('ยืนยันยกเลิก','confirm-cancel','','danger')}${button('กลับ','modal-close')}</div>`);});
document.addEventListener('change',async e=>{
 try{
 if(e.target.id==='report-date'){selectedDate=e.target.value;await refresh();}
 if(e.target.name==='guests'&&location.pathname!='/app'){syncBookingParty();await loadSlots();}
 if(e.target.id==='pay-method'){const cash=e.target.value==='CASH';$('#cash-fields').hidden=!cash;$('#mock-fields').hidden=cash;$('[name=received]').required=cash;}
 if(e.target.id==='reservation-filter')filterReservations();
 if(e.target.id==='owner-menu-category'){menuCategory=e.target.value;$('#owner-menu-grid').innerHTML=ownerMenuCards();}
 if(e.target.id==='guest-menu-category'){guestCategory=e.target.value;$('#guest-menu-grid').innerHTML=guestMenuCards();}
 }catch(error){toast(error.message,true);}
});
function filterReservations(){return AdminReservationView.filterRows();}
document.addEventListener('input',e=>{
 if(e.target.name==='guests'&&location.pathname==='/book')syncBookingParty();
 if(e.target.name==='reservation-search')filterReservations();
 if(e.target.id==='owner-menu-search'){menuSearch=e.target.value;$('#owner-menu-grid').innerHTML=ownerMenuCards();}
 if(e.target.id==='guest-menu-search'){guestSearch=e.target.value;$('#guest-menu-grid').innerHTML=guestMenuCards();}
 if(e.target.name==='received'&&bill){const change=Math.round(Number(e.target.value)*100)-bill.order.total_amount;$('#change-preview').textContent=change<0?'เงินยังไม่ครบ ขาด '+money(-change)+' บาท':'เงินทอน '+money(change)+' บาท';}
});
setInterval(async()=>{
 if(document.hidden||$('#modal').open||document.activeElement?.matches('input,textarea,select'))return;
 try{
 if(location.pathname.startsWith('/order/')){const g=await get('/api/guest?token='+encodeURIComponent(location.pathname.split('/').pop()));if(JSON.stringify(g)!==JSON.stringify(guest)){guest=g;renderGuest();}}
 else if(location.pathname==='/app'&&['tables','dashboard','printing','kitchen'].includes(view))await refresh();
 }catch(e){if(e.status===401){location.href='/login';}else if(e.status===404&&location.pathname.startsWith('/order/')){$('#app').innerHTML=publicHeader()+`<main class="public-main"><div class="notice">${E(e.message)}</div></main>`;}}
},10000);
boot();
