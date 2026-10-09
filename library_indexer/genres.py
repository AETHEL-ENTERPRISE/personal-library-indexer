"""Explainable English keyword rules, not a trained machine-learning model."""

import re
import unicodedata


# Each distinct match counts once. Subjects and titles take priority over text.
RULES: dict[str, tuple[str, ...]] = {
    "Technology": (
        "technology", "computer", "computing", "programming", "python",
        "javascript", "software", "algorithm", "algorithms", "database",
        "databases", "artificial intelligence", "machine learning", "networking",
    ),
    "Science": (
        "science", "physics", "chemistry", "biology", "astronomy", "planet",
        "planets", "solar system", "space", "ecology", "mathematics", "calculus",
    ),
    "Business": (
        "business", "entrepreneurship", "startup", "marketing", "accounting",
        "finance", "economics", "investment", "management", "revenue",
    ),
    "History": (
        "history", "historical", "civilization", "civilizations", "empire",
        "ancient", "archaeology", "medieval", "dynasty",
    ),
    "Fiction": (
        "fiction", "novel", "mystery", "fantasy", "romance", "thriller",
        "detective", "short story", "short stories", "adventure",
    ),
    "Self-help": (
        "self help", "personal development", "productivity", "mindfulness",
        "motivation", "habits", "time management", "goal setting",
    ),
    "Education": (
        "education", "teaching", "pedagogy", "curriculum", "classroom",
        "lesson planning", "textbook", "exam preparation",
    ),
    "Arts": (
        "art", "arts", "painting", "photography", "music", "sculpture",
        "drawing", "poetry", "architecture",
    ),
}
GENRES = tuple(sorted(RULES)) + ("Other",)


def normalized(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    # Do not treat the word 'fiction' inside 'non-fiction' as a fiction signal.
    text = re.sub(r"\bnon[\s-]?fiction\b", "nonfiction", text)
    return re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).strip()


def classify_genre(title: str, subjects: str, text: str) -> tuple[str, str]:
    """Return a genre and its evidence; ties stay Other instead of guessing."""
    for source, value in (("Subjects", subjects), ("Title", title), ("Text sample", text)):
        haystack = " " + normalized(value) + " "
        matches = {
            genre: [term for term in terms if " " + term + " " in haystack]
            for genre, terms in RULES.items()
        }
        best_score = max((len(words) for words in matches.values()), default=0)
        # A single broad word in body text is weak evidence.
        minimum = 2 if source == "Text sample" else 1
        if best_score < minimum:
            continue
        winners = [genre for genre, words in matches.items() if len(words) == best_score]
        if len(winners) == 1:
            genre = winners[0]
            return genre, f"{source}: {', '.join(matches[genre])}"
        return "Other", f"Mixed {source.lower()} signals; review manually."
    return "Other", "No clear keyword match; review manually."
