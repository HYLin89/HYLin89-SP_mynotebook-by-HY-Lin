from flask_restful import Resource,reqparse
import psycopg2 as pg2
from psycopg2 import extras
from flask import jsonify,make_response,request, g
from werkzeug.datastructures import FileStorage
import traceback
import os, re, logging

from server import db, limiter
from model import AccountsModel,ArticlesModel
from util.auth import token_required
from util.tags import tagSetting,tagQuery
from util.storage import bucket_upload,bucket_remove

logger = logging.getLogger(__name__)
secret_key = os.environ.get('JWT_SECRET_KEY')

#單篇文章(已發布)處理
class Article(Resource):
    @token_required(secret_key_=secret_key)
    @limiter.limit("5 per minute")
    @limiter.limit("10 per hour")
    def post(self,id=None):
        response,status_code={},200
        if id:
            status_code = 405
            response['msg'] = 'invalid action'
            return make_response(jsonify(response),status_code)
        
        data = request.get_json()
        current_user = g.jwt_payload['account']

        if not data or not data.get('title') or not data.get('content') or not data.get('cover_img'):
            status_code=400
            response['msg'] = 'title or content cannot be blanked in a new article'
            return make_response(jsonify(response),status_code)
        
        tags = data.get('tags',[])
        if type(tags) is not list:
            status_code = 400
            response['msg'] = 'invalid actions'
            return make_response(jsonify(response),status_code)
        else:
            tags = [i.strip() for i in tags if (type(i) is str and i.strip()) ]

        user = AccountsModel.query.filter_by(account = current_user,deactivate = False).first()
        if not user:
            status_code = 404
            response['msg'] = 'no such user'
            return make_response(jsonify(response),status_code)

        try:
            article = ArticlesModel(
                user_id=user.id,
                title=data.get('title'),
                cover_img=data.get('cover_img'),
                content=data.get('content'),
                status=data.get('status', 'draft'),
                deleted=False
            )
            
            db.session.add(article)
            if tags:
                article.tags = tagSetting(tags)

            db.session.commit()
            response['msg']='success'
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
        if not id:
            status_code = 400
            response['msg'] = 'article id is required'
            return make_response(jsonify(response),status_code)
        
        article = ArticlesModel.query.join(AccountsModel).filter(
            ArticlesModel.id == id,
            ArticlesModel.status == "public",
            ArticlesModel.deleted == False,
            AccountsModel.deactivate == False
        ).first()
        if not article:
            status_code=404
            response['msg'] = 'article or user not exists'
            return make_response(jsonify(response),status_code)
        
        try: 
            response = {
                'msg':'success',
                'article_data':{
                    'id':article.id,
                    'title':article.title,
                    'author':article.author.user_name,
                    'account':article.author.account,
                    'avatar':article.author.avatar,
                    'cover_img':article.cover_img,
                    'content':article.content,
                    'updated_at':article.updated_at
                },
                'tags':[tg.name for tg in article.tags]
            }
        except Exception as e:
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)
    
    @token_required(secret_key_=secret_key)
    @limiter.limit("10 per minute")
    def patch(self,id=None):
        response,status_code={},200
        if not id:
            status_code = 400
            response['msg'] = 'article id is required'
            return make_response(jsonify(response),status_code)
    
        current_user = g.jwt_payload['account']
        article = ArticlesModel.query.join(AccountsModel).filter(
            ArticlesModel.id == id,
            ArticlesModel.deleted == False,
            AccountsModel.deactivate == False,
            AccountsModel.account == current_user
        ).first()
        if not article:
            status_code=404
            response['msg'] = 'article not exists'
            return make_response(jsonify(response),status_code)
        
        data = request.get_json()
        if not data:
            status_code = 400
            response['msg'] = 'no data provided'
            return make_response(jsonify(response),status_code)

        updated_allow = ['title','cover_img','content','status','tags']
        updated_data = {key:value for key, value in data.items() if key in updated_allow}
    
        if not updated_data:
            status_code = 400
            response['msg'] = 'invalid actions'
            return make_response(jsonify(response),status_code)
        
        if 'tags' in updated_data:
                if type(updated_data['tags']) is not list:
                    status_code = 400
                    response['msg'] = 'invalid actions'
                    return make_response(jsonify(response),status_code)
                else:
                    tags = [i.strip() for i in updated_data['tags'] if (type(i) is str and i.strip()) ]
                    article.tags = tagSetting(tags)

        try:
            for key, value in updated_data.items():
                if key == 'tags':
                    continue
                setattr(article, key, value)

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
    @limiter.limit("5 per minute")
    def delete(self,id=None):
        response,status_code={},200
        if not id:
            status_code = 400
            response['msg'] = 'article id is required'
            return make_response(jsonify(response),status_code)
        
        current_user = g.jwt_payload['account']

        article = ArticlesModel.query.join(AccountsModel).filter(
            ArticlesModel.id == id,
            ArticlesModel.deleted == False,
            AccountsModel.deactivate == False,
            AccountsModel.account == current_user
        ).first()
        if not article:
            status_code=404
            response['msg'] = 'article not exists'
            return make_response(jsonify(response),status_code)

        try:
            article.deleted = True
            db.session.commit()
            response['msg'] = 'success'
        except Exception as e:
            db.session.rollback()
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)

#多篇文章(河道/查詢/作者頁)     
class Articles(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('page',type = int,required = False,default = 1,location = 'args')
        self.parser.add_argument('author',required = False,location = 'args')
        self.parser.add_argument('tag',type=str,required = False,location = 'args')
        self.parser.add_argument('query',type=str,required = False,location = 'args')
        self.parser.add_argument('mark_by',type=str,required = False,location = 'args')

    @limiter.limit("60 per minute")
    def get(self):
        response,status_code={},200
        arg = self.parser.parse_args()
        author_is = arg.get('author')
        page_is = arg.get('page')
        tag_is = arg.get('tag')
        query_is = arg.get('query')
        markBy_is = arg.get('mark_by')

        articles = ArticlesModel.query.join(AccountsModel).filter(
            ArticlesModel.deleted == False,
            ArticlesModel.status == 'public',
            AccountsModel.deactivate == False,
        )
        if author_is:
            articles = articles.filter(AccountsModel.account == author_is)
        if query_is:
            articles = articles.filter(ArticlesModel.title.contains(query_is))
        if markBy_is:
            articles = articles.filter(ArticlesModel.mark_by.any(AccountsModel.account == markBy_is))
        if tag_is:
            if ',' in tag_is:
                tag_is = tag_is.split(',')
            else:
                tag_is = [tag_is]
            for i in tag_is:
                articles = articles.filter(ArticlesModel.tags.any(name=i))

        try:
            paginate_data = articles.order_by(ArticlesModel.updated_at.desc()).paginate(page = page_is, per_page = 20, error_out = False,max_per_page=20)
            articles_item =[{
                'id':art.id,
                'title':art.title,
                'cover_img':art.cover_img,
                'author':art.author.user_name,
                'updated_at':art.updated_at,
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
                'article_data':articles_item,
                'meta':meta_data
            }
        except Exception as e:
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)

#作者單篇草稿處理
class Draft(Resource):
    @token_required(secret_key_=secret_key)
    @limiter.limit("60 per minute")
    def get(self,id):
        response,status_code={},200
        current_user = g.jwt_payload['account']
        if not id:
            status_code = 400
            response['msg'] = 'article id is required'
            return make_response(jsonify(response),status_code)
        
        article = ArticlesModel.query.join(AccountsModel).filter(
            ArticlesModel.id == id,
            ArticlesModel.status == "draft",
            ArticlesModel.deleted == False,
            AccountsModel.deactivate == False,
            AccountsModel.account == current_user
        ).first()
        if not article:
            status_code=404
            response['msg'] = 'articles not exists'
            return make_response(jsonify(response),status_code)
        
        try: 
            response = {
                'msg':'success',
                'article_data':{
                    'id':article.id,
                    'title':article.title,
                    'author':article.author.user_name,
                    'cover_img':article.cover_img,
                    'content':article.content
                },
                'tags':[tg.name for tg in article.tags]
            }
        except Exception as e:
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)

#作者多篇草稿(用戶本身履歷頁)
class Drafts(Resource):
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

        articles = ArticlesModel.query.join(AccountsModel).filter(
            ArticlesModel.deleted == False,
            ArticlesModel.status == 'draft',
            AccountsModel.deactivate == False,
            AccountsModel.account == current_user
        )

        try:
            paginate_data = articles.order_by(ArticlesModel.updated_at.desc()).paginate(page = page_is, per_page = 20, error_out = False,max_per_page=20)
            articles_item =[{
                'id':art.id,
                'title':art.title,
                'cover_img':art.cover_img,
                'updated_at':art.updated_at
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
                'article_data':articles_item,
                'meta':meta_data
            }
        except Exception as e:
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)

#網站標籤區渲染用
class AllTags(Resource):
    @limiter.limit("60 per minute")
    def get(self):
        response,status_code={},200
        alltags = tagQuery()
        response={
            'msg':'success',
            'data':alltags
        }
        return make_response(jsonify(response),status_code)

#文章封面處理
DEFAULT_COVER_URL = os.environ.get('DEFAULT_COVER_URL')
class CoverImgs(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('cover_img', type = FileStorage, required = True, location = 'files', help = 'you must upload an image')
        self.parser.add_argument('old_covers', type = str, required = False, location = 'form', help = 'error on removing')

    @token_required(secret_key_=secret_key)
    @limiter.limit("5 per minute")
    def post(self):
        response,status_code={},200
        current_user = g.jwt_payload['account']

        arg = self.parser.parse_args()
        cover_img_file = arg.get('cover_img')
        old_imgs = arg.get('old_covers')

        if old_imgs and old_imgs != DEFAULT_COVER_URL:
            if re.search(r'\/\w+\/[a-fA-F0-9-]+\.[a-zA-Z]+$',old_imgs) and (old_imgs.split("/")[-2] == current_user):
                try:
                    bucket_remove(old_imgs,'imgs')
                except Exception as e:
                    status_code=400
                    response['msg']=str(e)
                    return make_response(jsonify(response), status_code)
            else:
                status_code = 403
                response['msg'] = 'forbidden actions'
                return make_response(jsonify(response),status_code)

        try:     
            img_url = bucket_upload(cover_img_file,'imgs','cover_img',current_user)
            response={
                'msg' : 'success',
                'data':img_url
            }
            
        except Exception as e:
            status_code=500
            traceback.print_exc()
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)
    
#文章內文用圖片處理
class ContentImgs(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('content_img', type = FileStorage, required = True, location = 'files', help = 'you must upload an image')

    @token_required(secret_key_=secret_key)
    @limiter.limit("5 per minute")
    def post(self):
        response,status_code={},200
        current_user = g.jwt_payload['account']

        arg = self.parser.parse_args()
        content_img_file = arg.get('content_img')
        try:
            img_url = bucket_upload(content_img_file,'imgs','content',current_user)
                
            response={
                'msg' : 'success',
                'data':img_url
            }
        except ValueError as ve:
            status_code = 400
            response['msg'] = str(ve)

        except Exception as e:
            status_code = 500
            response['msg']='error'
            logger.exception(f'伺服器錯誤>> {str(e)}',exc_info=True)
        return make_response(jsonify(response),status_code)