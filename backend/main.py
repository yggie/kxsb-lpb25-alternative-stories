import time
import asyncio
import typing
import strawberry
import sqlalchemy
import app.models as appmodels
from enum import Enum
from urllib.parse import quote
from app.config import Config
from fastapi import FastAPI, WebSocket
from app.gamemaster.llms import llm
from langchain_core.prompts import ChatPromptTemplate
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter
from sqlalchemy.orm import Session
from app.database import connection
from app.logging import logger
from app.gamemaster.generate_next_story_block import (
    generate_next_story_block,
    TextAction,
    PhotoAction,
)

from app.luma import luma_client
import lumaai.types


@strawberry.type
class GameStoryBlock:
    id: int
    number: int
    is_final_act: bool
    dialogue: typing.List[str]
    previous_action: typing.Optional[str]
    backdrop_image_url: typing.Optional[str]
    possible_actions: typing.List[str]
    actions_consumed: int

    @staticmethod
    def from_data(block: appmodels.GameStoryBlock):
        previous_action = block.previous_action
        if previous_action == "":
            previous_action = None

        return GameStoryBlock(
            id=block.id,
            number=block.number,
            is_final_act=block.is_final_act,
            dialogue=block.dialogue,
            actions_consumed=block.actions_consumed,
            backdrop_image_url=block.backdrop_image_url,
            possible_actions=block.possible_actions,
            previous_action=previous_action,
        )


@strawberry.type
class Character:
    id: int
    name: str
    background: str
    profile_photo_url: str

    @staticmethod
    def from_data(character: appmodels.Character):
        return Character(
            id=character.id,
            name=character.name,
            background=character.background,
            profile_photo_url=character.profile_image_url,
        )


@strawberry.type
class GameSession:
    id: str
    title: str
    themes: typing.List[str]
    synopsis: str
    prologue: typing.List[str]
    characters: typing.List[Character]
    story_blocks: typing.List[GameStoryBlock]
    promo_image_url: str
    opening_video_url: str
    final_video_url: typing.Optional[str]
    total_actions: int

    def from_data(game_session: appmodels.GameSession):
        return GameSession(
            id=game_session.id,
            title=game_session.title,
            themes=game_session.themes,
            synopsis=game_session.synopsis,
            prologue=game_session.prologue,
            promo_image_url=game_session.promo_image_url,
            characters=list(
                map(
                    Character.from_data,
                    game_session.characters,
                )
            ),
            story_blocks=list(map(GameStoryBlock.from_data, game_session.story_blocks)),
            opening_video_url=game_session.opening_video_url,
            total_actions=game_session.total_actions,
            final_video_url=game_session.final_video_url,
        )


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
    def available_games() -> typing.List[GameSession]:
        with Session(connection) as session:
            statement = sqlalchemy.select(appmodels.GameSession).limit(100)

            game_sessions = session.scalars(statement).all()

            return list(map(GameSession.from_data, game_sessions))

    @strawberry.field
    def game(id: str) -> typing.Optional[GameSession]:
        with Session(connection) as session:
            statement = (
                sqlalchemy.select(appmodels.GameSession)
                .where(appmodels.GameSession.id == id)
                .limit(1)
            )

            game_session = session.scalars(statement).one()

            return GameSession.from_data(game_session)

    @strawberry.field
    async def debug_list_generations(page: int, per_page: int) -> LumaGenerations:
        if not Config.debug:
            raise Exception("not available")

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
    def reset(self, id: str) -> str:
        with Session(connection) as session:
            statement = (
                sqlalchemy.select(appmodels.GameSession)
                .where(appmodels.GameSession.id == id)
                .limit(1)
            )
            game_session = session.scalars(statement).one()
            game_session.story_blocks = []
            del_statement = sqlalchemy.delete(appmodels.GameStoryBlock).where(
                appmodels.GameStoryBlock.session_id == id
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
            case "start-game":
                asyncio.create_task(start_game_session(key, websocket))
                continue

            case "submit-photo":
                asyncio.create_task(submit_photo(key, websocket, data["url"]))
                continue

            case "take-action":
                asyncio.create_task(submit_action(key, websocket, data["action"]))
                continue

            case _:
                print("unexpected data", data)
                continue


async def start_game_session(key: str, ws: WebSocket):
    await _generic_action(key, ws, "", "")


async def submit_action(key: str, ws: WebSocket, action: str):
    await _generic_action(key, ws, action, "")


async def submit_photo(key: str, ws: WebSocket, photo_url: str):
    await _generic_action(key, ws, "", photo_url)


async def _generic_action(key: str, ws: WebSocket, action: str, photo_url: str):
    try:
        await _generic_action_inner(key, ws, action, photo_url)
    except Exception as e:
        logger.error(e)
        await ws.send_json({"type": "error", "message": "something went wrong"})


async def _generic_action_inner(key: str, ws: WebSocket, action: str, photo_url: str):
    print("ATTEMPT")
    print(action)
    print(photo_url)
    with Session(connection) as session:
        statement = (
            sqlalchemy.select(appmodels.GameSession)
            .where(appmodels.GameSession.id == key)
            .limit(1)
        )
        game_session = session.scalars(statement).one()

        if action == "" and photo_url == "" and len(game_session.story_blocks) > 0:
            logger.debug("skipping start game session - game already started")
            await ws.send_json({"type": "error", "message": "game already started"})
            return

        await ws.send_json({"type": "updated"})

        action_obj = TextAction(text="")
        if action != "":
            action_obj = TextAction(text=action)
        elif photo_url != "":
            action_obj = PhotoAction(url=photo_url)

        next_block = await generate_next_story_block(
            game_session=game_session, action=action_obj
        )

        game_session = session.scalars(statement).one()
        game_session.story_blocks.append(next_block)

        session.add_all([game_session])
        session.commit()

        await ws.send_json({"type": "updated"})

        await _update_photo(session, ws, game_session, next_block)


async def _update_photo(
    session: Session,
    ws: WebSocket,
    game: appmodels.GameSession,
    story_block: appmodels.GameStoryBlock,
):
    if Config.stub_image_generation:
        logger.debug("stub image - performing artificial wait")
        await asyncio.sleep(3)
        story_block.backdrop_image_url = (
            f"https://placehold.co/400?text={quote("backdrop image URL")}"
        )
        logger.debug("stub image - DONE")
    else:
        generation = await luma_client.generations.image.create(
            prompt=f"""
Using the visual styles: {game.visual_style}

Without including any text in the art, generate artwork for a novel inspired by the following dialogue:

{"\n- ".join(story_block.dialogue)}
""",
            aspect_ratio="3:4",
        )
        completed = False
        while not completed:
            logger.debug("checking video")
            gen = await luma_client.generations.get(id=generation.id)
            if gen.state == "completed":
                logger.debug("image ready")
                completed = True
                story_block.backdrop_image_url = gen.assets.image
            elif gen.state == "failed":
                raise RuntimeError(f"Generation failed: {gen.failure_reason}")
            await asyncio.sleep(2)

    session.add_all([story_block])
    session.commit()

    await ws.send_json({"type": "updated"})

    if story_block.is_final_act:
        await _create_final_video(session, ws, game)


async def _create_final_video(
    session: Session,
    ws: WebSocket,
    game: appmodels.GameSession,
):
    blocks = sorted(game.story_blocks, key=lambda b: b.number)

    story_block_chain = (
        ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
{base_character}

You will be provided with a synopsis for a short story, along with the reference
material that influences the story. Use the synopsis to generate a video, and
use the reference material to generate the video background, mood and setting.

From this information, describe a video scene that would be suitable as a
trailer for the short story in detail, going into detail on how the scene is
laid out, who is in the foreground and the camera movements or scene
transitions.

Keep this description succinct and no longer than 1 paragraph.
""",
                ),
                (
                    "human",
                    """
## Reference Material
{reference_material}

## Synopsis
{synopsis}

## Story Events
{story_events}
""",
                ),
            ]
        )
        | llm
    )

    previous_generation = None
    video_url = ""
    for block in blocks:
        keyframes = {}
        if previous_generation is not None:
            keyframes["frame0"] = {
                "type": "generation",
                "id": previous_generation.id,
            }

        story_block_response = await story_block_chain.ainvoke(
            {
                "base_character": "You are a helpful video director",
                "synopsis": game.synopsis,
                "reference_material": game.reference_material_summary,
                "story_events": "\n- ".join(block.dialogue),
            }
        )

        print(f"generating final video, frame {block.number} of {game.total_actions}")
        print(story_block_response.content)
        generation = await luma_client.generations.create(
            model="ray-flash-2",
            prompt=f"""
Using the visual style: {game.visual_style}

Generate a video using the following description:
{story_block_response.content}
""",
        )

        completed = False
        while not completed:
            print(f"checking video {block.number} of {game.total_actions}")
            gen = await luma_client.generations.get(id=generation.id)
            if gen.state == "completed":
                print("end video gen")
                video_url = gen.assets.video
                break
            elif gen.state == "failed":
                raise RuntimeError(f"Generation failed: {gen.failure_reason}")

            await asyncio.sleep(3)

        previous_generation = generation

    game.final_video_url = video_url

    session.add_all([game])
    session.commit()

    print("video done")

    await ws.send_json({"type": "updated"})
