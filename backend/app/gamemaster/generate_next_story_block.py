import re
import json
import asyncio
import typing
from functools import reduce
from dataclasses import dataclass
from urllib.parse import quote
from app.config import Config
from app.models import GameSession, GameStoryBlock
from app.logging import logger
from app.gamemaster.llms import llm, GAMEMASTER_BASE_CHARACTER
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
from app.luma import luma_client
from app.gamemaster.utils import clean_and_parse_json
from lumaai.types import Generation
from langchain_mistralai import ChatMistralAI
from mistralai import Mistral

_INTRO_BLOCKS_ = 1
_CLOSING_BLOCKS_ = 2

is_mistral = isinstance(llm, ChatMistralAI)

mistral_client = Mistral(api_key=Config.mistral_api_key)

_write_final_act_synopsis_ = """
{base_character}

You are tasked with writing the synopsis for the final act of a short story.

You will be provided with context for the story up to the final act, use the
information to write an appropriate ending for the story.

Respond with only the synopsis, and nothing else
"""

_write_act_template_ = """
{base_character}

You are tasked with writing the dialogue for a text-based adventure game. You will only need to write a small portion of the dialogue, up until an action is expected from the player. Players will only have limited attempts to influence the story.

You will be provided with context for the current story, including any requirements for the dialogue. The dialogue will be fed to the player one by one to keep the story engaging.

Players will take the role of the main character in the game. At the end of the dialogue, give the player an option to participate in the adventure. End the dialogue with an expectation for the main character to act. Also include a list of suggested actions that the character could take. For example:

```
["Accept the offer", "Negotiate for a better price", "Stick to your principles and refuse the offer"]
```

Your response should only include the content in JSON. The structure of the response should follow this example:

```
{{ "dialogue": ["This is the long dialogue", "Second part"], "possible_actions": ["Action 1", "Action 2"] }}
```
"""

_story_block_context_template_ = """
## Story Inspiration Reference
{project_reference}

## Synopsis
{project_synopsis}

## Current Act Synopsis
{project_current_act_synopsis}

## Main Character
{project_main_character}

## Supporting Characters
{project_supporting_characters_description}

## Additional Requirements
{additional_requirements}
"""

_write_story_block_ = (
    ChatPromptTemplate.from_messages(
        [
            ("system", _write_act_template_),
            ("human", _story_block_context_template_),
        ]
    )
) | llm

_write_final_act_synopsis_ = (
    ChatPromptTemplate.from_messages(
        [
            ("system", _write_final_act_synopsis_),
            ("human", _story_block_context_template_),
        ]
    )
) | llm


@dataclass
class TextAction:
    text: str


@dataclass
class PhotoAction:
    url: str


async def generate_next_story_block(
    game_session: GameSession, action: typing.Union[TextAction, PhotoAction]
):
    print("START NEXT BLOCK WRITING")
    parsed_response: dict
    blocks = game_session.story_blocks
    previous_block = None
    actions_consumed = 1
    if isinstance(action, PhotoAction):
        actions_consumed += 1
    block_number = len(blocks) + 1
    total_actions_consumed = actions_consumed
    if len(blocks) == 0:
        pass
    elif len(blocks) == 1:
        previous_block = blocks[0]
        total_actions_consumed += previous_block.actions_consumed
    else:
        previous_block = max(blocks, key=lambda b: b.number)
        total_actions_consumed = reduce(
            lambda a, b: b.actions_consumed + a, blocks, total_actions_consumed
        )
    actions_remaining = game_session.total_actions - total_actions_consumed

    new_story_block = GameStoryBlock()
    new_story_block.previous_action = ""

    if Config.stub_text_generation:
        logger.debug("stub text - applying artificial wait")
        await asyncio.sleep(5)

        raw_response = """
{{
  "dialogue": [
    "The air hangs thick with the smell of molten iron and coal dust, a familiar scent at Norton Cast Products. The rhythmic clang of hammers against metal echoes around you – a constant pulse in this sprawling foundry.",
    "You are Elara Finch, a junior assistant engineer, meticulously inspecting one of the newly cast stelae for the Blackwood Memorial. Each stone is meant to represent unity and remembrance after those… unsettling incidents that have been plaguing London lately.",
    "Two years. Two years since Thomas... The memory claws at you as always: the whirring gears, the sudden collapse, the hushed whispers afterward. They called it an accident. You know better.",
    "Mr. Blackwood's memorial. A grand gesture, he calls it. A balm for a troubled city.",
    "But something feels… off. The stelae aren’t perfect. There are subtle imperfections in the casting – minute flaws that shouldn’t be there. They seem deliberate, almost like… coded messages.",
    "A shimmering distortion momentarily disrupts your focus. A voice, crisp and intelligent, cuts through the din.",
    "“Look deeper, Miss Finch. Resonance can be manipulated, amplified. Calculated.” The figure flickers - Ada Lovelace’s familiar profile – before dissolving into the steam.",
    "You blink, disoriented. Ada? Here? Impossible… yet, her words linger in your mind like a phantom equation.",
    "Later that evening, you find yourself confiding in your father, Thomas Finch, a retired Royal Engineer.",
    "“Father, I saw something today... at the foundry. Something about the stelae…”",
    "He sighs, running a hand through his thinning hair. “Elara, my dear, it’s been two years. You're still grieving. These… flights of fancy aren’t becoming of you. Blackwood is a respected man, and this memorial is for the good of the city.”",
    "“But what if there’s something wrong with it? Something more than just imperfections?”",
    "“Nonsense. You worry too much. Focus on your work, Elara. Let these grand schemes be for others to manage." ],
  "possible_actions": [
    "Examine the stela more closely for hidden markings.",
    "Attempt to recall more details about Ada Lovelace’s appearance and message.",
    "Confront your father about his dismissive attitude."
  ]
}}
        """
        parsed_response = json.loads(raw_response)
        logger.debug("stub text - DONE")
    else:
        additional_requirements = ""
        project_current_act_synopsis = ""

        action_part = ""
        if isinstance(action, TextAction):
            new_story_block.previous_action = action.text
            action_part = f"\n\nThe player has taken the following action: {action.text}\n\nAssess the action if this is determined to be unrealistic or unsuitable in the context of the story, dismiss it and punish the player in the following dialogue"
        elif isinstance(action, PhotoAction):
            print("INVOKING MAGIC ASSISTANCE")
            new_story_block.previous_action = "photo"
            mchat_response = await mistral_client.chat.complete_async(
                model="pixtral-12b-2409",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"""
What is the most prominent object in this image? For example, this could be either a sword, knife, frying pan or pillow. This could also be animals or plants, like a fish, dog, or flower.

Respond only with the name of the item identified
""",
                            },
                            {"type": "image_url", "image_url": f"{action.url}"},
                        ],
                    }
                ],
            )
            magic_assistance = mchat_response.choices[0].message.content
            print(f"INVOKED MAGIC ASSISTANCE - {magic_assistance}")
            action_part = f"""
The player has invoked a secret power that allows them to break the laws of the world. The main character can now turn the situation in their favour using the special item endowed by the player:
- {magic_assistance}

Continue the dialogue in a way that allows the main character to use the item as though it magically appeared to assist them
"""

        previous_dialogue_part = ""
        if previous_block is not None:
            previous_dialogue_part = f"The next dialogue is a continuation of the previous dialogue:\n{"\n- ".join(previous_block.dialogue[-3:])}"

        main_characters = list(
            filter(lambda c: c.is_main_character, game_session.characters)
        )

        supporting_characters = list(
            filter(lambda c: not c.is_main_character, game_session.characters)
        )

        if block_number == 1:
            project_current_act_synopsis = game_session.opening_act_synopsis
            additional_requirements = "This is the opening dialogue, include more dialogue to introduce the world and the main character"
        elif block_number <= _INTRO_BLOCKS_:
            project_current_act_synopsis = game_session.opening_act_synopsis
            additional_requirements = f"{previous_dialogue_part}{action_part}"
        elif actions_remaining < _CLOSING_BLOCKS_:
            if game_session.final_act_synoposis != "":
                final_act_response = await _write_final_act_synopsis_.ainvoke(
                    {
                        "project_reference": game_session.reference_material_summary,
                        "base_character": GAMEMASTER_BASE_CHARACTER,
                        "project_synopsis": game_session.synopsis,
                        "project_current_act_synopsis": project_current_act_synopsis,
                        "project_main_character": f"Name: {main_characters[0].name}\bPersonality: {main_characters[0].personality}\nBackground: {main_characters[0].background}",
                        "project_supporting_characters_description": "\n\n".join(
                            list(
                                map(
                                    lambda c: f"Name: {c.name}\nPersonality: {c.personality}\nBackground: {c.background}",
                                    supporting_characters,
                                )
                            )
                        ),
                        "additional_requirements": additional_requirements,
                    }
                )
                if is_mistral:
                    game_session.final_act_synoposis = final_act_response.content
                else:
                    game_session.final_act_synoposis = final_act_response

            project_current_act_synopsis = game_session.final_act_synoposis

            if actions_remaining <= 0:
                additional_requirements += "\n\nThis is the final dialogue, use this opportunity to write an ending through the dialogue. The possible actions for the player should be an empty array"
            else:
                additional_requirements += "\nWe are approaching, but not yet at the end of the story, start slowly wrapping up the story"
        else:
            additional_requirements = f"{previous_dialogue_part}{action_part}"
            project_current_act_synopsis = game_session.middle_act_synopsis

        print(game_session.synopsis)
        print(project_current_act_synopsis)
        print("ADDITIONAL REQUIREMENTS")
        print(additional_requirements)

        raw_response = await _write_story_block_.ainvoke(
            {
                "project_reference": game_session.reference_material_summary,
                "base_character": GAMEMASTER_BASE_CHARACTER,
                "project_synopsis": game_session.synopsis,
                "project_current_act_synopsis": project_current_act_synopsis,
                "project_main_character": f"Name: {main_characters[0].name}\bPersonality: {main_characters[0].personality}\nBackground: {main_characters[0].background}",
                "project_supporting_characters_description": "\n\n".join(
                    list(
                        map(
                            lambda c: f"Name: {c.name}\nPersonality: {c.personality}\nBackground: {c.background}",
                            supporting_characters,
                        )
                    )
                ),
                "additional_requirements": additional_requirements,
            }
        )
        if is_mistral:
            parsed_response = clean_and_parse_json(raw_response.content)
        else:
            parsed_response = clean_and_parse_json(raw_response)

    new_story_block.dialogue = parsed_response["dialogue"]
    new_story_block.possible_actions = parsed_response["possible_actions"]
    new_story_block.is_final_act = total_actions_consumed >= game_session.total_actions
    new_story_block.number = block_number
    new_story_block.actions_consumed = actions_consumed
    new_story_block.backdrop_image_url = game_session.promo_image_url

    if previous_block is not None:
        new_story_block.backdrop_image_url = previous_block.backdrop_image_url

    return new_story_block


reg1 = re.compile(r"^`\.+$")
reg2 = re.compile(r"")
