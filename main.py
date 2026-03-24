from flask import jsonify
from flask_restful import Api
import psycopg2 as pg2
from psycopg2 import extras
from sqlalchemy import text
import os, jwt, logging

from server import app, socketio, emit, join_room
from resources.accounts import Register,Login,AccountVerifi,PSW,User,Avatar,Logout
from resources.articles import Article,Articles,AllTags,Draft,Drafts,ContentImgs,CoverImgs
from resources.messages import Message,Unreads,Messages
from resources.bookmark import Bookmark,UserBookmarkID
from resources.tknmanage import Clean, CronJob
from util.auth import is_blocked

api=Api(app)

api.add_resource(Register,'/api/v1/auth/register')
api.add_resource(Login,'/api/v1/auth/login')
api.add_resource(AccountVerifi,'/api/v1/verify')
api.add_resource(PSW,'/api/v1/rppsw')
api.add_resource(Logout,'/api/v1/auth/logout')
api.add_resource(User,'/api/v1/profile/<account>','/api/v1/profile/','/api/v1/profile/setting')
api.add_resource(Article,'/api/v1/article/<id>','/api/v1/article/','/api/v1/article')
api.add_resource(Articles,'/api/v1/articles')
api.add_resource(Drafts,'/api/v1/drafts')
api.add_resource(Draft,'/api/v1/draft/<id>','/api/v1/draft/')
api.add_resource(Avatar,'/api/v1/profile/avatar')
api.add_resource(CoverImgs,'/api/v1/article/cover')
api.add_resource(ContentImgs,'/api/v1/article/img')
api.add_resource(Message,'/api/v1/article/<id>/msg','/api/v1/article//msg','/api/v1/mailbox/<msg_id>','/api/v1/mailbox/')
api.add_resource(Unreads,'/api/v1/unreads','/api/v1/message/<msg_id>','/api/v1/message/')
api.add_resource(Messages,'/api/v1/messages')
api.add_resource(Bookmark,'/api/v1/bookmark/<id>','/api/v1/bookmark/','/api/v1/bmkaarticles')
api.add_resource(UserBookmarkID,'/api/v1/bookmarks')
api.add_resource(AllTags,'/api/v1/alltags')
api.add_resource(Clean,'/api/v1/clean_tkn')
api.add_resource(CronJob,'/api/v1/wake')

logger = logging.getLogger(__name__)
secret_key = os.environ.get('JWT_SECRET_KEY')

@socketio.on('connect')
def connect_socket(auth):
    
    if not auth or not auth.get('Authorization') or not auth.get('Authorization').startswith('Bearer '):
        # print('no auth error')
        return False
    
    token = auth.get('Authorization').split(" ")[1]
    try:
        payload = jwt.decode(token,secret_key,algorithms='HS256',audience='API_via_login')
        if is_blocked(payload.get('jti')):
            return False
   
    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False
    except Exception as e:
        # print('decode error')
        logger.exception(f'websocket錯誤>> {str(e)}',exc_info=True)
        return False
    join_room(payload['account'])

# @app.route('/')
# def test():
#     try:
#         db.session.execute(text("SELECT 1"))
#         return jsonify({"status":"success"})
#     except Exception as e:
#         return jsonify({"status":f"error,{str(e)}"})


if __name__ == "__main__":
    port = int(os.environ.get('PORT',5000))
    app.run(host='0.0.0.0',port=port)