from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FranchiseSeedRow:
    name: str
    publisher: str
    popularity: float
    demand: float
    longevity: float
    collector_strength: float


@dataclass(frozen=True)
class CharacterSeedRow:
    name: str
    publisher: str
    franchise: str
    popularity: float
    demand: float
    collector: float
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class CreatorSeedRow:
    name: str
    role: str
    popularity: float
    demand: float
    collector: float
    aliases: tuple[str, ...] = ()


FRANCHISE_SEEDS: tuple[FranchiseSeedRow, ...] = (
    FranchiseSeedRow("Batman", "DC", 98.0, 96.0, 95.0, 97.0),
    FranchiseSeedRow("Spider-Man", "Marvel", 97.0, 95.0, 94.0, 96.0),
    FranchiseSeedRow("X-Men", "Marvel", 94.0, 92.0, 93.0, 94.0),
    FranchiseSeedRow("TMNT", "IDW", 90.0, 88.0, 92.0, 91.0),
    FranchiseSeedRow("Transformers", "Skybound", 89.0, 87.0, 91.0, 90.0),
    FranchiseSeedRow("GI Joe", "Image", 82.0, 80.0, 88.0, 84.0),
    FranchiseSeedRow("Invincible", "Image", 86.0, 84.0, 80.0, 85.0),
    FranchiseSeedRow("Spawn", "Image", 85.0, 83.0, 90.0, 86.0),
    FranchiseSeedRow("Star Wars", "Marvel", 93.0, 91.0, 96.0, 92.0),
    FranchiseSeedRow("Power Rangers", "Boom!", 78.0, 76.0, 85.0, 79.0),
    FranchiseSeedRow("Gargoyles", "Dynamite", 72.0, 70.0, 82.0, 74.0),
    FranchiseSeedRow("Vampirella", "Dynamite", 74.0, 72.0, 86.0, 76.0),
    FranchiseSeedRow("Red Sonja", "Dynamite", 73.0, 71.0, 84.0, 75.0),
    FranchiseSeedRow("Superman", "DC", 92.0, 90.0, 94.0, 91.0),
    FranchiseSeedRow("Wonder Woman", "DC", 88.0, 86.0, 92.0, 87.0),
    FranchiseSeedRow("Flash", "DC", 84.0, 82.0, 88.0, 83.0),
    FranchiseSeedRow("Green Lantern", "DC", 83.0, 81.0, 87.0, 82.0),
    FranchiseSeedRow("Justice League", "DC", 87.0, 85.0, 90.0, 86.0),
    FranchiseSeedRow("Teen Titans", "DC", 80.0, 78.0, 84.0, 79.0),
    FranchiseSeedRow("Aquaman", "DC", 79.0, 77.0, 83.0, 78.0),
    FranchiseSeedRow("Avengers", "Marvel", 91.0, 89.0, 92.0, 90.0),
    FranchiseSeedRow("Fantastic Four", "Marvel", 86.0, 84.0, 91.0, 85.0),
    FranchiseSeedRow("Defenders", "Marvel", 78.0, 76.0, 82.0, 77.0),
    FranchiseSeedRow("Guardians of the Galaxy", "Marvel", 85.0, 83.0, 80.0, 84.0),
    FranchiseSeedRow("Conan", "Marvel", 77.0, 75.0, 89.0, 78.0),
    FranchiseSeedRow("Hellboy", "Dark Horse", 76.0, 74.0, 85.0, 77.0),
    FranchiseSeedRow("Buffy", "Boom!", 75.0, 73.0, 83.0, 74.0),
    FranchiseSeedRow("Firefly", "Boom!", 74.0, 72.0, 80.0, 73.0),
    FranchiseSeedRow("Aliens", "Marvel", 73.0, 71.0, 84.0, 72.0),
    FranchiseSeedRow("Predator", "Marvel", 72.0, 70.0, 83.0, 71.0),
    FranchiseSeedRow("Terminator", "Marvel", 71.0, 69.0, 82.0, 70.0),
    FranchiseSeedRow("Godzilla", "IDW", 80.0, 78.0, 86.0, 79.0),
    FranchiseSeedRow("King Kong", "Boom!", 68.0, 66.0, 78.0, 67.0),
    FranchiseSeedRow("Sonic", "IDW", 81.0, 79.0, 84.0, 80.0),
    FranchiseSeedRow("Mega Man", "Boom!", 70.0, 68.0, 79.0, 69.0),
    FranchiseSeedRow("Street Fighter", "UDON", 69.0, 67.0, 77.0, 68.0),
    FranchiseSeedRow("Mortal Kombat", "DC", 68.0, 66.0, 76.0, 67.0),
    FranchiseSeedRow("My Little Pony", "IDW", 65.0, 63.0, 80.0, 64.0),
    FranchiseSeedRow("Dungeons & Dragons", "IDW", 74.0, 72.0, 81.0, 73.0),
    FranchiseSeedRow("Magic: The Gathering", "BOOM!", 72.0, 70.0, 79.0, 71.0),
    FranchiseSeedRow("Critical Role", "Dark Horse", 77.0, 75.0, 70.0, 76.0),
    FranchiseSeedRow("The Boys", "Dynamite", 79.0, 77.0, 75.0, 78.0),
    FranchiseSeedRow("Walking Dead", "Image", 88.0, 86.0, 87.0, 85.0),
    FranchiseSeedRow("Saga", "Image", 84.0, 82.0, 78.0, 83.0),
    FranchiseSeedRow("Paper Girls", "Image", 70.0, 68.0, 72.0, 69.0),
    FranchiseSeedRow("East of West", "Image", 71.0, 69.0, 73.0, 70.0),
    FranchiseSeedRow("Black Hammer", "Dark Horse", 69.0, 67.0, 71.0, 68.0),
    FranchiseSeedRow("Umbrella Academy", "Dark Horse", 76.0, 74.0, 76.0, 75.0),
    FranchiseSeedRow("Archie", "Archie", 73.0, 71.0, 85.0, 72.0),
    FranchiseSeedRow("Riverdale", "Archie", 68.0, 66.0, 74.0, 67.0),
    FranchiseSeedRow("Judge Dredd", "Rebellion", 72.0, 70.0, 88.0, 73.0),
    FranchiseSeedRow("2000 AD", "Rebellion", 70.0, 68.0, 86.0, 71.0),
)

_EXTRA_FRANCHISES: tuple[tuple[str, str, float], ...] = tuple(
    (f"Franchise Pack {idx}", "Indie", 55.0 + (idx % 15))
    for idx in range(1, 6)
)

CHARACTER_SEEDS: tuple[CharacterSeedRow, ...] = (
    CharacterSeedRow("Batman", "DC", "Batman", 98.0, 96.0, 97.0, ("Dark Knight", "Bruce Wayne")),
    CharacterSeedRow("Spider-Man", "Marvel", "Spider-Man", 97.0, 95.0, 96.0, ("Peter Parker",)),
    CharacterSeedRow("Venom", "Marvel", "Spider-Man", 90.0, 88.0, 91.0, ("Eddie Brock",)),
    CharacterSeedRow("Wolverine", "Marvel", "X-Men", 93.0, 91.0, 94.0, ("Logan",)),
    CharacterSeedRow("Deadpool", "Marvel", "X-Men", 92.0, 90.0, 93.0, ("Wade Wilson",)),
    CharacterSeedRow("Cyclops", "Marvel", "X-Men", 82.0, 80.0, 83.0),
    CharacterSeedRow("Storm", "Marvel", "X-Men", 84.0, 82.0, 85.0),
    CharacterSeedRow("Jean Grey", "Marvel", "X-Men", 83.0, 81.0, 84.0),
    CharacterSeedRow("Magneto", "Marvel", "X-Men", 81.0, 79.0, 82.0),
    CharacterSeedRow("Leonardo", "IDW", "TMNT", 80.0, 78.0, 81.0),
    CharacterSeedRow("Raphael", "IDW", "TMNT", 79.0, 77.0, 80.0),
    CharacterSeedRow("Optimus Prime", "Skybound", "Transformers", 88.0, 86.0, 89.0),
    CharacterSeedRow("Bumblebee", "Skybound", "Transformers", 82.0, 80.0, 83.0),
    CharacterSeedRow("Snake Eyes", "Image", "GI Joe", 78.0, 76.0, 79.0),
    CharacterSeedRow("Invincible", "Image", "Invincible", 86.0, 84.0, 85.0, ("Mark Grayson",)),
    CharacterSeedRow("Spawn", "Image", "Spawn", 85.0, 83.0, 86.0, ("Al Simmons",)),
    CharacterSeedRow("Darth Vader", "Marvel", "Star Wars", 92.0, 90.0, 93.0),
    CharacterSeedRow("Luke Skywalker", "Marvel", "Star Wars", 88.0, 86.0, 89.0),
    CharacterSeedRow("Red Ranger", "Boom!", "Power Rangers", 76.0, 74.0, 77.0),
    CharacterSeedRow("Goliath", "Dynamite", "Gargoyles", 72.0, 70.0, 73.0),
    CharacterSeedRow("Vampirella", "Dynamite", "Vampirella", 74.0, 72.0, 75.0),
    CharacterSeedRow("Red Sonja", "Dynamite", "Red Sonja", 73.0, 71.0, 74.0),
    CharacterSeedRow("Superman", "DC", "Superman", 92.0, 90.0, 91.0, ("Clark Kent",)),
    CharacterSeedRow("Wonder Woman", "DC", "Wonder Woman", 88.0, 86.0, 87.0, ("Diana Prince",)),
    CharacterSeedRow("Harley Quinn", "DC", "Batman", 87.0, 85.0, 88.0),
    CharacterSeedRow("Joker", "DC", "Batman", 86.0, 84.0, 87.0),
    CharacterSeedRow("Iron Man", "Marvel", "Avengers", 89.0, 87.0, 90.0, ("Tony Stark",)),
    CharacterSeedRow("Captain America", "Marvel", "Avengers", 88.0, 86.0, 89.0, ("Steve Rogers",)),
    CharacterSeedRow("Hulk", "Marvel", "Avengers", 87.0, 85.0, 88.0, ("Bruce Banner",)),
    CharacterSeedRow("Thor", "Marvel", "Avengers", 86.0, 84.0, 87.0),
    CharacterSeedRow("Black Panther", "Marvel", "Avengers", 85.0, 83.0, 86.0, ("T'Challa",)),
    CharacterSeedRow("Doctor Strange", "Marvel", "Avengers", 84.0, 82.0, 85.0),
    CharacterSeedRow("Daredevil", "Marvel", "Defenders", 83.0, 81.0, 84.0, ("Matt Murdock",)),
    CharacterSeedRow("Punisher", "Marvel", "Defenders", 82.0, 80.0, 83.0, ("Frank Castle",)),
    CharacterSeedRow("Ghost Rider", "Marvel", "Defenders", 79.0, 77.0, 80.0),
    CharacterSeedRow("Silver Surfer", "Marvel", "Fantastic Four", 78.0, 76.0, 79.0),
    CharacterSeedRow("Human Torch", "Marvel", "Fantastic Four", 77.0, 75.0, 78.0),
    CharacterSeedRow("Thing", "Marvel", "Fantastic Four", 76.0, 74.0, 77.0),
    CharacterSeedRow("Mister Fantastic", "Marvel", "Fantastic Four", 75.0, 73.0, 76.0),
    CharacterSeedRow("Invisible Woman", "Marvel", "Fantastic Four", 74.0, 72.0, 75.0),
    CharacterSeedRow("Galactus", "Marvel", "Fantastic Four", 73.0, 71.0, 74.0),
    CharacterSeedRow("Moon Knight", "Marvel", "Avengers", 81.0, 79.0, 82.0, ("Marc Spector",)),
    CharacterSeedRow("She-Hulk", "Marvel", "Avengers", 80.0, 78.0, 81.0),
    CharacterSeedRow("Ms. Marvel", "Marvel", "Avengers", 79.0, 77.0, 80.0, ("Kamala Khan",)),
    CharacterSeedRow("Nightwing", "DC", "Batman", 82.0, 80.0, 83.0, ("Dick Grayson",)),
    CharacterSeedRow("Robin", "DC", "Batman", 78.0, 76.0, 79.0),
    CharacterSeedRow("Batgirl", "DC", "Batman", 77.0, 75.0, 78.0),
    CharacterSeedRow("Catwoman", "DC", "Batman", 76.0, 74.0, 77.0),
    CharacterSeedRow("Supergirl", "DC", "Superman", 75.0, 73.0, 76.0),
    CharacterSeedRow("Green Arrow", "DC", "Justice League", 74.0, 72.0, 75.0),
    CharacterSeedRow("Black Canary", "DC", "Justice League", 73.0, 71.0, 74.0),
    CharacterSeedRow("Shazam", "DC", "Justice League", 72.0, 70.0, 73.0),
    CharacterSeedRow("Constantine", "DC", "Justice League", 71.0, 69.0, 72.0),
    CharacterSeedRow("Swamp Thing", "DC", "Justice League", 70.0, 68.0, 71.0),
    CharacterSeedRow("Rick Grimes", "Image", "Walking Dead", 84.0, 82.0, 85.0),
    CharacterSeedRow("Negan", "Image", "Walking Dead", 78.0, 76.0, 79.0),
    CharacterSeedRow("Hellboy", "Dark Horse", "Hellboy", 76.0, 74.0, 77.0),
    CharacterSeedRow("Buffy", "Boom!", "Buffy", 75.0, 73.0, 76.0),
    CharacterSeedRow("Archie Andrews", "Archie", "Archie", 70.0, 68.0, 71.0),
    CharacterSeedRow("Judge Dredd", "Rebellion", "Judge Dredd", 72.0, 70.0, 73.0),
)

_EXTRA_CHARACTERS: tuple[tuple[str, str, str, float], ...] = tuple(
    (f"Supporting Hero {idx}", "Marvel", "Avengers", 58.0 + (idx % 12)) for idx in range(1, 46)
)

CREATOR_SEEDS: tuple[CreatorSeedRow, ...] = (
    CreatorSeedRow("Todd McFarlane", "ARTIST", 92.0, 90.0, 93.0, ("McFarlane",)),
    CreatorSeedRow("Daniel Warren Johnson", "WRITER", 88.0, 86.0, 87.0, ("DWJ",)),
    CreatorSeedRow("Scott Snyder", "WRITER", 87.0, 85.0, 86.0),
    CreatorSeedRow("Donny Cates", "WRITER", 86.0, 84.0, 85.0),
    CreatorSeedRow("Geoff Johns", "WRITER", 85.0, 83.0, 84.0),
    CreatorSeedRow("James Tynion IV", "WRITER", 84.0, 82.0, 83.0),
    CreatorSeedRow("Jonathan Hickman", "WRITER", 83.0, 81.0, 82.0),
    CreatorSeedRow("Jim Lee", "ARTIST", 90.0, 88.0, 91.0),
    CreatorSeedRow("Alex Ross", "COVER_ARTIST", 89.0, 87.0, 90.0),
    CreatorSeedRow("Peach Momoko", "COVER_ARTIST", 86.0, 84.0, 87.0),
    CreatorSeedRow("Ryan Ottley", "ARTIST", 85.0, 83.0, 86.0),
    CreatorSeedRow("Greg Capullo", "ARTIST", 84.0, 82.0, 85.0),
    CreatorSeedRow("Jason Aaron", "WRITER", 83.0, 81.0, 84.0),
    CreatorSeedRow("Chip Zdarsky", "WRITER", 82.0, 80.0, 83.0),
    CreatorSeedRow("Tom King", "WRITER", 81.0, 79.0, 82.0),
    CreatorSeedRow("Gerry Duggan", "WRITER", 80.0, 78.0, 81.0),
    CreatorSeedRow("Al Ewing", "WRITER", 79.0, 77.0, 80.0),
    CreatorSeedRow("Kelly Thompson", "WRITER", 78.0, 76.0, 79.0),
    CreatorSeedRow("Ram V", "WRITER", 77.0, 75.0, 78.0),
    CreatorSeedRow("Christopher Sebela", "WRITER", 76.0, 74.0, 77.0),
    CreatorSeedRow("Christopher Cantwell", "WRITER", 75.0, 73.0, 76.0),
    CreatorSeedRow("Ed Brubaker", "WRITER", 74.0, 72.0, 75.0),
    CreatorSeedRow("Brian Michael Bendis", "WRITER", 73.0, 71.0, 74.0),
    CreatorSeedRow("Mark Waid", "WRITER", 72.0, 70.0, 73.0),
    CreatorSeedRow("Grant Morrison", "WRITER", 71.0, 69.0, 72.0),
    CreatorSeedRow("Frank Miller", "WRITER", 70.0, 68.0, 71.0),
    CreatorSeedRow("Neil Gaiman", "WRITER", 69.0, 67.0, 70.0),
    CreatorSeedRow("Alan Moore", "WRITER", 68.0, 66.0, 69.0),
    CreatorSeedRow("Stan Lee", "WRITER", 67.0, 65.0, 68.0),
    CreatorSeedRow("Jack Kirby", "ARTIST", 66.0, 64.0, 67.0),
    CreatorSeedRow("Steve Ditko", "ARTIST", 65.0, 63.0, 66.0),
    CreatorSeedRow("John Romita Sr.", "ARTIST", 64.0, 62.0, 65.0),
    CreatorSeedRow("John Byrne", "ARTIST", 63.0, 61.0, 64.0),
    CreatorSeedRow("George Perez", "ARTIST", 62.0, 60.0, 63.0),
    CreatorSeedRow("Arthur Adams", "ARTIST", 61.0, 59.0, 62.0),
    CreatorSeedRow("Mike Mignola", "ARTIST", 60.0, 58.0, 61.0),
    CreatorSeedRow("Fiona Staples", "ARTIST", 59.0, 57.0, 60.0),
    CreatorSeedRow("Jamal Campbell", "ARTIST", 58.0, 56.0, 59.0),
    CreatorSeedRow("Jorge Molina", "COVER_ARTIST", 57.0, 55.0, 58.0),
    CreatorSeedRow("Jen Bartel", "COVER_ARTIST", 56.0, 54.0, 57.0),
    CreatorSeedRow("Michele Bandini", "COVER_ARTIST", 55.0, 53.0, 56.0),
    CreatorSeedRow("Stanley Artgerm Lau", "COVER_ARTIST", 54.0, 52.0, 55.0),
    CreatorSeedRow("Gabriele Dell'Otto", "COVER_ARTIST", 53.0, 51.0, 54.0),
    CreatorSeedRow("Adam Hughes", "COVER_ARTIST", 52.0, 50.0, 53.0),
    CreatorSeedRow("J Scott Campbell", "COVER_ARTIST", 51.0, 49.0, 52.0),
    CreatorSeedRow("David Finch", "ARTIST", 50.0, 48.0, 51.0),
    CreatorSeedRow("Marc Silvestri", "ARTIST", 49.0, 47.0, 50.0),
    CreatorSeedRow("Whilce Portacio", "ARTIST", 48.0, 46.0, 49.0),
    CreatorSeedRow("Rob Liefeld", "ARTIST", 47.0, 45.0, 48.0),
    CreatorSeedRow("Erik Larsen", "ARTIST", 46.0, 44.0, 47.0),
)

_EXTRA_CREATORS: tuple[tuple[str, str, float], ...] = tuple(
    (f"Indie Creator {idx}", "WRITER" if idx % 2 else "ARTIST", 44.0 + (idx % 20)) for idx in range(1, 56)
)

SOURCE_VERSION = "P51-01"
CONFIDENCE_BASE = 0.88
