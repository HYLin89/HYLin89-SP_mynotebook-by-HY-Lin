import psycopg2 as pg2
from psycopg2 import extras
from model import TagsModel
from server import db

def tagSetting(input_tags):
    input_tags = {i.casefold() for i in input_tags}
    exist_tags = TagsModel.query.filter(TagsModel.name.in_(input_tags)).all()
    new_tags = input_tags - {i.name for i in exist_tags}
    tag = []
    if new_tags:
        tag = [TagsModel(
            name = tg
        ) for tg in new_tags]

    return exist_tags + tag


def tagQuery():
    alltags = db.session.query(TagsModel.name).order_by(TagsModel.name).all()
    alltags = [tgs.name for tgs in alltags]
    return alltags