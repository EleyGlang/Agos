from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mysqldb import MySQL
from datetime import datetime
from config import DevelopmentConfig

app = Flask(__name__)

app.config.from_object(DevelopmentConfig)

app.secret_key = "4782b26e84c5d47d5d2ef09842980bcaf5e0b268af8891fdfeb62913dca728a0"

app.config['MYSQL_HOST'] = 'localhost'
app.config['']
