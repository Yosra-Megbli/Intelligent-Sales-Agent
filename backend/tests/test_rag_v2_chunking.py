"""
Tests for rag_v2/chunking.py - pure, no DB, no network.
"""

from rag_v2.chunking import chunk_text


def test_empty_text_produces_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_short_text_produces_a_single_chunk():
    chunks = chunk_text("Bonjour, ceci est un court texte.", target_tokens=500, overlap_tokens=50)
    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert chunks[0].text == "Bonjour, ceci est un court texte."


def test_long_text_splits_into_multiple_chunks():
    text = " ".join(f"mot{i}" for i in range(2000))
    chunks = chunk_text(text, target_tokens=500, overlap_tokens=50)
    assert len(chunks) > 1
    # Indices are sequential starting at 0.
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_no_word_is_ever_lost_even_with_one_giant_paragraph():
    """Regression: an earlier paragraph-aware version could flush a chunk
    and reset to only the overlap tail, silently dropping the rest of any
    paragraph much longer than the target size. Every word must appear in
    at least one chunk."""
    words = [f"mot{i}" for i in range(3000)]
    text = " ".join(words)  # one giant "paragraph", no blank lines at all

    chunks = chunk_text(text, target_tokens=500, overlap_tokens=50)

    seen = set()
    for c in chunks:
        seen.update(c.text.split())
    assert seen == set(words)


def test_consecutive_chunks_overlap():
    """The true overlap region is exactly overlap_words long (37, for
    overlap_tokens=50 at ~0.75 words/token) - it must land at chunk1's
    exact tail and chunk2's exact head, not just "somewhere in the last/
    first 10 words" (a looser check can miss it entirely depending on the
    computed step size, which is what the first version of this test got
    wrong, not the chunking implementation)."""
    text = " ".join(f"mot{i}" for i in range(1500))
    chunks = chunk_text(text, target_tokens=500, overlap_tokens=50)
    assert len(chunks) >= 2

    overlap_words = 37  # int(50 * 0.75)
    first_words = chunks[0].text.split()
    second_words = chunks[1].text.split()
    assert first_words[-overlap_words:] == second_words[:overlap_words]


def test_chunking_is_deterministic():
    text = "Ligne un.\n\nLigne deux avec plus de mots pour varier la taille.\n\n" * 50

    first = chunk_text(text)
    second = chunk_text(text)

    assert [c.text for c in first] == [c.text for c in second]
