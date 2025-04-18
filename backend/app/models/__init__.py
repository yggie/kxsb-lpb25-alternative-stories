import difflib
from functools import cached_property
import json
import typing
import sqlalchemy
import sqlalchemy.orm
from dataclasses import dataclass
from sqlalchemy.dialects import postgresql

engine = sqlalchemy.create_engine(
    sqlalchemy.engine.URL(
        drivername="postgresql",
        username="postgres",
        password="example",
        port=5432,
        host="localhost",
        database="postgres",
        query={},
    )
)
connection = engine.connect()

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
class EndStoryEvent:
    type: typing.Literal["story-end"]


@dataclass
class SubmitPhotoTaskEvent:
    type: typing.Literal["submit-photo"]
    photo_url: str


@dataclass
class ShowStoryPrologueEvent:
    type: typing.Literal["story-prologue"]
    lines: typing.List[str]


@dataclass
class ShowVideoEvent:
    type: typing.Literal["video"]
    video_url: str


@dataclass
class WritingNextStoryActEvent:
    type: typing.Literal["writing-next-act"]


@dataclass
class NewStoryActEvent:
    type: typing.Literal["new-act"]
    story_act_id: int


@dataclass
class PlayerPhotoTask:
    type: typing.Literal["player-photo-task"]
    requirements: typing.List[str]


@dataclass
class PlayerDialogueOptionsEvent:
    type: typing.Literal["player-options"]
    options: typing.List[str]


@dataclass
class CharacterDialogueEvent:
    type: typing.Literal["character"]
    character_id: int
    messages: typing.List[str]


GameSessionEvent = typing.Union[
    CharacterDialogueEvent,
    PlayerDialogueOptionsEvent,
    WritingNextStoryActEvent,
    NewStoryActEvent,
    PlayerPhotoTask,
    ShowStoryPrologueEvent,
    ShowVideoEvent,
    SubmitPhotoTaskEvent,
    EndStoryEvent,
]


@dataclass
class Character:
    id: int
    name: str
    personality: str
    background: str
    profile_image_url: str


@dataclass
class StoryEnding:
    name: str
    text: str
    detail: str


class GameSession(Base):
    __tablename__ = "game-sessions"

    id = sqlalchemy.orm.mapped_column(sqlalchemy.Uuid, primary_key=True)
    title: sqlalchemy.orm.Mapped[str]
    genres: sqlalchemy.orm.Mapped[list[str]]
    tone: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(sqlalchemy.Text())
    world_setting: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Text()
    )
    scenario_overview: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Text()
    )
    raw_events: sqlalchemy.orm.Mapped[json_scalar]
    raw_characters: sqlalchemy.orm.Mapped[json_scalar]
    raw_possible_endings: sqlalchemy.orm.Mapped[json_scalar]

    choices: sqlalchemy.orm.Mapped[list[int]]
    current_event_index: sqlalchemy.orm.Mapped[int]

    acts: sqlalchemy.orm.Mapped[typing.List["GameStoryAct"]] = (
        sqlalchemy.orm.relationship()
    )

    @cached_property
    def characters(self):
        chars = json.loads(self.raw_characters)

        return list(map(lambda c: Character(**c), chars))

    @cached_property
    def possible_endings(self):
        endings = json.loads(self.raw_possible_endings)

        return list(map(lambda e: StoryEnding(**e), endings))

    @property
    def events(self) -> typing.List[GameSessionEvent]:
        evs = json.loads(self.raw_events)

        def build_event(ev: dict):
            match ev["type"]:
                case "writing-next-act":
                    return WritingNextStoryActEvent(**ev)

                case "new-act":
                    return NewStoryActEvent(**ev)

                case "player-photo-task":
                    return PlayerPhotoTask(**ev)

                case "character":
                    return CharacterDialogueEvent(**ev)

                case "player-options":
                    return PlayerDialogueOptionsEvent(**ev)

                case "video":
                    return ShowVideoEvent(**ev)

                case "story-prologue":
                    return ShowStoryPrologueEvent(**ev)

                case "submit-photo":
                    return SubmitPhotoTaskEvent(**ev)

                case "story-end":
                    return EndStoryEvent(**ev)

                case _:
                    return None

        return list(map(build_event, evs))

    def write_events(self, events: GameSessionEvent):
        self.raw_events = json.dumps(list(map(lambda e: e.__dict__, events)))

    def load_writing_event(self):
        return [WritingNextStoryActEvent(type="writing-next-act")]

    def load_prephoto_events(self, story_act: "GameStoryAct"):
        chars = self.characters

        new_events = []

        def find_character(name: str):
            for c in chars:
                if c.name == name:
                    return c

            best_ratio = -1
            best_char = chars[0]
            for c in chars:
                ratio = difflib.SequenceMatcher(None, c.name, name).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_char = c

            return best_char

        def import_events(dialogue: typing.List[str]):
            last_char_event: typing.Optional[CharacterDialogueEvent] = None
            for item in dialogue:
                if item.startswith("*:"):
                    new_events.append(
                        PlayerDialogueOptionsEvent(
                            type="player-options",
                            options=list(
                                map(
                                    lambda x: x.strip(),
                                    item.replace("*:", "").split("*"),
                                )
                            ),
                        )
                    )
                    last_char_event = None
                else:
                    s = item.split(":")
                    char = find_character(s[0])
                    msg = ":".join(s[1:])

                    if last_char_event and last_char_event == char.id:
                        last_char_event.messages.append(msg)
                    else:
                        last_char_event = CharacterDialogueEvent(
                            type="character", character_id=char.id, messages=[msg]
                        )
                        new_events.append(last_char_event)

        new_events.append(NewStoryActEvent(type="new-act", story_act_id=story_act.id))
        new_events.append(
            ShowStoryPrologueEvent(type="story-prologue", lines=story_act.prologue),
        )
        new_events.append(
            ShowVideoEvent(type="video", video_url=story_act.opening_video_url),
        )
        import_events(json.loads(story_act.raw_dialogue))
        new_events.append(
            PlayerPhotoTask(
                type="player-photo-task",
                requirements=story_act.photo_requirements,
            )
        )

        return new_events

    def load_postphoto_events(self, story_act: "GameStoryAct", photo_url: str):
        chars = self.characters

        new_events = []

        def find_character(name: str):
            for c in chars:
                if c.name == name:
                    return c

            best_ratio = -1
            best_char = chars[0]
            for c in chars:
                ratio = difflib.SequenceMatcher(None, c.name, name).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_char = c

            return best_char

        def import_events(dialogue: typing.List[str]):
            last_char_event: typing.Optional[CharacterDialogueEvent] = None
            for item in dialogue:
                if item.startswith("*:"):
                    new_events.append(
                        PlayerDialogueOptionsEvent(
                            type="player-options",
                            options=list(
                                map(
                                    lambda x: x.strip(),
                                    item.replace("*:", "").split("*"),
                                )
                            ),
                        )
                    )
                    last_char_event = None
                else:
                    s = item.split(":")
                    char = find_character(s[0])
                    msg = ":".join(s[1:])

                    if last_char_event and last_char_event == char.id:
                        last_char_event.messages.append(msg)
                    else:
                        last_char_event = CharacterDialogueEvent(
                            type="character", character_id=char.id, messages=[msg]
                        )
                        new_events.append(last_char_event)

        new_events.append(
            SubmitPhotoTaskEvent(type="submit-photo", photo_url=photo_url)
        )
        import_events(json.loads(story_act.raw_post_photo_dialogue))
        if story_act.number == 3:
            new_events.append(EndStoryEvent(type="story-end"))

        return new_events


class GameStoryAct(Base):
    __tablename__ = "game-story-acts"

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(primary_key=True)
    title: sqlalchemy.orm.Mapped[str]
    number: sqlalchemy.orm.Mapped[int]
    is_final_act: sqlalchemy.orm.Mapped[bool]
    overview: sqlalchemy.orm.Mapped[str]
    prologue: sqlalchemy.orm.Mapped[str_list]
    opening_video_url: sqlalchemy.orm.Mapped[str]
    session_id = sqlalchemy.orm.mapped_column(
        sqlalchemy.Uuid, sqlalchemy.ForeignKey(f"{GameSession.__tablename__}.id")
    )
    next_act_id: sqlalchemy.orm.Mapped[typing.Optional[int]] = (
        sqlalchemy.orm.mapped_column(sqlalchemy.ForeignKey("game-story-acts.id"))
    )
    raw_dialogue: sqlalchemy.orm.Mapped[json_scalar]
    photo_requirements: sqlalchemy.orm.Mapped[str_list]
    raw_post_photo_dialogue: sqlalchemy.orm.Mapped[json_scalar]

    next_act: sqlalchemy.orm.Mapped[typing.Optional["GameStoryAct"]] = (
        sqlalchemy.orm.relationship("GameStoryAct")
    )
    session: sqlalchemy.orm.Mapped[GameSession] = sqlalchemy.orm.relationship(
        GameSession, back_populates="acts"
    )
