"""
Example: Using TranscriptDeduplicator to remove duplicate segments

This example demonstrates how to use the TranscriptDeduplicator to clean up
transcripts that have duplicate segments at chunk boundaries.
"""

from pathlib import Path

from flowscribe.core.deduplication import TranscriptDeduplicator
from flowscribe.core.models import MediaItem, Transcript, TranscriptSegment


def main():
    # Create a sample transcript with duplicates (simulating chunk overlap)
    media_item = MediaItem(path=Path("example.mp3"))

    segments = (
        TranscriptSegment(text="Hello world", start_seconds=0.0, end_seconds=2.0),
        TranscriptSegment(text="How are you today", start_seconds=2.5, end_seconds=5.0),
        # Duplicate from chunk overlap
        TranscriptSegment(text="How are you today", start_seconds=3.0, end_seconds=5.5),
        TranscriptSegment(text="I am doing great", start_seconds=6.0, end_seconds=8.0),
        TranscriptSegment(text="Thank you for asking", start_seconds=8.5, end_seconds=10.5),
        # Another duplicate
        TranscriptSegment(text="Thank you for asking", start_seconds=9.0, end_seconds=11.0),
    )

    transcript = Transcript(
        source=media_item,
        segments=segments,
        language="en",
        model_name="small",
    )

    print("Original transcript:")
    print(f"  Total segments: {len(transcript.segments)}")
    for i, seg in enumerate(transcript.segments, 1):
        print(f"  {i}. [{seg.start_seconds:.1f}s - {seg.end_seconds:.1f}s] {seg.text}")

    # Apply deduplication
    deduplicator = TranscriptDeduplicator(
        text_similarity_threshold=0.9,
        time_overlap_threshold_seconds=2.0,
    )
    deduplicated = deduplicator.deduplicate(transcript)

    print("\nDeduplicated transcript:")
    print(f"  Total segments: {len(deduplicated.segments)}")
    for i, seg in enumerate(deduplicated.segments, 1):
        print(f"  {i}. [{seg.start_seconds:.1f}s - {seg.end_seconds:.1f}s] {seg.text}")

    print(f"\nRemoved {len(transcript.segments) - len(deduplicated.segments)} duplicate segments")


if __name__ == "__main__":
    main()
