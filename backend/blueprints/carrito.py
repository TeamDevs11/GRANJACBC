from flask import Blueprint, jsonify, request
from utils.db import conectar_db
import pymysql.cursors
from flask_jwt_extended import jwt_required, get_jwt_identity
