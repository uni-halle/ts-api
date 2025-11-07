#!/bin/bash
# View database with readable status names

sudo docker compose exec ts-api python3 -c "
import sqlite3
from datetime import datetime

conn = sqlite3.connect('/home/python/ts-api/data/tsapi.db')

query = '''
SELECT 
    SUBSTR(uid, 1, 36) as job_id,
    CASE status
        WHEN 0 THEN 'Queued'
        WHEN 1 THEN 'Prepared'
        WHEN 2 THEN 'Processing'
        WHEN 3 THEN 'Completed'
        WHEN 4 THEN 'Failed'
        WHEN 5 THEN 'Canceled'
        ELSE 'Unknown'
    END as status,
    priority,
    whisper_language,
    datetime(created_at, 'unixepoch', 'localtime') as created,
    datetime(started_at, 'unixepoch', 'localtime') as started,
    datetime(completed_at, 'unixepoch', 'localtime') as completed
FROM jobs 
ORDER BY created_at DESC 
LIMIT 20
'''

cursor = conn.execute(query)
print()
print(f\"{'Job ID':<38} {'Status':<12} {'Pri':<4} {'Lang':<5} {'Created':<19}\")
print('=' * 90)
for row in cursor:
    job_id, status, priority, lang, created, started, completed = row
    lang = lang or 'N/A'
    print(f'{job_id:<38} {status:<12} {priority:<4} {lang:<5} {created or \"N/A\":<19}')

# Summary
print()
print('=' * 90)
summary_query = '''
SELECT 
    CASE status
        WHEN 0 THEN 'Queued'
        WHEN 1 THEN 'Prepared'
        WHEN 2 THEN 'Processing'
        WHEN 3 THEN 'Completed'
        WHEN 4 THEN 'Failed'
        WHEN 5 THEN 'Canceled'
    END as status_name,
    COUNT(*) as count
FROM jobs 
GROUP BY status
ORDER BY status
'''

cursor = conn.execute(summary_query)
print('Summary:')
for row in cursor:
    print(f'  {row[0]:<12}: {row[1]}')

# Queue info
queue_count = conn.execute('SELECT COUNT(*) FROM queue').fetchone()[0]
print(f'  Queue length: {queue_count}')
print()
"

