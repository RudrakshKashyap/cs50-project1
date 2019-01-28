import os
import smtplib
import requests
import datetime

from flask import Flask, session, render_template, request, redirect, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from flask_bcrypt import Bcrypt

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

bcrypt = Bcrypt()

"""ERROR"""


@app.before_first_request
def init_app():
    session["loggedin"] = "False"


@app.route("/")
def index():
    return redirect("/login")


@app.route("/home")
def home():
    try:
        session["loggedin"] == "False"
    except KeyError:
        return redirect("/login")
    if session["loggedin"] == "False":
        return redirect("/login")
    books = []
    mylist = db.execute("SELECT book FROM review  GROUP BY book").fetchall()
    print(mylist)
    for book in mylist:
        value = db.execute("SELECT * FROM books WHERE isbn = :book", {"book": book[0]}).fetchone()
        books.append(value)
        print(books)
    return render_template("index.html", name=session["username"], books=books)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    session["username"] = request.form.get("username")
    if not session["username"]:
        return render_template("register.html", error="Please provide username")
    session["email"] = request.form.get("email")
    if not session["email"]:
        return render_template("register.html", error="Please provide email")
    session["password"] = request.form.get("password")
    if not session["password"]:
        return render_template("register.html", error="Please provide password")
    confirm_password = request.form.get("confirm_password")
    if session["password"] != confirm_password:
        return render_template("register.html", error="Password not match")
    user = db.execute("SELECT username FROM users").fetchall()
    if session["username"] == user:
        return render_template("register.html", error="Username taken")
    session["loggedin"] = "Register"
    return redirect("/verify")


@app.route("/verify")
def verify():
    try:
        session["loggedin"] == "Register"
    except KeyError:
        return redirect("/login")
    if session["loggedin"] == "Register":
        return redirect("/register")

    session["hashed_email"] = bcrypt.generate_password_hash(session["email"]).decode('utf-8')
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login("200rudra@gmail.com", "os.getenv("app_password")
    server.sendmail("200rudra@gmail.com", session["email"], session["hashed_email"])
    print(session["email"])

    return render_template("verify.html",email = session["email"])


@app.route("/confirm", methods = ["POST"])
def confirm():
    session["otp"] = request.form.get("otp")
    if session["hashed_email"] == session["otp"]:
        db.execute("INSERT INTO users (username, email, password) VALUES (:username, :email, :password)",
            {"username": session["username"], "email": session["email"], "password": session["password"]})
        db.commit()
        session["loggedin"] = "True"
    else:
        return render_template("verify.html",error = "verification code not match")
    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/login", methods = ["GET","POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    session["username"] = request.form.get("username")
    session["password"] = request.form.get("password")
    """ERROR"""
    if not db.execute("SELECT * FROM users WHERE username = :username AND password = :password",
            {"username": session["username"], "password": session["password"]}).fetchone() or not session["username"] or not session["password"]:
        return render_template("login.html",error = "Invalid username or password")
    session["loggedin"] = "True"
    return redirect("/home")


@app.route("/search",methods = ["POST"])
def search():
    search = request.form.get("search")
    print(search)
    myfilter = request.form.get("filter")
    fstr = "%" + search + "%"
    if myfilter == "All":
        if not search:
            books = db.execute("SELECT * FROM books LIMIT 50",)
            return render_template("search.html", name = session["username"], books = books)
        books = db.execute("SELECT * FROM books WHERE isbn LIKE :search OR title LIKE :search OR author LIKE :search",
            {"search": fstr}).fetchall()
        return render_template("search.html", name = session["username"], books = books)
    books = db.execute("SELECT * FROM books WHERE :column LIKE :search",
            {"search": fstr,"column":myfilter}).fetchall()
    return render_template("search.html", name = session["username"], books = books)

@app.route("/book/<string:isbn>")
def book(isbn):
    try:
        session["loggedin"] == "False"
    except KeyError:
        return redirect("/login")
    if session["loggedin"] == "False":
        return redirect("/login")
    session['isbn'] = isbn
    session['comment'] = None
    print(isbn)
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "hnQ1hqyeAo79YSFFiekcg", "isbns": isbn})
    if res.status_code != 200:
      return "ERROR: API request unsuccessful."
    data = res.json()
    ratings = data["books"][0]["average_rating"]
    ratings_count = data["books"][0]["ratings_count"]
    title = db.execute("SELECT title FROM books WHERE isbn = :ibsn",{"ibsn": isbn}).fetchone()
    reviews = db.execute("SELECT * FROM review WHERE book = :ibsn",{"ibsn": isbn}).fetchall()
    reviews.reverse()
    for row in reviews:
        if row[3] == session["username"]:
            session['comment'] = "True"
    date = datetime.datetime.now().strftime("%y-%m-%d")
    return render_template("book.html",name = session["username"], ratings = ratings, ratings_count = ratings_count,reviews = reviews,title = title[0],date = date,isbn = isbn,comment = session['comment'])

@app.route("/insert", methods = ["POST"])
def insert():
    review = request.form.get("review")
    rating = request.form.get("rating")
    print(review)
    print(rating)
    print(session['isbn'])
    if not review or not rating:
        return redirect(f"/book/{session['isbn']}")
    db.execute("INSERT INTO review (review , book, person, ratings) VALUES (:review, :isbn, :person, :rating)",
        {"review":review,"isbn":session['isbn'],"person":session["username"],"rating":rating})
    db.commit()
    return redirect(f"/book/{session['isbn']}")



@app.route("/api/<string:isbn>")
def book_api(isbn):
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "hnQ1hqyeAo79YSFFiekcg", "isbns": isbn})
    mylist = db.execute("SELECT title,author,year FROM books WHERE isbn = :ibsn",{"ibsn": isbn}).fetchone()
    if res.status_code != 200 or not mylist:
      return "ERROR: API request unsuccessful."
    data = res.json()
    return jsonify({
        "title": mylist[0],
    "author": mylist[1],
    "year": mylist[2],
    "isbn": isbn,
    "review_count": data["books"][0]["ratings_count"],
    "average_score": data["books"][0]["average_rating"]
    })


@app.errorhandler(404)
def page_not_found(e):
    return "seems like you lost in space"
