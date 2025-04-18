import re
import json
import asyncio
import typing
from app.config import Config
from app.models import GameSession, GameStoryAct
from app.logging import logger
from app.gamemaster.llms import llm, GAMEMASTER_BASE_CHARACTER
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
from app.luma import luma_client
from lumaai.types import Generation

_write_act_template_ = """
{base_character}

You will be provided with a brief that lays out the background for the game. From this brief, write a suitable introductory act to introduce the characters and the background. This document is meant to guide writers to develop the story further, so avoid including any detailed character dialogue. The act is also meant to be short, so avoid developing the story too much and focus on simply introducing the world. Write the full specifications, along with providing a proposed title for this act.

If provided with information about the previous act, ensure that this act builds on that story towards any one of the specific endings.
{extra_act_instructions}

In addition, include a small section which includes text meant to open the act for players. This should be a sequence of short sentences, which will be shown to the player like a prologue in films.

Your response should only include the content in strictly JSON format. An example of a response:

```
{ "title": "Act 1", "document": "In this act...", "prologue": ["Once upon a time…", "In a land far, far away"] }
```
"""

_write_dialogue_and_tasks_template_ = """
{base_character}

Your job is to create the specifications for a text based game based on the provided materials. You will be provided with the full project brief from which you will have to write the full dialogue of the experience for the players.

The game is played out like an interactive messaging app. The characters defined in the story are all participants of the chat, and they should chat in a way that fits their personality and background including their mannerisms, emotions, spelling quirks and slang. For example, a string of messages written into the chat app from a character could be defined as:

```
Naomi: First message
Naomi: Second message
Naomi: Third message with emoji 😅
```

These messages should only include the written messages from the sender, however they may also include emojis when appropriate for the character.

Players can also participate in the conversation by responding with one of multiple dialogue options provided. These options allow the player to inject a bit of their personality into the conversation, but it should be inconsequential to the whole story. To denote player messages, start with an asterisk, with each response option separated by asterisks:

```
*: Response option 1 * Response option 2 * Response option 3
```

For this particular task, you will need to develop the dialogue for a single act in the story, in this case, the introductory act which will be used to build up the world and the characters.

The dialogue be long (at least 30 messages) and slowly tends towards one of the possible endings. Most of these messages should be the dialogue between the characters to help develop the story further. Focus on making the interactions between characters natural, with the player occasionally having a chance to jump into the conversation. All characters in the story should be participating in the dialogue.

Towards the end of the dialogue, the player will be asked to take a photo that will help the story progress. As part of the dialogue, the characters should describe the requirements of the photo that is consistent with the characters and the story. The requirements for the photo should be two criteria from the following list:

- Water
- Grass
- Trees
- Walls
- People
- Flowers
- Sky
- Landmarks

Use the last few messages from the characters to explain this requirement as part of the story to the player (a.k.a “Traveller”), as they will be the ones completing this task.

{extra_dialogue_instructions}

After the photo is taken, there will be additional dialogue from the characters. Expand on this dialogue assuming the player (Traveller) has met all of their requirements, and include at least 20 messages, with a bit more participation from the player (Traveller). This additional dialogue has the same format as the normal dialogue.

Return your response in strictly JSON format only. For example:

```
{ "dialogue": ["Lewis: What happened?", "Lewis: Was I too late? 😜", "*: No you're fine * I was waiting for so long!" ], "photo_requirements": ["Flowers", "Walls"], "post_photo_dialogue": ["Naomi: That is a great photo!", "* Thanks\n* Thank you" ] }
```
"""

_full_project_brief_template_ = """
# {project_title}

## Genres
{project_genres}

## Tone
{project_tone}

## World Setting
{project_world_setting}

## Characters
{project_characters_description}

## Current Act Overview
{project_scenario_overview}

## Last Act Overview
{last_act_overview}

## Endings
{project_endings_description}
"""

_write_act_ = (
    ChatPromptTemplate.from_messages(
        [
            SystemMessage(content=_write_act_template_),
            HumanMessage(content=_full_project_brief_template_),
        ]
    )
    | llm
)

_write_dialogue_ = (
    ChatPromptTemplate.from_messages(
        [
            SystemMessage(content=_write_dialogue_and_tasks_template_),
            HumanMessage(content=_full_project_brief_template_),
        ]
    )
    | llm
)


async def generate_game_story_act(
    game_session: GameSession, previous_acts: typing.List[GameStoryAct]
):
    parsed_response: dict
    total_acts = 3
    act_number = 1

    generation: Generation = None

    if Config.stub_text_generation:
        logger.debug("stub text - applying artificial wait")
        await asyncio.sleep(5)

        raw_response = """
    {
    "title": "Speaker's Corner Whispers",
    "document": "# Speaker’s Corner - Dusk\\n\\nThe scene opens at Speaker’s Corner in Hyde Park, just as dusk begins to settle. Evelyn Hart, a passionate activist known for her fiery speeches on women's rights, has just finished addressing a small crowd. She's packing up her notes, looking slightly weary but satisfied.\\n\\nAlex Turner, the musician, is nearby, tuning his guitar and occasionally glancing at Evelyn with an intrigued expression. He’s set up in a less-obvious spot, hoping to observe without being directly involved.\\n\\nNaomi, a young woman who seems perpetually glued to her phone, sits on a bench nearby, ostensibly scrolling through social media but subtly observing the scene. She's connected to a group chat with Evelyn and Alex.\\n\\nDr. Amelia Hartley, a historian specializing in London’s green spaces, is walking past, occasionally pausing to listen to snippets of conversations. She carries a worn leather-bound notebook.\\n\\nThe air is thick with the scent of freshly cut grass and the distant sounds of city life.",
    "dialogue": [
        "Evelyn: (To herself) Another speech done… feels like I barely made a dent, though. 😔",
        "Naomi: Hey Evelyn! Great speech as always 💪",
        "Alex: (Muttering to himself) Powerful stuff. Really powerful.",
        "Dr. Hartley: (To herself, scribbling in her notebook) The energy here… it’s palpable. So much history swirling around.",
        "Naomi: Did you see that guy slip you a note? 🤔",
        "Evelyn: What?! No way! I didn't notice anything...",
        "*: What did the note say? * Who was the guy?",
        "Naomi: He looked kinda shifty. Like he was trying to be sneaky.",
        "Alex: (To Naomi) You’ve got a good eye. People often try to hide things in plain sight.",
        "Evelyn: Okay, you're both creeping me out now! What note? Seriously!",
        "Naomi: Just kidding… mostly 😉",
        "Dr. Hartley: (Approaching Evelyn) Excuse me, I couldn’t help but overhear your speech. It was truly inspiring.",
        "Evelyn: Thank you so much! It's important to keep the conversation going.",
        "Alex: (To himself) Conversation… that’s what this is all about, isn’t it?",
        "Naomi: Guys, I just got a weird message. Someone sent me a photo of Evelyn with a note in her hand!",
        "Evelyn: A photo?! Of *me*? What's on the note?",
        "*: Ask to see the photo * Ignore it.",
        "Naomi: It says… 'Seek the Serpent’s gaze, where shadows play.' 🐍",
        "Alex: (Intrigued) ‘Seek the Serpent’s gaze…’ That sounds like a riddle.",
        "Dr. Hartley: The Serpentine! Of course! A reference to the lake.",
        "Evelyn: Seriously? This is getting ridiculous. I have a life, you know!",
        "Naomi: Calm down, Evelyn! It could be fun… a little mystery?",
        "Alex: (Smiling faintly) Mysteries are always more interesting than routine.",
        "Dr. Hartley: The Serpentine has been central to Hyde Park’s history for centuries. Many secrets lie beneath its surface.",
        "Evelyn: Fine, fine! But if this leads me into some ridiculous treasure hunt, I'm blaming all of you!",
        "Naomi: Okay, so Serpent’s gaze… we need to go to the Serpentine Lake. Let’s do it!",
        "Alex: Lead the way.",
        "Dr. Hartley: (Adjusting her notebook) Fascinating! This could be quite illuminating."
    ],
    "prologue": [
      "Step into the heart of London",
      "Uncover secrets hidden in plain sight.",
      "The whispers of history call you to adventure",
      "At Speaker’s Corner your journey begins.",
      "Listen carefully. The clues are there waiting for you."
     ],
    "photo_requirements": [
        "Water",
        "Walls"
    ],
    "post_photo_dialogue": [
        "Naomi: Okay, that’s amazing! The light reflecting off the water is perfect!",
        "Alex: Really captures the mood. Very atmospheric.",
        "Evelyn: I still think this whole thing is a bit much… but the photo *is* pretty good.",
        "Dr. Hartley: Excellent composition! You've managed to capture both the tranquility and the underlying sense of mystery.",
        "Naomi: The requirements were water and walls, you got them both!",
        "Alex: See? I told you it would be fun.",
        "Evelyn: Alright, alright. So, what now? Do we just… stare at the lake?",
        "Dr. Hartley: Perhaps there's something specific we should be looking for near the Serpentine’s edge... a marker, an inscription...",
        "Naomi: I wonder if it has anything to do with that old Victorian boathouse on the north side? It’s got some pretty interesting stonework.",
        "Alex: The boathouse… yes. That could be significant. Let's check it out.",
        "Evelyn: (Sighing) Fine, but I get to complain the whole time."
    ]
    }
        """
        parsed_response = json.loads(raw_response)
        logger.debug("stub text - DONE")
    else:
        last_act_overview = "N/A"
        extra_dialogue_instructions = ""
        extra_act_instructions = ""
        if len(previous_acts) > 0:
            last_act_overview = previous_acts[0].overview
            extra_dialogue_instructions = f"""
While writing the dialogue for this act, ensure to have some continuity from the dialogue written by the last writer. The dialogue from the previous act can be found below:
Previous dialogue in JSON: ${previous_acts[0].raw_post_photo_dialogue}
            """.strip()

            act_number = previous_acts[0].number + 1
            extra_act_instructions = f"This is act {act_number} of {total_acts}."

            if act_number == total_acts:
                extra_act_instructions = (
                    extra_act_instructions
                    + ". Use this act to bring the story to a conclusion towards one of the endings."
                )
                extra_dialogue_instructions = (
                    extra_dialogue_instructions
                    + "\n\nUse the post photo dialogue to close out the story."
                )
        else:
            extra_act_instructions = "This is the opening act, focus on introducing the world and the characters"
            extra_dialogue_instructions = "As part of the opening act, use the character dialogue to introduce the player (Traveller) to the world of the story"

        raw_response = await _write_act_.ainvoke(
            {
                "extra_act_instructions": extra_act_instructions,
                "base_character": GAMEMASTER_BASE_CHARACTER,
                "project_title": game_session.title,
                "project_genres": ", ".join(game_session.genres),
                "project_tone": game_session.tone,
                "project_world_setting": game_session.world_setting,
                "project_characters_description": "\n\n".join(
                    list(
                        map(
                            lambda c: f"Name: {c.name}\nPersonality: {c.personality}\nBackground: {c.background}\n",
                            game_session.characters,
                        )
                    )
                ),
                "last_act_overview": last_act_overview,
                "project_scenario_overview": game_session.scenario_overview,
                "project_endings_description": "\n\n".join(
                    list(
                        map(
                            lambda e: f"Name: {e.name}\nText: {e.text}\nDetail:\n```\n{e.detail}\n```",
                            game_session.possible_endings,
                        )
                    )
                ),
            }
        )
        parsed_response = clean_and_parse_json(raw_response.content)

        if not Config.stub_video_generation:
            camera_option = "camera dolly zoom"
            generation = await luma_client.generations.create(
                aspect_ratio="3:4",
                model="ray-flash-2",
                prompt=f"""
Generate a 30 second video suitable for a movie trailer, based on the following synopsis: {parsed_response["document"]}


Incorporate the following themes: hyper-realism, {", ".join(game_session.genres)}


The overal tone of the video should be: {game_session.tone}

The end of the video should slowly fade to black.

{camera_option}
                """,
            )

        raw_dialogue_response = await _write_dialogue_.ainvoke(
            {
                "base_character": GAMEMASTER_BASE_CHARACTER,
                "project_title": game_session.title,
                "project_genres": ", ".join(game_session.genres),
                "project_tone": game_session.tone,
                "project_world_setting": game_session.world_setting,
                "project_characters_description": "\n\n".join(
                    list(
                        map(
                            lambda c: f"Name: {c.name}\nPersonality: {c.personality}\nBackground: {c.background}\n",
                            game_session.characters,
                        )
                    )
                ),
                "extra_dialogue_instructions": extra_dialogue_instructions,
                "last_act_overview": last_act_overview,
                "project_scenario_overview": parsed_response["document"],
                "project_endings_description": "\n\n".join(
                    list(
                        map(
                            lambda e: f"Name: {e.name}\nText: {e.text}\nDetail:\n```\n{e.detail}\n```",
                            game_session.possible_endings,
                        )
                    )
                ),
            }
        )

        parsed_response = parsed_response | clean_and_parse_json(
            raw_dialogue_response.content
        )

    new_act = GameStoryAct()

    if Config.stub_video_generation:
        logger.debug("stub video - performing artificial wait")
        await asyncio.sleep(8)
        new_act.opening_video_url = "http://localhost:3000/videos/test.mp4"
        logger.debug("stub video - DONE")
    else:
        completed = False
        while not completed:
            logger.debug("checking video")
            gen = await luma_client.generations.get(id=generation.id)
            if gen.state == "completed":
                logger.debug("video ready")
                completed = True
                new_act.opening_video_url = gen.assets.video
            elif gen.state == "failed":
                raise RuntimeError(f"Generation failed: {gen.failure_reason}")
            await asyncio.sleep(3)

    new_act.title = parsed_response["title"]
    new_act.number = act_number
    new_act.is_final_act = act_number == total_acts
    new_act.overview = parsed_response["document"]
    new_act.prologue = parsed_response["prologue"]
    new_act.raw_dialogue = json.dumps(parsed_response["dialogue"])
    new_act.photo_requirements = parsed_response["photo_requirements"]
    new_act.raw_post_photo_dialogue = json.dumps(parsed_response["post_photo_dialogue"])

    return new_act


reg1 = re.compile(r"^`\.+$")
reg2 = re.compile(r"")


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
