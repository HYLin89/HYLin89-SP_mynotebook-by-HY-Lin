import os, logging, sys

log_format = '%(asctime)s - %(levelname)s - %(filename)s@%(levelno)s - %(message)s'
logging.basicConfig(
    level=logging.ERROR,
    format=log_format,
    handlers=[
        logging.FileHandler('app_errors.log',encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('socketio').setLevel(logging.ERROR)

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import distinct
from sqlalchemy import func
from flask import Flask
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO, emit, join_room
from flask_mail import Mail, Message
from supabase import create_client,Client
from dotenv import load_dotenv

load_dotenv()

raw_url = os.environ.get('ALLOW_FE_URLS', '')

# 2. 【關鍵防呆】自動拔除網址最後面的斜線，避免比對失敗
safe_origin = raw_url.rstrip('/') 

# 3. 再印一次確認乾淨了
print(f"====== 安全過濾後的 Origin: '{safe_origin}' ======", file=sys.stderr)


cors_config = {
    r"/*":{
        "origins":safe_origin ,
        "methods":["GET","POST","PATCH","DELETE"],
        "supports_credentials":True,
        "max_age":86400
    }
}

#flask server initialize
app = Flask(__name__)
CORS(app, resources=cors_config)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("PROJECT_PGSQL_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS']= False
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get("MAIL_ADDR")
app.config['MAIL_PASSWORD'] = os.environ.get("MAIL_PSW")
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get("MAIL_ADDR")
app.config['DEBUG']= True

#limiter
limiter = Limiter(app=app,key_func=get_remote_address)

#sqlalchemy server
db=SQLAlchemy(app)

#supabase storage connections for imgs
supabase: Client = create_client(
    os.environ.get("PROJECT_BUCKET_URL"),
    os.environ.get("SERVICE_ROLE_KEY")
)

#web-socket for message functions
socketio = SocketIO(app,cors_allowed_origins=safe_origin)

#mail server
mail = Mail(app)
