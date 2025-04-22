from functools import cached_property
import json
import typing
import sqlalchemy
import sqlalchemy.orm
from dataclasses import dataclass
from sqlalchemy.dialects import postgresql
import app.database  # import for side effects

int_list = list[int]
str_list = list[str]
json_list = list[int] | list[str]
json_scalar = typing.Union[float, str, bool]


# declarative base class
class Base(sqlalchemy.orm.DeclarativeBase):
    type_annotation_map = {
        str_list: postgresql.JSONB,
        int_list: postgresql.JSONB,
        json_list: postgresql.JSONB,
        json_scalar: postgresql.JSON,
    }


@dataclass
class Character:
    id: int
    name: str
    personality: str
    background: str
    profile_image_url: str
    is_main_character: bool


class GameSession(Base):
    __tablename__ = "game-sessions"

    id = sqlalchemy.orm.mapped_column(sqlalchemy.Uuid, primary_key=True)
    title: sqlalchemy.orm.Mapped[str]
    themes: sqlalchemy.orm.Mapped[list[str]]
    synopsis: sqlalchemy.orm.Mapped[str]
    visual_style: sqlalchemy.orm.Mapped[str]
    promo_image_url: sqlalchemy.orm.Mapped[str]
    reference_material_summary: sqlalchemy.orm.Mapped[str] = (
        sqlalchemy.orm.mapped_column(sqlalchemy.Text())
    )
    opening_video_url: sqlalchemy.orm.Mapped[str]
    opening_act_synopsis: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Text()
    )
    middle_act_synopsis: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Text()
    )
    final_act_synoposis: sqlalchemy.orm.Mapped[typing.Optional[str]] = (
        sqlalchemy.orm.mapped_column(sqlalchemy.Text())
    )
    raw_characters: sqlalchemy.orm.Mapped[json_scalar]
    prologue: sqlalchemy.orm.Mapped[str_list]
    remaining_actions: sqlalchemy.orm.Mapped[int]
    total_actions: sqlalchemy.orm.Mapped[int]
    final_video_url: sqlalchemy.orm.Mapped[typing.Optional[str]]

    closing_remarks: sqlalchemy.orm.Mapped[typing.Optional[str]]

    story_blocks: sqlalchemy.orm.Mapped[typing.List["GameStoryBlock"]] = (
        sqlalchemy.orm.relationship()
    )

    @property
    def characters(self):
        chars = json.loads(self.raw_characters)

        return list(map(lambda c: Character(**c), chars))

    @property
    def ordered_story_blocks(self):
        return self.story_blocks


class GameStoryBlock(Base):
    __tablename__ = "game-story-blocks"

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(primary_key=True)
    number: sqlalchemy.orm.Mapped[int]
    previous_action: sqlalchemy.orm.Mapped[str]
    actions_consumed: sqlalchemy.orm.Mapped[int]
    is_final_act: sqlalchemy.orm.Mapped[bool]
    dialogue: sqlalchemy.orm.Mapped[str_list]
    backdrop_image_url: sqlalchemy.orm.Mapped[typing.Optional[str]]
    session_id = sqlalchemy.orm.mapped_column(
        sqlalchemy.Uuid, sqlalchemy.ForeignKey(f"{GameSession.__tablename__}.id")
    )
    possible_actions: sqlalchemy.orm.Mapped[str_list]

    session: sqlalchemy.orm.Mapped[GameSession] = sqlalchemy.orm.relationship(
        GameSession, back_populates="story_blocks"
    )
