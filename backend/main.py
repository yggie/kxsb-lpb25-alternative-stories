import asyncio
import typing
import strawberry
import sqlalchemy
import app.models as appmodels
from enum import Enum
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter
from sqlalchemy.orm import Session
from app.models import connection
from app.logging import logger
from app.gamemaster.generate_game_story_act import generate_game_story_act
from app.luma import luma_client
import lumaai.types


@strawberry.type
class SubmitPhotoEvent:
    photo_url: str


@strawberry.type
class ShowStoryPrologueEvent:
    lines: typing.List[str]


@strawberry.type
class ShowVideoEvent:
    video_url: str


@strawberry.type
class WritingNewStoryActEvent:
    status: bool


@strawberry.type
class NewStoryActEvent:
    story_act_id: int


@strawberry.type
class PlayerNewDialogueOptionsEvent:
    options: typing.List[str]


@strawberry.type
class CharacterDialogueEvent:
    character_id: int
    messages: typing.List[str]


@strawberry.type
class PlayerPhotoTaskEvent:
    requirements: typing.List[str]


GameSessionEvent = typing.Union[
    CharacterDialogueEvent,
    PlayerPhotoTaskEvent,
    PlayerNewDialogueOptionsEvent,
    NewStoryActEvent,
    WritingNewStoryActEvent,
    ShowVideoEvent,
    ShowStoryPrologueEvent,
    SubmitPhotoEvent,
]


@strawberry.type
class Character:
    id: int
    name: str
    profile_photo_url: str

    @staticmethod
    def from_data(character: appmodels.Character):
        return Character(
            id=character.id,
            name=character.name,
            profile_photo_url=character.profile_image_url,
        )


@strawberry.type
class GameSession:
    session_key: str
    title: str
    events: typing.List[GameSessionEvent]
    characters: typing.List[Character]


@strawberry.type
class GameCommand:
    title: str


@strawberry.type
class LumaGenRequest:
    generation_type: str
    prompt: str
    aspect_ratio: str
    loop: bool
    model: str
    resolution: typing.Optional[str]
    duration: typing.Optional[str]


@strawberry.type
class LumaGenImageRequest:
    generation_type: str
    prompt: str
    aspect_ratio: str
    model: str


@strawberry.type
class LumaGenUpscaleVidRequest:
    generation_type: str
    resolution: typing.Optional[str]


@strawberry.enum
class LumaAssetType(Enum):
    VIDEO = "video"
    IMAGE = "image"
    PROGRESS_VIDEO = "progress_video"


@strawberry.type
class LumaGenAudioRequest:
    generation_type: str
    prompt: str
    negative_prompt: str


LumaRequest = typing.Union[
    LumaGenRequest, LumaGenImageRequest, LumaGenUpscaleVidRequest, LumaGenAudioRequest
]


@strawberry.type
class LumaGenAsset:
    type: LumaAssetType
    url: str


@strawberry.type
class LumaGeneration:
    id: str
    state: str
    generation_type: str
    model: str
    assets: typing.List[LumaGenAsset]
    request: LumaRequest


@strawberry.type
class LumaGenerations:
    count: int
    limit: int
    offset: int
    has_more: int
    generations: typing.List[LumaGeneration]


@strawberry.type
class Query:
    @strawberry.field
    def current_session(session_key: str) -> typing.Optional[GameSession]:
        with Session(connection) as session:
            statement = (
                sqlalchemy.select(appmodels.GameSession)
                .where(appmodels.GameSession.id == session_key)
                .limit(1)
            )

            game_session = session.scalars(statement).one()

            def serialize_event(ev: appmodels.GameSessionEvent):
                match ev.type:
                    case "character":
                        return CharacterDialogueEvent(
                            character_id=ev.character_id, messages=ev.messages
                        )

                    case "new-act":
                        return NewStoryActEvent(story_act_id=ev.story_act_id)

                    case "player-options":
                        return PlayerNewDialogueOptionsEvent(options=ev.options)

                    case "player-photo-task":
                        return PlayerPhotoTaskEvent(requirements=ev.requirements)

                    case "writing-next-act":
                        return WritingNewStoryActEvent(status=True)

                    case "video":
                        return ShowVideoEvent(video_url=ev.video_url)

                    case "story-prologue":
                        return ShowStoryPrologueEvent(lines=ev.lines)

                    case "submit-photo":
                        return SubmitPhotoEvent(photo_url=ev.photo_url)

            return GameSession(
                session_key=game_session.id,
                title=game_session.title,
                events=list(map(serialize_event, game_session.events)),
                characters=list(
                    map(
                        Character.from_data,
                        game_session.characters,
                    )
                ),
            )

        return None

    @strawberry.field
    async def debug_list_generations(page: int, per_page: int) -> LumaGenerations:
        generation = await luma_client.generations.list(
            limit=per_page, offset=(per_page * (page - 1))
        )

        def map_generation(gen: lumaai.types.Generation) -> LumaGeneration:
            req: LumaRequest
            match gen.request.generation_type:
                case "add_audio":
                    req = LumaGenAudioRequest(
                        generation_type=gen.generation_type,
                        prompt=gen.request.prompt,
                        negative_prompt=gen.request.negative_prompt,
                    )

                case "image":
                    req = LumaGenImageRequest(
                        generation_type=gen.generation_type,
                        model=gen.request.model,
                        prompt=gen.request.prompt,
                        aspect_ratio=gen.request.aspect_ratio,
                    )

                case "upscale_video":
                    req = LumaGenUpscaleVidRequest(
                        generation_type=gen.generation_type,
                        resolution=gen.request.resolution,
                    )

                case "video":
                    req = LumaGenRequest(
                        generation_type=gen.generation_type,
                        prompt=gen.request.prompt,
                        aspect_ratio=gen.request.aspect_ratio,
                        loop=gen.request.loop,
                        model=gen.request.model,
                        resolution=gen.request.resolution,
                        duration=gen.request.duration,
                    )

            def map_asset(asset: tuple[str, str]) -> LumaGenAsset:
                return LumaGenAsset(
                    type=asset[0],
                    url=asset[1],
                )

            return LumaGeneration(
                id=gen.id,
                state=gen.state,
                generation_type=gen.generation_type,
                model=gen.model,
                assets=filter(
                    lambda a: a.url != None, list(map(map_asset, gen.assets))
                ),
                request=req,
            )

        return LumaGenerations(
            count=generation.count,
            limit=generation.limit,
            has_more=generation.has_more,
            offset=generation.offset,
            generations=list(map(map_generation, generation.generations)),
        )


@strawberry.enum
class CommandType(Enum):
    START = "start"
    PICK_OPTION = "pick-option"


@strawberry.type
class Mutation:
    @strawberry.mutation
    def reset(self, session_key: str) -> str:
        with Session(connection) as session:
            statement = (
                sqlalchemy.select(appmodels.GameSession)
                .where(appmodels.GameSession.id == session_key)
                .limit(1)
            )
            game_session = session.scalars(statement).one()
            game_session.raw_events = "[]"
            del_statement = sqlalchemy.delete(appmodels.GameStoryAct).where(
                appmodels.GameStoryAct.session_id == session_key
            )
            session.execute(del_statement)
            session.add_all([game_session])
            session.commit()

            logger.debug("cleared game session")

            return "success"


schema = strawberry.Schema(query=Query, mutation=Mutation)

graphql_app = GraphQLRouter(schema)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graphql_app, prefix="/graphql")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, key: str | None = None):
    if key is None:
        websocket.close(401, "missing session key")
        return

    with Session(connection) as session:
        statement = (
            sqlalchemy.select(appmodels.GameSession)
            .where(appmodels.GameSession.id == key)
            .limit(1)
        )
        session.scalars(statement).one()

    await websocket.accept()
    while True:
        data = await websocket.receive_json()

        match data["type"]:
            case "start":
                asyncio.create_task(start_game_session(key, websocket))
                continue

            case "submit-photo":
                asyncio.create_task(submit_photo(key, websocket, data["photo_url"]))
                continue

            case _:
                print("unexpected data", data)
                continue


async def start_game_session(key: str, ws: WebSocket):
    with Session(connection) as session:
        statement = (
            sqlalchemy.select(appmodels.GameSession)
            .where(appmodels.GameSession.id == key)
            .limit(1)
        )
        game_session = session.scalars(statement).one()

        if len(game_session.events) > 0:
            logger.debug("skipping start game session - writing already in progress")
            await ws.send_json({"type": "error", "message": "writing in progress"})
            return

        game_session.write_events(
            game_session.events + game_session.load_writing_event()
        )

        session.add_all([game_session])
        session.commit()

        await ws.send_json({"type": "updated"})

        next_act = await generate_game_story_act(
            game_session=game_session, previous_acts=[]
        )

        game_session = session.scalars(statement).one()
        game_session.acts.append(next_act)

        session.add_all([game_session])
        session.commit()

        new_events = game_session.load_prephoto_events(next_act)
        game_session.write_events(game_session.events + new_events)

        session.add_all([game_session])
        session.commit()

        await ws.send_json({"type": "updated"})


async def submit_photo(key: str, ws: WebSocket, photo_url: str):
    with Session(connection) as session:
        statement = (
            sqlalchemy.select(appmodels.GameSession)
            .where(appmodels.GameSession.id == key)
            .limit(1)
        )
        game_session = session.scalars(statement).one()

        if (
            len(game_session.events) > 0
            and game_session.events[-1].type != "player-photo-task"
        ):
            logger.debug("submitted photo when it wasn't expected")
            await ws.send_json({"type": "error", "message": "invalid operation"})
            return

        statement2 = (
            sqlalchemy.select(appmodels.GameStoryAct)
            .where(
                appmodels.GameStoryAct.session_id == key
                and appmodels.GameStoryAct.next_act_id == None
            )
            .limit(1)
        )
        previous_act = session.scalars(statement2).one()

        game_session.write_events(
            game_session.events
            + game_session.load_postphoto_events(previous_act, photo_url=photo_url)
            + game_session.load_writing_event()
        )

        session.add_all([game_session])
        session.commit()

        await ws.send_json({"type": "updated"})

        game_session = session.scalars(statement).one()

        next_act = await generate_game_story_act(
            game_session=game_session, previous_acts=[previous_act]
        )
        game_session.acts.append(next_act)

        session.add_all([game_session])
        session.commit()

        game_session = session.scalars(statement).one()
        previous_act.next_act_id = next_act.id
        game_session.write_events(
            game_session.events + game_session.load_prephoto_events(next_act)
        )

        session.add_all([game_session, previous_act])
        session.commit()

        await ws.send_json({"type": "updated"})
