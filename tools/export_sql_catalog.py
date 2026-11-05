"""Refresh the catalog from SQL literals and the executable migration."""
import ast
import sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MAP={'reserve':'UC-RES-01','cancel':'UC-RES-08','lookup':'UC-RES-08','queue_create':'UC-RES-03','queue_call':'UC-RES-04','queue_skip':'UC-RES-04','queue_seat':'UC-RES-04','queue_cancel':'UC-RES-03/04','checkin':'UC-RES-05','no_show':'UC-RES-07','open_table':'UC-ORD-01','place_order':'UC-ORD-02','menu_save':'UC-ORD-03','pay':'UC-PAY-01','close_empty':'UC-PAY-01 (เพิ่มสำหรับยอดศูนย์)','settle':'UC-ACC-01','print_status':'หลาย UC: พิมพ์ซ้ำ','slots':'UC-RES-01/02','snapshot':'UC-RES-06/PAY-02/ACC-02','sales':'UC-PAY-02/ACC-01/02','bill':'UC-PAY-01','guest':'UC-ORD-02','assign_table':'UC-RES-04/05','batch_status':'UC-ORD-04','batches':'UC-ORD-02/04','print_job_data':'UC-DOC-01','report_data':'UC-PAY-02/ACC-02'}
entries=[]


class Visitor(ast.NodeVisitor):
    def __init__(self,path):self.path=path;self.context=[]
    def visit_FunctionDef(self,node):
        self.context.append(node.name);self.generic_visit(node);self.context.pop()
    def visit_If(self,node):
        label=None
        if isinstance(node.test,ast.Compare) and isinstance(node.test.left,ast.Name) and node.test.left.id=='a':
            comparator=node.test.comparators[0]
            if isinstance(comparator,ast.Constant):label=str(comparator.value)
            elif isinstance(comparator,(ast.Tuple,ast.Set)):label='/'.join(str(n.value) for n in comparator.elts if isinstance(n,ast.Constant))
        if label:self.context.append(label)
        for sub in node.body:self.visit(sub)
        if label:self.context.pop()
        for sub in node.orelse:self.visit(sub)
    def visit_Constant(self,node):
        if isinstance(node.value,str) and node.value.strip().upper().startswith(('SELECT ','INSERT ','UPDATE ','DELETE ','PRAGMA ','BEGIN ')):
            context=self.context[-1] if self.context else 'module'
            uc=MAP.get(context) or ' / '.join(MAP[v] for v in context.split('/') if v in MAP) or 'โครงสร้าง/ส่วนกลาง'
            entries.append((str(self.path.relative_to(ROOT)),node.lineno,context,uc,node.value.strip()))


for name in ['models/restaurant.py',*[str(p.relative_to(ROOT)) for p in sorted((ROOT/'models/operations').glob('*.py'))],'models/menu_catalog.py']:
    path=ROOT/name;Visitor(path).visit(ast.parse(path.read_text()))
output=['# SQL ที่ใช้ในโปรแกรมจริง','','สร้างจาก string literals ในโค้ดและ migration โดย `python3 tools/export_sql_catalog.py` คำสั่งใช้ `?` placeholders และ bind parameters ก่อนรัน ไม่ใช้ SQL แบบ MySQL เดิมมารันตรง ๆ','','หมายเลข Q เป็นรหัสใน catalog นี้ ไม่ใช่รหัส query เดิมในรายงาน ตาราง UC ใช้ trace จาก action และ method ร่วม กฎเวลา/สิทธิ์บางส่วนอยู่ใน Python ไม่ใช่ SQL เพียงอย่างเดียว','','ผลทดสอบยืนยันตามเส้นทางใน TESTING.md ไม่ได้อ้างว่า syntax catalog เพียงอย่างเดียวเป็นหลักฐานทดสอบทุก branch','']
for i,(name,line,context,uc,sql) in enumerate(entries,1):
    output.extend([f'## Q{i:03} — {uc}',f'`{name}:{line}` · `{context}`','','```sql',sql,'```',''])
output.extend(['## Migration versions 1–3','','โครงสร้างจริง รวม CHECK, UNIQUE, FK และ triggers:',''])
schema='\n'.join(p.read_text() for p in sorted((ROOT/'migrations').glob('*.sql')));buffer='';statements=[]
for char in schema:
    buffer+=char
    if char==';' and sqlite3.complete_statement(buffer):statements.append(buffer.strip());buffer=''
for i,s in enumerate(statements,1):output.extend([f'### DDL-{i:02}','','```sql',s,'```',''])
(ROOT/'docs/SQL_CATALOG.md').write_text('\n'.join(output))
print(f'Catalog: {len(entries)} SQL literals + {len(statements)} schema statements')
