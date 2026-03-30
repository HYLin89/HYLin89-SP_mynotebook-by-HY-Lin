from flask_restful import Resource,reqparse
import psycopg2 as pg2
from psycopg2 import extras
from flask import jsonify,make_response,request, g
import traceback
import os, re, logging

from server import db, limiter
from model import AccountsModel,ArticlesModel
from util.auth import token_required

logger = logging.getLogger(__name__)
secret_key = os.environ.get('JWT_SECRET_KEY')

#用戶書籤互動處理
class Bookmark(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('page',type = int,required = False,default = 1,location = 'args')
        self.parser.add_argument('author',required = True,location = 'args')

    @token_required(secret_key_=secret_key)
    @limiter.limit("5 per minute")
    def patch(self,id=None):
        response,status_code={},200
        if not id:
            status_code = 400
            response['msg'] = 'article id is required'
            return make_response(jsonify(response),status_code)
        
        current_user = g.jwt_payload['account']
        user = AccountsModel.query.filter_by(account = current_user, deactivate = False).first()
        if not user:
            status_code = 404
            response['msg'] = 'no such user'
            return make_response(jsonify(response),status_code)
        
        article = ArticlesModel.query.join(AccountsModel).filter(
            ArticlesModel.id == id,
            ArticlesModel.status == 'public',
            AccountsModel.deactivate == False,
            ArticlesModel.deleted == False,
            AccountsModel.account != current_user
            ).first()
        if not article :
            status_code = 404
            response['msg'] = 'article not exists'
            return make_response(jsonify(response),status_code)
        
        try:
            new_mark = user.marked
            if new_mark.filter(ArticlesModel.id == id).first():
                new_mark.remove(article)
            else:
                new_mark.append(article)
            db.session.commit()
            response['msg'] = 'success'

        except Exception as e:
            db.session.rollback()
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)

    
    @limiter.limit("60 per minute")
    def get(self,id=None):
        response,status_code={},200
        if id:
            status_code = 405
            response['msg'] = 'invalid action'
            return make_response(jsonify(response),status_code)
        
        arg = self.parser.parse_args()
        page_is = arg.get('page')
        author_is = arg.get('author')
        
        user = AccountsModel.query.filter_by(account = author_is, deactivate = False).first()
        if not user:
            status_code = 404
            response['msg'] = 'no such user'
            return make_response(jsonify(response),status_code)

        try:
            paginate_data = user.marked.join(ArticlesModel.author).filter(
                ArticlesModel.deleted == False,
                ArticlesModel.status == 'public',
                AccountsModel.deactivate == False
                ).paginate(page = page_is, per_page = 5, error_out = False,max_per_page=5)
            bk_articles = [{
                'id':art.id,
                'title':art.title,
                'cover_img':art.cover_img,
                'author':art.author.user_name,
                'claps':len(art.mark_by)
            } for art in paginate_data.items]
            meta_data = {
                'current_page':paginate_data.page,
                'total_pages':paginate_data.pages,
                'total_items':paginate_data.total,
                'has_next':paginate_data.has_next,
                'has_prev':paginate_data.has_prev
            }

            response = {
                'msg':'success',
                'article_data':bk_articles,
                'meta':meta_data
            }
        except Exception as e:
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)

#網站初始化時用戶已擁有全部書籤的id
class UserBookmarkID(Resource):
    @token_required(secret_key_=secret_key)
    @limiter.limit("60 per minute")
    def get(self):
        response,status_code={},200

        current_user = g.jwt_payload['account']
        user = AccountsModel.query.filter_by(account = current_user, deactivate = False).first()
        if not user:
            status_code = 404
            response['msg'] = 'no such user'
            return make_response(jsonify(response),status_code)
        try:
            user_marks = user.marked.all()
            response={
                'msg':'success',
                'data':[items.id for items in user_marks]
            }
        except Exception as e:
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)

            



