from flask import Flask, render_template
from app import app
from user.models import User


@app.route('/user/signup')
def signup():
    return User().signup()