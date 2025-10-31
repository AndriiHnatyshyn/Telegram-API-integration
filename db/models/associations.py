from sqlalchemy import Table, Column, ForeignKey, Integer
from db.engine import Base


account_chat_association = Table(
    'account_chat_association',
    Base.metadata,
    Column('account_id', Integer, ForeignKey('accounts.id'), primary_key=True),
    Column('chat_id', Integer, ForeignKey('chats.id'), primary_key=True)
)