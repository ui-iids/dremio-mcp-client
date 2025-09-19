from typing import TYPE_CHECKING

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    ForeignKey,
    MetaData,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData()


db = SQLAlchemy(
    model_class=Base,
    engine_options={
        # # To see generated SQL in stdout
        # "echo": True,
        # # To use Geometric queries, install geoalchemy2
        # "plugins": ["geoalchemy2"]
    },
)

# MyPy workaround for class issue
if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model
else:
    Model = db.Model


class People(Model):
    __tablename__ = "people"
    user_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column()
    username: Mapped[str] = mapped_column()


class Groups(Model):
    __tablename__ = "groups"
    group_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column()


class PeopleGroups(Model):
    __tablename__ = "people_groups"
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.group_id"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("people.user_id"), primary_key=True)
