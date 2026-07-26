from app.db.database import SessionLocal, engine
from sqlalchemy import text
print('DB',engine.url)
db=SessionLocal()
try:
 for table in ['users','mobile_one_shot_jobs','content_documents']:
  try:
   rows=db.execute(text(f'SELECT * FROM {table} ORDER BY 1 DESC LIMIT 20')).mappings().all()
   print('\nTABLE',table,'COUNT_SHOWN',len(rows))
   for r in rows: print(dict(r))
  except Exception as e: print('TABLE',table,'ERR',repr(e))
finally: db.close()
