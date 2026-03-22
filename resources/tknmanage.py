from flask_restful import Resource
import psycopg2 as pg2
from psycopg2 import extras
from flask import jsonify, make_response, request, g
import os, time, logging
import traceback

from server import db, limiter
from model import TokenModel

logger = logging.getLogger(__name__)


def need_blocked(jti,exp):
    token = TokenModel(
        token = jti,
        expired_at = exp
    )
    db.session.add(token)
    return 

def is_blocked(jti):
    is_token = TokenModel.query.filter_by(token = jti).first()
    if is_token :
        return True
    else:
        return False
    

#刪除過期token處理
class Clean(Resource):
    @limiter.limit("2 per 2 days")
    def delete(self):
        response, status_code = {},200

        secret = os.environ.get('CRON_AUTH_SECRETS')
        source = request.headers.get('x-secrets')
        if not source or source != secret:
            status_code = 401
            response['msg']='forbidden action'
            return make_response(jsonify(response),status_code)

        current_time = time.time()
        
        try:
            TokenModel.query.filter(TokenModel.expired_at < current_time).delete()
            db.session.commit()
            response['msg'] = 'success'
        except Exception as e:
            db.session.rollback()
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器清理錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)


