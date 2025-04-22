import uuid
import json
import random
import asyncio
import sqlalchemy
import sqlalchemy.orm
import app.models
from urllib.parse import quote
from app.gamemaster.llms import GAMEMASTER_BASE_CHARACTER
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mistralai import ChatMistralAI
from app.config import Config
from app.luma import luma_client
from app.gamemaster.llms import llm as fast_llm
from app.gamemaster.utils import clean_and_parse_json
from app.database import connection as conn

llm = ChatMistralAI(
    model_name="mistral-large-latest",
    temperature=0.3,
    api_key=Config.mistral_api_key,
)

session_key = uuid.uuid4()

d: dict
if Config.stub_text_generation:
    with open("./tests/example_gen.json", "r") as file:
        d = json.load(file)
else:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
{base_character}

You will be provided with text that will serve as the reference material for your next story. This material will have historical and cultural significance.

Your story should centre around a main character. Give details of this main character, including a detailed breakdown of their personality and background. The short story should revolve around the main character, illustrating a particularly challenging day in their day-to-day routine in the context of the story setting. Also, introduce a small cast of supporting characters (maximum of 2) who appears in the story.

In addition to the synopsis for the main story, also write two detailed synopsis for different sections of the story. Adhering to the three-act story framework, write details of the setup and confrontation acts only. Rely heavily on the reference material and the background of the main character while writing these acts, while also injecting a little bit of fantasy to make the story interesting.

Finally, include a short prologue built from the synopsis to introduce your story. The prologue should be broken into multiple short lines, fed to the player one at a time, similar to movie openings.

Remember to base your story around the reference material provided. Also extract the key historical and cultural details from this reference material and highlight them in your response.

Your response should only include the content in JSON. The structure of the response should follow this example:

```
{{ "title": "Act 1", "reference_material_summary": "A summary of the original reference material provided", "synopsis": "A short synopsis introducing the world", "themes": ["nature", "culture", "history"], "main_character": {{ "name": "Mr John Doe", "personality": "A quiet businessman", "background": "Mr John Doe’s detailed background" }}, "supporting_characters": [{{ "name": "Dr Watson", "personality": "Dr Watson’s personality in detail", "background": "Dr Watson’s background" }}, {{ "name": "Mrs Demure", "personality": "Friendly old lady", "background": "Owner and head chef of the neighbourhood bakery" }}], "setup_act": "detailed synopsis of the first act", "confrontation_act": "detailed synopsis of the second act", "prologue": ["Once upon a time…", "In a land far far away…"] }}
```
```
    """,
            ),
            ("human", "{reference_material}"),
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
            "is_main_character": False,
        },
        enumerate(d["supporting_characters"]),
    )
)

characters.append(
    d["main_character"]
    | {
        "id": 0,
        "profile_image_url": f"https://placehold.co/400?text={quote(d["main_character"]["name"])}",
        "is_main_character": True,
    }
)

game_session = app.models.GameSession()
game_session.visual_style = random.choice(
    [
        # "hyper-realism",
        "comics, halftone",
        "egyptian, mythology, greek",
        "animation, cartoon",
        "cgi, mysterious",
    ]
)
game_session.id = session_key
game_session.title = d["title"]
game_session.themes = d["themes"]
game_session.synopsis = d["synopsis"]
game_session.opening_video_url = "http://localhost:3000/videos/test.mp4"
game_session.opening_act_synopsis = d["setup_act"]
game_session.middle_act_synopsis = d["confrontation_act"]
game_session.prologue = d["prologue"]
game_session.promo_image_url = (
    f"https://placehold.co/600x400?text={quote("Promo Image")}"
)
game_session.total_actions = 8
game_session.remaining_actions = game_session.total_actions
game_session.reference_material_summary = d["reference_material_summary"]

# if not Config.stub_image_generation:

#     async def gen_character_profile_image(char: dict) -> str:
#         print("start char gen for", char["name"])
#         generation = await luma_client.generations.image.create(
#             prompt=f"""
# Create a social media profile picture of a character facing the camera.

# The image should have the following themes: {", ".join(d["themes"])}

# Use the following styles: {game_session.visual_style}

# The character has the following description:

# ## Background
# {char["background"]}

# ## Personality
# {char["personality"]}
#             """,
#             aspect_ratio="1:1",
#         )

#         completed = False
#         while not completed:
#             print("checking: ", char["name"])
#             gen = await luma_client.generations.get(id=generation.id)
#             if gen.state == "completed":
#                 print("IMAGE READY: ", char["name"])
#                 return gen.assets.image
#             elif gen.state == "failed":
#                 raise RuntimeError(f"Generation failed: {gen.failure_reason}")

#             await asyncio.sleep(3)
#         pass

#     async def gen_characters_image(chars: list[dict]) -> list[str]:
#         jobs = [gen_character_profile_image(char) for char in chars]
#         return await asyncio.gather(*jobs)

#     images = asyncio.run(gen_characters_image(characters))

#     for i, char in enumerate(characters):
#         char["profile_image_url"] = images[i]

if not Config.stub_video_generation:

    async def gen_video() -> tuple[str, str]:
        simple_chain = (
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
## Synopsis
{synopsis}

## Reference material
{reference_material}
""",
                    ),
                ]
            )
            | fast_llm
        )

        response = await simple_chain.ainvoke(
            {
                "base_character": "You are a helpful video director",
                "synopsis": game_session.synopsis,
                "reference_material": game_session.reference_material_summary,
            }
        )

        print("start video gen")
        generation = await luma_client.generations.create(
            model="ray-2",
            prompt=f"""
Using the following visual styles: {game_session.visual_style}

Generate a video using the following description:
{response.content}
""",
            loop=True,
        )

        completed = False
        while not completed:
            print("checking video")
            gen = await luma_client.generations.get(id=generation.id)
            if gen.state == "completed":
                print("end video gen")
                return (gen.assets.video, gen.assets.image)
            elif gen.state == "failed":
                raise RuntimeError(f"Generation failed: {gen.failure_reason}")

            await asyncio.sleep(3)
        pass

    (video_url, image_url) = asyncio.run(gen_video())
    game_session.opening_video_url = video_url
    game_session.promo_image_url = image_url

game_session.raw_characters = json.dumps(characters)

brief = f"""
# {game_session.title}

## Reference
{game_session.reference_material_summary}

## Themes
{", ".join(game_session.themes)}

## Synopsis
{game_session.synopsis}

### Act 1
{game_session.opening_act_synopsis}

### Act 2
{game_session.middle_act_synopsis}

## Characters
{"\n\n".join(list(map(lambda c: f"Name: {c.name}\nPersonality: {c.personality}\nBackground: {c.background}\n", game_session.characters)))}
"""

print(brief)

with sqlalchemy.orm.Session(conn) as session:
    session.add_all([game_session])
    session.commit()
    print("CREATED", game_session.id)
