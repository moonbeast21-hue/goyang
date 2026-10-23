from __future__ import annotations

from bisect import bisect_left

from .models import MediaType, VideoProject


STYLE_TRANSITIONS = {
    "감동적인 퇴임식": ["크로스 디졸브", "부드러운 확대", "페이드"],
    "밝고 즐거운 퇴임식": ["크로스 디졸브", "좌우 슬라이드", "부드러운 확대"],
    "영화 같은 추억 영상": ["Ken Burns", "크로스 디졸브", "부드러운 축소"],
}


def sort_by_date(project: VideoProject) -> None:
    indexed = list(enumerate(project.items))
    indexed.sort(key=lambda pair: (pair[1].capture_date is None, pair[1].capture_date or "", pair[0]))
    project.items = [item for _, item in indexed]


def _nearest_interval(target: float, beats: list[float], minimum: float, maximum: float) -> float:
    if len(beats) < 2:
        return target
    candidates: list[float] = []
    for stride in (4, 8, 16):
        for index in range(0, len(beats) - stride):
            value = beats[index + stride] - beats[index]
            if minimum <= value <= maximum:
                candidates.append(value)
    return min(candidates, key=lambda x: abs(x - target)) if candidates else target


def auto_edit(project: VideoProject) -> list[str]:
    settings = project.settings
    editable = [x for x in project.items if x.media_type == MediaType.PHOTO and not x.locked]
    video_seconds = sum(min(x.duration, settings.video_max_duration) for x in project.items if x.media_type == MediaType.VIDEO)
    target = settings.target_seconds
    if target and editable:
        base = (target - video_seconds) / len(editable)
    elif project.music and project.music[0].duration and editable:
        base = (project.music[0].duration - video_seconds) / len(editable)
    else:
        base = settings.default_duration
    warnings: list[str] = []
    if base < settings.min_duration or base > settings.max_duration:
        warnings.append(
            f"목표 길이에 필요한 사진 재생시간은 {base:.1f}초입니다. "
            f"설정 범위({settings.min_duration:.1f}~{settings.max_duration:.1f}초)로 제한했습니다."
        )
    base = max(settings.min_duration, min(settings.max_duration, base))
    beats = project.music[0].beats if project.music else []
    beat_duration = _nearest_interval(base, beats, settings.min_duration, settings.max_duration)
    sync = settings.sync_strength / 100
    transitions = STYLE_TRANSITIONS.get(settings.style, STYLE_TRANSITIONS["밝고 즐거운 퇴임식"])
    for index, item in enumerate(editable):
        weight = {"일반": 1.0, "중요": 1.2, "하이라이트": 1.45}.get(item.importance, 1.0)
        duration = ((1 - sync) * base + sync * beat_duration) * weight
        item.duration = round(max(settings.min_duration, min(settings.max_duration, duration)), 3)
        item.transition = transitions[index % len(transitions)]
    return warnings

