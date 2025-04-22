# Project: Alternative Stories

Submission for the [London, Paris, Berlin AI HackXelerator hackathon](https://www.kxsb.org/lpb25).

See the [project video](https://vimeo.com/1077755227/cafc9c4300?share=copy)

## Architecture

### Story Foundations

```mermaid
sequenceDiagram
    TextReference->>Mistral Large: use as a base
    Mistral Large->>StoryBase: generates
    StoryBase->>LumaAI: generate promo image/video
    LumaAI->>StoryBase: generated content
```

### Story Adaption

```mermaid
sequenceDiagram
    Player->>StoryBase: takes action
    StoryBase->>+Mistral Small: adapt story
    Mistral Small->>-StoryBase: next story block
    StoryBase->>Player: feed next part of the story
    StoryBase->>+LumaAI: generate promo image/video
    LumaAI->>-StoryBase: generated content
    StoryBase->>Player: add visuals
```