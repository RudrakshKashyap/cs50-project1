import os
from gmail import *
import requests
import datetime
from random import randint

from forms import RegistrationForm, LoginForm, VerifyForm

from flask import Flask, session, render_template, request, redirect, url_for, jsonify, flash
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
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

bcrypt = Bcrypt()

@app.route("/")
def index():
    return redirect('/home')

@app.route("/home")
def home():
    try:
        session["loggedin"] == "False"
    except KeyError:
        return redirect("/login")
    if session["loggedin"] == "True":
        books = []
        mylist = db.execute("SELECT book FROM review  GROUP BY book").fetchall()
        print(mylist)
        for book in mylist:
            value = db.execute("SELECT * FROM books WHERE isbn = :book", {"book": book[0]}).fetchone()
            books.append(value)
            print(books)
        return render_template("index.html", name=session["username"], books=books)
    return redirect("/login")


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    verifyform = VerifyForm()
    if form.validate_on_submit():
        user = db.execute("SELECT username FROM users where username = :username", {'username': form.username.data}).fetchone()
        email = db.execute("SELECT email FROM users where email = :email", {'email': form.email.data}).fetchone()
        if user:
            flash('Username taken!', 'danger')
            return render_template("register.html", form = form)
        if email:
            flash('An account with this email id already exist!', 'danger')
            return render_template("register.html", form = form)
        session['otp'] = randint(99999,999999)
        session['username'] = form.username.data
        session['email'] = form.email.data
        session['password'] = form.password.data
        subject = 'Goodreads'
        mail = GMail(subject + ' <200rudra@gmail.com>', os.getenv("password"))
        msg = Message('verify your email', to=form.email.data,
                      text = f"use {session['otp']} as your verification code")
        mail.send(msg)
        return render_template("verify.html", email=session['email'], verifyform = verifyform)
    return render_template("register.html", form = form)


@app.route('/verify', methods=['POST'])
def verify():
    verifyform = VerifyForm()
    if verifyform.validate_on_submit():
        session['loggedin'] = 'True'
        if session['otp'] == verifyform.otp.data:
            db.execute("INSERT INTO users (username, email, password) VALUES (:username, :email, :password)",
                {"username": session["username"], "email": session['email'],
                    "password": session['password']})
            db.commit()
            flash(f"Account created for {session['username']}!", 'success')
            return redirect(url_for('home'))
        flash("verification code didn't match", 'danger')
    return render_template("verify.html", email=session['email'], verifyform = verifyform)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/login", methods = ["GET","POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        if not db.execute("SELECT * FROM users WHERE username = :username AND password = :password",
                {"username": form.username.data, "password": form.password.data}).fetchone():
            flash('Invalid username or password !', 'danger')
            return render_template('login.html', form = form)
        session["loggedin"] = "True"
        session['username'] = form.username.data
        return redirect("/home")
    return render_template('login.html', form = form)


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
    return render_template('404.html')


if __name__ == '__main__':
    app.run(debug=True)
