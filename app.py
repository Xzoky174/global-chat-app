from functools import wraps
from os import getenv
from dotenv import load_dotenv

from flask import Flask, redirect, render_template, request, make_response

from flask_socketio import SocketIO, emit

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ColumnDefault, exc

from flask_jwt_extended import JWTManager, create_access_token, decode_token
from datetime import timedelta, datetime
from uuid import uuid4
from bcrypt import hashpw, gensalt, checkpw

from threading import Timer

load_dotenv(".env.local")

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///chat-app.db"
app.config["SECRET_KEY"] = getenv("SOCKETIO_SECRET_KEY")
app.config["JWT_SECRET_KEY"] = getenv("JWT_SECRET_KEY")

db = SQLAlchemy(app)
jwt = JWTManager(app)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    message = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(20), nullable=False)
    author_uid = db.Column(db.String(32), nullable=False)

    def __repr__(self) -> str:
        return f"<Message {self.id}>"


class User(db.Model):
    uid = db.Column(db.String(32), primary_key=True, nullable=False)
    username = db.Column(db.String(16), nullable=False, unique=True)
    password = db.Column(db.String(60), nullable=False)
    timed_out = db.Column(db.Boolean(), ColumnDefault(False))

    def __repr__(self) -> str:
        return f"<User {self.uid}>"


usersSentMessages = {}

socketio = SocketIO(app)


def token_required(request):
    def decorator(func):
        @wraps(func)
        def wrapper():
            token = request.cookies.get("access_token")

            if not token:
                return redirect("/signup")

            decoded_token = decode_token(token)["sub"]

            if not decoded_token:
                return redirect("/signup")

            user = User.query.filter_by(uid=decoded_token).first()

            if not user:
                return render_template("account-deleted.html")

            return func(user, decoded_token)

        return wrapper

    return decorator


def logged_in_no_access(request):
    def decorator(func):
        @wraps(func)
        def wrapper():
            token = request.cookies.get("access_token")

            if token:
                decoded_token = decode_token(token)["sub"]

                if decoded_token:
                    user = User.query.filter_by(uid=decoded_token).first()

                    if user:
                        return redirect("/")

            return func()

        return wrapper

    return decorator


def toBytes(str) -> bytes:
    return bytes(str, "utf-8")


@app.route("/")
@token_required(request)
def home(user, uid):
    messages = Message.query.all()

    return render_template(
        "index.html",
        messages=messages,
        username=user.username,
        uid=uid,
        timed_out=user.timed_out,
    )


@app.route("/signup", methods=["GET", "POST"])
@logged_in_no_access(request)
def signup():
    if request.method == "POST":
        username = request.form["username"]
        originalPassword = request.form["password"]
        confirmedPassword = request.form["confirm-password"]

        usernameLen = len(username)
        passwordLen = len(originalPassword)

        if usernameLen > 16:
            return render_template(
                "signup.html",
                error="Username Cannot be More than 16 Characters.",
                place="username",
                username=username,
            )
        elif usernameLen < 6:
            return render_template(
                "signup.html",
                error="Username Cannot be Less than 6 Characters.",
                place="username",
                username=username,
            )
        elif passwordLen > 16:
            return render_template(
                "signup.html",
                error="Password Cannot be More than 16 Characters.",
                place="password",
                username=username,
            )
        elif passwordLen < 8:
            return render_template(
                "signup.html",
                error="Password Cannot be Less than 8 Characters.",
                place="password",
                username=username,
            )
        elif confirmedPassword != originalPassword:
            return render_template(
                "signup.html",
                error="Passwords Do Not Match",
                place="confirm_password",
                username=username,
            )

        password = hashpw(
            toBytes(originalPassword),
            gensalt(),
        )

        uid = uuid4().hex

        user = User(username=username, password=password, uid=uid)

        try:
            db.session.add(user)
            db.session.commit()

            expires = timedelta(days=30)

            access_token = create_access_token(identity=uid, expires_delta=expires)

            response = make_response(redirect("/"))

            response.set_cookie("access_token", access_token, 2_592_000)

            return response
        except exc.IntegrityError:
            return render_template(
                "signup.html",
                error="Username Already Exists",
                place="username",
                username=username,
            )
        except Exception as e:
            print(e)
            return "500 | Something Went Wrong."
    else:
        return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
@logged_in_no_access(request)
def login():
    if request.method == "POST":
        username = request.form["username"]
        formPassword = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if not user:
            return render_template(
                "login.html",
                error="Account Not Found",
                place="username",
                username=username,
            )

        password = user.password

        isCorrect = checkpw(toBytes(formPassword), password)

        if not isCorrect:
            return render_template(
                "login.html",
                error="Incorrect Password",
                place="password",
                username=username,
            )

        expires = timedelta(days=30)
        access_token = create_access_token(identity=user.uid, expires_delta=expires)

        response = make_response(redirect("/"))
        response.set_cookie("access_token", access_token, 2_592_000)
        return response
    else:
        return render_template("login.html")


@app.route("/logout", methods=["GET", "POST"])
@token_required(request)
def logout(*_):
    if request.method == "POST":
        response = make_response(redirect("/logged-out"))

        response.set_cookie("access_token", "", 0)

        return response

    return render_template("logout.html")


@app.route("/logged-out")
@logged_in_no_access(request)
def logged_out():
    return render_template("logged-out.html")


@socketio.on("connect")
def connected():
    print(f"\n*[{datetime.now()}] New User Connected*\n")


@socketio.on("message")
def event(params):
    author = params["author"]

    def resetMessages():
        usersSentMessages[author] = 0
        print("reset!")

    def disable_timed_out():
        user = User.query.filter_by(username=author).first()
        user.timed_out = False

        db.session.commit()
        emit("time_out_finished")

    if author in usersSentMessages:
        if usersSentMessages[author] == 3:
            emit("spam")

            user = User.query.filter_by(username=author).first()
            user.timed_out = True

            db.session.commit()

            Timer(10.0, resetMessages).start()
            Timer(10.0, disable_timed_out).start()

            return

        usersSentMessages[author] += 1

    else:
        usersSentMessages[author] = 1

    Timer(2.0, resetMessages).start()

    message = Message(**params)

    db.session.add(message)
    db.session.commit()

    socketio.emit(
        "message",
        {
            "message": params["message"],
            "author": params["author"],
        },
    )


@socketio.on("typing")
def event(username):
    emit("typing", username, broadcast=True, include_self=False)


@socketio.on("stop-typing")
def event():
    emit("stop-typing", broadcast=True)


if __name__ == "__main__":
    socketio.run(app, debug=True)
