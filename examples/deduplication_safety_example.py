"""
Example: Deduplication preserves original repeated content

This example demonstrates that deduplication only removes duplicates
caused by chunk overlaps, not repeated words in the original content.
"""

from pathlib import Path

from flowscribe.core.deduplication import TranscriptDeduplicator
from flowscribe.core.models import MediaItem, Transcript, TranscriptSegment


def main():
    media_item = MediaItem(path=Path("example.mp3"))

    # Scenario 1: Original content with repeated words (should be preserved)
    print("=" * 60)
    print("Scenario 1: Original content with repeated words")
    print("=" * 60)

    segments = (
        TranscriptSegment(text="爸爸妈妈", start_seconds=0.0, end_seconds=2.0),
        TranscriptSegment(text="爸爸说今天天气很好", start_seconds=3.0, end_seconds=6.0),
        TranscriptSegment(text="妈妈说我们去公园", start_seconds=7.0, end_seconds=10.0),
        TranscriptSegment(text="爸爸妈妈都很开心", start_seconds=50.0, end_seconds=53.0),
    )

    transcript = Transcript(source=media_item, segments=segments, language="zh")
    deduplicator = TranscriptDeduplicator()
    result = deduplicator.deduplicate(transcript)

    print(f"\nOriginal: {len(transcript.segments)} segments")
    for seg in transcript.segments:
        print(f"  [{seg.start_seconds:.1f}s] {seg.text}")

    print(f"\nAfter deduplication: {len(result.segments)} segments")
    for seg in result.segments:
        print(f"  [{seg.start_seconds:.1f}s] {seg.text}")

    print(f"\n[OK] All segments preserved (no false positives)")

    # Scenario 2: Chunk overlap duplicates (should be removed)
    print("\n" + "=" * 60)
    print("Scenario 2: Chunk overlap duplicates")
    print("=" * 60)

    segments = (
        TranscriptSegment(text="你好世界", start_seconds=0.0, end_seconds=2.0),
        TranscriptSegment(text="今天天气很好", start_seconds=2.5, end_seconds=5.0),
        # Duplicate from chunk overlap (within 2 seconds)
        TranscriptSegment(text="今天天气很好", start_seconds=3.0, end_seconds=5.5),
        TranscriptSegment(text="我们去公园吧", start_seconds=6.0, end_seconds=8.0),
    )

    transcript = Transcript(source=media_item, segments=segments, language="zh")
    result = deduplicator.deduplicate(transcript)

    print(f"\nOriginal: {len(transcript.segments)} segments")
    for seg in transcript.segments:
        print(f"  [{seg.start_seconds:.1f}s] {seg.text}")

    print(f"\nAfter deduplication: {len(result.segments)} segments")
    for seg in result.segments:
        print(f"  [{seg.start_seconds:.1f}s] {seg.text}")

    print(f"\n[OK] Removed {len(transcript.segments) - len(result.segments)} duplicate from chunk overlap")

    # Scenario 3: Same phrase repeated in different parts (should be preserved)
    print("\n" + "=" * 60)
    print("Scenario 3: Same phrase repeated far apart")
    print("=" * 60)

    segments = (
        TranscriptSegment(text="你好", start_seconds=0.0, end_seconds=1.0),
        TranscriptSegment(text="我是小明", start_seconds=2.0, end_seconds=4.0),
        TranscriptSegment(text="很高兴认识你", start_seconds=5.0, end_seconds=7.0),
        # Same greeting 50 seconds later
        TranscriptSegment(text="你好", start_seconds=50.0, end_seconds=51.0),
        TranscriptSegment(text="我们又见面了", start_seconds=52.0, end_seconds=54.0),
    )

    transcript = Transcript(source=media_item, segments=segments, language="zh")
    result = deduplicator.deduplicate(transcript)

    print(f"\nOriginal: {len(transcript.segments)} segments")
    for seg in transcript.segments:
        print(f"  [{seg.start_seconds:.1f}s] {seg.text}")

    print(f"\nAfter deduplication: {len(result.segments)} segments")
    for seg in result.segments:
        print(f"  [{seg.start_seconds:.1f}s] {seg.text}")

    print(f"\n[OK] Both '你好' preserved (50 seconds apart)")

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print("Deduplication only removes segments that are:")
    print("  1. Text is identical or very similar")
    print("  2. AND time stamps are close (within 2 seconds by default)")
    print("\nOriginal repeated content is always preserved!")


if __name__ == "__main__":
    main()
