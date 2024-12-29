from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Enum,
    DECIMAL,
    Table,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "tbl_user"
    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(55))
    last_name = Column(String(55))
    creation_date = Column(DateTime, default=func.now())
    modification_date = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )
    role = Column(Enum("admin", "user"), default="user")
    email = Column(String(55))
    phone_number = Column(Integer)
    password = Column(String, nullable=False)

class Friends(Base):
    __tablename__ = "tbl_friends"
    friend_id = Column(Integer, ForeignKey("tbl_user.id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("tbl_user.id"), primary_key=True)
    creation_date = Column(DateTime, default=func.now())
    modification_date = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

class FriendRequests(Base):
    __tablename__ = "tbl_friend_requests"
    friend_request_id = Column(Integer, ForeignKey("tbl_user.id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("tbl_user.id"), primary_key=True)
    creation_date = Column(DateTime, default=func.now())
    modification_date = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

class Group(Base):
    __tablename__ = "tbl_group"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(55))
    creation_date = Column(DateTime, default=func.now())
    modification_date = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

class GroupMember(Base):
    __tablename__ = "tbl_group_member"
    group_id = Column(Integer, ForeignKey("tbl_group.id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("tbl_user.id"), primary_key=True)
    creation_date = Column(DateTime, default=func.now())
    modification_date = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

class Expense(Base):
    __tablename__ = "tbl_expenses"
    expense_id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("tbl_group.id"))
    description = Column(String(255))
    amount = Column(DECIMAL(10, 2))
    paid_by = Column(Integer, ForeignKey("tbl_user.id"))
    created_by = Column(Integer, ForeignKey("tbl_user.id"))
    split_type = Column(Enum("equal", "ratio", "exact"), default="equal")
    created_at = Column(DateTime, default=func.now())

class ExpenseSplit(Base):
    __tablename__ = "tbl_expense_split_table"
    split_id = Column(Integer, primary_key=True, autoincrement=True)
    expense_id = Column(Integer, ForeignKey("tbl_expenses.expense_id"))
    user_id = Column(Integer, ForeignKey("tbl_user.id"))
    share = Column(DECIMAL(10, 2))
    paid = Column(DECIMAL(10, 2), default=0)
    ratio = Column(Integer)

class Settlement(Base):
    __tablename__ = "tbl_settlements"
    settlement_id = Column(Integer, primary_key=True, autoincrement=True)
    payer_id = Column(Integer, ForeignKey("tbl_user.id"))
    payee_id = Column(Integer, ForeignKey("tbl_user.id"))
    group_id = Column(Integer, ForeignKey("tbl_group.id"))
    amount = Column(DECIMAL(10, 2))
    settled_at = Column(DateTime, default=func.now())
