from text_stats import word_count


def test_counts_words():
    assert word_count("fast terminal agents") == 3


def test_ignores_extra_spaces():
    assert word_count("  one   two  ") == 2
