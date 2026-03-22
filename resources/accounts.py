from flask_restful import Resource, reqparse
import psycopg2 as pg2
from psycopg2 import extras
from flask import jsonify, make_response, request, g
import traceback
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.datastructures import FileStorage
import re, os, jwt, uuid, time, logging

from server import db, limiter
from model import AccountsModel
from resources.tknmanage import need_blocked
from util.auth import token_required, verification
from util.storage import bucket_upload, bucket_remove
from util.mail import mail_verifi, mail_psw

logger = logging.getLogger(__name__)
secret_key = os.environ.get('JWT_SECRET_KEY')

#註冊功能
class Register(Resource):
    @limiter.limit("5 per minute")
    @limiter.limit("10 per day")
    def post(self):
        data = request.get_json()
        response,status_code={},201
        
        if (not data or not data.get('account') or not data.get('email') or not data.get('passwords')):
            status_code = 400
            response['msg'] = 'requirements cannot be blanked'
            return make_response(jsonify(response),status_code)
        
        if not (re.search(r'^[a-zA-Z0-9_-]+@[a-zA-Z0-9]+\.[a-z]+$',data.get('email'))):
            status_code = 400
            response['msg'] = 'please enter a valid email, the subaddresses are not allowed'
            return make_response(jsonify(response),status_code)
        if (AccountsModel.query.filter_by(email = data.get('email')).first()) or (AccountsModel.query.filter_by(account = data.get('account')).first()):
            status_code = 400
            response['msg'] = 'this email or account is already registered'
            return make_response(jsonify(response),status_code)
        
        if re.search(r'\W',data.get('account'),re.ASCII) or re.search(r' ',data.get('account')):
            status_code = 400
            response['msg'] = 'only english characters and digits are allowed'
            return make_response(jsonify(response),status_code)
        
        if (len(data.get('account'))>25) or (len(data.get('account'))<4):
            status_code = 400
            response['msg'] = 'account must have 4 to 25 characters'
            return make_response(jsonify(response),status_code)
        
        if (len(data.get('passwords'))<8) or (re.search(r'[^a-zA-Z0-9+_*@#$%^&!?-]',data.get('passwords'),re.ASCII)):
            status_code = 400
            response['msg'] = 'password cannot be shorter then 8-characters or use illegal characters'
            return make_response(jsonify(response),status_code)
        
        passwords_check = [r'[a-z]',r'[A-Z]',r'[0-9]',r'[+_*@#$%^&!?-]']
        for i in passwords_check:
            if not (re.search(i,data.get('passwords'),re.ASCII)):
                status_code = 400
                response['msg'] = 'the password must include captial and lower case letter, numbers and special symbols(+-_*@#$%^&!?) '
                return make_response(jsonify(response),status_code)
        try:
            psw_hashed = generate_password_hash(data.get('passwords'))
            user = AccountsModel(
                user_name=data.get('user_name',data.get('account')),
                account=data.get('account'),
                passwords=psw_hashed,
                email=data.get('email'),
                deactivate=False,
                avatar=None,
                bio=None,
                links=[],
                is_verified=False
            )
            db.session.add(user)
            db.session.commit()
            response['msg']='success'

            verifi_token = jwt.encode({'account':data.get('account'),'exp':time.time()+600,'aud':'API_via_email','jti':str(uuid.uuid4())},secret_key,algorithm='HS256')
            mail_verifi(recipient=data.get('email'),token=verifi_token)

        except Exception as e:
            db.session.rollback()
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)
    
#登入功能
class Login(Resource):
    @limiter.limit("5 per minute")
    @limiter.limit("30 per day")
    def post(self):
        response,status_code={},200
        data = request.get_json()
        if not data:
            status_code = 400
            response['msg'] = 'lacked of account or psw'
            return make_response(jsonify(response),status_code)
        
        account_login = data.get('account_login')
        psw_login = data.get('psw_login')
        if not account_login or not psw_login:
            status_code = 400
            response['msg'] = 'lacked of account or psw'
            return make_response(jsonify(response),status_code)
        try:
            user = AccountsModel.query.filter((AccountsModel.account == account_login)|(AccountsModel.email == account_login)).first()

            if user :
                if check_password_hash(user.passwords,psw_login):
                    valid_token = jwt.encode({'account':user.account,'exp':time.time()+86400,'aud':'API_via_login','jti':str(uuid.uuid4())},secret_key,algorithm='HS256')
                    response = {"msg":'success',
                                "valid_token":valid_token,
                                "user_data":{
                                    "account":user.account,
                                    "avatar":user.avatar,
                                    "user_name":user.user_name,
                                    "email":user.email,
                                    "is_verified":user.is_verified}
                                }
                else:
                    status_code=401
                    response['msg'] = 'incorrect email-addr, account or psw'
            else:
                status_code=401
                response['msg'] = 'no such account or email'
        except Exception as e:
            db.session.rollback()
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)
    
#使用者品牌頁
class User(Resource):
    @limiter.limit("60 per minute")
    def get(self,account=None):
        response,status_code={},200
        if not account:
            status_code = 400
            response['msg'] = 'account is required'
            return make_response(jsonify(response),status_code)
        
        try:
            user = AccountsModel.query.filter_by(account = account,deactivate = False).first()
            if not user:
                status_code = 404
                response['msg'] = 'No such user'
                return make_response(jsonify(response),status_code)
            response = {
                'msg':'success',
                'user':{
                    'user_name':user.user_name,
                    'avatar':user.avatar,
                    'bio':user.bio,
                    'links':user.links
                }
            }
        except Exception as e:
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)
    
    @token_required(secret_key_=secret_key)
    @limiter.limit("10 per minute")
    def patch(self,account=None):
        response,status_code={},200
        if account:
            status_code = 405
            response['msg'] = 'invalid action'
            return make_response(jsonify(response),status_code)

        current_user = g.jwt_payload['account']
        data = request.get_json()
        if not data:
            status_code = 400
            response['msg'] = 'no updated data provided'
            return make_response(jsonify(response),status_code)

        updated_allow = ['user_name','bio','links','passwords']
        updated_data = {key : value for key, value in data.items() if key in updated_allow}
        if not updated_data:
            status_code = 400
            response['msg'] = 'invalid actions'
            return make_response(jsonify(response),status_code)
        
        user = AccountsModel.query.filter_by(account = current_user, deactivate = False).first()
        if not user:
            status_code = 404
            response['msg'] = 'No such user'
            return make_response(jsonify(response),status_code)
        
        if 'links' in updated_data:
            if (len('links') > 8):
                status_code = 400
                response['msg'] = 'cannot allow more than 8-links'
                return make_response(jsonify(response),status_code)

        if 'passwords' in updated_data:
            if (len(updated_data['passwords'])<8) or (re.search(r'[^a-zA-Z0-9+_*@#$%^&!?-]',updated_data['passwords'],re.ASCII)):
                status_code = 400
                response['msg'] = 'password cannot be shorter then 8-characters or use illegal characters'
                return make_response(jsonify(response),status_code)
            passwords_check = [r'[a-z]',r'[A-Z]',r'[0-9]',r'[+_*@#$%^&!?-]']
            for i in passwords_check:
                if not (re.search(i,updated_data['passwords'],re.ASCII)):
                    status_code = 400
                    response['msg'] = 'the password must include captial and lower case letter, numbers and special symbols(+-_*@#$%^&!?) '
                    return make_response(jsonify(response),status_code)
            if check_password_hash(user.passwords,updated_data['passwords']):
                status_code = 400
                response['msg'] = 'new password cannot be the same as previous one'
                return make_response(jsonify(response),status_code)
            updated_data['passwords']  = generate_password_hash(updated_data['passwords'])

        try:
            for key, value in updated_data.items():
                setattr(user, key, value)
            # db.session.query(AccountsModel).filter_by(account = current_user).update(updated_data)
            db.session.commit()
            response['msg'] = 'success'
        except Exception as e:
            db.session.rollback()
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)
        
    @token_required(secret_key_=secret_key)
    @limiter.limit("2 per day")
    def delete(self,account=None):
        response,status_code={},200
        if account:
            status_code = 405
            response['msg'] = 'invalid action'
            return make_response(jsonify(response),status_code)

        current_user = g.jwt_payload['account']
        data = request.get_json()
        if not data or not data.get('passwords'):
            status_code = 401
            response['msg'] = 'request rejected'
            return make_response(jsonify(response),status_code)
        
        user = AccountsModel.query.filter_by(account = current_user, deactivate = False).first()
        if not user:
            status_code = 404
            response['msg'] = 'No such user'
            return make_response(jsonify(response),status_code)
        
        if check_password_hash(user.passwords,data.get('passwords')):
            try:
                user.deactivate=True
                db.session.commit()
                response['msg'] = 'success'

            except Exception as e:
                db.session.rollback()
                status_code=500
                traceback.print_exc()
                response['msg']='error'
                logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        else:
            status_code = 401
            response['msg'] = 'request rejected'
        return make_response(jsonify(response),status_code)

#使用者頭像
class Avatar(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('avatar', type = FileStorage, required = True, location = 'files', help = 'you must upload an image')

    @token_required(secret_key_=secret_key)
    @limiter.limit("5 per minute")
    def patch(self):
        response,status_code={},200
        current_user = g.jwt_payload['account']

        arg = self.parser.parse_args()
        avatar_file = arg.get('avatar')

        user = AccountsModel.query.filter_by(account = current_user,deactivate = False).first()
        if not user:
            status_code = 404
            response['msg'] = 'No such user'
            return make_response(jsonify(response),status_code)
        if user.avatar and re.search(r'\/\w+\/[a-fA-F0-9-]+\.[a-zA-Z]+$',user.avatar):
            try:
                bucket_remove(user.avatar,'avatars')
            except Exception as e:
                status_code=400
                response['msg']=str(e)
                return make_response(jsonify(response), status_code)
        try:
            try:
                img_url = bucket_upload(avatar_file,'avatars','avatar',current_user)
            except Exception as e:
                status_code = 400
                response['msg'] = str(e)
                return make_response(jsonify(response),status_code)

            user.avatar = img_url
            db.session.commit()
            response['msg'] = 'success'
            
        except Exception as e:
            db.session.rollback()
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)

#寄發驗證信處理
class AccountVerifi(Resource):
    @token_required(secret_key_=secret_key)
    @limiter.limit("2 per minute")
    @limiter.limit("5 per day")
    def post(self):
        response,status_code={},200
        current_user = g.jwt_payload['account']
        user = AccountsModel.query.filter_by(account = current_user,deactivate = False, is_verified = False).first()
        if user:
            verifi_token = jwt.encode({'account':user.account,'exp':time.time()+600,'aud':'API_via_email','jti':str(uuid.uuid4())},secret_key,algorithm='HS256')
            mail_verifi(recipient=user.email,token=verifi_token)

        response['msg'] = 'mail sending successfully'
        return make_response(jsonify(response),status_code)

    @verification(secret_key_=secret_key)
    @limiter.limit("2 per day")
    def patch(self):
        response,status_code={},200
        current_user = g.jwt_v_payload['account']
        

        user = AccountsModel.query.filter_by(account = current_user,deactivate = False, is_verified = False).first()
        if not user:
            status_code = 404
            response['msg'] = 'No such user'
            return make_response(jsonify(response),status_code)
        
        try:
            need_blocked(jti=g.jwt_v_payload['jti'],exp=g.jwt_v_payload['exp'])    
            user.is_verified = True
            db.session.commit()
            response['msg'] = 'success'
        except Exception as e:
            db.session.rollback()
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)
    
#寄發密碼重設處理
class PSW(Resource):
    @limiter.limit("2 per minute")
    @limiter.limit("5 per day")
    def post(self):
        response,status_code={},200
        data = request.get_json()
        if not data or not data.get('account_login'):
            status_code = 400
            response['msg'] = 'requirements cannot be blanked'
            return make_response(jsonify(response),status_code)
        
        account_login = data.get('account_login')
        user = AccountsModel.query.filter(((AccountsModel.account ==  account_login)|(AccountsModel.email ==  account_login)),AccountsModel.deactivate == False).first()
        if user:
            psw_token = jwt.encode({'account':user.account,'exp':time.time()+600,'aud':'API_via_email','jti':str(uuid.uuid4())},secret_key,algorithm='HS256')
            mail_psw(recipient=user.email,token=psw_token)
        response['msg'] = 'mail sending successfully'
        return make_response(jsonify(response),status_code)
    
    @verification(secret_key_=secret_key)
    @limiter.limit("2 per minute")
    def patch(self):
        response,status_code={},200
        current_user = g.jwt_v_payload['account']
        

        data = request.get_json()
        if not data or not data.get('passwords'):
            status_code = 400
            response['msg'] = 'requirements cannot be blanked'
            return make_response(jsonify(response),status_code)
        
        user = AccountsModel.query.filter_by(account = current_user,deactivate = False).first()
        if not user:
            status_code = 404
            response['msg'] = 'No such user'
            return make_response(jsonify(response),status_code)
        
        if (len(data.get('passwords'))<8) or (re.search(r'[^a-zA-Z0-9+_*@#$%^&!?-]',data.get('passwords'),re.ASCII)):
            status_code = 400
            response['msg'] = 'password cannot be shorter then 8-characters or use illegal characters'
            return make_response(jsonify(response),status_code)
        passwords_check = [r'[a-z]',r'[A-Z]',r'[0-9]',r'[+_*@#$%^&!?-]']
        for i in passwords_check:
            if not (re.search(i,data.get('passwords'),re.ASCII)):
                status_code = 400
                response['msg'] = 'the password must include captial and lower case letter, numbers and special symbols(+-_*@#$%^&!?) '
                return make_response(jsonify(response),status_code)
        if check_password_hash(user.passwords,data.get('passwords')):
            status_code = 400
            response['msg'] = 'new password cannot be the same as previous one'
            return make_response(jsonify(response),status_code)
        
        new_psw = generate_password_hash(data.get('passwords'))
        try:
            user.passwords = new_psw
            need_blocked(jti=g.jwt_v_payload['jti'],exp=g.jwt_v_payload['exp'])
            db.session.commit()
            response['msg'] = 'success'
        except Exception as e:
            db.session.rollback()
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)

#登出功能
class Logout(Resource):
    @token_required(secret_key_=secret_key)
    @limiter.limit("5 per minute")
    def post(self):
        response,status_code={},200
        payload = g.jwt_payload
        try:
            need_blocked(jti=payload['jti'],exp=payload['exp'])
            db.session.commit()

            response={
                'msg':'success'
            }
        except Exception as e:
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)




