from flask import jsonify, request
from flask_restplus import Resource, Namespace, cors
from namex.utils.util import cors_preflight
import json
from namex import jwt
from flask import current_app
from namex.models import db

from namex.utils.logging import setup_logging
setup_logging() ## important to do this first

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import func, text
from sqlalchemy.inspection import inspect


from namex.models import WordClassification as wordClassificationDAO,  User

import datetime
from datetime import datetime as dt


# Register a local namespace for the event history
api = Namespace('Auto_Analyze', description='auto-analyze names for immediate approval')
@cors_preflight("GET")
@api.route('/<string:name>', methods=['GET','OPTIONS'])
class Auto_Analyze(Resource):
    @staticmethod
    @cors.crossdomain(origin='*')
    @jwt.requires_auth
    def get():

        name_results = []
        return jsonify({'name_results': name_results})