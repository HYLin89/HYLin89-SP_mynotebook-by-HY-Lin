from flask import jsonify,make_response,request,g
import jwt, logging, random, time
from functools import wraps
from resources.tknmanage import is_blocked

logger = logging.getLogger(__name__)

def token_required(secret_key_):
    def auth_func(func):
        @wraps(func)
        def wrap(*args, **kargs):
            #驗證JWT-token
            try:
                token_ = request.headers.get('Authorization')
                
                if not token_ or not token_.startswith("Bearer "):
                    return make_response(jsonify({'msg':'invalid token or unauthorized'}),401)
                
                token_ = token_.split(" ")[1]
                payload = jwt.decode(token_,secret_key_,algorithms=['HS256'],audience='API_via_login')
                if is_blocked(payload.get('jti')):
                    return make_response(jsonify({'msg':'invalid token or unauthorized'}),401)
                else:
                    g.jwt_payload = payload
                
            except jwt.ExpiredSignatureError:
                return make_response(jsonify({'msg':'login expired, please retry'}),401)
            except jwt.InvalidTokenError:
                return make_response(jsonify({'msg':'invalid token or unauthorized'}),401)
            except Exception as e:
                logger.exception(f'伺服器錯誤>> {e}',exc_info=True)
                return make_response(jsonify({'msg':f'error, {str(e)}'}),500)
            
            return func(*args,**kargs)
        return wrap
    return auth_func

def verification(secret_key_):
    def auth_func(func):
        @wraps(func)
        def wrap(*args, **kargs):
            #驗證JWT-token
            try:
                token_ = request.headers.get('Authorization')
                
                if not token_ or not token_.startswith("Bearer "):
                    return make_response(jsonify({'msg':'invalid token or unauthorized'}),401)
                
                token_ = token_.split(" ")[1]
                payload = jwt.decode(token_,secret_key_,algorithms=['HS256'],audience='API_via_email')
                if is_blocked(payload.get('jti')):
                    return make_response(jsonify({'msg':'invalid token or unauthorized'}),401)
                else:
                    g.jwt_v_payload = payload
                
            except jwt.ExpiredSignatureError:
                return make_response(jsonify({'msg':'login expired, please retry'}),401)
            except jwt.InvalidTokenError:
                return make_response(jsonify({'msg':'invalid token or unauthorized'}),401)
            except Exception as e:
                logger.exception(f'伺服器錯誤>> {e}',exc_info=True)
                return make_response(jsonify({'msg':f'error, {str(e)}'}),500)
            
            return func(*args,**kargs)
        return wrap
    return auth_func



        





