import uuid
import json
import asyncio
import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.engine
import app.models
from urllib.parse import quote
from app.gamemaster.llms import GAMEMASTER_BASE_CHARACTER
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mistralai import ChatMistralAI
from app.config import Config
from app.luma import luma_client

llm = ChatMistralAI(
    model_name="mistral-large-latest",
    temperature=0.8,
    api_key=Config.mistral_api_key,
)


def clean_and_parse_json(llm_response: str) -> dict:
    lines = llm_response.splitlines()
    if lines[0].startswith("`"):
        lines = lines[1:]
    if lines[-1].startswith("`"):
        lines = lines[:-1]
    print("TEST")
    print("\n".join(lines))
    print("TEST")
    return json.loads("\n".join(lines))


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
conn = engine.connect()

session_key = uuid.uuid4()

d: dict
if Config.stub_text_generation:
    with open("./example_gen.json", "r") as file:
        d = json.load(file)
else:
    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessage(
                content="""
{base_character}

You will be provided reference material for the project, which you must base
your story on. Based on this brief, write a detailed
design document for the background of the immersive story. Include details of the
genre of the story, expand on the chosen background and world setting.

For the world setting, while drawing inspiration from the reference material,
mix it with popular fictional genres, from either Fantasy, Steampunk, Medieval,
Futuristic, Dystopian or Espionage.

Be sure to include details of the locations present in the world that would be important
to the story, whether real or fantasy. Also for the purpose of the story, include
a detailed set of characters who will be a part of the story and a brief
overview of the scenario that will be played out during the experience.

Be sure to make every character unique and have their own personality. We want
a diverse cast that represents every popular character archetype in the
fictional universe. Since this is a text driven story, be sure to include
information about how each character might converse in text, including any
quirks in their behaviour, slangs or mannerisms that they might adopt. Include
these descriptions as part of their personality.

Also include multiple options for possible endings which has at least one good
ending, one bad ending and then some options in between. For each ending, give a
rough explanation of the types of choices that would lead players to this
ending. Also include a secret ending, which will be difficult to unlock.

In your response, include only the full brief in JSON and no other commentary.
Use the following structure:

```
{{ "title": "Title of the experience", "genres": ["history", "mystery", "fantasy", "steampunk"], "tone": "detailed explanation of the tone", "world_setting": "detailed explanation of the world setting", "characters": [{{ "name": "Marcus", "personality": "detailed personality", "background": "detailed background" }}], "scenario_overview": "detailed overall storyline", "possible_endings": [{{} "name": "Ending 1", "text": "And they lived happily ever after", "detail": "detail and criteria for ending 1" }}, {{ "name": "Ending 2", "text": "Fate would never let them be together", "detail": "detail and criteria of ending 2" }}] }}
```
    """
            ),
            HumanMessage(content="# Reference Material\n\n{reference_material}"),
        ]
    )

    chain = prompt | llm

    print("start prompt gen")
    response = chain.invoke(
        {
            "base_character": GAMEMASTER_BASE_CHARACTER,
            "reference_material": """
This is the most royal of London’s Royal Parks. Shaped by generations of monarchs and bordered by three royal palaces, St. James’s Park is the home of ceremonial events in the capital. From royal weddings and jubilees to military parades and state celebrations – this is the park where history is made. Come and explore it for yourself…

There’s always something to see here - from soldiers in scarlet tunics marching down The Mall to bright beds of flowers bursting with blooms. Don’t miss the classic London views from the lake, where you should also keep an eye out for the famous pelicans who call the park home. Did you know that pelicans have been kept at the park since 1664, when a Russian ambassador presented them to King Charles II? You can often find them perched on benches by the lake, graciously greeting visitors from around the world.  

You’ll spot many famous landmarks in St. James’s Park – from sweeping Admiralty Arch to the ceremonial hotspot Horse Guards Parade. And then of course there’s Buckingham Palace – head down The Mall for that world-famous view! Among the park’s diverse statues, you’ll encounter the statue of Queen Elizabeth the Queen Mother, adorned in a resplendent, flamboyant plumed hat, a testament to regal elegance. Nearby, the simple yet poignant white marble Boy Statue invites reflection, adding a touch of innocence and contemplation to the park’s ambiance.

If you’re looking to get away from the crowds, wander along the peaceful lakeside path where you can admire the spectacular trees and abundance of colourful waterbirds. There’s always something new to discover in this historic landscape – from spring bulbs to autumn colours.  
            """,
        }
    )

    print(response.content)

    d = clean_and_parse_json(response.content)

characters: list[dict] = list(
    map(
        lambda x: x[1]
        | {
            "id": 1 + x[0],
            "profile_image_url": f"https://placehold.co/400?text={quote(x[1]["name"])}",
        },
        enumerate(d["characters"]),
    )
)

if not Config.stub_image_generation:

    async def gen_character_profile_image(char: dict) -> str:
        print("start char gen for", char["name"])
        generation = await luma_client.generations.image.create(
            prompt=f"""
Create a hyper-realistic social media profile picture of a character facing the camera.

The image should have the following themes: {", ".join(d["genres"])}

The character has the following description:

## Background
{char["background"]}

## Personality
{char["personality"]}
            """,
            aspect_ratio="1:1",
        )

        completed = False
        while not completed:
            print("checking: ", char["name"])
            gen = await luma_client.generations.get(id=generation.id)
            if gen.state == "completed":
                print("IMAGE READY: ", char["name"])
                return gen.assets.image
            elif gen.state == "failed":
                raise RuntimeError(f"Generation failed: {gen.failure_reason}")

            await asyncio.sleep(3)
        pass

    async def gen_characters_image(chars: list[dict]) -> list[str]:
        jobs = [gen_character_profile_image(char) for char in chars]
        return await asyncio.gather(*jobs)

    images = asyncio.run(gen_characters_image(characters))

    for i, char in enumerate(characters):
        char["profile_image_url"] = images[i]

game_session = app.models.GameSession()
game_session.id = session_key
game_session.title = d["title"]
game_session.genres = d["genres"]
game_session.tone = d["tone"]
game_session.choices = []
game_session.current_event_index = 0
game_session.world_setting = d["world_setting"]
game_session.raw_events = "[]"
game_session.raw_characters = json.dumps(characters)
game_session.scenario_overview = d["scenario_overview"]
game_session.raw_possible_endings = json.dumps(d["possible_endings"])

brief = f"""
# {game_session.title}

## Genres
{', '.join(game_session.genres)}

## Tone
{game_session.tone}

## World Setting
{game_session.world_setting}

## Characters
{"\n\n".join(list(map(lambda c: f"Name: {c.name}\nPersonality: {c.personality}\nBackground: {c.background}\n", game_session.characters)))}

## Scenario Overview
{game_session.scenario_overview}

{"\n\n".join(list(map(lambda e: f"Name: {e.name}\nText: {e.text}\nDetail:\n```\n{e.detail}\n```", game_session.possible_endings)))}
"""

print(brief)

with sqlalchemy.orm.Session(conn) as session:
    session.add_all([game_session])
    session.commit()

    print("CREATED", game_session.id)
