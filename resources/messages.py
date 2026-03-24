from flask_restful import Resource, reqparse
import psycopg2 as pg2
from psycopg2 import extras
from flask import jsonify,make_response,request, g
from datetime import datetime,timezone
import traceback
import os, logging

from server import db, distinct, func, socketio, limiter
from util.auth import token_required
from model import MessageModel,AccountsModel,ArticlesModel

logger = logging.getLogger(__name__)
secret_key = os.environ.get('JWT_SECRET_KEY')

#單篇站內信處理
class Message(Resource):
    @token_required(secret_key_=secret_key)
    @limiter.limit("2 per minute")
    @limiter.limit("5 per day")
    def post(self,id):
        response,status_code={},200
        if not id:
            status_code = 400
            response['msg'] = 'article id is required'
            return make_response(jsonify(response),status_code)
        
        data = request.get_json().get('content')
        current_user = g.jwt_payload['account']

        if (not data):
            status_code = 400
            response['msg'] = 'requirements cannot be blanked'
            return make_response(jsonify(response),status_code)
        
        user = AccountsModel.query.filter_by(account = current_user, deactivate = False, is_verified= True).first()
        if not user :
            status_code=404
            response['msg'] = 'account not verified'
            return make_response(jsonify(response),status_code)
        
        article = ArticlesModel.query.join(AccountsModel).filter(
            ArticlesModel.id == id,
            ArticlesModel.status == "public",
            ArticlesModel.deleted == False,
            AccountsModel.deactivate == False,
        ).first()
        if not article:
            status_code=404
            response['msg'] = 'article or user not exists'
            return make_response(jsonify(response),status_code)
        if article.author.account == current_user:
            status_code=400
            response['msg'] = 'invalid actions, message to your own articles are forbiddened'
            return make_response(jsonify(response),status_code)

        try:
            new_message = MessageModel(
                sender = user.account,
                receiver = article.author.account,
                article_id = id,
                content = data,
                parent_id = None
            )
            db.session.add(new_message)
            db.session.commit()
            response['msg'] = 'success'

        except Exception as e:
            db.session.rollback()
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)

        if response['msg'] == 'success':
            try:
                if len(data)>15:
                    ws_content = data,
                else:
                    ws_content = f'{data[:15]}...'
                socketio.emit(
                    'new_message',
                    {
                        'account':user.account,
                        'article':f'About: {article.title}',
                        'content':ws_content,
                        'timestamp':str(datetime.now(timezone.utc))
                    },
                    to=article.author.account
                )

            except Exception as e:
                status_code=500
                traceback.print_exc()
                response['msg']='error'
                logger.exception(f'SOCKET錯誤>> {str(e)}',exc_info=True)
        
        return make_response(jsonify(response),status_code)
    
    @token_required(secret_key_=secret_key)
    @limiter.limit("60 per minute")
    def get(self,msg_id):
        response,status_code={},200
        if not msg_id:
            status_code = 400
            response['msg'] = 'message id is required'
            return make_response(jsonify(response),status_code)

        target = MessageModel.query.get(msg_id)
        if target.parent_id:
            root = target.parent_id
        else:
            root = target.id
        message = MessageModel.query.filter((MessageModel.id == root)|(MessageModel.parent_id == root)).order_by(MessageModel.created_at.asc()).all()
        if not message:
            status_code = 404
            response['msg'] = 'message not exists'
            return make_response(jsonify(response),status_code)

        try:
            data = [{
                'msg_id':msg.id,
                'user':msg.sender,
                'content':msg.content,
                'article_id':msg.article_id,
                'datetime':str(msg.created_at)[0:10],
                'parent_id':msg.parent_id } for msg in message]
            response = {
                'msg':'success',
                'message_data':data
            }
        except Exception as e:
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)

    @token_required(secret_key_=secret_key)
    def patch(self,msg_id):
        response,status_code={},200
        if not msg_id:
            status_code = 400
            response['msg'] = 'message id is required'
            return make_response(jsonify(response),status_code)
        
        current_user = g.jwt_payload['account']
        
        message = MessageModel.query.filter(
            (MessageModel.id == msg_id) |(MessageModel.parent_id == msg_id),
            MessageModel.receiver == current_user,
            MessageModel.is_read == False
            ).all()
        if not message:
            status_code = 404
            response['msg'] = 'target not exists'
            return make_response(jsonify(response),status_code)
        
        try:
            for msg in message:
                msg.is_read = True

            db.session.commit()
            response['msg'] = 'success'

        except Exception as e:
            db.session.rollback()
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)
    
#處理未讀狀態(右上角小數字渲染)
class Unreads(Resource):
    @token_required(secret_key_=secret_key)
    @limiter.limit("60 per minute")
    def get(self):
        response,status_code={},200
        current_user = g.jwt_payload['account']

        try:
            message = MessageModel.query.filter_by(receiver=current_user, is_read = False).count()
            response = {
                'msg':'success',
                'unread_counts':message
            }
            
        except Exception as e:
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)

#回覆單篇未讀訊息    
    @token_required(secret_key_=secret_key)
    @limiter.limit("5 per minute")
    def post(self,msg_id):
        response,status_code={},200
        if not msg_id:
            status_code = 400
            response['msg'] = 'message id is required'
            return make_response(jsonify(response),status_code)
        
        data = request.get_json().get('content')
        current_user = g.jwt_payload['account']

        if (not data):
            status_code = 400
            response['msg'] = 'requirements cannot be blanked'
            return make_response(jsonify(response),status_code)
        
        user = AccountsModel.query.filter_by(account = current_user, deactivate = False, is_verified= True).first()
        if not user:
            status_code=404
            response['msg'] = 'no such user'
            return make_response(jsonify(response),status_code)
        
        message = MessageModel.query.filter(MessageModel.id == msg_id).first()
        if not message:
            status_code=404
            response['msg'] = 'target not exists'
            return make_response(jsonify(response),status_code)
        if message.receiver == current_user:
            status_code=400
            response['msg'] = 'invalid actions, message to your own articles are forbiddened'
            return make_response(jsonify(response),status_code)

        try:
            new_message = MessageModel(
                sender = current_user,
                receiver = message.sender,
                article_id = message.article.id,
                content = data,
                parent_id = msg_id
            )
            db.session.add(new_message)
            db.session.commit()
            response['msg'] = 'success'

        except Exception as e:
            db.session.rollback()
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)

        if response['msg'] == 'success':
            try:
                if len(data)>15:
                    ws_content = data,
                else:
                    ws_content = f'{data[:15]}...'
                socketio.emit(
                    'new_message',
                    {
                        'account':user.current_user,
                        'article':f'About: {message.article.title}',
                        'content':ws_content,
                        'timestamp':str(datetime.now(timezone.utc))
                    },
                    to=message.msg_sender.account
                )

            except Exception as e:
                status_code=500
                traceback.print_exc()
                response['msg']='error'
                logger.exception(f'SOCKET錯誤>> {str(e)}',exc_info=True)
        
        return make_response(jsonify(response),status_code)

#渲染信箱介面左側總覽
class Messages(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('page',type = int,required = False,default = 1,location = 'args')

    @token_required(secret_key_=secret_key)
    @limiter.limit("60 per minute")
    def get(self):
        response,status_code={},200
        arg = self.parser.parse_args()
        page_is = arg.get('page')

        current_user = g.jwt_payload['account']
        
        try:
            thread_expr = func.coalesce(MessageModel.parent_id, MessageModel.id).label('thread_id')
            sub = db.session.query(thread_expr, func.max(MessageModel.created_at).label('latest')).filter((MessageModel.receiver == current_user)|(MessageModel.sender == current_user)).group_by(thread_expr).subquery()
            paginate_data = MessageModel.query.join(sub,(func.coalesce(MessageModel.parent_id,MessageModel.id) == sub.c.thread_id) & (MessageModel.created_at == sub.c.latest)).order_by(MessageModel.created_at.desc()).paginate(page=page_is, per_page=10, error_out=False, max_per_page=10)
            message_item = [{
                'id':msg.id,
                'title':f'About: {msg.article.title}',
                'timestamp':str(msg.created_at)[0:10],
                'from':msg.sender,
                'is_read':msg.is_read,
            } for msg in paginate_data.items]
       
            meta_data = {
                'current_page':paginate_data.page,
                'total_pages':paginate_data.pages,
                'total_items':paginate_data.total,
                'has_next':paginate_data.has_next,
            }
            response = {
                'msg':'success',
                'messages':message_item,
                "meta":meta_data
            }
            
        except Exception as e:
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)
            







