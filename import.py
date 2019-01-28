import os
import csv

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session,sessionmaker

engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

f = open("books.csv")
reader = csv.reader(f)
for ibsn, title, author, year in reader:
	db.execute("INSERT INTO books (ibsn, title, author, year) VALUES (:ibsn, :title, :author, :year)",
		{"ibsn": ibsn, "title": title, "author": author, "year": year})
	print(f"Added {title}")
	db.commit()
	
