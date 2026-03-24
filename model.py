#建立資料庫模型，提供可傳送資料庫欄位
from server import db
from datetime import datetime,timezone

class AccountsModel(db.Model):
    __tablename__='accounts'
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(15),unique=True)
    account = db.Column(db.String(25),nullable=False,unique=True)
    passwords = db.Column(db.String,nullable=False)
    email = db.Column(db.Text,nullable=False,unique=True)
    deactivate = db.Column(db.Boolean,default=False)
    avatar = db.Column(db.Text)
    bio = db.Column(db.Text)
    links = db.Column(db.JSON)
    is_verified = db.Column(db.Boolean)

    articles = db.relationship('ArticlesModel',backref = 'author', lazy='dynamic')

    def __init__(self,user_name,account,passwords,email,deactivate,avatar,bio,links,is_verified):
        self.user_name = user_name
        self.account = account
        self.passwords = passwords
        self.email = email
        self.deactivate = deactivate
        self.avatar = avatar
        self.bio = bio
        self.links = links
        self.is_verified = is_verified

BooksMarks = db.Table(
    'bookmark',
    db.Column('user_id',db.Integer, db.ForeignKey('accounts.id'), primary_key=True, nullable=False),
    db.Column('article_id',db.Integer, db.ForeignKey('articles.id'), primary_key=True, nullable=False)
    )

#中介表 tags2articles
ArticleTag = db.Table(
    'article_tag',
    db.Column('article_id',db.Integer, db.ForeignKey('articles.id'), primary_key=True, nullable=False),
    db.Column('tag_id',db.Integer, db.ForeignKey('tags.id'), primary_key=True, nullable=False)
    )

class ArticlesModel(db.Model):
    __tablename__='articles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('accounts.id'),nullable=False)
    title = db.Column(db.Text, nullable=False,unique=True)
    cover_img = db.Column(db.Text)
    content = db.Column(db.Text, nullable=False,unique=True)
    created_at = db.Column(db.DateTime,default = datetime.now(timezone.utc),server_default = db.func.now())
    updated_at = db.Column(db.DateTime,default = datetime.now(timezone.utc),onupdate = datetime.now(timezone.utc),server_default = db.func.now())
    status = db.Column(db.String,default='draft')
    deleted = db.Column(db.Boolean, default=False)

    tags = db.relationship('TagsModel',secondary = ArticleTag ,backref = db.backref('articles', lazy='dynamic'))
    mark_by = db.relationship('AccountsModel',secondary = BooksMarks, backref = db.backref('marked', lazy='dynamic'))

class TagsModel(db.Model):
    __tablename__='tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False, unique=True)

class MessageModel(db.Model):
    __tablename__='messages'
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(15),db.ForeignKey('accounts.account'), nullable=False)
    receiver = db.Column(db.String(15),db.ForeignKey('accounts.account'), nullable=False)
    article_id = db.Column(db.Integer,db.ForeignKey('articles.id'), nullable=False)
    content = db.Column(db.Text,nullable=False)
    is_read = db.Column(db.Boolean,default=False)
    created_at = db.Column(db.DateTime,default = datetime.now(timezone.utc),server_default = db.func.now())
    parent_id = db.Column(db.Integer,default = None)

    article = db.relationship('ArticlesModel',backref="messages")
    msg_sender = db.relationship('AccountsModel',foreign_keys=[sender],backref= 'sent_msg')


class TokenModel(db.Model):
    __tablename__ = 'invalid_tokens'
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    token = db.Column(db.Text, nullable=False, unique=True)
    expired_at = db.Column(db.Float, nullable=False)


