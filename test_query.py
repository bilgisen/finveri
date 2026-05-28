import sqlite3
conn = sqlite3.connect('finveri.db')
print("Total rows in daily_prices:", conn.execute("select count(1) from daily_prices").fetchone()[0])
print("USDTRY rows in daily_prices:", conn.execute("select count(1) from daily_prices where ticker='USDTRY'").fetchone()[0])
print("USDTRY min date:", conn.execute("select min(date) from daily_prices where ticker='USDTRY'").fetchone()[0])
print("USDTRY max date:", conn.execute("select max(date) from daily_prices where ticker='USDTRY'").fetchone()[0])
print("USDTRY sample rows:", conn.execute("select date, open, close from daily_prices where ticker='USDTRY' limit 5").fetchall())
