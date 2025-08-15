from flask import blueprint, jsonify, request
from utils.db import conectar_db
from flask_jwt_extendend import jwt_required
from utils.auth_decorators import admin_required
import pymysql.cursors