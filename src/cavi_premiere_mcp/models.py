"""Argument and result models of the Premiere tools."""

from typing import Annotated, Any, Literal

from cavi_mcp_core.contracts import Result
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .app import Kind, Seconds, Track

MarkerType = Literal["comment", "chapter", "segmentation", "weblink"]
MarkerColor = Annotated[int, Field(ge=0, le=7)]


def web_link(type_, url):
    """A web link marker needs its url, and a url belongs to a web link marker."""
    if (type_ == "weblink") != (url is not None):
        raise ValueError("type weblink needs url, and url needs type weblink")


class App(BaseModel):
    app: str | None
    version: str
    pids: list[int]
    error: str | None = None


class Status(Result):
    premiere: App
    bridge: App
    media_encoder: App
    relay: str
    mailbox: str
    prores_preset: str | None


class BridgeInstall(Result):
    path: str
    matches: bool
    next: str


class Script(Result):
    answer: str
    report: Any = None


class Transition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str  # an alias (cross_dissolve, film_dissolve, dip_to_white, dip_to_black) or a name premiere_transitions lists
    frames: int = Field(ge=1, le=600)


class Clip(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file: str
    start: Seconds
    in_point: Seconds
    out_point: Seconds
    transition: Transition | None = None


class Cut(Result):
    project: str
    master: str
    fps: str
    frames: int
    cut_frames: int
    transitions: list[str]
    warnings: list[str]


class Transitions(Result):
    video: list[str]
    audio: list[str]
    aliases: dict[str, str]


class PresetEntry(BaseModel):
    name: str
    format: str
    source: Literal["premiere", "media_encoder", "user"]
    path: str


class Presets(Result):
    export: list[PresetEntry]
    sequence: list[PresetEntry]


class Project(Result):
    project: str | None
    name: str | None
    open: int
    sequences: int
    closed: str | None = None
    saved_from: str | None = None


class Item(BaseModel):
    name: str
    id: str
    bin: str
    kind: Literal["clip", "bin", "sequence"]
    media_path: str | None
    offline: bool | None
    duration: float | None
    clip_duration: float | None
    label: int | None
    fps: float | None
    width: int | None
    height: int | None


class TimelineClip(BaseModel):
    position: int
    name: str
    item_id: str | None = None
    start: float
    end: float
    in_point: float
    out_point: float
    speed: float = 100
    reversed: bool = False
    media_path: str | None


class Move(BaseModel):
    name: str | None
    start: float
    end: float


class Lane(BaseModel):
    index: int
    name: str
    clips: list[TimelineClip]
    transitions: list[Move]


class Marker(BaseModel):
    name: str
    comment: str
    start: float
    end: float
    color: int | None = None
    type: str | None = None
    url: str | None = None


class SequenceInfo(BaseModel):
    name: str
    id: str
    active: bool
    fps: float
    width: int
    height: int
    end: float
    video: list[Lane]
    audio: list[Lane]
    markers: list[Marker]


class Inspect(Result):
    project: str
    bins: list[str]
    items: list[Item]
    sequences: list[SequenceInfo]


class Imported(BaseModel):
    name: str
    id: str
    media_path: str | None


class Import(Result):
    bin: str
    imported: list[Imported]
    warnings: list[str]


class NewSequence(Result):
    name: str
    id: str
    fps: float
    width: int
    height: int
    video_tracks: int
    audio_tracks: int


class Placed(Result):
    """One placed clip in clip, or with a clips list every placed clip in clips."""

    sequence: str
    clip: TimelineClip | None = None
    clips: list[TimelineClip] | None = None


class Placement(BaseModel):
    """One clip of a clips list; a field left out takes the call's value."""

    model_config = ConfigDict(extra="forbid")
    item: str
    at: Seconds
    kind: Kind | None = None
    track: Track | None = None
    in_point: Seconds | None = None
    out_point: Seconds | None = None
    mode: Literal["overwrite", "insert"] | None = None


class Opened(Result):
    sequence: str
    id: str


class Props(Result):
    clip: str
    applied: dict[str, Any]
    keyframes: dict[str, list[dict[str, Any]]]


class Added(Result):
    clip: str
    transition: Move | None = None
    removed: Move | None = None


class Replaced(Result):
    name: str
    previous_path: str | None
    media_path: str
    offline: bool
    verified: bool
    sequence_clips: int


class Markers(Result):
    sequence: str
    added: int
    total: int


class Mogrt(Result):
    clip: str
    start: float
    end: float
    track: int | None = None
    parameters: list[str] = []
    text: dict[str, str]


class Export(Result):
    sequence: str
    master: str
    fps: float
    frames: int
    expected_frames: int | None
    complete: bool
    warnings: list[str]


class Reframed(Result):
    source: str
    sequence: dict[str, Any]


class Interchange(Result):
    action: str
    path: str
    size: int
    sequence: str | None = None
    imported: list[str] | None = None


class Captions(Result):
    sequence: str
    item: str
    captions: int


class Key(BaseModel):
    model_config = ConfigDict(extra="forbid")
    time: Seconds
    value: Any = None
    color: Annotated[str, Field(pattern=r"^#?[0-9a-fA-F]{6}$")] | None = None
    interpolation: Literal["linear", "hold", "bezier"] | None = None


class Param(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    value: Any = None
    color: Annotated[str, Field(pattern=r"^#?[0-9a-fA-F]{6}$")] | None = None
    index: Annotated[int, Field(ge=0)] = 0  # which of several parameters share this display name
    keyframes: list[Key] | None = None


class Effects(Result):
    video: list[str]
    audio: list[str]


class EffectAdded(Result):
    clip: str
    components_before: int
    components: list[dict[str, Any]]


class EffectSet(Result):
    clip: str
    applied: dict[str, Any]
    components: list[dict[str, Any]] | None = None
    removed: str | None = None


class Fit(Result):
    clip: str
    source: dict[str, int]
    pixel_aspect: float | None = None
    sequence_size: dict[str, int]
    scale: float


class ItemState(BaseModel):
    name: str
    bin: str
    kind: str
    label: int
    xmp: dict[str, str]


class Items(Result):
    item: ItemState | None
    subclip: dict[str, str] | None = None
    interpretation: dict[str, Any] | None = None
    proxy: dict[str, Any] | None = None
    deleted: str | None = None


class Scenes(Result):
    clip: str
    cuts: list[float]
    applied: str
    clips_after: int | None = None
    markers: int | None = None


class SubClip(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    in_point: Seconds
    out_point: Seconds
    hard: bool = False


class Interpret(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frame_rate: Annotated[float, Field(gt=0, le=240)] | None = None
    pixel_aspect: Annotated[float, Field(gt=0, le=10)] | None = None
    alpha: Literal["none", "straight", "premultiplied", "ignore"] | None = None
    invert_alpha: bool | None = None
    field_order: Literal["default", "progressive", "upper", "lower"] | None = None
    remove_pulldown: bool | None = None


class Keyframe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    time: Seconds
    position: tuple[float, float] | None = None
    scale: float | None = Field(default=None, ge=0)
    rotation: float | None = None
    opacity: float | None = Field(default=None, ge=0, le=100)
    volume_db: float | None = Field(default=None, ge=-96, le=15)


class BeatGrid(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bpm: float = Field(gt=0, le=1000)
    beats_per_bar: int = Field(default=4, ge=1, le=32)
    start: Seconds = 0
    end: Annotated[float, Field(gt=0)]


class NewMarker(BaseModel):
    model_config = ConfigDict(extra="forbid")
    time: Seconds
    name: str = ""
    comment: str = ""
    duration: Seconds = 0
    color: MarkerColor | None = Field(default=None, description="Marker color index, 0 to 7.")
    type: MarkerType | None = Field(default=None, description="Marker type; comment when omitted.")
    url: str | None = Field(default=None, description="Link of a weblink marker.")

    @model_validator(mode="after")
    def _link(self):
        web_link(self.type, self.url)
        return self


class EditedClip(BaseModel):
    track: int
    name: str
    start: float
    end: float
    in_point: float
    out_point: float
    enabled: bool
    position: int | None
    linked: int


class Removed(BaseModel):
    name: str
    start: float
    end: float
    mode: str
    partners: int = 0


class ClipEdit(Result):
    sequence: str
    clip: EditedClip | None = None
    removed: Removed | None = None
    note: str | None = None


class Razor(Result):
    sequence: str
    cuts: int
    clips_before: int
    clips_after: int


class Speed(Result):
    clip: str
    speed: float
    reversed: bool
    start: float
    end: float
    duration: float


class SequenceState(BaseModel):
    name: str
    id: str
    width: int
    height: int
    fps: float
    audio_rate: int
    end: float
    in_point: float | None
    out_point: float | None


class SequenceChange(Result):
    sequence: SequenceState | None = None
    nested: SequenceState | None = None
    duplicate: SequenceState | None = None
    deleted: str | None = None
    sequences: list[str]


class TrackCounts(BaseModel):
    video: int
    audio: int


class TrackState(BaseModel):
    index: int
    name: str
    muted: bool
    locked: bool
    targeted: bool
    clips: int
    volume: float | None = None  # audio tracks: linear gain as Premiere shows it, 1.0 is 0 dB


class TrackLists(BaseModel):
    video: list[TrackState]
    audio: list[TrackState]


class Tracks(Result):
    sequence: str
    before: TrackCounts
    after: TrackCounts
    tracks: TrackLists


class Still(BaseModel):
    time: float
    path: str
    width: int
    height: int


class Frames(Result):
    sequence: str
    frames: list[Still]


class LinkRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Kind
    track: Track = 0
    position_index: Annotated[int, Field(ge=0)]


class NestSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clips: Annotated[list[LinkRef], Field(min_length=1)]
    name: str = ""


class SequenceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width: Annotated[int, Field(ge=16, le=16384)] | None = None
    height: Annotated[int, Field(ge=16, le=16384)] | None = None
    fps: Annotated[float, Field(gt=0, le=240)] | None = None
    audio_rate: Annotated[int, Field(ge=8000, le=192000)] | None = None


class TrackSet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Kind
    track: Track
    muted: bool | None = None
    locked: bool | None = None
    targeted: bool | None = None
    volume_db: float | None = Field(default=None, ge=-96, le=6, description="Audio track Volume in dB, -96 to 6.")

